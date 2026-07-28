"""Tests for Phase V catalog tools and LRU cache management."""

import os
import tempfile
import time
import unittest

from viv_ai.mcp.filesystem import FilesystemPolicy
from viv_ai.mcp.session import WorkspaceSession, WorkspaceSessionManager


class FakeVW:
    """Minimal vivisect workspace stand-in."""
    def getFunctions(self):
        return []


class TestWorkspaceSessionMetadata(unittest.TestCase):
    """Phase V: richer session metadata fields."""

    def test_session_has_metadata_fields(self):
        session = WorkspaceSession(workspace_id='test1', path='/tmp/test.bin', workspace=FakeVW())
        d = session.to_dict()
        self.assertIn('last_accessed_ts', d)
        self.assertIn('open_count', d)
        self.assertIn('alias', d)
        self.assertIn('source_kind', d)
        self.assertIn('loaded_from_viv', d)
        self.assertIn('analysis_started', d)
        self.assertIn('analysis_completed', d)
        self.assertIn('estimated_size_bytes', d)

    def test_touch_updates_lru_and_count(self):
        session = WorkspaceSession(workspace_id='test2', path='/tmp/test.bin', workspace=FakeVW())
        prev_ts = session.last_accessed_ts
        prev_count = session.open_count
        time.sleep(0.01)
        session.touch()
        self.assertGreater(session.last_accessed_ts, prev_ts)
        self.assertEqual(session.open_count, prev_count + 1)


class TestLRUCache(unittest.TestCase):
    """Phase V: LRU eviction from the session manager."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_eviction_removes_lru_session(self):
        """With max_cached=2, opening a 3rd session evicts the LRU."""
        mgr = WorkspaceSessionManager(
            workspace_loader=lambda p: FakeVW(),
            max_cached=2,
        )
        s1 = mgr.open_workspace(os.path.join(self.tmpdir, 'a.bin'), workspace=FakeVW())
        s2 = mgr.open_workspace(os.path.join(self.tmpdir, 'b.bin'), workspace=FakeVW())
        self.assertEqual(len(mgr._sessions), 2)

        # Touch s2 to make it more recent, then add a 3rd
        s2.touch()
        time.sleep(0.01)
        s3 = mgr.open_workspace(os.path.join(self.tmpdir, 'c.bin'), workspace=FakeVW())
        self.assertEqual(len(mgr._sessions), 2)
        # s1 should have been evicted (oldest)
        self.assertNotIn(s1.workspace_id, mgr._sessions)

    def test_no_eviction_when_cache_unlimited(self):
        mgr = WorkspaceSessionManager(
            workspace_loader=lambda p: FakeVW(),
            max_cached=0,  # unlimited
        )
        sessions = []
        for i in range(10):
            path = os.path.join(self.tmpdir, f'{i}.bin')
            s = mgr.open_workspace(path, workspace=FakeVW())
            sessions.append(s)
        self.assertEqual(len(mgr._sessions), 10)

    def test_stale_viv_evicted(self):
        mgr = WorkspaceSessionManager(
            workspace_loader=lambda p: FakeVW(),
            max_cached=2,
        )
        s1 = mgr.open_workspace(os.path.join(self.tmpdir, 'a.bin'), workspace=FakeVW())
        s2 = mgr.open_workspace(os.path.join(self.tmpdir, 'b.bin'), workspace=FakeVW())
        s1.touch()
        time.sleep(0.01)
        s3 = mgr.open_workspace(os.path.join(self.tmpdir, 'c.bin'), workspace=FakeVW())
        self.assertEqual(len(mgr._sessions), 2)
        # s2 (not touched) should be evicted
        self.assertNotIn(s2.workspace_id, mgr._sessions)


class TestSelectorAutoOpen(unittest.TestCase):
    """Phase V: Selector-based auto-open resolution."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name
        for name in ['sample.bin', 'test.bin', 'other.exe']:
            open(os.path.join(self.tmpdir, name), 'w').close()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_open_by_alias_returns_session(self):
        """Workspaces opened with alias can be found by alias."""
        mgr = WorkspaceSessionManager(
            workspace_loader=lambda p: FakeVW(),
            filesystem_policy=FilesystemPolicy(base_dir=self.tmpdir),
        )
        path = os.path.join(self.tmpdir, 'sample.bin')
        session = mgr.open_workspace(path, workspace=FakeVW())
        # session gets an alias derived from the path as fallback
        self.assertIn(session.workspace_id, mgr._alias_index.get(session.alias or '', ''))
        self.assertIsNotNone(session.alias)

    def test_open_by_path_resolved_from_alias(self):
        """Alias index maps alias -> workspace_id."""
        mgr = WorkspaceSessionManager(
            workspace_loader=lambda p: FakeVW(),
            filesystem_policy=FilesystemPolicy(base_dir=self.tmpdir),
        )
        path = os.path.join(self.tmpdir, 'sample.bin')
        session = mgr.open_workspace(path, workspace=FakeVW())
        resolved = mgr._alias_index.get(session.alias or '')
        self.assertEqual(resolved, session.workspace_id)


class TestVivPreference(unittest.TestCase):
    """Phase V: prefer .viv over raw binary."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name
        self.bin_path = os.path.join(self.tmpdir, 'sample.bin')
        self.viv_path = os.path.join(self.tmpdir, 'sample.bin.viv')
        open(self.bin_path, 'w').close()
        open(self.viv_path, 'w').close()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_prefer_existing_viv(self):
        """When both .bin and .viv exist, prefer the .viv."""
        loads = []
        def loader(path):
            loads.append(path)
            return FakeVW()
        mgr = WorkspaceSessionManager(
            workspace_loader=loader,
            filesystem_policy=FilesystemPolicy(base_dir=self.tmpdir),
            prefer_existing_viv=True,
        )
        mgr.open_workspace(self.bin_path)
        self.assertEqual(len(loads), 1)
        self.assertEqual(loads[0], self.viv_path)

    def test_force_reanalyze_ignores_viv(self):
        """With force_reanalyze=True, load from binary even if .viv exists."""
        loads = []
        def loader(path):
            loads.append(path)
            return FakeVW()
        mgr = WorkspaceSessionManager(
            workspace_loader=loader,
            filesystem_policy=FilesystemPolicy(base_dir=self.tmpdir),
            prefer_existing_viv=True,
            force_reanalyze=True,
        )
        mgr.open_workspace(self.bin_path)
        self.assertEqual(len(loads), 1)
        self.assertEqual(loads[0], self.bin_path)


if __name__ == '__main__':
    unittest.main()

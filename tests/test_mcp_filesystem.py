"""Tests for the filesystem access policy and catalog primitives."""

import os
import tempfile
import unittest

from viv_ai.mcp.filesystem import (
    FilesystemPolicy,
    normalize_path,
    is_allowed_path,
    discover_files,
    find_candidate_workspace_files,
    get_file_info,
)


class TestFilesystemPolicy(unittest.TestCase):
    """FilesystemPolicy dataclass construction and defaults."""

    def test_default_policy_has_no_base_dir(self):
        policy = FilesystemPolicy()
        self.assertIsNone(policy.effective_base)
        self.assertFalse(policy.allow_root)
        self.assertFalse(policy.server_mode)

    def test_policy_with_base_dir(self):
        policy = FilesystemPolicy(base_dir='/tmp')
        self.assertEqual(policy.effective_base, '/tmp')
        self.assertFalse(policy.allow_root)

    def test_policy_with_allow_root(self):
        policy = FilesystemPolicy(base_dir='/', allow_root=True)
        self.assertEqual(policy.effective_base, '/')
        self.assertTrue(policy.allow_root)

    def test_policy_repr(self):
        policy = FilesystemPolicy(base_dir='/tmp')
        r = repr(policy)
        self.assertIn('base_dir', r)
        self.assertIn('allow_root', r)
        self.assertIn('server_mode', r)


class TestNormalizePath(unittest.TestCase):
    """Path resolution and boundary enforcement."""

    def test_allows_path_under_base(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = FilesystemPolicy(base_dir=tmpdir)
            sub = os.path.join(tmpdir, 'foo.bin')
            open(sub, 'w').close()
            resolved = normalize_path('foo.bin', policy)
            self.assertEqual(resolved, sub)

    def test_rejects_path_outside_base(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = FilesystemPolicy(base_dir=tmpdir)
            with self.assertRaises(ValueError):
                normalize_path('/etc/passwd', policy)

    def test_allows_same_as_base(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = FilesystemPolicy(base_dir=tmpdir)
            resolved = normalize_path(tmpdir, policy)
            self.assertEqual(resolved, tmpdir)

    def test_rejects_root_without_allow_root(self):
        policy = FilesystemPolicy()  # no base_dir, allow_root=False
        with self.assertRaises(ValueError):
            normalize_path('/', policy)

    def test_allows_root_with_allow_root(self):
        policy = FilesystemPolicy(base_dir='/', allow_root=True)
        resolved = normalize_path('/', policy)
        self.assertEqual(resolved, '/')

    def test_allows_any_path_in_unrestricted_mode(self):
        policy = FilesystemPolicy()
        resolved = normalize_path('/etc/hostname', policy)
        self.assertIn('hostname', resolved)

    def test_relative_path_joins_with_base(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = FilesystemPolicy(base_dir=tmpdir)
            sub = os.path.join(tmpdir, 'bar.exe')
            open(sub, 'w').close()
            resolved = normalize_path('bar.exe', policy)
            self.assertEqual(resolved, sub)

    def test_absolute_path_expands_user(self):
        policy = FilesystemPolicy()
        resolved = normalize_path('~/', policy)
        self.assertTrue(os.path.isabs(resolved))

    def test_server_mode_allows_external_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = FilesystemPolicy(base_dir=tmpdir, server_mode=True)
            # server mode should be more permissive
            resolved = normalize_path(tmpdir, policy)
            self.assertEqual(resolved, tmpdir)


class TestIsAllowedPath(unittest.TestCase):
    """Boolean check for path validity."""

    def test_returns_true_for_allowed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = FilesystemPolicy(base_dir=tmpdir)
            self.assertTrue(is_allowed_path(tmpdir, policy))

    def test_returns_false_for_disallowed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            policy = FilesystemPolicy(base_dir=tmpdir)
            self.assertFalse(is_allowed_path('/etc', policy))


class TestDiscoverFiles(unittest.TestCase):
    """Bounded recursive file listing."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name
        # Create test files
        for name in ['a.bin', 'b.bin', 'c.exe', 'd.viv']:
            open(os.path.join(self.tmpdir, name), 'w').close()
        # Create a subdir with files
        os.makedirs(os.path.join(self.tmpdir, 'sub'), exist_ok=True)
        for name in ['e.bin', 'f.viv']:
            open(os.path.join(self.tmpdir, 'sub', name), 'w').close()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_discover_all_files(self):
        policy = FilesystemPolicy(base_dir=self.tmpdir)
        files = discover_files(self.tmpdir, policy, limit=100)
        paths = {f['path'] for f in files}
        self.assertIn(os.path.join(self.tmpdir, 'a.bin'), paths)
        self.assertIn(os.path.join(self.tmpdir, 'sub', 'e.bin'), paths)
        self.assertGreaterEqual(len(files), 6)

    def test_discover_filter_by_suffix(self):
        policy = FilesystemPolicy(base_dir=self.tmpdir)
        files = discover_files(self.tmpdir, policy, limit=100, suffixes=('.viv',))
        paths = {f['path'] for f in files}
        self.assertIn(os.path.join(self.tmpdir, 'd.viv'), paths)
        self.assertIn(os.path.join(self.tmpdir, 'sub', 'f.viv'), paths)
        self.assertEqual(len(files), 2)

    def test_discover_pagination(self):
        policy = FilesystemPolicy(base_dir=self.tmpdir)
        all_files = discover_files(self.tmpdir, policy, limit=100)
        first_two = discover_files(self.tmpdir, policy, limit=2, offset=0)
        self.assertEqual(len(first_two), 2)

    def test_discover_marks_viv_files(self):
        policy = FilesystemPolicy(base_dir=self.tmpdir)
        files = discover_files(self.tmpdir, policy, limit=100, suffixes=('.viv',))
        for f in files:
            self.assertTrue(f['is_viv'])

    def test_discover_outside_base_raises(self):
        policy = FilesystemPolicy(base_dir=self.tmpdir)
        with self.assertRaises(ValueError):
            discover_files('/etc', policy)


class TestFindCandidateWorkspaceFiles(unittest.TestCase):
    """Determine what exists at a path."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name
        self.bin_path = os.path.join(self.tmpdir, 'sample.bin')
        self.viv_path = os.path.join(self.tmpdir, 'sample.bin.viv')
        open(self.bin_path, 'w').close()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_binary_only(self):
        policy = FilesystemPolicy(base_dir=self.tmpdir)
        viv, binary = find_candidate_workspace_files(self.bin_path, policy)
        self.assertIsNone(viv)
        self.assertEqual(binary, self.bin_path)

    def test_prefers_viv(self):
        policy = FilesystemPolicy(base_dir=self.tmpdir)
        open(self.viv_path, 'w').close()
        viv, binary = find_candidate_workspace_files(self.bin_path, policy)
        self.assertEqual(viv, self.viv_path)
        self.assertEqual(binary, self.bin_path)

    def test_non_existent_path(self):
        policy = FilesystemPolicy(base_dir=self.tmpdir)
        viv, binary = find_candidate_workspace_files(
            os.path.join(self.tmpdir, 'nonexistent.bin'), policy
        )
        self.assertIsNone(viv)
        self.assertIsNone(binary)

    def test_viv_path_direct(self):
        policy = FilesystemPolicy(base_dir=self.tmpdir)
        open(self.viv_path, 'w').close()
        viv, binary = find_candidate_workspace_files(self.viv_path, policy)
        self.assertEqual(viv, self.viv_path)
        self.assertIsNone(binary)


class TestGetFileInfo(unittest.TestCase):
    """File metadata queries."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir.name
        self.bin_path = os.path.join(self.tmpdir, 'test.bin')
        open(self.bin_path, 'w').close()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_returns_file_info(self):
        policy = FilesystemPolicy(base_dir=self.tmpdir)
        info = get_file_info(self.bin_path, policy)
        self.assertTrue(info['exists'])
        self.assertEqual(info['type'], 'file')
        self.assertFalse(info['is_viv'])
        self.assertIsInstance(info['alias'], str)

    def test_nonexistent_file(self):
        policy = FilesystemPolicy(base_dir=self.tmpdir)
        info = get_file_info(os.path.join(self.tmpdir, 'nonexistent.bin'), policy)
        self.assertFalse(info['exists'])

    def test_viv_file_detection(self):
        policy = FilesystemPolicy(base_dir=self.tmpdir)
        viv_path = os.path.join(self.tmpdir, 'data.viv')
        open(viv_path, 'w').close()
        info = get_file_info(viv_path, policy)
        self.assertTrue(info['is_viv'])

    def test_info_includes_alias(self):
        policy = FilesystemPolicy(base_dir=self.tmpdir)
        info = get_file_info(self.bin_path, policy)
        self.assertEqual(info['alias'], 'test')


if __name__ == '__main__':
    unittest.main()

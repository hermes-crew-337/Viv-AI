"""Integration test: MCP server tools against a real Vivisect workspace.

Creates a real VivWorkspace from a binary, runs analysis, opens it
through the MCP server, and exercises the tool surface against real
Vivisect objects rather than FakeVW mocks.

Requires VIVTESTFILES to point at a vivtestfiles checkout.
Set SKIP_REAL_VIV_INTEGRATION=1 to skip this test in CI.
"""

import os
import pathlib
import time
import unittest

# Allow users to skip this integration test (needs VIVTESTFILES + vivisect)
integration = unittest.skipIf(
    os.environ.get('SKIP_REAL_VIV_INTEGRATION') == '1',
    'SKIP_REAL_VIV_INTEGRATION=1 set',
)


def _find_testfiles() -> str | None:
    """Resolve VIVTESTFILES from env or relative to this repo."""
    env = os.environ.get('VIVTESTFILES')
    if env:
        return env
    # Fallback: check next to the workspace repos
    candidate = pathlib.Path(__file__).resolve().parents[1] / 'vivtestfiles'
    return str(candidate) if candidate.is_dir() else None


VIVTESTFILES = _find_testfiles()
NEED_BINARY_SKIP = unittest.skipUnless(
    VIVTESTFILES,
    'VIVTESTFILES not set -- no test binaries available',
)


@NEED_BINARY_SKIP
@integration
class RealVivWorkspaceIntegrationTests(unittest.TestCase):
    """Exercise MCP server tools against a real analyzed Vivisect workspace.

    Uses a small i386 ELF (~15 KB) from vivtestfiles that analyzes in
    under a second, giving us real functions, imports, exports and
    metadata to validate tool outputs against.
    """

    BINARY = 'linux/i386/syscalls.elf'

    @classmethod
    def setUpClass(cls):
        import vivisect

        binary_path = os.path.join(VIVTESTFILES, cls.BINARY)
        cls.assertTrue(
            os.path.isfile(binary_path),
            f'Test binary not found: {binary_path}',
        )

        vw = vivisect.VivWorkspace()
        vw.loadFromFile(binary_path)
        # Full analysis -- small binary, ~0.5 s
        t0 = time.monotonic()
        vw.analyze()
        cls._analysis_elapsed = time.monotonic() - t0
        cls.vw = vw

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'vw'):
            cls.vw = None

    def setUp(self):
        from viv_ai.mcp.server import VivAIMcpServer

        self.server = VivAIMcpServer(
            workspace_loader=lambda path: self.__class__.vw,
        )
        self.wid = self._open()

    def _open(self):
        result = self.server.call_tool(
            'workspace_open', path='/tmp/syscalls.bin',
        )
        self.assertTrue(result['ok'], msg=result.get('error', ''))
        return result['data']['workspace_id']

    # -- metadata & status --------------------------------------------------

    def test_workspace_open_returns_real_meta_and_function_count(self):
        """Workspace metadata comes from the real loaded binary."""
        result = self.server.call_tool(
            'workspace_open', path='/tmp/syscalls.bin',
        )
        self.assertTrue(result['ok'])
        data = result['data']
        self.assertEqual(data['metadata']['architecture'], 'i386')
        self.assertEqual(data['metadata']['platform'], 'linux')
        self.assertEqual(data['metadata']['format'], 'elf')
        self.assertEqual(data['function_count'], 14)

    def test_workspace_status_reflects_real_workspace(self):
        result = self.server.call_tool(
            'workspace_status', workspace_id=self.wid,
        )
        self.assertTrue(result['ok'])
        ws = result['data']['workspace']
        self.assertEqual(ws['path'], '/tmp/syscalls.bin')
        self.assertEqual(ws['metadata']['architecture'], 'i386')

    def test_get_metadata_tool(self):
        result = self.server.call_tool(
            'get_metadata', workspace_id=self.wid,
        )
        self.assertTrue(result['ok'])
        meta = result['data']['metadata']
        self.assertEqual(meta['architecture'], 'i386')
        self.assertEqual(meta['platform'], 'linux')
        self.assertEqual(meta['format'], 'elf')

    # -- imports / exports ---------------------------------------------------

    def test_get_imports_from_real_binary(self):
        result = self.server.call_tool(
            'get_imports', workspace_id=self.wid,
        )
        self.assertTrue(result['ok'])
        imports = result['data']['imports']
        self.assertGreater(len(imports), 0)
        for entry in imports:
            self.assertIn('symbol', entry)
            self.assertIn('va', entry)

    def test_get_exports_from_real_binary(self):
        result = self.server.call_tool(
            'get_exports', workspace_id=self.wid,
        )
        self.assertTrue(result['ok'])
        exports = result['data']['exports']
        self.assertGreater(len(exports), 0)
        for entry in exports:
            self.assertIn('name', entry)
            self.assertIn('va', entry)

    # -- functions -----------------------------------------------------------

    def test_find_functions_returns_analyzed_functions(self):
        """find_functions with no filter returns all analyzed functions."""
        result = self.server.call_tool(
            'find_functions', workspace_id=self.wid,
        )
        self.assertTrue(result['ok'])
        funcs = result['data']['functions']
        self.assertGreater(len(funcs), 0)
        # At least some should have names from analysis
        named = [f for f in funcs if f.get('name')]
        self.assertGreater(len(named), 0)
        for f in funcs:
            self.assertIn('va', f)

    def test_find_functions_with_name_glob_filters(self):
        """find_functions with a name glob can filter results."""
        result = self.server.call_tool(
            'find_functions', workspace_id=self.wid,
            name_glob='*plt*',
        )
        self.assertTrue(result['ok'])
        funcs = result['data']['functions']
        # PLT functions should be found
        self.assertGreater(len(funcs), 0)
        for f in funcs:
            self.assertIn('plt', (f.get('name', '') or '').lower())

    def test_get_function_summary_on_real_function(self):
        """get_function_summary returns real function data."""
        funcs = self.server.call_tool(
            'find_functions', workspace_id=self.wid,
        )
        first_fva = funcs['data']['functions'][0]['va']

        result = self.server.call_tool(
            'get_function_summary',
            workspace_id=self.wid,
            fva=first_fva,
        )
        self.assertTrue(result['ok'])
        data = result['data']
        self.assertIn('function', data)
        self.assertIn('name', data['function'])
        self.assertIn('va', data['function'])

    # -- strings -------------------------------------------------------------

    def test_get_strings_finds_real_strings(self):
        result = self.server.call_tool(
            'get_strings', workspace_id=self.wid,
        )
        self.assertTrue(result['ok'])
        strings = result['data']['strings']
        # Even a small binary should have some identifiable strings
        for entry in strings:
            self.assertIn('value', entry)
            self.assertIn('va', entry)

    def test_get_strings_pagination(self):
        result = self.server.call_tool(
            'get_strings', workspace_id=self.wid,
            max_results=5,
        )
        self.assertTrue(result['ok'])
        self.assertLessEqual(len(result['data']['strings']), 5)
        self.assertIn('pagination', result['data'])

    # -- names ---------------------------------------------------------------

    def test_get_names_from_real_workspace(self):
        result = self.server.call_tool(
            'get_names', workspace_id=self.wid,
        )
        self.assertTrue(result['ok'])
        names = result['data']['names']
        self.assertGreater(len(names), 0)
        for entry in names:
            self.assertIn('name', entry)
            self.assertIn('va', entry)

    # -- function graph ------------------------------------------------------

    def test_get_function_graph_on_real_function(self):
        funcs = self.server.call_tool(
            'find_functions', workspace_id=self.wid,
        )
        first_fva = funcs['data']['functions'][0]['va']

        result = self.server.call_tool(
            'get_function_graph',
            workspace_id=self.wid,
            fva=first_fva,
            max_nodes=10,
            max_edges=10,
        )
        self.assertTrue(result['ok'])
        data = result['data']
        self.assertGreater(data['node_count'], 0)
        self.assertGreater(len(data['nodes']), 0)
        self.assertIn('edges', data)

    # -- cross-references ----------------------------------------------------

    def test_get_xrefs_to_and_from_real_function(self):
        funcs = self.server.call_tool(
            'find_functions', workspace_id=self.wid,
        )
        first_fva = funcs['data']['functions'][0]['va']

        to_result = self.server.call_tool(
            'get_xrefs_to', workspace_id=self.wid, va=first_fva,
        )
        self.assertTrue(to_result['ok'])
        self.assertIn('xrefs', to_result['data'])

        from_result = self.server.call_tool(
            'get_xrefs_from', workspace_id=self.wid, va=first_fva,
        )
        self.assertTrue(from_result['ok'])
        self.assertIn('xrefs', from_result['data'])

    # -- analysis status -----------------------------------------------------

    def test_analysis_status_reports_real_count(self):
        result = self.server.call_tool(
            'workspace_analysis_status', workspace_id=self.wid,
        )
        self.assertTrue(result['ok'])
        count = result['data']['function_count']
        self.assertGreater(count, 0)

    # -- workspace lifecycle -------------------------------------------------

    def test_workspace_close_and_verify_gone(self):
        """Open a second workspace, close it, confirm it's gone."""
        result = self.server.call_tool(
            'workspace_open', path='/tmp/syscalls-dup.bin',
        )
        self.assertTrue(result['ok'])
        wid2 = result['data']['workspace_id']

        close_result = self.server.call_tool(
            'workspace_close', workspace_id=wid2,
        )
        self.assertTrue(close_result['ok'])
        self.assertTrue(close_result['data']['closed'])

        # Verify it's gone
        status = self.server.call_tool(
            'workspace_status', workspace_id=wid2,
        )
        self.assertFalse(status['ok'])

    # -- list_workspaces -----------------------------------------------------

    def test_list_workspaces_includes_open_workspace(self):
        result = self.server.call_tool('list_workspaces')
        self.assertTrue(result['ok'])
        workspaces = result['data']['workspaces']
        ids = [w['workspace_id'] for w in workspaces]
        self.assertIn(self.wid, ids)

import unittest


class FakeVW:
    def __init__(self):
        self.meta = {
            'Architecture': 'amd64',
            'Platform': 'linux',
            'Format': 'elf',
        }

    def getMeta(self, name):
        return self.meta.get(name)

    def getEntryPoints(self):
        return [0x401000]

    def getImports(self):
        return []

    def getExports(self):
        return []

    def getLocations(self, ltype):
        return []

    def getFunctions(self):
        return [0x401000]

    def getFunctionBlocks(self, fva):
        return [(0x401000, 8, 0x401000)]

    def getCallers(self, fva):
        return []


class McpServerTests(unittest.TestCase):
    def test_build_default_tool_registry_exposes_workspace_foundation_tools(self):
        from viv_ai.mcp.tools import build_default_registry

        registry = build_default_registry()

        self.assertIn('workspace_open', registry)
        self.assertIn('workspace_status', registry)
        self.assertIn('workspace_close', registry)
        self.assertIn('get_metadata', registry)

    def test_mcp_server_registers_tools_and_reports_startup_state(self):
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer()
        info = server.server_info()

        self.assertEqual(info['name'], 'viv_ai_mcp')
        self.assertFalse(info['running'])
        self.assertIn('workspace_open', info['tools'])

    def test_workspace_open_tool_can_open_and_status_workspace(self):
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        opened = server.call_tool('workspace_open', path='/tmp/a.out')
        workspace_id = opened['data']['workspace_id']
        status = server.call_tool('workspace_status', workspace_id=workspace_id)

        self.assertTrue(opened['ok'])
        self.assertEqual(status['data']['workspace']['path'], '/tmp/a.out')
        self.assertEqual(status['data']['workspace']['metadata']['format'], 'elf')

    def test_metadata_tool_reads_from_open_workspace(self):
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        opened = server.call_tool('workspace_open', path='/tmp/a.out')
        workspace_id = opened['data']['workspace_id']
        result = server.call_tool('get_metadata', workspace_id=workspace_id)

        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['metadata']['architecture'], 'amd64')
        self.assertEqual(result['summary'], 'linux amd64 elf workspace')

    def test_unknown_tool_returns_structured_error(self):
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer()
        result = server.call_tool('nope')

        self.assertFalse(result['ok'])
        self.assertIn('unknown tool', result['error'])


if __name__ == '__main__':
    unittest.main()

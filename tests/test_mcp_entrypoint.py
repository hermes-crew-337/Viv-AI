import io
import json
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


class McpEntrypointTests(unittest.TestCase):
    def test_pyproject_exposes_stdio_entrypoint_script(self):
        import tomllib
        from pathlib import Path

        pyproject = Path(__file__).resolve().parents[1] / 'pyproject.toml'
        data = tomllib.loads(pyproject.read_text())

        self.assertEqual(data['project']['scripts']['viv-ai-mcp'], 'viv_ai.mcp.entrypoint:main')

    def test_serve_once_handles_initialize_and_tools_list_requests(self):
        from viv_ai.mcp.entrypoint import serve_once
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())

        initialize_in = io.StringIO(json.dumps({'id': 1, 'method': 'initialize', 'params': {}}) + '\n')
        initialize_out = io.StringIO()
        keep_running = serve_once(server, initialize_in, initialize_out)
        initialize_resp = json.loads(initialize_out.getvalue())

        self.assertTrue(keep_running)
        self.assertEqual(initialize_resp['id'], 1)
        self.assertEqual(initialize_resp['result']['serverInfo']['name'], 'viv_ai_mcp')

        list_in = io.StringIO(json.dumps({'id': 2, 'method': 'tools/list', 'params': {}}) + '\n')
        list_out = io.StringIO()
        keep_running = serve_once(server, list_in, list_out)
        list_resp = json.loads(list_out.getvalue())

        self.assertTrue(keep_running)
        self.assertEqual(list_resp['id'], 2)
        tools = {tool['name']: tool for tool in list_resp['result']['tools']}
        self.assertIn('workspace_open', tools)
        self.assertIn('ai_explain_function', tools)
        self.assertEqual(tools['workspace_open']['inputSchema']['required'], ['path'])
        self.assertIn('path', tools['workspace_open']['inputSchema']['properties'])
        self.assertTrue(tools['get_metadata']['annotations']['readOnlyHint'])
        self.assertFalse(tools['apply_function_rename']['annotations']['readOnlyHint'])

    def test_serve_once_handles_tool_call_and_shutdown(self):
        from viv_ai.mcp.entrypoint import serve_once
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())

        open_req = {
            'id': 3,
            'method': 'tools/call',
            'params': {'name': 'workspace_open', 'arguments': {'path': '/tmp/a.out'}},
        }
        open_in = io.StringIO(json.dumps(open_req) + '\n')
        open_out = io.StringIO()
        keep_running = serve_once(server, open_in, open_out)
        open_resp = json.loads(open_out.getvalue())

        self.assertTrue(keep_running)
        self.assertTrue(open_resp['result']['ok'])
        workspace_id = open_resp['result']['data']['workspace_id']

        meta_req = {
            'id': 4,
            'method': 'tools/call',
            'params': {'name': 'get_metadata', 'arguments': {'workspace_id': workspace_id}},
        }
        meta_in = io.StringIO(json.dumps(meta_req) + '\n')
        meta_out = io.StringIO()
        keep_running = serve_once(server, meta_in, meta_out)
        meta_resp = json.loads(meta_out.getvalue())

        self.assertTrue(keep_running)
        self.assertTrue(meta_resp['result']['ok'])
        self.assertEqual(meta_resp['result']['data']['metadata']['format'], 'elf')

        shutdown_in = io.StringIO(json.dumps({'id': 5, 'method': 'shutdown', 'params': {}}) + '\n')
        shutdown_out = io.StringIO()
        keep_running = serve_once(server, shutdown_in, shutdown_out)
        shutdown_resp = json.loads(shutdown_out.getvalue())

        self.assertFalse(keep_running)
        self.assertIsNone(shutdown_resp['result'])

    def test_serve_once_returns_parse_error_for_invalid_json(self):
        from viv_ai.mcp.entrypoint import serve_once
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        bad_in = io.StringIO('{not json}\n')
        bad_out = io.StringIO()

        keep_running = serve_once(server, bad_in, bad_out)
        response = json.loads(bad_out.getvalue())

        self.assertTrue(keep_running)
        self.assertEqual(response['error']['code'], -32700)

    def test_serve_once_validates_tool_call_params_shape(self):
        from viv_ai.mcp.entrypoint import serve_once
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        req = {'id': 7, 'method': 'tools/call', 'params': {'name': 'workspace_open', 'arguments': 'nope'}}
        req_in = io.StringIO(json.dumps(req) + '\n')
        req_out = io.StringIO()

        keep_running = serve_once(server, req_in, req_out)
        response = json.loads(req_out.getvalue())

        self.assertTrue(keep_running)
        self.assertEqual(response['error']['code'], -32602)

    def test_build_arg_parser_accepts_config_option(self):
        from viv_ai.mcp.entrypoint import build_arg_parser

        parser = build_arg_parser()
        args = parser.parse_args(['--once', '--config', '/tmp/viv-ai.json'])

        self.assertTrue(args.once)
        self.assertEqual(args.config, '/tmp/viv-ai.json')


if __name__ == '__main__':
    unittest.main()

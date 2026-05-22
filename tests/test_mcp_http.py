import http.client
import json
import threading
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


class McpHttpTransportTests(unittest.TestCase):
    def test_http_server_handles_initialize_and_tools_list_with_bearer_auth(self):
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0, auth_token='secret-token')
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request(
                'POST',
                '/mcp',
                body=json.dumps({'id': 1, 'method': 'initialize', 'params': {}}),
                headers={'Content-Type': 'application/json', 'Authorization': 'Bearer secret-token'},
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            self.assertEqual(payload['result']['serverInfo']['name'], 'viv_ai_mcp')

            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request(
                'POST',
                '/mcp',
                body=json.dumps({'id': 2, 'method': 'tools/list', 'params': {}}),
                headers={'Content-Type': 'application/json', 'Authorization': 'Bearer secret-token'},
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            tools = {tool['name']: tool for tool in payload['result']['tools']}
            self.assertEqual(tools['workspace_open']['inputSchema']['required'], ['path'])
            self.assertTrue(tools['get_metadata']['annotations']['readOnlyHint'])
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_http_server_rejects_missing_auth_header(self):
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0, auth_token='secret-token')
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request(
                'POST',
                '/mcp',
                body=json.dumps({'id': 3, 'method': 'ping', 'params': {}}),
                headers={'Content-Type': 'application/json'},
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 401)
            self.assertEqual(payload['error']['code'], 401)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_http_server_uses_config_auth_env_reference_without_exposing_secret(self):
        import os

        from viv_ai.config import AiConfig
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        os.environ['VIV_AI_MCP_TOKEN'] = 'top-secret'
        try:
            config = AiConfig.from_dict({
                'mcp_http_bind_host': '127.0.0.1',
                'mcp_http_bind_port': 0,
                'mcp_http_auth_token_env': 'VIV_AI_MCP_TOKEN',
            })
            server = VivAIMcpServer()
            httpd = create_http_server(server, config=config)
            info = httpd.vivai_http_info()

            self.assertEqual(info['auth_token_env'], 'VIV_AI_MCP_TOKEN')
            self.assertTrue(info['auth_required'])
            self.assertNotIn('top-secret', json.dumps(info))
        finally:
            os.environ.pop('VIV_AI_MCP_TOKEN', None)

    def test_http_shutdown_request_stops_transport(self):
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0, auth_token='secret-token')
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request(
                'POST',
                '/mcp',
                body=json.dumps({'id': 9, 'method': 'shutdown', 'params': {}}),
                headers={'Content-Type': 'application/json', 'Authorization': 'Bearer secret-token'},
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            self.assertIsNone(payload['result'])
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        finally:
            if thread.is_alive():
                httpd.shutdown()
                thread.join(timeout=5)
            httpd.server_close()


if __name__ == '__main__':
    unittest.main()

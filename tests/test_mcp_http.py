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

    def test_http_server_supports_api_key_auth_via_config(self):
        import os

        from viv_ai.config import AiConfig
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        os.environ['VIV_AI_MCP_API_KEY'] = 'secret-api-key'
        try:
            config = AiConfig.from_dict({
                'mcp_http_bind_host': '127.0.0.1',
                'mcp_http_bind_port': 0,
                'mcp_http_api_key_env': 'VIV_AI_MCP_API_KEY',
            })
            server = VivAIMcpServer()
            httpd = create_http_server(server, config=config)
            info = httpd.vivai_http_info()

            self.assertEqual(info['api_key_env'], 'VIV_AI_MCP_API_KEY')
            self.assertTrue(info['auth_required'])
            self.assertNotIn('secret-api-key', json.dumps(info))
        finally:
            os.environ.pop('VIV_AI_MCP_API_KEY', None)

    def test_http_server_handles_initialize_with_api_key_auth(self):
        import os

        from viv_ai.config import AiConfig
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        os.environ['VIV_AI_MCP_API_KEY'] = 'secret-api-key'
        try:
            config = AiConfig.from_dict({
                'mcp_http_bind_host': '127.0.0.1',
                'mcp_http_bind_port': 0,
                'mcp_http_api_key_env': 'VIV_AI_MCP_API_KEY',
            })
            server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
            httpd = create_http_server(server, config=config)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = httpd.server_address
                conn = http.client.HTTPConnection(host, port, timeout=5)
                conn.request(
                    'POST',
                    '/mcp',
                    body=json.dumps({'id': 1, 'method': 'initialize', 'params': {}}),
                    headers={'Content-Type': 'application/json', 'X-API-Key': 'secret-api-key'},
                )
                resp = conn.getresponse()
                payload = json.loads(resp.read())
                self.assertEqual(resp.status, 200)
                self.assertEqual(payload['result']['serverInfo']['name'], 'viv_ai_mcp')
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
        finally:
            os.environ.pop('VIV_AI_MCP_API_KEY', None)

    def test_http_server_rejects_invalid_api_key(self):
        import os

        from viv_ai.config import AiConfig
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        os.environ['VIV_AI_MCP_API_KEY'] = 'secret-api-key'
        try:
            config = AiConfig.from_dict({
                'mcp_http_bind_host': '127.0.0.1',
                'mcp_http_bind_port': 0,
                'mcp_http_api_key_env': 'VIV_AI_MCP_API_KEY',
            })
            server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
            httpd = create_http_server(server, config=config)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = httpd.server_address
                conn = http.client.HTTPConnection(host, port, timeout=5)
                conn.request(
                    'POST',
                    '/mcp',
                    body=json.dumps({'id': 3, 'method': 'ping', 'params': {}}),
                    headers={'Content-Type': 'application/json', 'X-API-Key': 'wrong-key'},
                )
                resp = conn.getresponse()
                payload = json.loads(resp.read())
                self.assertEqual(resp.status, 401)
                self.assertEqual(payload['error']['code'], 401)
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
        finally:
            os.environ.pop('VIV_AI_MCP_API_KEY', None)

    def test_http_server_accepts_api_key_in_authorization_header(self):
        import os

        from viv_ai.config import AiConfig
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        os.environ['VIV_AI_MCP_API_KEY'] = 'secret-api-key'
        try:
            config = AiConfig.from_dict({
                'mcp_http_bind_host': '127.0.0.1',
                'mcp_http_bind_port': 0,
                'mcp_http_api_key_env': 'VIV_AI_MCP_API_KEY',
            })
            server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
            httpd = create_http_server(server, config=config)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = httpd.server_address
                conn = http.client.HTTPConnection(host, port, timeout=5)
                conn.request(
                    'POST',
                    '/mcp',
                    body=json.dumps({'id': 1, 'method': 'initialize', 'params': {}}),
                    headers={'Content-Type': 'application/json', 'Authorization': 'Bearer secret-api-key'},
                )
                resp = conn.getresponse()
                payload = json.loads(resp.read())
                self.assertEqual(resp.status, 200)
                self.assertEqual(payload['result']['serverInfo']['name'], 'viv_ai_mcp')
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
        finally:
            os.environ.pop('VIV_AI_MCP_API_KEY', None)

    def test_http_server_enforces_request_size_limits(self):
        from viv_ai.config import AiConfig
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        config = AiConfig.from_dict({
            'mcp_http_bind_host': '127.0.0.1',
            'mcp_http_bind_port': 0,
            'mcp_http_max_request_size': 100,  # Very small limit for testing
        })
        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, config=config)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            # Send a request that's too large
            large_request = 'a' * 200  # 200 bytes, exceeds 100 byte limit
            conn.request(
                'POST',
                '/mcp',
                body=large_request,
                headers={'Content-Type': 'application/json', 'Content-Length': '200'},
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 413)
            self.assertEqual(payload['error']['code'], 413)
            self.assertIn('request entity too large', payload['error']['message'])
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_http_server_accepts_requests_under_size_limit(self):
        from viv_ai.config import AiConfig
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        config = AiConfig.from_dict({
            'mcp_http_bind_host': '127.0.0.1',
            'mcp_http_bind_port': 0,
            'mcp_http_max_request_size': 1000,  # Larger limit
        })
        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, config=config)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            # Send a request that's under the limit
            small_request = json.dumps({'id': 1, 'method': 'ping', 'params': {}})
            conn.request(
                'POST',
                '/mcp',
                body=small_request,
                headers={'Content-Type': 'application/json'},
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            self.assertEqual(payload['result'], {})
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_http_server_handles_missing_content_length(self):
        from viv_ai.config import AiConfig
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        config = AiConfig.from_dict({
            'mcp_http_bind_host': '127.0.0.1',
            'mcp_http_bind_port': 0,
            'mcp_http_max_request_size': 1000,
        })
        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, config=config)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            # Send a request without Content-Length header
            conn.request(
                'POST',
                '/mcp',
                body=json.dumps({'id': 1, 'method': 'ping', 'params': {}}),
                headers={'Content-Type': 'application/json'},
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            self.assertEqual(payload['result'], {})
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_http_server_uses_config_request_size_limit(self):
        from viv_ai.config import AiConfig
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        config = AiConfig.from_dict({
            'mcp_http_bind_host': '127.0.0.1',
            'mcp_http_bind_port': 0,
            'mcp_http_max_request_size': 500,
        })
        server = VivAIMcpServer()
        httpd = create_http_server(server, config=config)
        info = httpd.vivai_http_info()

        self.assertEqual(info['max_request_size'], 500)

    def test_http_server_generates_request_ids_for_error_responses(self):
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            # Send a request to a non-existent path
            conn.request(
                'POST',
                '/non-existent',
                body=json.dumps({'method': 'ping', 'params': {}}),
                headers={'Content-Type': 'application/json'},
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 404)
            self.assertIn('id', payload)
            self.assertIsNotNone(payload['id'])
            self.assertEqual(payload['error']['code'], 404)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_http_server_includes_request_id_in_parse_errors(self):
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            # Send invalid JSON
            conn.request(
                'POST',
                '/mcp',
                body='invalid json',
                headers={'Content-Type': 'application/json'},
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)  # JSON-RPC errors are returned with 200 status
            self.assertIn('id', payload)
            self.assertIsNotNone(payload['id'])
            self.assertEqual(payload['error']['code'], -32700)  # Parse error
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_http_server_error_response_format(self):
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            # Send a request with an invalid method
            conn.request(
                'POST',
                '/mcp',
                body=json.dumps({'id': 1, 'method': 'non_existent_method', 'params': {}}),
                headers={'Content-Type': 'application/json'},
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)  # JSON-RPC errors are returned with 200 status
            self.assertEqual(payload['id'], 1)
            self.assertIn('error', payload)
            self.assertIn('code', payload['error'])
            self.assertIn('message', payload['error'])
            self.assertEqual(payload['error']['code'], -32601)  # Method not found
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

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

    def test_http_arg_parser_accepts_config_option(self):
        from viv_ai.mcp.http_transport import build_arg_parser

        parser = build_arg_parser()
        args = parser.parse_args(['--config', '/tmp/viv-ai.json', '--path', '/custom'])

        self.assertEqual(args.config, '/tmp/viv-ai.json')
        self.assertEqual(args.path, '/custom')


if __name__ == '__main__':
    unittest.main()

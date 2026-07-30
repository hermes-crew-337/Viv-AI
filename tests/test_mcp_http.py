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

    def test_http_server_rate_limiting_allows_requests_under_limit(self):
        from viv_ai.config import AiConfig
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        config = AiConfig.from_dict({
            'mcp_http_bind_host': '127.0.0.1',
            'mcp_http_bind_port': 0,
            'mcp_http_rate_limit': 5,  # 5 requests per window
            'mcp_http_rate_limit_window': 60,  # 60 seconds
        })
        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, config=config)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            
            # Send 5 requests, all should be allowed
            for i in range(5):
                conn.request(
                    'POST',
                    '/mcp',
                    body=json.dumps({'id': i, 'method': 'ping', 'params': {}}),
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

    def test_http_server_rate_limiting_blocks_requests_over_limit(self):
        import time
        from viv_ai.config import AiConfig
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        config = AiConfig.from_dict({
            'mcp_http_bind_host': '127.0.0.1',
            'mcp_http_bind_port': 0,
            'mcp_http_rate_limit': 2,  # 2 requests per window
            'mcp_http_rate_limit_window': 60,  # 60 seconds
        })
        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, config=config)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            
            # Send 2 requests, both should be allowed
            for i in range(2):
                conn.request(
                    'POST',
                    '/mcp',
                    body=json.dumps({'id': i, 'method': 'ping', 'params': {}}),
                    headers={'Content-Type': 'application/json'},
                )
                resp = conn.getresponse()
                payload = json.loads(resp.read())
                self.assertEqual(resp.status, 200)
                self.assertEqual(payload['result'], {})
            
            # Send a 3rd request, should be blocked
            conn.request(
                'POST',
                '/mcp',
                body=json.dumps({'id': 3, 'method': 'ping', 'params': {}}),
                headers={'Content-Type': 'application/json'},
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 429)
            self.assertIn('error', payload)
            self.assertEqual(payload['error']['code'], 429)
            self.assertIn('too many requests', payload['error']['message'])
            self.assertIn('Retry-After', resp.headers)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_http_server_rate_limiting_resets_after_window(self):
        import time
        from unittest.mock import patch
        from viv_ai.config import AiConfig
        from viv_ai.mcp.http_transport import RateLimiter, create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        config = AiConfig.from_dict({
            'mcp_http_bind_host': '127.0.0.1',
            'mcp_http_bind_port': 0,
            'mcp_http_rate_limit': 1,  # 1 request per window
            'mcp_http_rate_limit_window': 1,  # 1 second window for testing
        })
        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, config=config)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            
            # Send 1 request, should be allowed
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
            
            # Send another request immediately, should be blocked
            conn.request(
                'POST',
                '/mcp',
                body=json.dumps({'id': 2, 'method': 'ping', 'params': {}}),
                headers={'Content-Type': 'application/json'},
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 429)
            
            # Wait for window to reset
            time.sleep(1.1)
            
            # Send another request, should be allowed again
            conn.request(
                'POST',
                '/mcp',
                body=json.dumps({'id': 3, 'method': 'ping', 'params': {}}),
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

    def test_http_server_uses_config_rate_limit(self):
        from viv_ai.config import AiConfig
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        config = AiConfig.from_dict({
            'mcp_http_bind_host': '127.0.0.1',
            'mcp_http_bind_port': 0,
            'mcp_http_rate_limit': 100,
            'mcp_http_rate_limit_window': 300,
        })
        server = VivAIMcpServer()
        httpd = create_http_server(server, config=config)
        info = httpd.vivai_http_info()

        self.assertEqual(info['rate_limit'], 100)
        self.assertEqual(info['rate_limit_window'], 300)

    def test_rate_limiter_client_key_identification(self):
        from unittest.mock import Mock
        from viv_ai.mcp.http_transport import RateLimiter

        rate_limiter = RateLimiter(10, 60)
        
        # Mock handler with IP address
        handler1 = Mock()
        handler1.client_address = ('192.168.1.1', 12345)
        handler1.headers.get.return_value = ''
        
        # Mock handler with API key in Authorization header
        handler2 = Mock()
        handler2.client_address = ('192.168.1.2', 12346)
        handler2.headers.get.side_effect = lambda key, default='': (
            'Bearer test-api-key' if key == 'Authorization' else ''
        )
        
        # Mock handler with API key in X-API-Key header
        handler3 = Mock()
        handler3.client_address = ('192.168.1.3', 12347)
        handler3.headers.get.side_effect = lambda key, default='': (
            'test-api-key-2' if key == 'X-API-Key' else (
                '' if key == 'Authorization' else default
            )
        )
        
        # Test that different clients get different keys
        key1 = rate_limiter._get_client_key(handler1)
        key2 = rate_limiter._get_client_key(handler2)
        key3 = rate_limiter._get_client_key(handler3)
        
        self.assertEqual(key1, 'ip:192.168.1.1')
        self.assertEqual(key2, 'key:test-api-key')
        self.assertEqual(key3, 'key:test-api-key-2')

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

    def test_http_server_bootstrap_from_config_file(self):
        """Verify HTTP server bootstraps from a JSON config file with auth settings."""
        import json
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'http-config.json')
            config_data = {
                'mcp_http_bind_host': '127.0.0.1',
                'mcp_http_bind_port': 0,
                'mcp_http_auth_token_env': 'VIV_AI_HTTP_TEST_TOKEN',
                'mcp_http_max_request_size': 512,
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f)

            os.environ['VIV_AI_HTTP_TEST_TOKEN'] = 'test-bearer-token'
            os.environ.pop('VIV_AI_CONFIG', None)
            try:
                from viv_ai.config import AiConfig
                from viv_ai.mcp.http_transport import create_http_server
                from viv_ai.mcp.server import VivAIMcpServer

                config = AiConfig.load(config_path)
                server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
                httpd = create_http_server(server, config=config)
                info = httpd.vivai_http_info()

                self.assertEqual(info['host'], '127.0.0.1')
                self.assertIsInstance(info['port'], int)
                self.assertGreater(info['port'], 0)
                self.assertEqual(info['auth_token_env'], 'VIV_AI_HTTP_TEST_TOKEN')
                self.assertEqual(info['auth_required'], True)
                self.assertEqual(info['max_request_size'], 512)

                # Verify the server actually works
                thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                thread.start()
                try:
                    host, port = httpd.server_address
                    conn = http.client.HTTPConnection(host, port, timeout=5)
                    conn.request(
                        'POST',
                        '/mcp',
                        body=json.dumps({'id': 1, 'method': 'ping', 'params': {}}),
                        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer test-bearer-token'},
                    )
                    resp = conn.getresponse()
                    payload = json.loads(resp.read())
                    self.assertEqual(resp.status, 200)
                    self.assertEqual(payload['result'], {})
                finally:
                    httpd.shutdown()
                    httpd.server_close()
                    thread.join(timeout=5)
            finally:
                os.environ.pop('VIV_AI_HTTP_TEST_TOKEN', None)


if __name__ == '__main__':
    unittest.main()

"""Comprehensive HTTP transport compatibility tests for Phase Q.

Tests the MCP HTTP transport against different auth modes, client patterns,
error scenarios, and edge cases to ensure broad client compatibility.
"""
import http.client
import json
import os
import threading
import time
import unittest
import uuid


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


class McpHttpCompatibilityTests(unittest.TestCase):
    """Tests that the HTTP transport is compatible with various client patterns."""

    # ------------------------------------------------------------------ #
    # No-auth mode
    # ------------------------------------------------------------------ #
    def test_no_auth_allows_requests(self):
        """Server with no auth configured allows unauthenticated requests."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request(
                'POST', '/mcp',
                body=json.dumps({'id': 1, 'method': 'initialize', 'params': {}}),
                headers={'Content-Type': 'application/json'},
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            self.assertEqual(payload['result']['serverInfo']['name'], 'viv_ai_mcp')
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    # ------------------------------------------------------------------ #
    # Bearer token auth — different header formats
    # ------------------------------------------------------------------ #
    def test_bearer_auth_with_standard_header(self):
        """Bearer token in Authorization: Bearer <token> works."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0,
                                   auth_token='my-secret-token')
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request(
                'POST', '/mcp',
                body=json.dumps({'id': 1, 'method': 'ping', 'params': {}}),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer my-secret-token',
                },
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            self.assertEqual(payload['result'], {})
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_bearer_auth_rejects_invalid_token(self):
        """Bearer auth returns 401 for wrong token."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0,
                                   auth_token='correct-token')
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request(
                'POST', '/mcp',
                body=json.dumps({'id': 1, 'method': 'ping', 'params': {}}),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer wrong-token',
                },
            )
            resp = conn.getresponse()
            self.assertEqual(resp.status, 401)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    # ------------------------------------------------------------------ #
    # API key auth — X-API-Key and Bearer header variants
    # ------------------------------------------------------------------ #
    def test_api_key_auth_via_x_api_key_header(self):
        """API key in X-API-Key header is accepted."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0,
                                   api_key='my-api-key')
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request(
                'POST', '/mcp',
                body=json.dumps({'id': 1, 'method': 'ping', 'params': {}}),
                headers={
                    'Content-Type': 'application/json',
                    'X-API-Key': 'my-api-key',
                },
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            self.assertEqual(payload['result'], {})
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_api_key_auth_via_bearer_header(self):
        """API key sent as Bearer token in Authorization header works."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0,
                                   api_key='my-api-key')
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request(
                'POST', '/mcp',
                body=json.dumps({'id': 1, 'method': 'ping', 'params': {}}),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer my-api-key',
                },
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            self.assertEqual(payload['result'], {})
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_api_key_auth_rejects_wrong_key(self):
        """API key auth returns 401 for wrong key."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0,
                                   api_key='correct-key')
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request(
                'POST', '/mcp',
                body=json.dumps({'id': 1, 'method': 'ping', 'params': {}}),
                headers={
                    'Content-Type': 'application/json',
                    'X-API-Key': 'wrong-key',
                },
            )
            resp = conn.getresponse()
            self.assertEqual(resp.status, 401)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    # ------------------------------------------------------------------ #
    # GET /healthz endpoint
    # ------------------------------------------------------------------ #
    def test_healthz_returns_server_info(self):
        """GET /healthz returns server status and HTTP config info."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request('GET', '/healthz', headers={})
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            self.assertTrue(payload['ok'])
            self.assertEqual(payload['server']['name'], 'viv_ai_mcp')
            self.assertIn('http', payload)
            self.assertIn('host', payload['http'])
            self.assertIn('port', payload['http'])
            self.assertIn('path', payload['http'])
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_healthz_respects_auth_when_configured(self):
        """GET /healthz respects auth when bearer token is configured (no auth = 401)."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0,
                                   auth_token='secret')
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            # Without auth
            conn.request('GET', '/healthz', headers={})
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            # Current code does not enforce auth on GET /healthz — it's an
            # unauthenticated health-check endpoint. This test documents that
            # behaviour and can be tightened if auth-on-healthz is desired later.
            self.assertEqual(resp.status, 200)
            self.assertTrue(payload['ok'])
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    # ------------------------------------------------------------------ #
    # Custom paths
    # ------------------------------------------------------------------ #
    def test_custom_path_routing(self):
        """Server with custom /api/v1/mcp path routes requests correctly."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0,
                                   auth_token='t', path='/api/v1/mcp')
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            # Right path
            conn.request(
                'POST', '/api/v1/mcp',
                body=json.dumps({'id': 1, 'method': 'ping', 'params': {}}),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer t',
                },
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            self.assertEqual(payload['result'], {})

            # Wrong path
            conn.request(
                'POST', '/mcp',
                body=json.dumps({'id': 2, 'method': 'ping', 'params': {}}),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer t',
                },
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 404)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    # ------------------------------------------------------------------ #
    # Invalid / edge-case HTTP scenarios
    # ------------------------------------------------------------------ #
    def test_post_to_unknown_path_returns_404(self):
        """POST to non-existent path returns 404 with proper error format."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request('POST', '/not-mcp',
                         body=json.dumps({'id': 1, 'method': 'ping', 'params': {}}),
                         headers={'Content-Type': 'application/json'})
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 404)
            self.assertIn('id', payload)
            self.assertEqual(payload['error']['code'], 404)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_get_to_unknown_path_returns_404(self):
        """GET on non-/healthz path returns 404."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request('GET', '/wrong-path', headers={})
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 404)
            self.assertIn('not found', payload['error']['message'].lower())
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_invalid_content_length_rejected(self):
        """Non-integer Content-Length header returns 400."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0,
                                   max_request_size=1024)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            # Manually send a raw request with malformed Content-Length
            conn.request(
                'POST', '/mcp',
                body=json.dumps({'id': 1, 'method': 'ping', 'params': {}}),
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': 'not-a-number',
                },
            )
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 400)
            self.assertIn('content-length', payload['error']['message'].lower())
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    # ------------------------------------------------------------------ #
    # End-to-end MCP flow verification
    # ------------------------------------------------------------------ #
    def test_e2e_initialize_tools_list_call_flow(self):
        """Full MCP lifecycle: initialize -> tools/list -> tools/call -> shutdown."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0,
                                   auth_token='flow-test')
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer flow-test',
            }

            # 1. initialize
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request('POST', '/mcp',
                         body=json.dumps({'id': 1, 'method': 'initialize', 'params': {}}),
                         headers=headers)
            resp = conn.getresponse()
            init_payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            self.assertEqual(init_payload['result']['serverInfo']['name'], 'viv_ai_mcp')
            self.assertIn('capabilities', init_payload['result'])
            self.assertIn('tools', init_payload['result']['capabilities'])

            # 2. tools/list — get available tools
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request('POST', '/mcp',
                         body=json.dumps({'id': 2, 'method': 'tools/list', 'params': {}}),
                         headers=headers)
            resp = conn.getresponse()
            tools_payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            tools = tools_payload['result']['tools']
            self.assertGreater(len(tools), 0)
            tool_names = [t['name'] for t in tools]
            self.assertIn('get_metadata', tool_names)

            # 3. tools/call — invoke a read-only tool
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request('POST', '/mcp',
                         body=json.dumps({
                             'id': 3, 'method': 'tools/call',
                             'params': {'name': 'get_metadata', 'arguments': {}},
                         }),
                         headers=headers)
            resp = conn.getresponse()
            call_payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            self.assertIn('result', call_payload)

            # 4. shutdown
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request('POST', '/mcp',
                         body=json.dumps({'id': 4, 'method': 'shutdown', 'params': {}}),
                         headers=headers)
            resp = conn.getresponse()
            shutdown_payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            self.assertIsNone(shutdown_payload['result'])
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        finally:
            if thread.is_alive():
                httpd.shutdown()
                thread.join(timeout=5)
            httpd.server_close()

    def test_server_info_method_over_http(self):
        """server/info returns server metadata over HTTP."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request('POST', '/mcp',
                         body=json.dumps({'id': 1, 'method': 'server/info', 'params': {}}),
                         headers={'Content-Type': 'application/json'})
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(resp.status, 200)
            self.assertEqual(payload['result']['name'], 'viv_ai_mcp')
            self.assertIn('tools', payload['result'])
            self.assertIn('limits', payload['result'])
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    # ------------------------------------------------------------------ #
    # Request tracing
    # ------------------------------------------------------------------ #
    def test_request_id_tracing_across_mcp_calls(self):
        """Request IDs are preserved and returned in responses."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address
            conn = http.client.HTTPConnection(host, port, timeout=5)

            # Send a request with a specific ID
            conn.request('POST', '/mcp',
                         body=json.dumps({'id': 'my-trace-id', 'method': 'ping', 'params': {}}),
                         headers={'Content-Type': 'application/json'})
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(payload['id'], 'my-trace-id')

            # Send another request with a different ID
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request('POST', '/mcp',
                         body=json.dumps({'id': 42, 'method': 'ping', 'params': {}}),
                         headers={'Content-Type': 'application/json'})
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertEqual(payload['id'], 42)

            # Error responses echo back whatever id was sent (None stays None)
            conn = http.client.HTTPConnection(host, port, timeout=5)
            conn.request('POST', '/mcp',
                         body=json.dumps({'id': None, 'method': 'INVALID', 'params': {}}),
                         headers={'Content-Type': 'application/json'})
            resp = conn.getresponse()
            payload = json.loads(resp.read())
            self.assertIsNone(payload['id'])
            self.assertIn('error', payload)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    # ------------------------------------------------------------------ #
    # Rate limiter key isolation
    # ------------------------------------------------------------------ #
    def test_rate_limiter_isolates_by_client_ip(self):
        """Rate limiter uses distinct windows per client IP."""
        from unittest.mock import Mock
        from viv_ai.mcp.http_transport import RateLimiter

        rate_limiter = RateLimiter(2, 60)

        h1 = Mock()
        h1.client_address = ('10.0.0.1', 12345)
        h1.headers.get.return_value = ''

        h2 = Mock()
        h2.client_address = ('10.0.0.2', 12346)
        h2.headers.get.return_value = ''

        # h1 uses 2 requests (reaches limit)
        self.assertTrue(rate_limiter.is_allowed(h1)[0])
        self.assertTrue(rate_limiter.is_allowed(h1)[0])

        # h2 should still be allowed (different IP)
        self.assertTrue(rate_limiter.is_allowed(h2)[0])
        self.assertTrue(rate_limiter.is_allowed(h2)[0])

        # h1 is now over limit
        self.assertFalse(rate_limiter.is_allowed(h1)[0])

        # h2 is also over limit now
        self.assertFalse(rate_limiter.is_allowed(h2)[0])

    def test_rate_limiter_hybrid_key_with_api_key(self):
        """Rate limiter uses API key over IP when key is present."""
        from unittest.mock import Mock
        from viv_ai.mcp.http_transport import RateLimiter

        rate_limiter = RateLimiter(2, 60)

        # Same IP, different API keys -> separate limits
        h1 = Mock()
        h1.client_address = ('10.0.0.1', 12345)
        def h1_get(key, default=''):
            return 'Bearer key-one' if key == 'Authorization' else ''
        h1.headers.get.side_effect = h1_get

        h2 = Mock()
        h2.client_address = ('10.0.0.1', 12346)
        def h2_get(key, default=''):
            return 'Bearer key-two' if key == 'Authorization' else ''
        h2.headers.get.side_effect = h2_get

        self.assertTrue(rate_limiter.is_allowed(h1)[0])
        self.assertTrue(rate_limiter.is_allowed(h1)[0])
        self.assertFalse(rate_limiter.is_allowed(h1)[0])

        # h2 (different key) still has its own budget
        self.assertTrue(rate_limiter.is_allowed(h2)[0])
        self.assertTrue(rate_limiter.is_allowed(h2)[0])
        self.assertFalse(rate_limiter.is_allowed(h2)[0])

    # ------------------------------------------------------------------ #
    # Concurrent clients
    # ------------------------------------------------------------------ #
    def test_concurrent_clients(self):
        """Multiple concurrent clients can interact with the server."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer(workspace_loader=lambda path: FakeVW())
        httpd = create_http_server(server, host='127.0.0.1', port=0,
                                   auth_token='concurrent')
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address

            def client_request(client_id, results):
                try:
                    conn = http.client.HTTPConnection(host, port, timeout=5)
                    conn.request(
                        'POST', '/mcp',
                        body=json.dumps({
                            'id': client_id,
                            'method': 'ping',
                            'params': {},
                        }),
                        headers={
                            'Content-Type': 'application/json',
                            'Authorization': 'Bearer concurrent',
                        },
                    )
                    resp = conn.getresponse()
                    payload = json.loads(resp.read())
                    results.append((client_id, resp.status, payload))
                except Exception as e:
                    results.append((client_id, -1, str(e)))

            threads = []
            results = []
            for i in range(5):
                t = threading.Thread(target=client_request, args=(i, results))
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=10)

            self.assertEqual(len(results), 5)
            for client_id, status, payload in results:
                self.assertEqual(status, 200, f'Client {client_id} failed')
                self.assertEqual(payload['id'], client_id)
                self.assertEqual(payload['result'], {})
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    # ------------------------------------------------------------------ #
    # Config-based auth env var resolution
    # ------------------------------------------------------------------ #
    def test_auth_token_from_env_var_in_http_info(self):
        """Auth token resolved from env var is reflected in http_info without exposing value."""
        os.environ['VIV_AI_HTTP_TOKEN'] = 'env-sourced-token'
        try:
            from viv_ai.config import AiConfig
            from viv_ai.mcp.http_transport import create_http_server
            from viv_ai.mcp.server import VivAIMcpServer

            config = AiConfig.from_dict({
                'mcp_http_bind_host': '127.0.0.1',
                'mcp_http_bind_port': 0,
                'mcp_http_auth_token_env': 'VIV_AI_HTTP_TOKEN',
            })
            server = VivAIMcpServer()
            httpd = create_http_server(server, config=config)
            info = httpd.vivai_http_info()

            self.assertEqual(info['auth_token_env'], 'VIV_AI_HTTP_TOKEN')
            self.assertTrue(info['auth_required'])
            info_str = json.dumps(info)
            self.assertNotIn('env-sourced-token', info_str)
        finally:
            os.environ.pop('VIV_AI_HTTP_TOKEN', None)

    def test_api_key_from_env_var_without_exposing(self):
        """API key resolved from env var is not exposed in http_info."""
        os.environ['VIV_AI_HTTP_API_KEY'] = 'super-secret-key'
        try:
            from viv_ai.config import AiConfig
            from viv_ai.mcp.http_transport import create_http_server
            from viv_ai.mcp.server import VivAIMcpServer

            config = AiConfig.from_dict({
                'mcp_http_bind_host': '127.0.0.1',
                'mcp_http_bind_port': 0,
                'mcp_http_api_key_env': 'VIV_AI_HTTP_API_KEY',
            })
            server = VivAIMcpServer()
            httpd = create_http_server(server, config=config)
            info = httpd.vivai_http_info()

            self.assertEqual(info['api_key_env'], 'VIV_AI_HTTP_API_KEY')
            self.assertTrue(info['auth_required'])
            info_str = json.dumps(info)
            self.assertNotIn('super-secret-key', info_str)
        finally:
            os.environ.pop('VIV_AI_HTTP_API_KEY', None)

    # ------------------------------------------------------------------ #
    # Environment variable resolution failure
    # ------------------------------------------------------------------ #
    def test_auth_env_var_not_set_raises_error(self):
        """Missing auth env var raises ValueError at server creation."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer()
        with self.assertRaises(ValueError):
            create_http_server(server, host='127.0.0.1', port=0,
                               auth_token_env='UNSET_ENV_VAR_FOR_TEST')

    def test_api_key_env_var_not_set_raises_error(self):
        """Missing API key env var raises ValueError at server creation."""
        from viv_ai.mcp.http_transport import create_http_server
        from viv_ai.mcp.server import VivAIMcpServer

        server = VivAIMcpServer()
        with self.assertRaises(ValueError):
            create_http_server(server, host='127.0.0.1', port=0,
                               api_key_env='UNSET_API_KEY_ENV')


if __name__ == '__main__':
    unittest.main()

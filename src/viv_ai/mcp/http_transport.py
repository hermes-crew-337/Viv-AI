import argparse
import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Iterable, Optional

from ..config import AiConfig, load_runtime_config
from ..service import AnalysisService
from .entrypoint import _error_response, _handle_request, _parse_request
from .server import VivAIMcpServer


def _resolve_auth(auth_token: Optional[str] = None, auth_token_env: Optional[str] = None, api_key: Optional[str] = None, api_key_env: Optional[str] = None):
    # Resolve bearer token auth
    token = None
    token_env = None
    if auth_token is not None:
        token = auth_token
    elif auth_token_env:
        value = os.getenv(auth_token_env)
        if not value:
            raise ValueError(f'HTTP auth token env var is not set: {auth_token_env}')
        token = value
        token_env = auth_token_env
    
    # Resolve API key auth
    key = None
    key_env = None
    if api_key is not None:
        key = api_key
    elif api_key_env:
        value = os.getenv(api_key_env)
        if not value:
            raise ValueError(f'HTTP API key env var is not set: {api_key_env}')
        key = value
        key_env = api_key_env
    
    return token, token_env, key, key_env


def create_http_server(server: VivAIMcpServer, host: str = '127.0.0.1', port: int = 0, path: str = '/mcp', auth_token: Optional[str] = None, auth_token_env: Optional[str] = None, api_key: Optional[str] = None, api_key_env: Optional[str] = None, max_request_size: Optional[int] = None, config: Optional[AiConfig] = None) -> ThreadingHTTPServer:
    if config is not None:
        host = config.mcp_http_bind_host
        port = config.mcp_http_bind_port
        auth_token_env = config.mcp_http_auth_token_env
        api_key_env = config.mcp_http_api_key_env
        max_request_size = config.mcp_http_max_request_size
    auth_token, auth_token_env, api_key, api_key_env = _resolve_auth(auth_token=auth_token, auth_token_env=auth_token_env, api_key=api_key, api_key_env=api_key_env)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _generate_request_id(self) -> str:
            """Generate a unique request ID for tracing."""
            return str(uuid.uuid4())

        def _write_json(self, status: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _check_auth(self) -> bool:
            # If no auth is configured, allow access
            if auth_token is None and api_key is None:
                return True
            
            # Check bearer token auth
            if auth_token is not None:
                header = self.headers.get('Authorization', '')
                if header == f'Bearer {auth_token}':
                    return True
            
            # Check API key auth
            if api_key is not None:
                # Check Authorization header for Bearer API key
                header = self.headers.get('Authorization', '')
                if header == f'Bearer {api_key}':
                    return True
                # Check X-API-Key header
                api_key_header = self.headers.get('X-API-Key', '')
                if api_key_header == api_key:
                    return True
            
            self._write_json(401, _error_response(None, 401, 'unauthorized'))
            return False

        def _check_request_size(self) -> bool:
            """Check if the request size is within limits."""
            if max_request_size is None:
                return True
            
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                self._write_json(400, _error_response(None, 400, 'invalid content-length'))
                return False
            
            if length > max_request_size:
                self._write_json(413, _error_response(None, 413, f'request entity too large: {length} bytes exceeds {max_request_size} bytes limit'))
                return False
            
            return True

        def do_POST(self) -> None:
            request_id = self._generate_request_id()
            
            if self.path != path:
                self._write_json(404, _error_response(request_id, 404, f'not found: {self.path}'))
                return
            if not self._check_auth():
                return
            if not self._check_request_size():
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                self._write_json(400, _error_response(request_id, 400, 'invalid content-length'))
                return
            raw = self.rfile.read(length).decode('utf-8')
            request, error = _parse_request(raw)
            if error is not None:
                # Add request ID to error response
                error['id'] = request_id
                self._write_json(200, error)
                return
            # Add request ID to the request for tracing
            if request is not None:
                request['id'] = request.get('id', request_id)
            response, keep_running = _handle_request(server, request)
            self._write_json(200, response)
            if not keep_running:
                threading.Thread(target=httpd.shutdown, daemon=True).start()

        def do_GET(self) -> None:
            request_id = self._generate_request_id()
            
            if self.path == '/healthz':
                self._write_json(200, {'ok': True, 'server': server.server_info(), 'http': httpd.vivai_http_info()})
                return
            self._write_json(404, _error_response(request_id, 404, f'not found: {self.path}'))

    httpd = ThreadingHTTPServer((host, port), Handler)

    def vivai_http_info() -> Dict[str, Any]:
        bound_host, bound_port = httpd.server_address[:2]
        return {
            'host': bound_host,
            'port': bound_port,
            'path': path,
            'auth_required': auth_token is not None or api_key is not None,
            'auth_token_env': auth_token_env,
            'api_key_env': api_key_env,
            'max_request_size': max_request_size,
        }

    httpd.vivai_http_info = vivai_http_info  # type: ignore[attr-defined]
    return httpd


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Viv-AI MCP HTTP transport')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--path', default='/mcp')
    parser.add_argument('--auth-token-env', default=None)
    parser.add_argument('--api-key-env', default=None)
    parser.add_argument('--max-request-size', type=int, default=1024*1024, help='Maximum request size in bytes (default: 1MB)')
    parser.add_argument('--config', default=None, help='path to a Viv-AI JSON config file; defaults to $VIV_AI_CONFIG or ~/.config/viv-ai/config.json')
    return parser


def main(argv: Optional[Iterable[str]] = None, server: Optional[VivAIMcpServer] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    config = None
    if server is None:
        config = load_runtime_config(args.config)
        server = VivAIMcpServer(analysis_service=AnalysisService(config))
    server.start()
    httpd = create_http_server(
        server,
        host=args.host,
        port=args.port,
        path=args.path,
        auth_token_env=args.auth_token_env,
        api_key_env=args.api_key_env,
        max_request_size=args.max_request_size,
        config=config,
    )
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        server.stop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

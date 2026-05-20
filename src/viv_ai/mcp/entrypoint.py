from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Iterable, Optional, TextIO

from .server import VivAIMcpServer


_PROTOCOL_VERSION = '2026-03-26'


def _tool_descriptors(server: VivAIMcpServer) -> list[Dict[str, Any]]:
    tools = []
    for name in sorted(server.tool_registry.keys()):
        tools.append(
            {
                'name': name,
                'description': f'Viv-AI MCP tool: {name}',
                'inputSchema': {
                    'type': 'object',
                    'properties': {},
                    'additionalProperties': True,
                },
            }
        )
    return tools


def _ok_response(request_id: Any, result: Any) -> Dict[str, Any]:
    return {'jsonrpc': '2.0', 'id': request_id, 'result': result}


def _error_response(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {'jsonrpc': '2.0', 'id': request_id, 'error': {'code': code, 'message': message}}


def _handle_request(server: VivAIMcpServer, request: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    request_id = request.get('id')
    method = request.get('method')
    params = dict(request.get('params') or {})

    if method == 'initialize':
        result = {
            'protocolVersion': _PROTOCOL_VERSION,
            'serverInfo': {'name': server.server_info()['name'], 'version': '0.1.0'},
            'capabilities': {'tools': {'listChanged': False}},
        }
        return _ok_response(request_id, result), True

    if method == 'ping':
        return _ok_response(request_id, {}), True

    if method == 'tools/list':
        return _ok_response(request_id, {'tools': _tool_descriptors(server)}), True

    if method == 'tools/call':
        name = params.get('name', '')
        arguments = dict(params.get('arguments') or {})
        result = server.call_tool(name, **arguments)
        return _ok_response(request_id, result), True

    if method == 'shutdown':
        server.stop()
        return _ok_response(request_id, None), False

    if method == 'server/info':
        return _ok_response(request_id, server.server_info()), True

    return _error_response(request_id, -32601, f'method not found: {method}'), True


def serve_once(server: VivAIMcpServer, instream: TextIO, outstream: TextIO) -> bool:
    line = instream.readline()
    if not line:
        return False
    request = json.loads(line)
    response, keep_running = _handle_request(server, request)
    outstream.write(json.dumps(response) + '\n')
    outstream.flush()
    return keep_running


def serve_forever(server: VivAIMcpServer, instream: TextIO, outstream: TextIO) -> int:
    server.start()
    keep_running = True
    while keep_running:
        keep_running = serve_once(server, instream, outstream)
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Viv-AI MCP stdio entrypoint')
    parser.add_argument('--once', action='store_true', help='process a single JSON-RPC request from stdin and exit')
    return parser


def main(argv: Optional[Iterable[str]] = None, instream: Optional[TextIO] = None, outstream: Optional[TextIO] = None, server: Optional[VivAIMcpServer] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    server = server or VivAIMcpServer()
    instream = instream or sys.stdin
    outstream = outstream or sys.stdout
    if args.once:
        server.start()
        serve_once(server, instream, outstream)
        return 0
    return serve_forever(server, instream, outstream)


if __name__ == '__main__':
    raise SystemExit(main())

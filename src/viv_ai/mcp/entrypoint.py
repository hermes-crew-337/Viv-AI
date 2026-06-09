"""Entrypoint for the Viv-AI MCP server over stdio (JSON-RPC 2.0)."""

from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Dict, Iterable, Optional, TextIO

from ..config import load_runtime_config
from ..service import AnalysisService
from .server import VivAIMcpServer
from .tools import build_tool_metadata

_PROTOCOL_VERSION = '2026-03-26'

_ANALYSIS_TIMEOUT = 60  # seconds for the background initial analysis


def _viv_load(path: str) -> Any:
    """Load a binary into a Vivisect workspace and start background analysis."""
    import vivisect

    vw = vivisect.VivWorkspace()
    vw.loadFromFile(path)
    # Launch analysis in a daemon thread so the server can start serving
    # immediately while analysis catches up in the background.
    t = threading.Thread(target=vw.analyze, daemon=True, name=f"analyze-{path}")
    t.start()
    return vw


def _tool_descriptors(server: VivAIMcpServer) -> list[Dict[str, Any]]:
    metadata = build_tool_metadata()
    tools = []
    for name in sorted(server.tool_registry.keys()):
        descriptor = dict(metadata.get(name, {}))
        descriptor['name'] = name
        descriptor.setdefault('description', f'Viv-AI MCP tool: {name}')
        descriptor.setdefault(
            'inputSchema',
            {
                'type': 'object',
                'properties': {},
                'required': [],
                'additionalProperties': True,
            },
        )
        descriptor.setdefault('annotations', {'readOnlyHint': False})
        tools.append(descriptor)
    return tools


def _ok_response(request_id: Any, result: Any) -> Dict[str, Any]:
    return {'jsonrpc': '2.0', 'id': request_id, 'result': result}


def _error_response(request_id: Any, code: int, message: str, data: Optional[Any] = None) -> Dict[str, Any]:
    error = {'code': code, 'message': message}
    if data is not None:
        error['data'] = data
    return {'jsonrpc': '2.0', 'id': request_id, 'error': error}


def _parse_request(line: str) -> tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        return None, _error_response(None, -32700, f'parse error: {exc.msg}')
    if not isinstance(request, dict):
        return None, _error_response(None, -32600, 'invalid request: expected object')
    return request, None


def _handle_request(server: VivAIMcpServer, request: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    request_id = request.get('id')
    method = request.get('method')
    raw_params = request.get('params') or {}
    if not isinstance(raw_params, dict):
        return _error_response(request_id, -32602, 'invalid params: expected object'), True
    params = dict(raw_params)

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
        raw_arguments = params.get('arguments') or {}
        if not isinstance(raw_arguments, dict):
            return _error_response(request_id, -32602, 'invalid params: arguments must be an object'), True
        arguments = dict(raw_arguments)
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
    request, error = _parse_request(line)
    if error is not None:
        outstream.write(json.dumps(error) + '\n')
        outstream.flush()
        return True
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
    parser.add_argument('--config', default=None, help='path to a Viv-AI JSON config file; defaults to $VIV_AI_CONFIG or ~/.config/viv-ai/config.json')
    parser.add_argument('--analyze-timeout', type=int, default=60, help='max seconds for background analysis on open (default 60)')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--read-only', dest='read_only', action='store_true', default=None, help='block mutations (overrides config)')
    group.add_argument('--read-write', dest='read_only', action='store_false', default=None, help='allow mutations (overrides config)')
    return parser


def main(argv: Optional[Iterable[str]] = None, instream: Optional[TextIO] = None, outstream: Optional[TextIO] = None, server: Optional[VivAIMcpServer] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if server is None:
        config = load_runtime_config(args.config)
        mcp_timeout = getattr(config, 'mcp_max_tool_seconds', None) if config else None
        # CLI --read-only / --read-write overrides config value
        ro = args.read_only if args.read_only is not None else getattr(config, 'read_only', True)
        server = VivAIMcpServer(
            workspace_loader=_viv_load,
            analysis_service=AnalysisService(config),
            read_only=ro,
            max_tool_seconds=mcp_timeout or 120.0,  # generous for analysis-heavy tools
        )
    instream = instream or sys.stdin
    outstream = outstream or sys.stdout
    if args.once:
        server.start()
        serve_once(server, instream, outstream)
        return 0
    return serve_forever(server, instream, outstream)


if __name__ == '__main__':
    raise SystemExit(main())

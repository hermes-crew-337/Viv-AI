import threading
import time
import unittest


class FakeVW:
    def __init__(self):
        self.meta = {'Architecture': 'amd64', 'Platform': 'linux', 'Format': 'elf'}

    def getMeta(self, name, default=None):
        return self.meta.get(name, default)


class BlockingTool:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def __call__(self, manager, **kwargs):
        self.started.set()
        self.release.wait(timeout=1.0)
        return {
            'ok': True,
            'workspace_id': None,
            'request_scope': 'workspace',
            'data': {'released': True},
            'summary': 'released',
            'warnings': [],
            'provenance': {'tool': 'blocking'},
            'error': None,
        }


class McpOperationalTests(unittest.TestCase):
    def test_server_returns_structured_timeout_error_for_slow_tool(self):
        from viv_ai.mcp.server import VivAIMcpServer

        def slow_tool(manager, **kwargs):
            time.sleep(0.2)
            return {'ok': True}

        server = VivAIMcpServer(tool_registry={'slow': slow_tool}, max_tool_seconds=0.05)
        start = time.monotonic()
        result = server.call_tool('slow')
        elapsed = time.monotonic() - start

        self.assertFalse(result['ok'])
        self.assertIn('timed out', result['error'])
        self.assertLess(elapsed, 0.15)

    def test_server_enforces_timeout_from_worker_thread(self):
        from viv_ai.mcp.server import VivAIMcpServer

        def slow_tool(manager, **kwargs):
            time.sleep(0.2)
            return {'ok': True}

        server = VivAIMcpServer(tool_registry={'slow': slow_tool}, max_tool_seconds=0.05, max_concurrent_tools=1)
        holder = {}

        def invoke():
            start = time.monotonic()
            holder['result'] = server.call_tool('slow')
            holder['elapsed'] = time.monotonic() - start

        worker = threading.Thread(target=invoke)
        worker.start()
        worker.join(timeout=1.0)

        self.assertFalse(holder['result']['ok'])
        self.assertIn('timed out', holder['result']['error'])
        self.assertLess(holder['elapsed'], 0.15)

    def test_server_rejects_calls_over_concurrency_limit(self):
        from viv_ai.mcp.server import VivAIMcpServer

        blocker = BlockingTool()
        server = VivAIMcpServer(tool_registry={'blocking': blocker}, max_concurrent_tools=1)
        first_result = {}

        def run_first():
            first_result['value'] = server.call_tool('blocking')

        worker = threading.Thread(target=run_first)
        worker.start()
        blocker.started.wait(timeout=1.0)

        second = server.call_tool('blocking')
        blocker.release.set()
        worker.join(timeout=1.0)

        self.assertFalse(second['ok'])
        self.assertIn('concurrency', second['error'])
        self.assertTrue(first_result['value']['ok'])


if __name__ == '__main__':
    unittest.main()

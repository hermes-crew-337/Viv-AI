"""Tests for viv_ai.mcp.schemas — ToolRequest and ToolResponse dataclasses."""

import unittest


class ToolRequestTests(unittest.TestCase):
    def test_default_fields(self):
        from viv_ai.mcp.schemas import ToolRequest
        req = ToolRequest(workspace_id=None, request_scope='workspace', tool_name='')
        self.assertIsNone(req.workspace_id)
        self.assertEqual(req.request_scope, 'workspace')
        self.assertEqual(req.tool_name, '')
        self.assertEqual(req.arguments, {})

    def test_to_dict_roundtrip(self):
        from viv_ai.mcp.schemas import ToolRequest
        req = ToolRequest(
            workspace_id='ws-1',
            request_scope='workspace',
            tool_name='analyze_function',
            arguments={'va': '0x401000'},
        )
        d = req.to_dict()
        self.assertEqual(d['workspace_id'], 'ws-1')
        self.assertEqual(d['tool_name'], 'analyze_function')
        self.assertEqual(d['arguments'], {'va': '0x401000'})

    def test_from_dict(self):
        from viv_ai.mcp.schemas import ToolRequest
        data = {
            'workspace_id': 'ws-2',
            'request_scope': 'workspace',
            'tool_name': 'list_functions',
            'arguments': {'va': '0x402000'},
        }
        req = ToolRequest.from_dict(data)
        self.assertEqual(req.workspace_id, 'ws-2')
        self.assertEqual(req.tool_name, 'list_functions')
        self.assertEqual(req.arguments, {'va': '0x402000'})

    def test_from_dict_minimal(self):
        from viv_ai.mcp.schemas import ToolRequest
        req = ToolRequest.from_dict({})
        self.assertIsNone(req.workspace_id)
        self.assertEqual(req.request_scope, 'workspace')
        self.assertEqual(req.tool_name, '')
        self.assertEqual(req.arguments, {})


class ToolResponseTests(unittest.TestCase):
    def test_ok_factory(self):
        from viv_ai.mcp.schemas import ToolResponse
        resp = ToolResponse.ok(
            workspace_id='ws-1',
            request_scope='workspace',
            data={'summary': 'ok'},
            warnings=['truncated'],
            summary='analysis complete',
        )
        self.assertTrue(resp.ok)
        self.assertEqual(resp.workspace_id, 'ws-1')
        self.assertEqual(resp.data, {'summary': 'ok'})
        self.assertEqual(resp.warnings, ['truncated'])
        self.assertEqual(resp.summary, 'analysis complete')
        self.assertFalse(resp.truncated)

    def test_error_factory(self):
        from viv_ai.mcp.schemas import ToolResponse
        resp = ToolResponse.error_response(
            workspace_id='ws-1',
            request_scope='workspace',
            error='provider unavailable',
            warnings=['timeout'],
        )
        self.assertFalse(resp.ok)
        self.assertEqual(resp.error, 'provider unavailable')
        self.assertEqual(resp.warnings, ['timeout'])
        self.assertEqual(resp.summary, '')
        self.assertEqual(resp.data, {})

    def test_to_dict_ok(self):
        from viv_ai.mcp.schemas import ToolResponse
        resp = ToolResponse.ok('ws-1', 'workspace', {'result': 42}, provenance={'source': 'cache'})
        d = resp.to_dict()
        self.assertTrue(d['ok'])
        self.assertEqual(d['data'], {'result': 42})
        self.assertEqual(d['provenance'], {'source': 'cache'})

    def test_to_dict_error(self):
        from viv_ai.mcp.schemas import ToolResponse
        resp = ToolResponse.error_response('ws-1', 'workspace', 'fail')
        d = resp.to_dict()
        self.assertFalse(d['ok'])
        self.assertEqual(d['error'], 'fail')

    def test_optional_provenance(self):
        from viv_ai.mcp.schemas import ToolResponse
        resp = ToolResponse.ok('ws-1', 'workspace', {})
        self.assertEqual(resp.provenance, {})

    def test_default_values_in_constructor(self):
        from viv_ai.mcp.schemas import ToolResponse
        resp = ToolResponse(True, None, 'workspace', data=None)
        self.assertEqual(resp.data, {})
        self.assertEqual(resp.warnings, [])
        self.assertEqual(resp.provenance, {})
        self.assertEqual(resp.summary, '')

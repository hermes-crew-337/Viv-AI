import unittest


class FakeVW:
    def __init__(self):
        self.meta = {'Architecture': 'amd64', 'Platform': 'linux', 'Format': 'elf'}
        self.calls = []
        self.rename_result = Ellipsis

    def getMeta(self, name):
        return self.meta.get(name)

    def makeName(self, va, name):
        self.calls.append(('makeName', va, name))
        if self.rename_result is not Ellipsis:
            return self.rename_result
        return name

    def setComment(self, va, comment):
        self.calls.append(('setComment', va, comment))


class McpMutationToolTests(unittest.TestCase):
    def _server(self, policy='conservative_readonly'):
        from viv_ai.mcp.server import VivAIMcpServer

        return VivAIMcpServer(workspace_loader=lambda path: FakeVW(), mutation_policy=policy)

    def _open(self, server):
        return server.call_tool('workspace_open', path='/tmp/sample.bin')['data']['workspace_id']

    def test_registry_exposes_phase_k_proposal_and_apply_tools(self):
        from viv_ai.mcp.tools import build_default_registry

        registry = build_default_registry()

        self.assertIn('propose_function_rename', registry)
        self.assertIn('propose_comment', registry)
        self.assertIn('apply_function_rename', registry)
        self.assertIn('apply_comment', registry)

    def test_proposal_tools_work_in_readonly_mode_without_mutating(self):
        server = self._server(policy='conservative_readonly')
        workspace_id = self._open(server)

        rename = server.call_tool('propose_function_rename', workspace_id=workspace_id, fva='0x401000', new_name='decrypt_payload')
        comment = server.call_tool('propose_comment', workspace_id=workspace_id, va='0x401000', comment='possible parser dispatch')
        vw = server.session_manager.get_workspace(workspace_id)

        self.assertTrue(rename['ok'])
        self.assertTrue(comment['ok'])
        self.assertFalse(rename['data']['applied'])
        self.assertFalse(comment['data']['applied'])
        self.assertIn('proposal', rename['data'])
        self.assertEqual(vw.calls, [])

    def test_apply_tools_are_blocked_in_readonly_mode(self):
        server = self._server(policy='conservative_readonly')
        workspace_id = self._open(server)

        rename = server.call_tool('apply_function_rename', workspace_id=workspace_id, fva='0x401000', new_name='decrypt_payload')
        comment = server.call_tool('apply_comment', workspace_id=workspace_id, va='0x401000', comment='possible parser dispatch')
        vw = server.session_manager.get_workspace(workspace_id)

        self.assertFalse(rename['ok'])
        self.assertFalse(comment['ok'])
        self.assertIn('readonly', rename['error'])
        self.assertIn('readonly', comment['error'])
        self.assertEqual(vw.calls, [])

    def test_apply_tools_are_blocked_in_review_mode(self):
        server = self._server(policy='review_before_apply')
        workspace_id = self._open(server)

        rename = server.call_tool('apply_function_rename', workspace_id=workspace_id, fva='0x401000', new_name='decrypt_payload')

        self.assertFalse(rename['ok'])
        self.assertIn('review required', rename['error'])

    def test_apply_tools_mutate_when_direct_apply_enabled(self):
        server = self._server(policy='direct_apply_enabled')
        workspace_id = self._open(server)

        rename = server.call_tool('apply_function_rename', workspace_id=workspace_id, fva='0x401000', new_name='decrypt_payload')
        comment = server.call_tool('apply_comment', workspace_id=workspace_id, va='0x401000', comment='possible parser dispatch')
        vw = server.session_manager.get_workspace(workspace_id)

        self.assertTrue(rename['ok'])
        self.assertTrue(comment['ok'])
        self.assertTrue(rename['data']['applied'])
        self.assertTrue(comment['data']['applied'])
        self.assertEqual(vw.calls, [
            ('makeName', 0x401000, 'decrypt_payload'),
            ('setComment', 0x401000, 'possible parser dispatch'),
        ])

    def test_apply_tool_reports_workspace_decline_structurally(self):
        server = self._server(policy='direct_apply_enabled')
        workspace_id = self._open(server)
        vw = server.session_manager.get_workspace(workspace_id)
        vw.rename_result = None

        rename = server.call_tool('apply_function_rename', workspace_id=workspace_id, fva='0x401000', new_name='decrypt_payload')

        self.assertFalse(rename['ok'])
        self.assertIn('failed to apply function rename', rename['error'])
        self.assertEqual(rename['data']['proposal']['va'], '0x00401000')


if __name__ == '__main__':
    unittest.main()

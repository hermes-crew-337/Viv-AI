import unittest


class FakeVW:
    def __init__(self):
        self.meta = {'Architecture': 'amd64', 'Platform': 'linux', 'Format': 'elf'}
        self.calls = []
        self.rename_result = Ellipsis

    def getMeta(self, name, default=None):
        return self.meta.get(name, default)

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

    def test_apply_function_rename_applied_flags_committed(self):
        server = self._server('direct_apply_enabled')
        wid = self._open(server)

        result = server.call_tool('apply_function_rename', workspace_id=wid, fva='0x401000', new_name='custom')

        self.assertTrue(result['ok'])
        self.assertTrue(result['data']['applied'])

    def test_campaign_renames_proposal_registered(self):
        from viv_ai.mcp.tools import build_default_registry

        registry = build_default_registry()
        self.assertIn('propose_campaign_renames', registry)
        self.assertIn('apply_campaign_renames', registry)
        self.assertIn('propose_campaign_comments', registry)
        self.assertIn('apply_campaign_comments', registry)

    def test_campaign_renames_proposal_readonly(self):
        server = self._server('conservative_readonly')
        wid = self._open(server)

        result = server.call_tool('propose_campaign_renames', workspace_id=wid, renames=[
            {'fva': '0x401000', 'new_name': 'func_a'},
            {'fva': '0x401010', 'new_name': 'func_b'},
        ])

        self.assertTrue(result['ok'])
        data = result['data']
        self.assertEqual(len(data['results']), 2)
        for r in data['results']:
            self.assertFalse(r['applied'])
            self.assertIn('readonly', r['reason'])

    def test_campaign_renames_apply_readonly_fails(self):
        server = self._server('conservative_readonly')
        wid = self._open(server)

        result = server.call_tool('apply_campaign_renames', workspace_id=wid, renames=[
            {'fva': '0x401000', 'new_name': 'func_a'},
        ])

        self.assertFalse(result['ok'])

    def test_campaign_renames_apply_allowed(self):
        server = self._server('direct_apply_enabled')
        wid = self._open(server)

        result = server.call_tool('apply_campaign_renames', workspace_id=wid, renames=[
            {'fva': '0x401000', 'new_name': 'func_a'},
        ])
        vw = server.session_manager.get_workspace(wid)

        self.assertTrue(result['ok'])
        data = result['data']
        self.assertEqual(len(data['results']), 1)
        self.assertTrue(data['results'][0]['applied'])
        self.assertIn(('makeName', 0x401000, 'func_a'), vw.calls)

    def test_campaign_comments_proposal(self):
        server = self._server('conservative_readonly')
        wid = self._open(server)

        result = server.call_tool('propose_campaign_comments', workspace_id=wid, comments=[
            {'va': '0x401000', 'comment': 'entry point'},
            {'va': '0x401005', 'comment': 'loop start'},
        ])

        self.assertTrue(result['ok'])
        data = result['data']
        self.assertEqual(len(data['results']), 2)
        for r in data['results']:
            self.assertFalse(r['applied'])

    def test_campaign_comments_apply_allowed(self):
        server = self._server('direct_apply_enabled')
        wid = self._open(server)

        result = server.call_tool('apply_campaign_comments', workspace_id=wid, comments=[
            {'va': '0x401000', 'comment': 'entry'},
        ])
        vw = server.session_manager.get_workspace(wid)

        self.assertTrue(result['ok'])
        data = result['data']
        self.assertTrue(data['results'][0]['applied'])
        self.assertIn(('setComment', 0x401000, 'entry'), vw.calls)

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

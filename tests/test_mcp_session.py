import unittest


class FakeVW:
    def __init__(self, label='sample'):
        self.label = label
        self.meta = {
            'Architecture': 'amd64',
            'Platform': 'linux',
            'Format': 'elf',
        }

    def getMeta(self, name):
        return self.meta.get(name)


class McpSessionTests(unittest.TestCase):
    def test_workspace_session_manager_open_list_get_and_close(self):
        from viv_ai.mcp.session import WorkspaceSessionManager

        manager = WorkspaceSessionManager()
        workspace = FakeVW('alpha')

        session = manager.open_workspace('/tmp/a.out', workspace=workspace)
        listed = manager.list_workspaces()
        fetched = manager.get_workspace(session.workspace_id)
        closed = manager.close_workspace(session.workspace_id)

        self.assertEqual(session.workspace_id, listed[0]['workspace_id'])
        self.assertEqual(listed[0]['path'], '/tmp/a.out')
        self.assertEqual(fetched, workspace)
        self.assertTrue(closed)
        self.assertEqual(manager.list_workspaces(), [])

    def test_workspace_session_manager_rejects_unknown_workspace_id(self):
        from viv_ai.mcp.session import WorkspaceSessionError, WorkspaceSessionManager

        manager = WorkspaceSessionManager()

        with self.assertRaises(WorkspaceSessionError):
            manager.get_workspace('missing')

        with self.assertRaises(WorkspaceSessionError):
            manager.close_workspace('missing')

    def test_workspace_session_manager_can_reuse_existing_workspace_id_for_same_path(self):
        from viv_ai.mcp.session import WorkspaceSessionManager

        manager = WorkspaceSessionManager()
        first = manager.open_workspace('/tmp/a.out', workspace=FakeVW('alpha'))
        second = manager.open_workspace('/tmp/a.out', workspace=FakeVW('beta'))

        self.assertEqual(first.workspace_id, second.workspace_id)
        self.assertEqual(manager.list_workspaces()[0]['path'], '/tmp/a.out')

    def test_tool_request_and_response_schemas_round_trip(self):
        from viv_ai.mcp.schemas import ToolRequest, ToolResponse

        request = ToolRequest(
            workspace_id='ws-1',
            request_scope='function',
            tool_name='get_function_summary',
            arguments={'va': '0x401000'},
        )
        response = ToolResponse.ok(
            workspace_id='ws-1',
            request_scope='function',
            data={'summary': 'parser entrypoint'},
            warnings=['truncated callers'],
            truncated=True,
            provenance={'source': 'unit-test'},
            summary='parser entrypoint',
        )

        self.assertEqual(ToolRequest.from_dict(request.to_dict()).tool_name, 'get_function_summary')
        self.assertTrue(response.ok)
        self.assertEqual(response.data['summary'], 'parser entrypoint')
        self.assertEqual(response.summary, 'parser entrypoint')
        self.assertTrue(response.truncated)


if __name__ == '__main__':
    unittest.main()

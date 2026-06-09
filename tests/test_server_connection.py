"""Unit tests for Vivisect Server connection and follow-the-leader MCP tools."""

import unittest
from unittest.mock import patch, MagicMock

from viv_ai.mcp.server import VivAIMcpServer
from viv_ai.mcp.schemas import ToolResponse


FAKE_SERVER_HOST = '10.0.0.50'
FAKE_SERVER_PORT = 0x4074
FAKE_WSNAME = 'firmware.viv'


class FakeServerProxy:
    """Mimics the cobra ``VivServer`` proxy returned by ``connectToServer``."""

    def listWorkspaces(self):
        return [FAKE_WSNAME, 'other.viv']

    def getServerVersion(self):
        return 'Vivisect Server v1.0'


class FakeRemoteVW:
    """Fake remote workspace (connected to a Vivisect Server).

    Has ``.server`` set so ``_has_server()`` and ``_get_server_proxy()``
    work.  Implements all leader API methods as tiny state machines.
    """

    def __init__(self):
        self.meta = {
            'Architecture': 'amd64',
            'Platform': 'linux',
            'Format': 'elf',
        }
        self.server = FakeVivServerClient()
        # leader-session state
        self._leader_sessions: dict = {}
        self._leader_locs: dict = {}
        self._chats: list = []

    def getMeta(self, name):
        return self.meta.get(name)

    def getFunctions(self):
        return [0x401000, 0x402000]

    # ---- leader API -------------------------------------------------------

    def iAmLeader(self, uuid, winname, locexpr=None):
        self._leader_sessions[uuid] = ('ai_agent', winname)
        self._leader_locs[uuid] = locexpr

    def followTheLeader(self, uuid, expr):
        self._leader_locs[uuid] = expr

    def killLeaderSession(self, uuid):
        self._leader_sessions.pop(uuid, None)
        self._leader_locs.pop(uuid, None)

    def getLeaderSessions(self):
        return dict(self._leader_sessions)

    def getLeaderLoc(self, uuid):
        return self._leader_locs.get(uuid)

    def getLeaderInfo(self, uuid=None):
        if uuid is None:
            return list(self._leader_sessions.items())
        info = self._leader_sessions.get(uuid)
        return info if info else (None, None)

    def chat(self, msg):
        self._chats.append(msg)


class FakeVivServerClient:
    """Mimics ``VivServerClient`` — the ``.server`` attribute on a remote VW.

    ``_get_server_proxy(vw)`` returns ``vw.server.server``.
    """

    def __init__(self):
        self.server = FakeServerProxy()


class ServerConnectionToolTests(unittest.TestCase):
    """Tests for server_connect / server_disconnect / server_list_workspaces."""

    def setUp(self):
        self.server = VivAIMcpServer(
            workspace_loader=lambda path: None,
        )

    def _patch_remote(self, fake_vw=None):
        """Patch the two session-level imports that talk to the real server."""
        if fake_vw is None:
            fake_vw = FakeRemoteVW()
        patchers = [
            patch('viv_ai.mcp.session.connect_to_server',
                  return_value=FakeServerProxy()),
            patch('viv_ai.mcp.session.get_remote_workspace',
                  return_value=fake_vw),
        ]
        for p in patchers:
            p.start()
        self.addCleanup(p.stop)
        return fake_vw

    # -- server_connect -----------------------------------------------------

    def test_server_connect_returns_workspace_with_connection_info(self):
        fake_vw = self._patch_remote()

        result = self.server.call_tool(
            'server_connect',
            host=FAKE_SERVER_HOST,
            wsname=FAKE_WSNAME,
        )

        self.assertTrue(result['ok'])
        self.assertIn('workspace_id', result['data'])
        self.assertIn('connection', result['data'])
        self.assertEqual(result['data']['connection']['host'], FAKE_SERVER_HOST)
        self.assertEqual(result['data']['connection']['wsname'], FAKE_WSNAME)
        self.assertEqual(result['data']['function_count'], 2)
        self.assertIn('connected', result['summary'])

    def test_server_connect_dedup_reuses_existing_session(self):
        fake_vw = self._patch_remote()

        r1 = self.server.call_tool(
            'server_connect', host=FAKE_SERVER_HOST, wsname=FAKE_WSNAME,
        )
        r2 = self.server.call_tool(
            'server_connect', host=FAKE_SERVER_HOST, wsname=FAKE_WSNAME,
        )

        self.assertTrue(r1['ok'])
        self.assertTrue(r2['ok'])
        self.assertEqual(r1['data']['workspace_id'], r2['data']['workspace_id'])

    # -- server_disconnect --------------------------------------------------

    def test_server_disconnect_closes_workspace(self):
        fake_vw = self._patch_remote()
        conn = self.server.call_tool(
            'server_connect', host=FAKE_SERVER_HOST, wsname=FAKE_WSNAME,
        )
        wid = conn['data']['workspace_id']

        result = self.server.call_tool('server_disconnect', workspace_id=wid)

        self.assertTrue(result['ok'])
        self.assertTrue(result['data']['disconnected'])

    def test_server_disconnect_cleans_up_leader_session(self):
        fake_vw = self._patch_remote()
        conn = self.server.call_tool(
            'server_connect', host=FAKE_SERVER_HOST, wsname=FAKE_WSNAME,
        )
        wid = conn['data']['workspace_id']

        # start a leader session first
        self.server.call_tool('leader_start', workspace_id=wid)
        result = self.server.call_tool('server_disconnect', workspace_id=wid)

        self.assertTrue(result['ok'])
        self.assertTrue(result['data']['disconnected'])

        # workspace is no longer tracked — workspace_status returns an error
        result2 = self.server.call_tool('workspace_status', workspace_id=wid)
        self.assertFalse(result2['ok'])
        self.assertIn('unknown workspace', result2['error'])

    def test_server_disconnect_on_unknown_workspace_returns_error(self):
        result = self.server.call_tool(
            'server_disconnect', workspace_id='nope',
        )
        self.assertFalse(result['ok'])

    # -- server_list_workspaces ---------------------------------------------

    def test_server_list_workspaces_returns_server_workspaces(self):
        fake_vw = self._patch_remote()
        conn = self.server.call_tool(
            'server_connect', host=FAKE_SERVER_HOST, wsname=FAKE_WSNAME,
        )
        wid = conn['data']['workspace_id']

        result = self.server.call_tool(
            'server_list_workspaces', workspace_id=wid,
        )

        self.assertTrue(result['ok'])
        self.assertIn(FAKE_WSNAME, result['data']['workspaces'])
        self.assertIn('other.viv', result['data']['workspaces'])

    def test_server_list_workspaces_fails_without_server(self):
        # open a local workspace (no server connection)
        open_result = self.server.call_tool(
            'workspace_open', path='/tmp/fake.bin',
        )
        self.assertTrue(open_result['ok'])
        wid = open_result['data']['workspace_id']

        result = self.server.call_tool(
            'server_list_workspaces', workspace_id=wid,
        )
        self.assertFalse(result['ok'])
        self.assertIn('not connected', result['error'])


class LeaderToolTests(unittest.TestCase):
    """Tests for the follow-the-leader tools (leader_start/end/etc)."""

    def setUp(self):
        self.server = VivAIMcpServer(
            workspace_loader=lambda path: None,
        )
        self._fake_vw = FakeRemoteVW()
        patchers = [
            patch('viv_ai.mcp.session.connect_to_server',
                  return_value=FakeServerProxy()),
            patch('viv_ai.mcp.session.get_remote_workspace',
                  return_value=self._fake_vw),
        ]
        for p in patchers:
            p.start()
        self.addCleanup(p.stop)

        conn = self.server.call_tool(
            'server_connect', host=FAKE_SERVER_HOST, wsname=FAKE_WSNAME,
        )
        self.wid = conn['data']['workspace_id']

    # -- leader_start -------------------------------------------------------

    def test_leader_start_creates_leader_session(self):
        result = self.server.call_tool(
            'leader_start', workspace_id=self.wid,
            session_name='Test Session', initial_location='0x401000',
        )

        self.assertTrue(result['ok'])
        self.assertIn('leader_uuid', result['data'])
        self.assertEqual(result['data']['session_name'], 'Test Session')
        self.assertEqual(result['data']['initial_location'], '0x401000')
        self.assertIn('started leader session', result['summary'])

        # check the fake vw state
        sessions = self._fake_vw.getLeaderSessions()
        self.assertEqual(len(sessions), 1)
        uuid = list(sessions.keys())[0]
        self.assertEqual(sessions[uuid][1], 'Test Session')
        self.assertEqual(self._fake_vw.getLeaderLoc(uuid), '0x401000')

    def test_leader_start_with_defaults(self):
        result = self.server.call_tool(
            'leader_start', workspace_id=self.wid,
        )

        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['session_name'], 'AI Analysis Session')
        self.assertEqual(result['data']['initial_location'], '0x0')

    # -- leader_navigate ----------------------------------------------------

    def test_leader_navigate_broadcasts_location(self):
        start = self.server.call_tool(
            'leader_start', workspace_id=self.wid,
        )
        uuid = start['data']['leader_uuid']

        result = self.server.call_tool(
            'leader_navigate', workspace_id=self.wid,
            location_expr='0x402000',
        )

        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['location'], '0x402000')
        self.assertEqual(self._fake_vw.getLeaderLoc(uuid), '0x402000')

    def test_leader_navigate_without_leader_returns_error(self):
        result = self.server.call_tool(
            'leader_navigate', workspace_id=self.wid,
            location_expr='0x401000',
        )

        self.assertFalse(result['ok'])
        self.assertIn('no active leader', result['error'])

    # -- leader_end ---------------------------------------------------------

    def test_leader_end_ends_session(self):
        start = self.server.call_tool('leader_start', workspace_id=self.wid)
        uuid = start['data']['leader_uuid']

        result = self.server.call_tool('leader_end', workspace_id=self.wid)

        self.assertTrue(result['ok'])
        self.assertTrue(result['data']['ended'])
        self.assertEqual(result['data']['leader_uuid'], uuid)

        # verify state cleaned up on the vw
        self.assertEqual(len(self._fake_vw.getLeaderSessions()), 0)

    def test_leader_end_without_leader_returns_error(self):
        result = self.server.call_tool('leader_end', workspace_id=self.wid)
        self.assertFalse(result['ok'])
        self.assertIn('no active leader', result['error'])

    # -- leader_list --------------------------------------------------------

    def test_leader_list_returns_active_sessions(self):
        self.server.call_tool('leader_start', workspace_id=self.wid,
                              session_name='AI Analysis Session')

        result = self.server.call_tool('leader_list', workspace_id=self.wid)

        self.assertTrue(result['ok'])
        # leader_start reuses the existing leader UUID for this workspace,
        # so there is exactly 1 session (overwritten, not duplicated)
        self.assertEqual(len(result['data']['sessions']), 1)
        s = result['data']['sessions'][0]
        self.assertEqual(s['session_name'], 'AI Analysis Session')

    # -- leader_get_location ------------------------------------------------

    def test_leader_get_location_returns_current_loc(self):
        self.server.call_tool('leader_start', workspace_id=self.wid,
                              initial_location='0x402000')

        result = self.server.call_tool(
            'leader_get_location', workspace_id=self.wid,
        )

        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['current_location'], '0x402000')

    def test_leader_get_location_with_specific_uuid(self):
        start = self.server.call_tool('leader_start', workspace_id=self.wid)
        uuid = start['data']['leader_uuid']

        self.server.call_tool(
            'leader_navigate', workspace_id=self.wid,
            location_expr='0x401000',
        )

        result = self.server.call_tool(
            'leader_get_location', workspace_id=self.wid,
            session_uuid=uuid,
        )

        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['current_location'], '0x401000')

    def test_leader_get_location_without_leader_returns_error(self):
        result = self.server.call_tool(
            'leader_get_location', workspace_id=self.wid,
        )
        self.assertFalse(result['ok'])
        self.assertIn('no leader_uuid', result['error'])

    # -- leader_chat --------------------------------------------------------

    def test_leader_chat_sends_message(self):
        self.server.call_tool('leader_start', workspace_id=self.wid)

        result = self.server.call_tool(
            'leader_chat', workspace_id=self.wid,
            message='Hello from AI analyst',
        )

        self.assertTrue(result['ok'])
        self.assertTrue(result['data']['message_sent'])
        self.assertEqual(result['data']['message_length'], 21)
        self.assertIn('Hello from AI analyst', self._fake_vw._chats)

    def test_leader_chat_without_server_returns_error(self):
        # open a local workspace (no server connection)
        open_result = self.server.call_tool(
            'workspace_open', path='/tmp/fake.bin',
        )
        wid = open_result['data']['workspace_id']

        result = self.server.call_tool(
            'leader_chat', workspace_id=wid, message='hi',
        )
        self.assertFalse(result['ok'])
        self.assertIn('not connected', result['error'])

    # -- leader_explain_and_navigate ----------------------------------------

    def test_explain_navigate_no_ai_fallback(self):
        """When no provider is configured, falls back to navigate-only."""
        self.server.call_tool('leader_start', workspace_id=self.wid)
        self.server.session_manager.analysis_service = None

        result = self.server.call_tool(
            'leader_explain_and_navigate', workspace_id=self.wid,
            fva='0x401000',
        )

        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['navigated_to'], '0x401000')
        self.assertFalse(result['data']['ai_analysis_completed'])
        self.assertIsNone(result['data']['analysis'])
        self.assertIn('no AI provider', result['summary'])

    def test_explain_navigate_without_leader_returns_error(self):
        result = self.server.call_tool(
            'leader_explain_and_navigate', workspace_id=self.wid,
            fva='0x401000',
        )
        self.assertFalse(result['ok'])
        self.assertIn('no active leader', result['error'])

    # -- validate_server_mode helpers ---------------------------------------

    def test_leader_tools_fail_on_local_workspace(self):
        """All leader/server tools check _validate_server_mode first."""
        open_result = self.server.call_tool(
            'workspace_open', path='/tmp/fake.bin',
        )
        self.assertTrue(open_result['ok'])
        wid = open_result['data']['workspace_id']

        for tool in ('leader_start', 'leader_list', 'leader_get_location',
                     'leader_end', 'server_list_workspaces'):
            r = self.server.call_tool(tool, workspace_id=wid)
            self.assertFalse(r['ok'], msg=f'{tool} should have failed')
            self.assertIn('not connected', r.get('error', ''), msg=f'{tool}')
        # leader_chat requires an extra message arg
        r_chat = self.server.call_tool('leader_chat', workspace_id=wid, message='hi')
        self.assertFalse(r_chat['ok'], msg='leader_chat should have failed')
        self.assertIn('not connected', r_chat.get('error', ''), msg='leader_chat')


class RegistryMetaConsistencyTests(unittest.TestCase):
    """Ensure every new server/leader tool has matching metadata & registry."""

    def test_registry_contains_server_and_leader_tools(self):
        from viv_ai.mcp.tools import build_default_registry

        registry = build_default_registry()

        for name in ('server_connect', 'server_disconnect',
                     'server_list_workspaces',
                     'leader_start', 'leader_navigate', 'leader_end',
                     'leader_list', 'leader_get_location', 'leader_chat',
                     'leader_explain_and_navigate'):
            self.assertIn(name, registry, msg=f'{name} missing from registry')

    def test_metadata_matches_registry_count(self):
        from viv_ai.mcp.tools import build_default_registry, build_tool_metadata

        registry = build_default_registry()
        metadata = build_tool_metadata()

        missing_meta = set(registry.keys()) - set(metadata.keys())
        missing_reg = set(metadata.keys()) - set(registry.keys())

        self.assertEqual(missing_meta, set(),
                         f'In registry but no metadata: {missing_meta}')
        self.assertEqual(missing_reg, set(),
                         f'In metadata but not registry: {missing_reg}')


if __name__ == '__main__':
    unittest.main()

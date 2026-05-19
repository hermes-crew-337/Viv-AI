import unittest


class FakeVW:
    def __init__(self):
        self.current_function = 0x401000
        self.graph_requests = []

    def getFunction(self, va):
        return 0x401000 if va in (0x401000, 0x401004) else None

    def getFunctionGraph(self, fva):
        self.graph_requests.append(fva)
        return {'graph_for': fva}


class FakeService:
    def __init__(self):
        self.calls = []

    def analyze_binary(self, vw, options=None):
        self.calls.append(('binary', dict(options or {})))
        return {
            'task_type': 'binary_summary',
            'cache_hit': False,
            'provider': {'type': 'ollama', 'model': 'qwen'},
            'analysis': {'summary': 'binary overview', 'confidence': 'high', 'evidence': ['ep 0x401000']},
        }

    def analyze_function(self, vw, fva, options=None):
        self.calls.append(('function', fva, dict(options or {})))
        return {
            'task_type': 'function_summary',
            'cache_hit': True,
            'provider': {'type': 'ollama', 'model': 'qwen'},
            'analysis': {
                'summary': 'function overview',
                'confidence': 'medium',
                'evidence': ['caller main'],
                'proposed_name': 'parse_input',
            },
        }

    def analyze_graph(self, graph, options=None):
        self.calls.append(('graph', graph, dict(options or {})))
        return {
            'task_type': 'graph_summary',
            'cache_hit': False,
            'provider': {'type': 'ollama', 'model': 'qwen'},
            'analysis': {'summary': 'dispatcher graph', 'confidence': 'medium', 'evidence': ['loop hub']},
        }


class WorkflowTests(unittest.TestCase):
    def test_panel_can_switch_scope_and_records_history_entries(self):
        from viv_ai.ui.widgets import AIHelperPanel

        vw = FakeVW()
        service = FakeService()
        panel = AIHelperPanel(vw, object(), service=service)

        panel.set_scope('binary')
        first = panel.run_current_analysis()
        panel.set_scope('function')
        second = panel.run_current_analysis()

        self.assertEqual(service.calls[0], ('binary', {}))
        self.assertEqual(service.calls[1], ('function', 0x401000, {}))
        self.assertEqual(first['analysis']['summary'], 'binary overview')
        self.assertEqual(second['analysis']['summary'], 'function overview')
        self.assertEqual(len(panel.history), 2)
        self.assertEqual(panel.history[0]['task_type'], 'binary_summary')
        self.assertTrue(panel.history[1]['cache_hit'])
        self.assertIn('cache hit', panel.history[1]['status'])

    def test_panel_can_run_graph_analysis_for_current_function(self):
        from viv_ai.ui.widgets import AIHelperPanel

        vw = FakeVW()
        service = FakeService()
        panel = AIHelperPanel(vw, object(), service=service)

        panel.set_scope('graph')
        result = panel.run_current_analysis(options={'max_nodes': 12})

        self.assertEqual(vw.graph_requests, [0x401000])
        self.assertEqual(service.calls, [('graph', {'graph_for': 0x401000}, {'max_nodes': 12})])
        self.assertEqual(result['task_type'], 'graph_summary')
        self.assertEqual(panel.last_result['analysis']['summary'], 'dispatcher graph')

    def test_panel_returns_structured_error_for_binary_scope_without_provider(self):
        from viv_ai.ui.widgets import AIHelperPanel

        panel = AIHelperPanel(FakeVW(), object())
        panel.set_scope('binary')

        result = panel.run_current_analysis()

        self.assertIn('error', result)
        self.assertEqual(result['task_type'], 'binary_summary')

    def test_panel_returns_structured_error_for_graph_scope_without_provider(self):
        from viv_ai.ui.widgets import AIHelperPanel

        panel = AIHelperPanel(FakeVW(), object())
        panel.set_scope('graph')

        result = panel.run_current_analysis()

        self.assertIn('error', result)
        self.assertEqual(result['task_type'], 'graph_summary')

    def test_review_panel_maintains_multi_item_queue_and_advances_after_apply(self):
        from viv_ai.models import MutationPolicy
        from viv_ai.ui.review import ReviewApplyPanel

        class ApplyVW:
            def __init__(self):
                self.names = {}
                self.comments = {}

            def makeName(self, va, name):
                self.names[va] = name
                return name

            def setComment(self, va, comment):
                self.comments[va] = comment

        vw = ApplyVW()
        panel = ReviewApplyPanel(vw, mutation_policy=MutationPolicy.DIRECT_APPLY_ENABLED)

        panel.stage_suggestions(0x401000, proposed_name='parse_input')
        panel.stage_suggestions(0x402000, proposed_comment='decrypt loop')

        queue = panel.preview_queue()
        first = panel.apply_current()

        self.assertEqual(len(queue), 2)
        self.assertEqual(queue[0]['va'], '0x00401000')
        self.assertTrue(first['applied'])
        self.assertEqual(vw.names[0x401000], 'parse_input')
        self.assertEqual(panel.current_target_va, 0x402000)
        self.assertEqual(panel.preview_actions()[0]['comment'], 'decrypt loop')

    def test_review_queue_skips_empty_suggestions(self):
        from viv_ai.models import MutationPolicy
        from viv_ai.ui.review import ReviewApplyPanel

        class ApplyVW:
            def makeName(self, va, name):
                return name

            def setComment(self, va, comment):
                return None

        panel = ReviewApplyPanel(ApplyVW(), mutation_policy=MutationPolicy.DIRECT_APPLY_ENABLED)
        panel.stage_suggestions(0x401000)
        panel.stage_suggestions(0x402000, proposed_comment='decrypt loop')

        self.assertEqual(panel.current_target_va, 0x402000)
        self.assertEqual(len(panel.preview_queue()), 1)

    def test_review_panel_apply_all_processes_entire_queue(self):
        from viv_ai.models import MutationPolicy
        from viv_ai.ui.review import ReviewApplyPanel

        class ApplyVW:
            def __init__(self):
                self.names = {}
                self.comments = {}

            def makeName(self, va, name):
                self.names[va] = name
                return name

            def setComment(self, va, comment):
                self.comments[va] = comment

        vw = ApplyVW()
        panel = ReviewApplyPanel(vw, mutation_policy=MutationPolicy.DIRECT_APPLY_ENABLED)
        panel.stage_suggestions(0x401000, proposed_name='parse_input')
        panel.stage_suggestions(0x402000, proposed_comment='decrypt loop')

        result = panel.apply_all()

        self.assertTrue(result['applied'])
        self.assertEqual(vw.names[0x401000], 'parse_input')
        self.assertEqual(vw.comments[0x402000], 'decrypt loop')
        self.assertIsNone(panel.current_target_va)
        self.assertEqual(panel.preview_queue(), [])

    def test_review_queue_does_not_drop_item_when_apply_is_blocked(self):
        from viv_ai.models import MutationPolicy
        from viv_ai.ui.review import ReviewApplyPanel

        class ApplyVW:
            def makeName(self, va, name):
                return name

            def setComment(self, va, comment):
                return None

        panel = ReviewApplyPanel(ApplyVW(), mutation_policy=MutationPolicy.REVIEW_BEFORE_APPLY)
        panel.stage_suggestions(0x401000, proposed_name='parse_input')
        panel.stage_suggestions(0x402000, proposed_comment='decrypt loop')

        result = panel.apply_current(approved=False)

        self.assertFalse(result['applied'])
        self.assertEqual(panel.current_target_va, 0x401000)
        self.assertEqual(len(panel.preview_queue()), 2)

    def test_settings_controller_can_apply_updates_from_ui_state(self):
        from viv_ai.config import AiConfig, ProviderConfig
        from viv_ai.models import MutationPolicy
        from viv_ai.ui.settings import SettingsController

        controller = SettingsController(AiConfig(
            default_provider='ollama',
            default_model='qwen',
            providers={
                'ollama': ProviderConfig(provider_type='ollama', model='qwen', endpoint='http://MATRIX:11434'),
                'openai': ProviderConfig(provider_type='openai_compat', model='gpt-4.1', endpoint='https://api.openai.test'),
            },
        ))

        updated = controller.apply_updates({
            'default_provider': 'openai',
            'mutation_policy': 'review_before_apply',
            'remote_providers_enabled': True,
        })

        self.assertEqual(updated.default_provider, 'openai')
        self.assertEqual(updated.mutation_policy, MutationPolicy.REVIEW_BEFORE_APPLY)
        self.assertTrue(updated.remote_providers_enabled)

    def test_settings_updates_propagate_to_bound_panel_state(self):
        from viv_ai.config import AiConfig, ProviderConfig
        from viv_ai.models import MutationPolicy
        from viv_ai.ui.settings import SettingsController
        from viv_ai.ui.widgets import AIHelperPanel

        config = AiConfig(
            default_provider='ollama',
            providers={
                'ollama': ProviderConfig(provider_type='ollama', model='qwen', endpoint='http://MATRIX:11434'),
                'openai': ProviderConfig(provider_type='openai_compat', model='gpt-4.1', endpoint='https://api.openai.test'),
            },
            mutation_policy=MutationPolicy.CONSERVATIVE_READONLY,
        )
        panel = AIHelperPanel(FakeVW(), object(), config=config)
        controller = SettingsController(config)
        controller.bind_panel(panel)

        controller.apply_updates({
            'default_provider': 'openai',
            'mutation_policy': 'direct_apply_enabled',
        })

        self.assertEqual(panel.config.default_provider, 'openai')
        self.assertEqual(panel.review_panel.mutation_policy, MutationPolicy.DIRECT_APPLY_ENABLED)


if __name__ == '__main__':
    unittest.main()

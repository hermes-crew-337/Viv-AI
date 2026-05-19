import pathlib
import tempfile
import unittest


class FakeVW:
    def __init__(self):
        self.names = {}
        self.comments = {}

    def makeName(self, va, name):
        self.names[va] = name
        return name

    def setComment(self, va, comment):
        self.comments[va] = comment


class ReviewAndSettingsTests(unittest.TestCase):
    def test_review_panel_requires_explicit_apply_in_review_mode(self):
        from viv_ai.models import MutationPolicy
        from viv_ai.ui.review import ReviewApplyPanel

        vw = FakeVW()
        panel = ReviewApplyPanel(vw, mutation_policy=MutationPolicy.REVIEW_BEFORE_APPLY)
        panel.stage_suggestions(0x401000, proposed_name='parse_input', proposed_comment='possible parser')

        preview = panel.preview_actions()
        result = panel.apply_all()

        self.assertEqual(len(preview), 2)
        self.assertFalse(result['applied'])
        self.assertEqual(vw.names, {})
        self.assertEqual(vw.comments, {})

    def test_review_panel_applies_staged_suggestions_in_direct_mode(self):
        from viv_ai.models import MutationPolicy
        from viv_ai.ui.review import ReviewApplyPanel

        vw = FakeVW()
        panel = ReviewApplyPanel(vw, mutation_policy=MutationPolicy.DIRECT_APPLY_ENABLED)
        panel.stage_suggestions(0x401000, proposed_name='parse_input', proposed_comment='possible parser')

        result = panel.apply_all()

        self.assertTrue(result['applied'])
        self.assertEqual(vw.names[0x401000], 'parse_input')
        self.assertEqual(vw.comments[0x401000], 'possible parser')

    def test_review_panel_can_apply_after_explicit_approval_in_review_mode(self):
        from viv_ai.models import MutationPolicy
        from viv_ai.ui.review import ReviewApplyPanel

        vw = FakeVW()
        panel = ReviewApplyPanel(vw, mutation_policy=MutationPolicy.REVIEW_BEFORE_APPLY)
        panel.stage_suggestions(0x401000, proposed_name='parse_input', proposed_comment='possible parser')

        result = panel.apply_all(approved=True)

        self.assertTrue(result['applied'])
        self.assertEqual(vw.names[0x401000], 'parse_input')
        self.assertEqual(vw.comments[0x401000], 'possible parser')

    def test_settings_controller_persists_non_secret_fields_only(self):
        from viv_ai.config import AiConfig, ProviderConfig
        from viv_ai.ui.settings import SettingsController

        cfg = AiConfig(
            default_provider='ollama',
            default_model='cas/llama-3.2-3b-instruct:latest',
            providers={
                'ollama': ProviderConfig(
                    provider_type='ollama',
                    model='cas/llama-3.2-3b-instruct:latest',
                    endpoint='http://MATRIX:11434',
                    api_key_env='OLLAMA_TOKEN',
                )
            },
        )
        controller = SettingsController(cfg)

        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / 'viv-ai.json'
            controller.save(path)
            text = path.read_text('utf-8')

        self.assertIn('default_provider', text)
        self.assertIn('OLLAMA_TOKEN', text)
        self.assertNotIn('supersecret', text)


if __name__ == '__main__':
    unittest.main()

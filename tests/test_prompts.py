import unittest

from viv_ai.prompts import ANALYSIS_SCHEMAS, build_task_prompt_bundle


class PromptTests(unittest.TestCase):
    def test_all_phase_b_schemas_include_evidence_and_confidence(self):
        for task_name in ('binary_summary', 'function_summary', 'graph_summary', 'symbolik_summary'):
            schema = ANALYSIS_SCHEMAS[task_name]
            props = schema['properties']
            self.assertIn('evidence', props)
            self.assertIn('confidence', props)
            self.assertIn('summary', props)

    def test_prompt_bundle_is_deterministic_and_mentions_bounded_scope(self):
        payload = {'function': {'va': '0x00401000', 'name': 'main'}}
        bundle = build_task_prompt_bundle('function_summary', payload)

        self.assertEqual(bundle['task_type'], 'function_summary')
        self.assertEqual(bundle['schema'], ANALYSIS_SCHEMAS['function_summary'])
        self.assertIn('bounded reverse-engineering context', bundle['system_prompt'])
        self.assertIn('facts separately from hypotheses', bundle['system_prompt'])
        self.assertEqual(bundle['user_payload'], payload)


if __name__ == '__main__':
    unittest.main()

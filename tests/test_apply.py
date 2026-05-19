import unittest


class FakeWorkspace:
    def __init__(self):
        self.calls = []
        self.rename_result = Ellipsis

    def makeName(self, va, name):
        self.calls.append(('makeName', va, name))
        if self.rename_result is not Ellipsis:
            return self.rename_result
        return name

    def setComment(self, va, comment):
        self.calls.append(('setComment', va, comment))


class ApplyTests(unittest.TestCase):
    def test_readonly_policy_blocks_function_rename(self):
        from viv_ai.apply import apply_function_rename
        from viv_ai.models import MutationPolicy

        vw = FakeWorkspace()
        result = apply_function_rename(vw, 0x401000, 'decrypt_payload', MutationPolicy.CONSERVATIVE_READONLY)

        self.assertFalse(result['applied'])
        self.assertEqual(vw.calls, [])
        self.assertIn('readonly', result['reason'])

    def test_review_policy_returns_proposal_without_mutating(self):
        from viv_ai.apply import apply_comment_suggestion
        from viv_ai.models import MutationPolicy

        vw = FakeWorkspace()
        result = apply_comment_suggestion(vw, 0x401000, 'possible parser dispatch', MutationPolicy.REVIEW_BEFORE_APPLY)

        self.assertFalse(result['applied'])
        self.assertEqual(vw.calls, [])
        self.assertEqual(result['proposal']['comment'], 'possible parser dispatch')

    def test_direct_apply_policy_performs_exact_mutation(self):
        from viv_ai.apply import apply_function_rename, apply_comment_suggestion
        from viv_ai.models import MutationPolicy

        vw = FakeWorkspace()
        rename = apply_function_rename(vw, 0x401000, 'decrypt_payload', MutationPolicy.DIRECT_APPLY_ENABLED)
        comment = apply_comment_suggestion(vw, 0x401000, 'possible parser dispatch', MutationPolicy.DIRECT_APPLY_ENABLED)

        self.assertTrue(rename['applied'])
        self.assertTrue(comment['applied'])
        self.assertEqual(vw.calls, [
            ('makeName', 0x401000, 'decrypt_payload'),
            ('setComment', 0x401000, 'possible parser dispatch'),
        ])

    def test_rename_apply_reports_failure_when_workspace_declines_name(self):
        from viv_ai.apply import apply_function_rename
        from viv_ai.models import MutationPolicy

        vw = FakeWorkspace()
        vw.rename_result = None
        result = apply_function_rename(vw, 0x401000, 'decrypt_payload', MutationPolicy.DIRECT_APPLY_ENABLED)

        self.assertFalse(result['applied'])
        self.assertIn('failed', result['reason'])

    def test_rename_apply_reports_failure_when_workspace_applies_different_name(self):
        from viv_ai.apply import apply_function_rename
        from viv_ai.models import MutationPolicy

        vw = FakeWorkspace()
        vw.rename_result = 'decrypt_payload_0'
        result = apply_function_rename(vw, 0x401000, 'decrypt_payload', MutationPolicy.DIRECT_APPLY_ENABLED)

        self.assertFalse(result['applied'])
        self.assertEqual(result['proposal']['applied_name'], 'decrypt_payload_0')
        self.assertIn('different', result['reason'])


if __name__ == '__main__':
    unittest.main()

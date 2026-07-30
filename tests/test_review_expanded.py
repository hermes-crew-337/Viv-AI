"""Tests for viv_ai/ui/review.py — full suite matching real API."""
from __future__ import annotations

from unittest.mock import MagicMock
import unittest


class TestReviewApplyPanelInit(unittest.TestCase):
    def test_init_default_policy(self):
        from viv_ai.ui.review import ReviewApplyPanel
        from viv_ai.models import MutationPolicy
        panel = ReviewApplyPanel(None)
        self.assertEqual(panel.mutation_policy, MutationPolicy.REVIEW_BEFORE_APPLY)

    def test_init_custom_policy(self):
        from viv_ai.ui.review import ReviewApplyPanel
        from viv_ai.models import MutationPolicy
        panel = ReviewApplyPanel(None, MutationPolicy.DIRECT_APPLY_ENABLED)
        self.assertEqual(panel.mutation_policy, MutationPolicy.DIRECT_APPLY_ENABLED)

    def test_init_sets_defaults(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        self.assertIsNone(panel.target_va)
        self.assertIsNone(panel.pending_name)
        self.assertIsNone(panel.pending_comment)
        self.assertEqual(panel._queue, [])

    def test_current_target_va_property(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        self.assertIsNone(panel.current_target_va)


class TestStageSuggestions(unittest.TestCase):
    def test_stage_both(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        panel.stage_suggestions(0x401000, proposed_name="main", proposed_comment="entry")
        self.assertEqual(len(panel._queue), 1)
        self.assertEqual(panel.target_va, 0x401000)
        self.assertEqual(panel.pending_name, "main")

    def test_stage_name_only(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        panel.stage_suggestions(0x401000, proposed_name="helper")
        self.assertEqual(panel.pending_name, "helper")
        self.assertIsNone(panel.pending_comment)

    def test_stage_comment_only(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        panel.stage_suggestions(0x401000, proposed_comment="note")
        self.assertEqual(panel.pending_comment, "note")
        self.assertIsNone(panel.pending_name)

    def test_stage_neither_skips(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        panel.stage_suggestions(0x401000)
        self.assertEqual(panel._queue, [])

    def test_stage_multiple(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        panel.stage_suggestions(0x401000, proposed_name="a")
        panel.stage_suggestions(0x401050, proposed_name="b")
        self.assertEqual(len(panel._queue), 2)

    def test_stage_loads_current_when_target_none(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        panel.stage_suggestions(0x401000, proposed_name="first")
        self.assertEqual(panel.target_va, 0x401000)


class TestPreview(unittest.TestCase):
    def test_preview_queue(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        panel.stage_suggestions(0x401000, proposed_name="main")
        preview = panel.preview_queue()
        self.assertEqual(len(preview), 1)
        self.assertTrue(preview[0]["has_name"])

    def test_preview_queue_empty(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        self.assertEqual(panel.preview_queue(), [])

    def test_preview_actions_with_both(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        panel.stage_suggestions(0x401000, proposed_name="main", proposed_comment="entry")
        actions = panel.preview_actions()
        self.assertEqual(len(actions), 2)

    def test_preview_actions_no_target(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        self.assertEqual(panel.preview_actions(), [])


class TestApply(unittest.TestCase):
    def test_apply_name_direct(self):
        """makeName must return the applied name for success."""
        from viv_ai.ui.review import ReviewApplyPanel
        from viv_ai.models import MutationPolicy
        vw = MagicMock()
        vw.makeName.return_value = "main"
        panel = ReviewApplyPanel(vw, MutationPolicy.DIRECT_APPLY_ENABLED)
        panel.stage_suggestions(0x401000, proposed_name="main")
        result = panel.apply_current(approved=True)
        self.assertTrue(result["applied"])

    def test_apply_comment_direct(self):
        from viv_ai.ui.review import ReviewApplyPanel
        from viv_ai.models import MutationPolicy
        vw = MagicMock()
        panel = ReviewApplyPanel(vw, MutationPolicy.DIRECT_APPLY_ENABLED)
        panel.stage_suggestions(0x401000, proposed_comment="my comment")
        result = panel.apply_current(approved=True)
        self.assertTrue(result["applied"])
        vw.setComment.assert_called_once_with(0x401000, "my comment")

    def test_apply_readonly_blocks(self):
        from viv_ai.ui.review import ReviewApplyPanel
        from viv_ai.models import MutationPolicy
        panel = ReviewApplyPanel(None, MutationPolicy.CONSERVATIVE_READONLY)
        panel.stage_suggestions(0x401000, proposed_name="main")
        result = panel.apply_current(approved=True)
        self.assertFalse(result["applied"])

    def test_apply_review_blocks(self):
        from viv_ai.ui.review import ReviewApplyPanel
        from viv_ai.models import MutationPolicy
        panel = ReviewApplyPanel(None, MutationPolicy.REVIEW_BEFORE_APPLY)
        panel.stage_suggestions(0x401000, proposed_name="main")
        result = panel.apply_current()
        self.assertFalse(result["applied"])

    def test_apply_review_with_approval(self):
        from viv_ai.ui.review import ReviewApplyPanel
        from viv_ai.models import MutationPolicy
        vw = MagicMock()
        vw.makeName.return_value = "main"
        panel = ReviewApplyPanel(vw, MutationPolicy.REVIEW_BEFORE_APPLY)
        panel.stage_suggestions(0x401000, proposed_name="main")
        result = panel.apply_current(approved=True)
        self.assertTrue(result["applied"])

    def test_apply_no_suggestions(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        result = panel.apply_current(approved=True)
        self.assertFalse(result["applied"])

    def test_apply_queues_next(self):
        from viv_ai.ui.review import ReviewApplyPanel
        from viv_ai.models import MutationPolicy
        vw = MagicMock()
        vw.makeName.return_value = "first"
        panel = ReviewApplyPanel(vw, MutationPolicy.DIRECT_APPLY_ENABLED)
        panel.stage_suggestions(0x401000, proposed_name="first")
        panel.stage_suggestions(0x401050, proposed_name="second")
        panel.apply_current(approved=True)
        self.assertEqual(panel.target_va, 0x401050)

    def test_apply_makeName_mismatch(self):
        """When makeName returns different name, apply fails."""
        from viv_ai.ui.review import ReviewApplyPanel
        from viv_ai.models import MutationPolicy
        vw = MagicMock()
        vw.makeName.return_value = "other"
        panel = ReviewApplyPanel(vw, MutationPolicy.DIRECT_APPLY_ENABLED)
        panel.stage_suggestions(0x401000, proposed_name="main")
        result = panel.apply_current(approved=True)
        self.assertFalse(result["applied"])

    def test_apply_makeName_falsy(self):
        """When makeName returns falsy, apply fails."""
        from viv_ai.ui.review import ReviewApplyPanel
        from viv_ai.models import MutationPolicy
        vw = MagicMock()
        vw.makeName.return_value = ""
        panel = ReviewApplyPanel(vw, MutationPolicy.DIRECT_APPLY_ENABLED)
        panel.stage_suggestions(0x401000, proposed_name="main")
        result = panel.apply_current(approved=True)
        self.assertFalse(result["applied"])


class TestApplyAll(unittest.TestCase):
    def test_apply_all_success(self):
        from viv_ai.ui.review import ReviewApplyPanel
        from viv_ai.models import MutationPolicy
        vw = MagicMock()
        vw.makeName.side_effect = ["a", "b"]
        panel = ReviewApplyPanel(vw, MutationPolicy.DIRECT_APPLY_ENABLED)
        panel.stage_suggestions(0x401000, proposed_name="a")
        panel.stage_suggestions(0x401050, proposed_name="b")
        result = panel.apply_all(approved=True)
        self.assertTrue(result["applied"])
        self.assertEqual(len(result["results"]), 2)

    def test_apply_all_empty(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        result = panel.apply_all(approved=True)
        self.assertFalse(result["applied"])

    def test_apply_all_stops_on_failure(self):
        from viv_ai.ui.review import ReviewApplyPanel
        from viv_ai.models import MutationPolicy
        vw = MagicMock()
        # First succeeds, second returns mismatched name
        vw.makeName.side_effect = ["good", "other"]
        panel = ReviewApplyPanel(vw, MutationPolicy.DIRECT_APPLY_ENABLED)
        panel.stage_suggestions(0x401000, proposed_name="good")
        panel.stage_suggestions(0x401050, proposed_name="bad")
        result = panel.apply_all(approved=True)
        self.assertFalse(result["applied"])


class TestSkip(unittest.TestCase):
    def test_skip_current(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        panel.stage_suggestions(0x401000, proposed_name="a")
        panel.stage_suggestions(0x401050, proposed_name="b")
        self.assertTrue(panel.skip_current())
        self.assertEqual(panel.target_va, 0x401050)

    def test_skip_empty(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        self.assertFalse(panel.skip_current())

    def test_skip_last(self):
        from viv_ai.ui.review import ReviewApplyPanel
        panel = ReviewApplyPanel(None)
        panel.stage_suggestions(0x401000, proposed_name="a")
        panel.skip_current()
        self.assertIsNone(panel.target_va)


if __name__ == "__main__":
    unittest.main()

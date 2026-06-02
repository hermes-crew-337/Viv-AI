"""Tests for viv_ai.symbolik — summarize_symbolik_paths with path data."""

import unittest


class SummarizeSymbolikPathsTests(unittest.TestCase):
    def test_empty_paths(self):
        from viv_ai.symbolik import summarize_symbolik_paths
        result = summarize_symbolik_paths([])
        self.assertEqual(result['paths'], [])
        self.assertEqual(result['path_count'], 0)
        self.assertEqual(result['truncated']['paths'], 0)

    def test_single_path(self):
        from viv_ai.symbolik import summarize_symbolik_paths
        paths = [{
            'path_id': 'P1',
            'constraints': [('eax', '>', '0')],
            'effects': [('ebx', '=', 'eax')],
            'return_relation': 'eax',
        }]
        result = summarize_symbolik_paths(paths)
        self.assertEqual(result['path_count'], 1)
        self.assertEqual(result['paths'][0]['path_id'], 'P1')
        self.assertEqual(len(result['paths'][0]['constraints']), 1)
        self.assertEqual(len(result['paths'][0]['effects']), 1)

    def test_truncation_of_paths(self):
        from viv_ai.symbolik import summarize_symbolik_paths
        paths = [{'path_id': f'P{i}'} for i in range(20)]
        result = summarize_symbolik_paths(paths, max_paths=5)
        self.assertEqual(result['path_count'], 20)
        self.assertEqual(len(result['paths']), 5)
        self.assertEqual(result['truncated']['paths'], 15)

    def test_truncation_of_constraints(self):
        from viv_ai.symbolik import summarize_symbolik_paths
        path = {'path_id': 'P1', 'constraints': list(range(20)), 'effects': []}
        result = summarize_symbolik_paths([path], max_paths=8, max_constraints=3)
        self.assertEqual(len(result['paths'][0]['constraints']), 3)
        self.assertEqual(result['paths'][0]['truncated']['constraints'], 17)

    def test_truncation_of_effects(self):
        from viv_ai.symbolik import summarize_symbolik_paths
        path = {'path_id': 'P1', 'constraints': [], 'effects': list(range(20))}
        result = summarize_symbolik_paths([path], max_paths=8, max_constraints=3, max_effects=4)
        self.assertEqual(len(result['paths'][0]['effects']), 4)
        self.assertEqual(result['paths'][0]['truncated']['effects'], 16)

    def test_multiple_paths(self):
        from viv_ai.symbolik import summarize_symbolik_paths
        paths = [
            {'path_id': 'P1', 'constraints': [('a', '==', '1')], 'effects': []},
            {'path_id': 'P2', 'constraints': [], 'effects': [('b', '=', 'a')]},
        ]
        result = summarize_symbolik_paths(paths)
        self.assertEqual(result['path_count'], 2)
        self.assertEqual(result['paths'][0]['path_id'], 'P1')
        self.assertEqual(result['paths'][1]['path_id'], 'P2')

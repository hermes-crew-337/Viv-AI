import unittest


class FakeVW:
    def __init__(self):
        self.current_function = 0x401000
        self.graph_requests = []

    def getFunctionGraph(self, fva):
        self.graph_requests.append(fva)
        return {'graph_for': fva}


class FakeAsyncService:
    def __init__(self):
        self.calls = []

    def analyze_function(self, vw, fva, options=None):
        self.calls.append(('function', fva, dict(options or {})))
        return {
            'task_type': 'function_summary',
            'cache_hit': False,
            'provider': {'type': 'ollama', 'model': 'qwen'},
            'analysis': {
                'summary': 'parse loop with file I/O',
                'confidence': 'medium',
                'evidence': ['calls ReadFile', 'loop on newline'],
                'proposed_name': 'parse_input',
                'proposed_comment': 'suspected parser entrypoint',
            },
        }

    def analyze_graph(self, graph, options=None):
        self.calls.append(('graph', graph, dict(options or {})))
        return {
            'task_type': 'graph_summary',
            'cache_hit': True,
            'provider': {'type': 'ollama', 'model': 'qwen'},
            'analysis': {
                'summary': 'graph dominated by dispatcher node',
                'confidence': 'high',
                'evidence': ['hub block 0x401050'],
            },
        }


class UiAsyncTests(unittest.TestCase):
    def test_background_job_runner_tracks_status_progress_and_result(self):
        from viv_ai.ui.jobs import BackgroundJobRunner

        runner = BackgroundJobRunner()
        progress = []

        job = runner.submit('function_summary', lambda update: (update(25, 'extracting'), update(90, 'waiting on provider'), {'task_type': 'function_summary', 'analysis': {'summary': 'ok'}})[-1])
        snapshot = runner.run_pending()[0]

        self.assertEqual(job.job_id, snapshot['job_id'])
        self.assertEqual(snapshot['status'], 'completed')
        self.assertEqual(snapshot['progress'], 90)
        self.assertEqual(snapshot['message'], 'waiting on provider')
        self.assertEqual(snapshot['result']['analysis']['summary'], 'ok')

    def test_background_job_runner_captures_failure(self):
        from viv_ai.ui.jobs import BackgroundJobRunner

        runner = BackgroundJobRunner()
        runner.submit('graph_summary', lambda update: (_ for _ in ()).throw(RuntimeError('boom')))

        snapshot = runner.run_pending()[0]

        self.assertEqual(snapshot['status'], 'failed')
        self.assertIn('boom', snapshot['error'])

    def test_panel_can_schedule_non_blocking_analysis_and_collect_rendered_result(self):
        from viv_ai.ui.widgets import AIHelperPanel

        vw = FakeVW()
        service = FakeAsyncService()
        panel = AIHelperPanel(vw, object(), service=service)

        panel.set_scope('graph')
        job = panel.schedule_current_analysis(options={'max_nodes': 8})
        updates = panel.run_pending_jobs()

        self.assertEqual(job.status, 'completed')
        self.assertEqual(service.calls, [('graph', {'graph_for': 0x401000}, {'max_nodes': 8})])
        self.assertEqual(updates[0]['status'], 'completed')
        self.assertIn('dispatcher node', panel.render_last_result())
        self.assertEqual(panel.job_history[-1]['task_type'], 'graph_summary')
        self.assertTrue(panel.job_history[-1]['cache_hit'])

    def test_panel_reports_failed_background_job_without_mutating_review_queue(self):
        from viv_ai.ui.widgets import AIHelperPanel
        from viv_ai.ui.jobs import BackgroundJobRunner

        class BrokenService:
            def analyze_function(self, vw, fva, options=None):
                raise RuntimeError('provider offline')

        panel = AIHelperPanel(FakeVW(), object(), service=BrokenService(), job_runner=BackgroundJobRunner())
        job = panel.schedule_current_analysis()
        updates = panel.run_pending_jobs()

        self.assertEqual(job.status, 'failed')
        self.assertIn('provider offline', updates[0]['error'])
        self.assertEqual(panel.review_panel.preview_queue(), [])
        self.assertIn('provider offline', panel.render_last_result())

    def test_function_job_preserves_target_va_if_selection_changes_before_completion(self):
        from viv_ai.ui.widgets import AIHelperPanel
        from viv_ai.ui.jobs import BackgroundJobRunner

        vw = FakeVW()
        service = FakeAsyncService()
        panel = AIHelperPanel(vw, object(), service=service, job_runner=BackgroundJobRunner())

        panel.set_scope('function')
        panel.schedule_current_analysis()
        vw.current_function = 0x402000
        panel.run_pending_jobs()

        self.assertEqual(panel.review_panel.current_target_va, 0x401000)
        self.assertEqual(panel.review_panel.pending_name, 'parse_input')


if __name__ == '__main__':
    unittest.main()

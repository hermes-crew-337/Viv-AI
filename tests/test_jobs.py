"""Tests for viv_ai.ui.jobs — BackgroundJob, RunnableJob, BackgroundJobRunner (headless/no-Qt)."""

import unittest
import time


class BackgroundJobTests(unittest.TestCase):
    def test_job_defaults(self):
        from viv_ai.ui.jobs import BackgroundJob
        job = BackgroundJob(
            job_id='test-1',
            task_type='fn_summary',
            fn=lambda update: {'result': 'ok'},
        )
        self.assertEqual(job.job_id, 'test-1')
        self.assertEqual(job.task_type, 'fn_summary')
        self.assertEqual(job.status, 'pending')
        self.assertEqual(job.progress, 0)
        self.assertEqual(job.message, 'queued')
        self.assertIsNone(job.result)
        self.assertIsNone(job.error)
        self.assertIsNone(job.metadata)

    def test_job_to_dict(self):
        from viv_ai.ui.jobs import BackgroundJob
        job = BackgroundJob('j1', 'test', lambda u: {}, metadata={'va': 0x401000})
        job.status = 'completed'
        job.result = {'summary': 'done'}
        d = job.to_dict()
        self.assertEqual(d['job_id'], 'j1')
        self.assertEqual(d['status'], 'completed')
        self.assertEqual(d['result'], {'summary': 'done'})
        self.assertEqual(d['metadata'], {'va': 0x401000})


class RunnableJobTests(unittest.TestCase):
    def test_run_executes_job_function(self):
        from viv_ai.ui.jobs import BackgroundJob, RunnableJob
        state = {'ran': False}

        def job_fn(update):
            state['ran'] = True
            return {'result': 42}

        job = BackgroundJob('r1', 'test', job_fn)
        runner = RunnableJob(job)
        runner.run()
        self.assertTrue(state['ran'])
        self.assertEqual(job.status, 'completed')
        self.assertEqual(job.result, {'result': 42})
        self.assertEqual(job.progress, 100)

    def test_run_handles_exception(self):
        from viv_ai.ui.jobs import BackgroundJob, RunnableJob

        def job_fn(update):
            raise ValueError('test error')

        job = BackgroundJob('r2', 'test', job_fn)
        runner = RunnableJob(job)
        runner.run()
        self.assertEqual(job.status, 'failed')
        self.assertIn('test error', job.error)

    def test_cancellation_before_run(self):
        from viv_ai.ui.jobs import BackgroundJob, RunnableJob
        state = {'ran': False}

        def job_fn(update):
            state['ran'] = True
            return {}

        job = BackgroundJob('r3', 'test', job_fn)
        runner = RunnableJob(job)
        runner.cancel()
        runner.run()
        self.assertFalse(state['ran'])
        self.assertEqual(job.status, 'cancelled')

    def test_cancellation_updates_message(self):
        from viv_ai.ui.jobs import BackgroundJob, RunnableJob

        def job_fn(update):
            return {'ok': True}

        job = BackgroundJob('r4', 'test', job_fn)
        runner = RunnableJob(job)
        runner.cancel()
        runner.run()
        self.assertEqual(job.message, 'cancelled')


class BackgroundJobRunnerTests(unittest.TestCase):
    def setUp(self):
        from viv_ai.ui.jobs import BackgroundJobRunner
        self.runner = BackgroundJobRunner()

    def test_submit_creates_pending_job(self):
        job = self.runner.submit('test', lambda u: {'result': 1})
        self.assertEqual(len(self.runner.jobs), 1)
        self.assertEqual(job.status, 'pending')
        self.assertEqual(job.task_type, 'test')

    def test_submit_with_metadata(self):
        job = self.runner.submit('test', lambda u: {}, metadata={'va': 0x401000})
        self.assertEqual(job.metadata, {'va': 0x401000})

    def test_pending_count(self):
        self.runner.submit('a', lambda u: {})
        self.runner.submit('b', lambda u: {})
        self.assertEqual(self.runner.pending_count(), 2)
        self.assertEqual(self.runner.running_count(), 0)

    def test_cancel_not_found(self):
        result = self.runner.cancel_job('nonexistent')
        self.assertFalse(result)

    def test_cancel_pending(self):
        job = self.runner.submit('test', lambda u: {})
        result = self.runner.cancel_job(job.job_id)
        self.assertTrue(result)
        self.assertEqual(job.status, 'cancelled')

    def test_run_pending_executes_all_pending(self):
        results = []

        def make_job_fn(val):
            def fn(update):
                update(50, 'processing')
                results.append(val)
                return {'val': val}
            return fn

        self.runner.submit('test', make_job_fn(1))
        self.runner.submit('test', make_job_fn(2))
        snapshots = self.runner.run_pending()

        self.assertEqual(len(snapshots), 2)
        self.assertEqual(results, [1, 2])
        self.assertEqual(snapshots[0]['status'], 'completed')
        self.assertEqual(snapshots[0]['result'], {'val': 1})

    def test_run_pending_with_progress_update(self):
        progress_updates = []

        def job_fn(update):
            update(10, 'starting')
            update(50, 'working')
            update(100, 'done')
            return {'ok': True}

        job = self.runner.submit('test', job_fn)
        snapshots = self.runner.run_pending()

        self.assertEqual(job.progress, 100)
        self.assertEqual(job.message, 'done')

    def test_run_pending_handles_exception(self):
        def job_fn(update):
            raise RuntimeError('boom')

        self.runner.submit('test', job_fn)
        snapshots = self.runner.run_pending()
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]['status'], 'failed')
        self.assertIn('boom', snapshots[0]['error'])

    def test_cancel_running_job_via_runnable(self):
        from viv_ai.ui.jobs import BackgroundJob, RunnableJob

        # Submit a job normally (no Qt, so it'll be pending)
        job = self.runner.submit('test', lambda u: {'ok': True})

        # When Qt is absent, submit doesn't start threads — cancel by job_id
        result = self.runner.cancel_job(job.job_id)
        self.assertTrue(result)
        self.assertEqual(job.status, 'cancelled')

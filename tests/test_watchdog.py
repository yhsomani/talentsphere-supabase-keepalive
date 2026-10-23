import datetime as dt
import io
import json
import unittest

from scripts.watchdog import main, recent_success

NOW = dt.datetime(2026, 10, 23, 12, tzinfo=dt.timezone.utc)
ENV = {
    "GITHUB_TOKEN": "sample-do-not-print",
    "GITHUB_REPOSITORY": "owner/repository",
    "WATCHDOG_MAX_AGE_HOURS": "18",
}


class Response:
    status = 200

    def __init__(self, runs):
        self.body = io.BytesIO(json.dumps({"workflow_runs": runs}).encode())

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, n=-1):
        return self.body.read(n)


def run(event, conclusion, hour):
    return {
        "event": event,
        "conclusion": conclusion,
        "updated_at": (NOW - dt.timedelta(hours=hour)).isoformat(),
    }


class WatchdogTests(unittest.TestCase):
    def test_recent_success(self):
        self.assertTrue(recent_success([run("schedule", "success", 7)], NOW, 18))

    def test_ignore_successful_ci_only_runs(self):
        self.assertFalse(recent_success([run("push", "success", 1)], NOW, 18))

    def test_old_scheduled_run_is_not_enough(self):
        self.assertFalse(recent_success([run("schedule", "success", 20)], NOW, 18))

    def test_failed_recent_run_is_not_enough(self):
        self.assertFalse(recent_success([run("workflow_dispatch", "failure", 1)], NOW, 18))

    def test_successful_manual_ping_counts(self):
        self.assertTrue(recent_success([run("workflow_dispatch", "success", 5)], NOW, 18))

    def test_future_timestamp_is_not_enough(self):
        self.assertFalse(recent_success([run("schedule", "success", -1)], NOW, 18))

    def test_exit_zero_on_success(self):
        self.assertEqual(main(ENV, lambda *a, **k: Response([run("schedule", "success", 7)]), NOW), 0)

    def test_exit_failure_on_no_recent_ping(self):
        self.assertEqual(main(ENV, lambda *a, **k: Response([run("push", "success", 1)]), NOW), 1)

    def test_missing_credentials(self):
        self.assertEqual(main({}, now=NOW), 2)


if __name__ == "__main__":
    unittest.main()

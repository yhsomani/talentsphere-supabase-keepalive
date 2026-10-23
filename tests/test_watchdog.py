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

    def __init__(self, payload):
        self.body = io.BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, n=-1):
        return self.body.read(n)


def run(event, conclusion, hour, branch="main"):
    return {
        "id": 123,
        "head_branch": branch,
        "event": event,
        "conclusion": conclusion,
        "updated_at": (NOW - dt.timedelta(hours=hour)).isoformat(),
    }


def opener_for(runs, job_result="success"):
    def opener(req, timeout=20):
        if "/jobs?" in req.full_url:
            return Response({"jobs": [{"name": "ping", "conclusion": job_result}]})
        return Response({"workflow_runs": runs})
    return opener


class WatchdogTests(unittest.TestCase):
    def test_recent_success(self):
        self.assertEqual(len(list(recent_success([run("schedule", "success", 7)], NOW, 18))), 1)

    def test_ignore_successful_ci_only_runs(self):
        self.assertEqual(list(recent_success([run("push", "success", 1)], NOW, 18)), [])

    def test_old_scheduled_run_is_not_enough(self):
        self.assertEqual(list(recent_success([run("schedule", "success", 20)], NOW, 18)), [])

    def test_failed_recent_run_is_not_enough(self):
        self.assertEqual(list(recent_success([run("workflow_dispatch", "failure", 1)], NOW, 18)), [])

    def test_successful_manual_ping_counts(self):
        self.assertEqual(len(list(recent_success([run("workflow_dispatch", "success", 5)], NOW, 18))), 1)

    def test_other_branch_does_not_count(self):
        self.assertEqual(list(recent_success([run("workflow_dispatch", "success", 1, "feature")], NOW, 18)), [])

    def test_future_timestamp_is_not_enough(self):
        self.assertEqual(list(recent_success([run("schedule", "success", -1)], NOW, 18)), [])

    def test_exit_zero_on_real_ping(self):
        self.assertEqual(main(ENV, opener_for([run("schedule", "success", 7)]), NOW), 0)

    def test_fails_if_ping_job_skipped(self):
        self.assertEqual(main(ENV, opener_for([run("schedule", "success", 7)], "skipped"), NOW), 1)

    def test_exit_failure_on_no_recent_ping(self):
        self.assertEqual(main(ENV, opener_for([run("push", "success", 1)]), NOW), 1)

    def test_missing_credentials(self):
        self.assertEqual(main({}, now=NOW), 2)


if __name__ == "__main__":
    unittest.main()

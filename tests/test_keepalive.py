import io
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest.mock import Mock

from scripts.keepalive import configuration, main, ping


ENV = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_test",
}


class Response:
    status = 200

    def __init__(self, body=b"1", status=200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body


class KeepaliveTests(unittest.TestCase):
    def test_success(self):
        opener = Mock(return_value=Response())
        self.assertEqual(main(ENV, opener=opener), 0)
        request = opener.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertTrue(request.full_url.endswith("/rest/v1/rpc/keepalive_ping"))
        self.assertNotIn("Authorization", request.headers)

    def test_wrong_response_is_failure(self):
        self.assertEqual(main(ENV, opener=lambda *a, **k: Response(b"{}")), 1)

    def test_non_200_is_failure(self):
        self.assertEqual(main(ENV, opener=lambda *a, **k: Response(status=201)), 1)

    def test_401_does_not_retry_or_expose_credentials(self):
        secret = "sb_publishable_do_not_log"
        env = {**ENV, "SUPABASE_PUBLISHABLE_KEY": secret}
        opener = Mock(side_effect=urllib.error.HTTPError("url", 401, "Unauthorized", {}, None))
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(env, opener=opener), 1)
        self.assertEqual(opener.call_count, 1)
        self.assertNotIn(secret, output.getvalue())

    def test_retry_transient_failure(self):
        opener = Mock(side_effect=[urllib.error.URLError("offline"), Response()])
        self.assertEqual(main(ENV, opener=opener, sleep=lambda _: None), 0)
        self.assertEqual(opener.call_count, 2)

    def test_missing_key(self):
        self.assertEqual(main({"SUPABASE_URL": ENV["SUPABASE_URL"]}), 2)

    def test_reject_insecure_url(self):
        with self.assertRaises(ValueError):
            configuration({**ENV, "SUPABASE_URL": "http://example.supabase.co"})

    def test_reject_secret_key(self):
        with self.assertRaises(ValueError):
            configuration({**ENV, "SUPABASE_PUBLISHABLE_KEY": "sb_secret_test"})

    def test_reject_rpc_path(self):
        with self.assertRaises(ValueError):
            configuration({**ENV, "KEEPALIVE_RPC": "../admin"})

    def test_url_trim(self):
        self.assertEqual(configuration({**ENV, "SUPABASE_URL": " https://example.supabase.co/ "})[0], ENV["SUPABASE_URL"])


if __name__ == "__main__":
    unittest.main()

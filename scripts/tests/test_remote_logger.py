"""
Unit tests for remote_logger module
Verifies non-blocking, fail-safe remote logging to Google Sheets Webhooks and Firebase.
"""

import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.common_stuff.remote_logger import (
    log_application_to_remote,
    _send_payload_sync,
    _send_http_post
)


class TestRemoteLogger(unittest.TestCase):

    def setUp(self):
        # Save env
        self.orig_env = dict(os.environ)

    def tearDown(self):
        # Restore env
        os.environ.clear()
        os.environ.update(self.orig_env)

    def test_log_without_env_config(self):
        """Test that logging with no env vars skips gracefully and returns False."""
        os.environ.pop("GOOGLE_SHEETS_WEBHOOK_URL", None)
        os.environ.pop("REMOTE_LOGGER_WEBHOOK_URL", None)
        os.environ.pop("FIREBASE_WEBHOOK_URL", None)
        os.environ.pop("FIREBASE_PROJECT_ID", None)

        res = log_application_to_remote(
            job_title="Software Engineer",
            company="Acme Corp",
            portal="Naukri",
            status="successful",
            questions_answered=2,
            async_exec=False
        )
        self.assertFalse(res)

    @patch("scripts.common_stuff.remote_logger._send_http_post")
    def test_google_sheets_webhook(self, mock_post):
        """Test logging to Google Sheets Webhook when URL is configured."""
        mock_post.return_value = True
        os.environ["GOOGLE_SHEETS_WEBHOOK_URL"] = "https://script.google.com/macros/s/test/exec"

        res = log_application_to_remote(
            job_title="Frontend Developer",
            company="Tech Inc",
            portal="LinkedIn",
            status="successful",
            questions_answered=5,
            async_exec=False
        )

        self.assertTrue(res)
        mock_post.assert_called_once()
        url_arg, payload_arg = mock_post.call_args[0]
        self.assertEqual(url_arg, "https://script.google.com/macros/s/test/exec")
        self.assertEqual(payload_arg["job_title"], "Frontend Developer")
        self.assertEqual(payload_arg["company"], "Tech Inc")
        self.assertEqual(payload_arg["portal"], "LinkedIn")
        self.assertEqual(payload_arg["status"], "successful")
        self.assertEqual(payload_arg["questions_answered"], 5)

    @patch("scripts.common_stuff.remote_logger._send_http_post")
    def test_firebase_firestore_rest_api(self, mock_post):
        """Test logging to Firebase Firestore REST API when project ID is set."""
        mock_post.return_value = True
        os.environ.pop("GOOGLE_SHEETS_WEBHOOK_URL", None)
        os.environ["FIREBASE_PROJECT_ID"] = "my-test-project"

        res = log_application_to_remote(
            job_title="Backend Developer",
            company="Cloud Ltd",
            portal="Instahyre",
            status="failed",
            questions_answered=0,
            async_exec=False
        )

        self.assertTrue(res)
        mock_post.assert_called_once()
        url_arg, payload_arg = mock_post.call_args[0]
        self.assertIn("my-test-project", url_arg)
        self.assertIn("job_applications", url_arg)
        self.assertEqual(payload_arg["fields"]["job_title"]["stringValue"], "Backend Developer")
        self.assertEqual(payload_arg["fields"]["company"]["stringValue"], "Cloud Ltd")
        self.assertEqual(payload_arg["fields"]["portal"]["stringValue"], "Instahyre")
        self.assertEqual(payload_arg["fields"]["status"]["stringValue"], "failed")

    @patch("scripts.common_stuff.remote_logger._send_http_post")
    def test_fail_safe_behavior_on_network_exception(self, mock_post):
        """Test that network failures never raise exceptions out of log_application_to_remote."""
        mock_post.side_effect = Exception("Network connection timeout")
        os.environ["GOOGLE_SHEETS_WEBHOOK_URL"] = "https://invalid-webhook.com"

        # Should NOT raise exception
        try:
            res = log_application_to_remote(
                job_title="Data Scientist",
                company="AI Labs",
                portal="Naukri",
                status="successful",
                async_exec=False
            )
            self.assertFalse(res)
        except Exception as e:
            self.fail(f"log_application_to_remote raised an exception: {e}")

    def test_async_daemon_thread_execution(self):
        """Test non-blocking async daemon thread execution mode."""
        os.environ["GOOGLE_SHEETS_WEBHOOK_URL"] = "https://script.google.com/macros/s/test/exec"

        with patch("scripts.common_stuff.remote_logger._send_payload_sync") as mock_sync:
            res = log_application_to_remote(
                job_title="DevOps Engineer",
                company="Ops Co",
                portal="LinkedIn",
                status="successful",
                async_exec=True
            )
            self.assertTrue(res)


if __name__ == "__main__":
    unittest.main()

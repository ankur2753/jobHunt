"""
Remote Logger Subsystem
Sends job application completion events to Google Sheets (via Webhook) or Firebase Firestore (fallback).

Design Requirements:
1. Non-Blocking & Fail-Safe: All network/logger operations are safely isolated. Network/logger failures
   NEVER raise exceptions or disrupt primary automation workflows.
2. Standard Library First: Uses urllib.request with fallback to requests if installed, avoiding heavy dependencies.
3. Primary Option: Google Sheets Webhook URL (GOOGLE_SHEETS_WEBHOOK_URL or REMOTE_LOGGER_WEBHOOK_URL).
4. Secondary Option: Firebase Firestore (FIREBASE_WEBHOOK_URL or FIREBASE_PROJECT_ID).

Google Apps Script Template Code (Paste into Google Sheets -> Extensions -> Apps Script):
---------------------------------------------------------------------------------------
function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(["Timestamp", "Job Title", "Company", "Portal", "Status", "Questions Answered"]);
      sheet.getRange(1, 1, 1, 6).setFontWeight("bold");
    }
    var data = {};
    if (e && e.postData && e.postData.contents) {
      data = JSON.parse(e.postData.contents);
    }
    var timestamp = data.timestamp || new Date().toISOString();
    var jobTitle = data.job_title || "Unknown Job";
    var company = data.company || data.company_name || "Unknown Company";
    var portal = data.portal || "Unknown Portal";
    var status = data.status || "UNKNOWN";
    var questionsAnswered = data.questions_answered !== undefined ? data.questions_answered : 0;
    
    sheet.appendRow([timestamp, jobTitle, company, portal, status, questionsAnswered]);
    return ContentService.createTextOutput(JSON.stringify({ "status": "success" }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ "status": "error", "message": err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
---------------------------------------------------------------------------------------
"""

import os
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

# Attempt loading .env if available
try:
    from dotenv import load_dotenv
    project_root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(project_root / ".env")
except ImportError:
    pass

logger = logging.getLogger(__name__)


def _send_http_post(url: str, payload: Dict[str, Any], timeout: float = 10.0) -> bool:
    """
    Send HTTP POST request with JSON payload.
    Tries `requests` library first if available, falls back to `urllib.request`.
    """
    json_bytes = json.dumps(payload).encode("utf-8")
    
    # Try requests module first if present
    try:
        import requests
        resp = requests.post(url, json=payload, timeout=timeout)
        if resp.status_code in (200, 201, 302):
            return True
        logger.warning(f"Remote logger POST to {url} returned HTTP status {resp.status_code}")
        return False
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Remote logger HTTP request via requests failed: {e}")
        return False

    # Fallback to standard library urllib.request
    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            url,
            data=json_bytes,
            headers={"Content-Type": "application/json", "User-Agent": "JobHuntAgent/1.0"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            if status_code in (200, 201, 302):
                return True
            logger.warning(f"Remote logger POST to {url} returned HTTP status {status_code}")
            return False
    except Exception as e:
        logger.warning(f"Remote logger HTTP request via urllib failed: {e}")
        return False


def _send_payload_sync(payload: Dict[str, Any]) -> bool:
    """
    Synchronously dispatches the payload to configured endpoints:
    1. Google Sheets Webhook URL (GOOGLE_SHEETS_WEBHOOK_URL or REMOTE_LOGGER_WEBHOOK_URL)
    2. Firebase Webhook / Firestore REST API (FIREBASE_WEBHOOK_URL or FIREBASE_PROJECT_ID)
    """
    sent_any = False
    
    # 1. Primary Option — Google Sheets Webhook
    gs_url = os.getenv("GOOGLE_SHEETS_WEBHOOK_URL") or os.getenv("REMOTE_LOGGER_WEBHOOK_URL")
    if gs_url and gs_url.strip():
        try:
            success = _send_http_post(gs_url.strip(), payload)
            if success:
                logger.info(f"Successfully logged application '{payload.get('job_title')}' to Google Sheets webhook.")
                sent_any = True
            else:
                logger.warning(f"Failed to log application '{payload.get('job_title')}' to Google Sheets webhook.")
        except Exception as e:
            logger.warning(f"Error logging to Google Sheets webhook: {e}")

    # 2. Secondary Option — Firebase Firestore
    fb_webhook_url = os.getenv("FIREBASE_WEBHOOK_URL")
    fb_project_id = os.getenv("FIREBASE_PROJECT_ID")
    
    if fb_webhook_url and fb_webhook_url.strip():
        try:
            success = _send_http_post(fb_webhook_url.strip(), payload)
            if success:
                logger.info(f"Successfully logged application '{payload.get('job_title')}' to Firebase Webhook.")
                sent_any = True
            else:
                logger.warning(f"Failed to log application '{payload.get('job_title')}' to Firebase Webhook.")
        except Exception as e:
            logger.warning(f"Error logging to Firebase Webhook: {e}")
    elif fb_project_id and fb_project_id.strip():
        try:
            # Firestore REST API endpoint
            firestore_url = (
                f"https://firestore.googleapis.com/v1/projects/{fb_project_id.strip()}/"
                f"databases/(default)/documents/job_applications"
            )
            firestore_payload = {
                "fields": {
                    "job_title": {"stringValue": str(payload.get("job_title", ""))},
                    "company": {"stringValue": str(payload.get("company", ""))},
                    "portal": {"stringValue": str(payload.get("portal", ""))},
                    "status": {"stringValue": str(payload.get("status", ""))},
                    "timestamp": {"stringValue": str(payload.get("timestamp", ""))},
                    "questions_answered": {"integerValue": int(payload.get("questions_answered", 0))},
                }
            }
            success = _send_http_post(firestore_url, firestore_payload)
            if success:
                logger.info(f"Successfully logged application '{payload.get('job_title')}' to Firebase Firestore REST API.")
                sent_any = True
            else:
                logger.warning(f"Failed to log application '{payload.get('job_title')}' to Firebase Firestore REST API.")
        except Exception as e:
            logger.warning(f"Error logging to Firestore REST API: {e}")

    if not (gs_url or fb_webhook_url or fb_project_id):
        logger.debug("No remote logger webhook URL configured in environment. Skipping remote log.")

    return sent_any


def log_application_to_remote(
    job_title: str,
    company: str,
    portal: str,
    status: str,
    questions_answered: int = 0,
    timestamp: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
    async_exec: bool = True
) -> bool:
    """
    Logs job application attempt to remote services (Google Sheets / Firebase).

    Args:
        job_title: Name of the position applied for.
        company: Name of the hiring company.
        portal: Application portal (e.g., 'Naukri', 'LinkedIn', 'Instahyre').
        status: Status string (e.g., 'successful', 'failed', 'partial', 'skipped').
        questions_answered: Number of form questions answered.
        timestamp: ISO format string timestamp. Defaults to current UTC time.
        extra_data: Optional dictionary with additional fields.
        async_exec: If True, executes network POST in a background daemon thread so it is non-blocking.

    Returns:
        bool: True if log dispatch was initiated (or succeeded), False on immediate configuration check or failure.
        NEVER raises an exception.
    """
    try:
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

        payload = {
            "job_title": str(job_title or "Unknown Job"),
            "company": str(company or "Unknown Company"),
            "portal": str(portal or "Unknown Portal"),
            "status": str(status or "UNKNOWN"),
            "timestamp": str(timestamp),
            "questions_answered": int(questions_answered or 0),
        }

        if extra_data and isinstance(extra_data, dict):
            payload.update(extra_data)

        if async_exec:
            thread = threading.Thread(
                target=_send_payload_sync,
                args=(payload,),
                daemon=True,
                name="RemoteLoggerThread"
            )
            thread.start()
            return True
        else:
            return _send_payload_sync(payload)

    except Exception as e:
        logger.warning(f"Fail-safe caught exception in remote_logger: {e}")
        return False


if __name__ == "__main__":
    import sys
    print("Testing remote_logger module...")
    test_result = log_application_to_remote(
        job_title="Senior AI Engineer",
        company="Antigravity Test Co",
        portal="TestPortal",
        status="successful",
        questions_answered=3,
        async_exec=False
    )
    print(f"Remote logger test complete. Result: {test_result}")

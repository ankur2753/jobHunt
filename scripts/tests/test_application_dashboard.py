import json
import csv
import shutil
import tempfile
import sys
from pathlib import Path
import pytest

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.common_stuff.application_dashboard import ApplicationDashboardWriter

def test_dashboard_writer():
    # Use a temporary directory for tests
    temp_dir = tempfile.mkdtemp()
    try:
        writer = ApplicationDashboardWriter(logs_dir=temp_dir)
        
        # Test mock data
        portal_name = "Naukri"
        summary = {
            "attempted": 2,
            "successful": 1,
            "failed": 1,
            "skipped": 0
        }
        applications = [
            {
                "company_name": "Test Company 1",
                "job_title": "Software Engineer",
                "job_url": "https://www.naukri.com/job-1",
                "status": "successful",
                "message": "Applied successfully"
            },
            {
                "company_name": "Test Company 2",
                "job_title": "Frontend Developer",
                "job_url": "https://www.naukri.com/job-2",
                "status": "failed",
                "message": "Form filler error"
            }
        ]
        
        # Write first run
        timestamp1 = "2026-07-18T12:00:00"
        writer.write_run(portal_name, summary, applications, run_timestamp=timestamp1)
        
        # Verify JSON
        assert writer.json_path.exists()
        with open(writer.json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            assert len(json_data) == 1
            entry = json_data[0]
            assert entry["run_timestamp"] == timestamp1
            assert entry["portal_name"] == portal_name
            assert entry["summary"]["attempted"] == 2
            assert entry["summary"]["successful"] == 1
            assert entry["summary"]["failed"] == 1
            assert entry["summary"]["skipped"] == 0
            assert len(entry["applications"]) == 2
            assert entry["applications"][0]["company_name"] == "Test Company 1"
            assert entry["applications"][0]["status"] == "successful"
            assert entry["applications"][1]["status"] == "failed"
            
        # Verify CSV
        assert writer.csv_path.exists()
        with open(writer.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            # 1 header row + 2 data rows
            assert len(rows) == 3
            # Check header
            assert rows[0] == [
                "run_timestamp", "portal_name", "company_name", "job_title", "job_url",
                "status", "message", "attempted", "successful", "failed", "skipped"
            ]
            # Check row 1
            assert rows[1] == [
                timestamp1, portal_name, "Test Company 1", "Software Engineer", "https://www.naukri.com/job-1",
                "successful", "Applied successfully", "2", "1", "1", "0"
            ]
            
        # Test appending a second run
        timestamp2 = "2026-07-18T13:00:00"
        summary2 = {
            "attempted": 1,
            "successful": 0,
            "failed": 0,
            "skipped": 1
        }
        applications2 = [
            {
                "company_name": "Test Company 3",
                "job_title": "Backend Developer",
                "job_url": "https://www.naukri.com/job-3",
                "status": "skipped",
                "message": "External redirect"
            }
        ]
        
        writer.write_run(portal_name, summary2, applications2, run_timestamp=timestamp2)
        
        # Verify JSON has both entries
        with open(writer.json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            assert len(json_data) == 2
            assert json_data[1]["run_timestamp"] == timestamp2
            assert json_data[1]["summary"]["skipped"] == 1
            assert json_data[1]["applications"][0]["company_name"] == "Test Company 3"
            
        # Verify CSV appended rows correctly
        with open(writer.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            # 1 header row + 2 rows from run 1 + 1 row from run 2 = 4 rows
            assert len(rows) == 4
            assert rows[3][0] == timestamp2
            assert rows[3][2] == "Test Company 3"
            assert rows[3][5] == "skipped"
            assert rows[3][7] == "1" # attempted
            assert rows[3][10] == "1" # skipped
            
    finally:
        shutil.rmtree(temp_dir)

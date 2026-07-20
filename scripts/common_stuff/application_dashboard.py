import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

class ApplicationDashboardWriter:
    """Logs job application runs to JSON and CSV dashboard files under logs/."""
    
    def __init__(self, logs_dir: str = "logs"):
        # Resolve path relative to project root or use absolute
        # Typically run from workspace root, but make sure it handles both
        self.logs_dir = Path(logs_dir).resolve()
        self.json_path = self.logs_dir / "applications_dashboard.json"
        self.csv_path = self.logs_dir / "applications_dashboard.csv"

    def _ensure_dir(self) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def write_run(
        self,
        portal_name: str,
        summary: Dict[str, int],
        applications: List[Dict[str, Any]],
        run_timestamp: Optional[str] = None
    ) -> None:
        """
        Write a single run's logs to JSON and CSV dashboard files.
        Appends to existing logs.
        """
        self._ensure_dir()
        if not run_timestamp:
            run_timestamp = datetime.now().isoformat()
            
        # 1. Update JSON
        self._update_json(run_timestamp, portal_name, summary, applications)
        
        # 2. Update CSV
        self._update_csv(run_timestamp, portal_name, summary, applications)

    def _update_json(
        self,
        run_timestamp: str,
        portal_name: str,
        summary: Dict[str, int],
        applications: List[Dict[str, Any]]
    ) -> None:
        data = []
        if self.json_path.exists():
            try:
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                    if not isinstance(data, list):
                        data = []
            except Exception:
                data = []
                
        new_entry = {
            "run_timestamp": run_timestamp,
            "portal_name": portal_name,
            "summary": {
                "attempted": summary.get("attempted", 0),
                "successful": summary.get("successful", 0),
                "failed": summary.get("failed", 0),
                "skipped": summary.get("skipped", 0)
            },
            "applications": [
                {
                    "company_name": app.get("company_name", ""),
                    "job_title": app.get("job_title", ""),
                    "job_url": app.get("job_url", ""),
                    "status": app.get("status", "failed"),
                    "message": app.get("message", "")
                }
                for app in applications
            ]
        }
        data.append(new_entry)
        
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _update_csv(
        self,
        run_timestamp: str,
        portal_name: str,
        summary: Dict[str, int],
        applications: List[Dict[str, Any]]
    ) -> None:
        headers = [
            "run_timestamp",
            "portal_name",
            "company_name",
            "job_title",
            "job_url",
            "status",
            "message",
            "attempted",
            "successful",
            "failed",
            "skipped"
        ]
        
        file_exists = self.csv_path.exists()
        
        with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(headers)
                
            attempted = summary.get("attempted", 0)
            successful = summary.get("successful", 0)
            failed = summary.get("failed", 0)
            skipped = summary.get("skipped", 0)
            
            if not applications:
                writer.writerow([
                    run_timestamp,
                    portal_name,
                    "",
                    "",
                    "",
                    "",
                    "No applications processed",
                    attempted,
                    successful,
                    failed,
                    skipped
                ])
            else:
                for app in applications:
                    writer.writerow([
                        run_timestamp,
                        portal_name,
                        app.get("company_name", ""),
                        app.get("job_title", ""),
                        app.get("job_url", ""),
                        app.get("status", ""),
                        app.get("message", ""),
                        attempted,
                        successful,
                        failed,
                        skipped
                    ])

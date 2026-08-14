"""
Unit tests for Orchestrator Configuration & JSON Error Handling
Ensures that orchestrator gracefully handles missing, empty, or malformed JSON files.
"""

import json
import pytest
from pathlib import Path
import tempfile
import shutil
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.orchestrator.orchestrator import safe_load_json, compute_review_mode


class TestOrchestratorConfig:
    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_safe_load_json_valid(self):
        file_path = self.temp_dir / "valid.json"
        file_path.write_text(json.dumps({"targetTitles": ["QA Engineer"]}), encoding="utf-8")

        data = safe_load_json(file_path)
        assert data.get("targetTitles") == ["QA Engineer"]

    def test_safe_load_json_empty_file_fallback(self):
        # Create empty file
        empty_file = self.temp_dir / "job_prefrences.json"
        empty_file.write_text("", encoding="utf-8")

        # Create example fallback in same dir
        example_file = self.temp_dir / "job_prefrences.example.json"
        example_file.write_text(json.dumps({"targetTitles": ["Fallback Title"]}), encoding="utf-8")

        data = safe_load_json(empty_file)
        assert data.get("targetTitles") == ["Fallback Title"]

    def test_safe_load_json_corrupt_json_fallback(self):
        corrupt_file = self.temp_dir / "user_details.json"
        corrupt_file.write_text("NOT_VALID_JSON{", encoding="utf-8")

        data = safe_load_json(corrupt_file, default={"name": "Default User"})
        assert data.get("name") == "Default User"

    def test_safe_load_json_missing_file_returns_default(self):
        missing_file = self.temp_dir / "non_existent.json"
        data = safe_load_json(missing_file, default={"key": "value"})
        assert data == {"key": "value"}

    def test_compute_review_mode(self):
        assert compute_review_mode("naukri") is False
        assert compute_review_mode("linkedin") is True


if __name__ == "__main__":
    pytest.main([__file__])

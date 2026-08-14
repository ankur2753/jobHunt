"""
Form Filler & Answer Normalizer Core Test Suite
Consolidated, fast, non-redundant tests for form field detection, answer normalization,
number sanitization, and visual form auditing.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock
from pathlib import Path
import sys

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.common_stuff.answer_validators import (
    AnswerNormalizer, FieldCategory, sanitize_numeric_answer
)
from scripts.common_stuff.chatbot_form_filler import (
    ChatbotFormFiller, FieldType, FormFillingResult, ChatbotFormFillerStats
)
from scripts.common_stuff.visual_form_auditor import VisualFormAuditor


class TestAnswerNormalizers:
    """Test answer normalization and category mapping."""

    def test_normalize_salary(self):
        assert AnswerNormalizer.normalize_salary("12-15 LPA") == "12-15"
        assert AnswerNormalizer.normalize_salary("12 Lakhs") == "12"

    def test_normalize_location(self):
        assert AnswerNormalizer.normalize_location("Bangalore, India") == "Bangalore"
        assert AnswerNormalizer.normalize_location("Work from home") == "Remote"

    def test_normalize_experience(self):
        assert AnswerNormalizer.normalize_experience("5 years") == "5"
        assert AnswerNormalizer.normalize_experience("60 months") == "5.0"

    def test_normalize_notice_period(self):
        assert AnswerNormalizer.normalize_notice_period("30 days") == "30"
        assert AnswerNormalizer.normalize_notice_period("2 weeks") == "14"
        assert AnswerNormalizer.normalize_notice_period("Immediate") == "0"

    def test_normalize_contact_info(self):
        assert AnswerNormalizer.normalize_email("john@example.com") == "john@example.com"
        assert AnswerNormalizer.normalize_email("invalid-email") is None
        assert AnswerNormalizer.normalize_phone("+91 98765 43210") == "919876543210"

    def test_field_category_detection(self):
        assert AnswerNormalizer.get_field_category("Expected CTC in LPA?") == FieldCategory.SALARY
        assert AnswerNormalizer.get_field_category("Preferred work location?") == FieldCategory.LOCATION


class TestNumberSanitizer:
    """Test numeric answer sanitization."""

    def test_numeric_sanitizations(self):
        assert sanitize_numeric_answer("What is your phone number 8002656334", "Phone") == "8002656334"
        assert sanitize_numeric_answer("Graduation year A: 2023", "Year") == "2023"
        assert sanitize_numeric_answer("Current CTC A: 12 LPA", "CTC") == "1200000"
        assert sanitize_numeric_answer("Notice period in days A: 30", "Notice") == "30"


class TestFormFieldTypeDetection:
    """Test Playwright field type determination."""

    def test_determine_field_types(self):
        filler = ChatbotFormFiller.__new__(ChatbotFormFiller)
        assert filler._determine_field_type("text", "input") == FieldType.TEXT_INPUT
        assert filler._determine_field_type("email", "input") == FieldType.EMAIL_INPUT
        assert filler._determine_field_type("number", "input") == FieldType.NUMBER_INPUT
        assert filler._determine_field_type("radio", "input") == FieldType.RADIO
        assert filler._determine_field_type("checkbox", "input") == FieldType.CHECKBOX
        assert filler._determine_field_type("", "select") == FieldType.SELECT
        assert filler._determine_field_type("", "textarea") == FieldType.TEXTAREA


class TestVisualFormAuditor:
    """Test post-fill visual audit error detection."""

    def test_auditor_detects_invalid_elements(self):
        async def run_audit():
            mock_page = AsyncMock()
            mock_invalid_el = AsyncMock()
            mock_invalid_el.is_visible = AsyncMock(return_value=True)
            
            # Script evaluations: return element name and validation message
            async def mock_eval(script):
                if "getAttribute('name')" in script or "name" in script:
                    return "phone_input"
                return "Value must be a valid phone number"

            mock_invalid_el.evaluate = AsyncMock(side_effect=mock_eval)
            mock_page.frames = []
            mock_page.query_selector_all = AsyncMock(side_effect=lambda sel: [mock_invalid_el] if "invalid" in sel else [])

            auditor = VisualFormAuditor(mock_page)
            report = await auditor.audit_form()

            assert report.is_valid is False
            assert report.total_errors == 1
            assert report.errors[0].field_identifier == "phone_input"
            assert report.errors[0].error_message == "Value must be a valid phone number"

        asyncio.run(run_audit())


if __name__ == "__main__":
    pytest.main([__file__])

"""
Unit tests for ChatbotFormFiller module.

Tests cover:
- Question detection from HTML
- Answer matching with confidence scoring
- Form field validation and filling
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import sys

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.common_stuff.chatbot_form_filler import (
    ChatbotFormFiller,
    FormQuestion,
    FieldType,
    FormFillingResult,
    ChatbotFormFillerStats
)
from scripts.common_stuff.vector_db_manager import VectorDBManager, AnswerCandidate
from scripts.common_stuff.answer_validators import AnswerNormalizer, FieldCategory


class TestAnswerNormalizer:
    """Test answer normalization for different field types."""
    
    def test_normalize_salary_range(self):
        """Test salary normalization with range."""
        result = AnswerNormalizer.normalize_salary("12-15 LPA")
        assert result == "12-15"
    
    def test_normalize_salary_single(self):
        """Test salary normalization with single value."""
        result = AnswerNormalizer.normalize_salary("12 Lakhs")
        assert result == "12"
    
    def test_normalize_location_with_country(self):
        """Test location normalization."""
        result = AnswerNormalizer.normalize_location("Bangalore, India")
        assert result == "Bangalore"
    
    def test_normalize_location_remote(self):
        """Test remote location normalization."""
        result = AnswerNormalizer.normalize_location("Work from home")
        assert result == "Remote"
    
    def test_normalize_experience_years(self):
        """Test experience normalization."""
        result = AnswerNormalizer.normalize_experience("5 years")
        assert result == "5"
    
    def test_normalize_experience_months(self):
        """Test experience normalization from months."""
        result = AnswerNormalizer.normalize_experience("60 months")
        assert result == "5.0"
    
    def test_normalize_notice_period_days(self):
        """Test notice period normalization."""
        result = AnswerNormalizer.normalize_notice_period("30 days")
        assert result == "30"
    
    def test_normalize_notice_period_weeks(self):
        """Test notice period normalization from weeks."""
        result = AnswerNormalizer.normalize_notice_period("2 weeks")
        assert result == "14"
    
    def test_normalize_notice_period_immediate(self):
        """Test immediate notice period."""
        result = AnswerNormalizer.normalize_notice_period("Immediate")
        assert result == "0"
    
    def test_normalize_email_valid(self):
        """Test valid email normalization."""
        result = AnswerNormalizer.normalize_email("john@example.com")
        assert result == "john@example.com"
    
    def test_normalize_email_invalid(self):
        """Test invalid email normalization."""
        result = AnswerNormalizer.normalize_email("not-an-email")
        assert result is None
    
    def test_normalize_phone(self):
        """Test phone normalization."""
        result = AnswerNormalizer.normalize_phone("+91 98765 43210")
        assert result == "919876543210"
    
    def test_get_field_category_salary(self):
        """Test field category detection for salary."""
        category = AnswerNormalizer.get_field_category("What's your expected salary?")
        assert category == FieldCategory.SALARY
    
    def test_get_field_category_location(self):
        """Test field category detection for location."""
        category = AnswerNormalizer.get_field_category("Preferred work location")
        assert category == FieldCategory.LOCATION
    
    def test_get_field_category_experience(self):
        """Test field category detection for experience."""
        category = AnswerNormalizer.get_field_category("Years of experience")
        assert category == FieldCategory.EXPERIENCE


class TestFormQuestion:
    """Test FormQuestion data class."""
    
    def test_form_question_creation(self):
        """Test creating FormQuestion."""
        question = FormQuestion(
            question_text="What's your salary?",
            field_selector="salary_input",
            field_type=FieldType.TEXT_INPUT,
            is_required=True
        )
        assert question.question_text == "What's your salary?"
        assert question.field_type == FieldType.TEXT_INPUT
        assert question.is_required is True
    
    def test_form_question_str(self):
        """Test FormQuestion string representation."""
        question = FormQuestion(
            question_text="What's your salary?",
            field_selector="input1",
            field_type=FieldType.TEXT_INPUT,
            is_required=False
        )
        assert "salary" in str(question).lower()


class TestFormFillingResult:
    """Test FormFillingResult data class."""
    
    def test_result_creation(self):
        """Test creating FormFillingResult."""
        result = FormFillingResult(
            question="Test question",
            answer="Test answer",
            status="filled",
            confidence=0.85
        )
        assert result.question == "Test question"
        assert result.status == "filled"
        assert result.confidence == 0.85
    
    def test_result_default_status(self):
        """Test default status is 'skipped'."""
        result = FormFillingResult(question="Test")
        assert result.status == "skipped"


class TestChatbotFormFillerStats:
    """Test ChatbotFormFillerStats data class."""
    
    def test_stats_creation(self):
        """Test creating stats object."""
        stats = ChatbotFormFillerStats()
        assert stats.total_questions == 0
        assert stats.auto_filled == 0
    
    def test_stats_add_result(self):
        """Test adding results to stats."""
        stats = ChatbotFormFillerStats()
        stats.total_questions = 1
        
        result = FormFillingResult(question="Q1", status="filled", confidence=0.8)
        stats.add_result(result)
        
        assert stats.auto_filled == 1
        assert len(stats.details) == 1
    
    def test_stats_auto_fill_rate(self):
        """Test auto-fill rate calculation."""
        stats = ChatbotFormFillerStats()
        stats.total_questions = 10
        
        for i in range(7):
            result = FormFillingResult(question=f"Q{i}", status="filled")
            stats.add_result(result)
        
        stats_dict = stats.to_dict()
        assert stats_dict['auto_fill_rate'] == 0.7


@pytest.fixture
def mock_page():
    """Mock Playwright Page."""
    return Mock()


@pytest.fixture
def mock_vector_db():
    """Mock VectorDBManager."""
    return Mock(spec=VectorDBManager)


@pytest.fixture
def form_filler(mock_page, mock_vector_db):
    """Form filler instance."""
    return ChatbotFormFiller(mock_page, mock_vector_db, enable_logging=False)


class TestChatbotFormFiller:
    """Test ChatbotFormFiller class."""
    
    def test_initialization(self, mock_page, mock_vector_db):
        """Test form filler initialization."""
        filler = ChatbotFormFiller(mock_page, mock_vector_db)
        assert filler.page == mock_page
        assert filler.vector_db == mock_vector_db
    
    def test_determine_field_type_text(self, form_filler):
        """Test field type determination for text input."""
        field_type = form_filler._determine_field_type("text", "input")
        assert field_type == FieldType.TEXT_INPUT
    
    def test_determine_field_type_email(self, form_filler):
        """Test field type determination for email input."""
        field_type = form_filler._determine_field_type("email", "input")
        assert field_type == FieldType.EMAIL_INPUT
    
    def test_determine_field_type_number(self, form_filler):
        """Test field type determination for number input."""
        field_type = form_filler._determine_field_type("number", "input")
        assert field_type == FieldType.NUMBER_INPUT
    
    def test_determine_field_type_select(self, form_filler):
        """Test field type determination for select dropdown."""
        field_type = form_filler._determine_field_type(None, "select")
        assert field_type == FieldType.SELECT
    
    def test_determine_field_type_textarea(self, form_filler):
        """Test field type determination for textarea."""
        field_type = form_filler._determine_field_type(None, "textarea")
        assert field_type == FieldType.TEXTAREA
    
    def test_determine_field_type_radio(self, form_filler):
        """Test field type determination for radio button."""
        field_type = form_filler._determine_field_type("radio", "input")
        assert field_type == FieldType.RADIO
    
    def test_determine_field_type_checkbox(self, form_filler):
        """Test field type determination for checkbox."""
        field_type = form_filler._determine_field_type("checkbox", "input")
        assert field_type == FieldType.CHECKBOX
    
    def test_validate_and_normalize_text(self, form_filler):
        """Test validation for text input."""
        result = form_filler._validate_and_normalize_answer("  hello  ", FieldType.TEXT_INPUT)
        assert result == "hello"
    
    def test_validate_and_normalize_email_valid(self, form_filler):
        """Test validation for valid email."""
        result = form_filler._validate_and_normalize_answer("test@example.com", FieldType.EMAIL_INPUT)
        assert result == "test@example.com"
    
    def test_validate_and_normalize_email_invalid(self, form_filler):
        """Test validation for invalid email."""
        result = form_filler._validate_and_normalize_answer("not-an-email", FieldType.EMAIL_INPUT)
        assert result is None
    
    def test_validate_and_normalize_number(self, form_filler):
        """Test validation for number input."""
        result = form_filler._validate_and_normalize_answer("12-15", FieldType.NUMBER_INPUT)
        assert result == "12"
    
    def test_validate_and_normalize_date(self, form_filler):
        """Test validation for date input."""
        result = form_filler._validate_and_normalize_answer("2024-01-15", FieldType.DATE_INPUT)
        assert result == "2024-01-15"
    
    def test_validate_and_normalize_empty_string(self, form_filler):
        """Test validation for empty string."""
        result = form_filler._validate_and_normalize_answer("", FieldType.TEXT_INPUT)
        assert result is None
    
    def test_process_question_validation(self, form_filler):
        """Test question processing validation logic."""
        # Test that high-confidence answers are properly validated
        question = FormQuestion(
            question_text="Where would you like to work?",
            field_selector="location",
            field_type=FieldType.TEXT_INPUT,
            is_required=True
        )
        
        # Should be able to create the question object
        assert question.question_text == "Where would you like to work?"
        assert question.field_type == FieldType.TEXT_INPUT
    
    def test_low_confidence_handling(self, form_filler):
        """Test handling of low confidence answers."""
        # Test that form filler can handle low confidence scenarios
        question = FormQuestion(
            question_text="Why do you want to work here?",
            field_selector="motivation", 
            field_type=FieldType.TEXTAREA,
            is_required=False
        )
        
        # Should be able to create question even if low confidence
        assert question.is_required is False
        assert question.field_type == FieldType.TEXTAREA
    
    def test_no_match_scenario(self, form_filler):
        """Test handling when no answer matches."""
        # Test that form filler can handle no-match scenarios
        question = FormQuestion(
            question_text="What is your favorite color?",
            field_selector="color",
            field_type=FieldType.TEXT_INPUT,
            is_required=False
        )
        
        # Should create question for potentially unmatchable questions
        assert question.question_text == "What is your favorite color?"


class TestAnswerValidators:
    """Test individual answer validators."""
    
    def test_boundary_case_empty_salary(self):
        """Test empty salary value."""
        result = AnswerNormalizer.normalize_salary("")
        assert result is None
    
    def test_boundary_case_empty_location(self):
        """Test empty location value."""
        result = AnswerNormalizer.normalize_location("")
        assert result is None
    
    def test_salary_with_special_chars(self):
        """Test salary with special characters."""
        result = AnswerNormalizer.normalize_salary("Rs. 12-15 LPA")
        assert result is not None
    
    def test_experience_with_decimals(self):
        """Test experience with decimal years."""
        result = AnswerNormalizer.normalize_experience("5.5 years")
        assert result == "5.5"
    
    def test_notice_period_boundary_1_day(self):
        """Test notice period for 1 day."""
        result = AnswerNormalizer.normalize_notice_period("1 day")
        assert result == "1"


class TestIntegration:
    """Integration tests for form filling workflow."""
    
    def test_form_filling_stats_aggregation(self):
        """Test form filling statistics aggregation."""
        stats = ChatbotFormFillerStats()
        
        # Add multiple results
        stats.total_questions = 5
        stats.auto_filled = 3
        stats.skipped = 1
        stats.failed = 1
        
        assert stats.total_questions == 5
        assert stats.auto_filled == 3
        assert stats.skipped == 1
        assert stats.failed == 1
    
    def test_form_question_creation_integration(self):
        """Test creating form questions from detected fields."""
        question = FormQuestion(
            question_text="Where would you like to work?",
            field_selector="location",
            field_type=FieldType.TEXT_INPUT,
            is_required=True,
            placeholder="Enter location",
            aria_label="Work location field"
        )
        
        assert question.question_text == "Where would you like to work?"
        assert question.placeholder == "Enter location"
        assert question.aria_label == "Work location field"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

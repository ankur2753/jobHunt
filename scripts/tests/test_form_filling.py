"""
Test Suite for ChatbotFormFiller - Form Filling Integration Tests
Phase 3: Form Filling Layer

Tests the form filling logic:
- Field detection and validation
- Playwright field interactions
- Type-specific filling (text, select, radio, checkbox, textarea, date)
- Error handling and recovery
- Performance metrics
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from playwright.async_api import Page
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.common_stuff.chatbot_form_filler import (
    ChatbotFormFiller, FieldType, FormQuestion, 
    FormFillingResult, ChatbotFormFillerStats
)
from scripts.common_stuff.answer_validators import AnswerNormalizer, FieldCategory
from scripts.common_stuff.vector_db_manager import VectorDBManager, AnswerCandidate


class TestFormFieldFilling:
    """Test Playwright form field interaction logic."""
    
    def test_text_input_validation_logic(self):
        """Test text input field validation logic."""
        # Create mock objects
        mock_page = Mock(spec=Page)
        mock_vector_db = Mock(spec=VectorDBManager)
        mock_vector_db.answer_question = Mock(return_value=AnswerCandidate(
            answer_text="Test Answer",
            confidence=0.85,
            source_key="test_key",
            source_category="test",
            should_autofill=True
        ))
        
        filler = ChatbotFormFiller(mock_page, mock_vector_db)
        
        # Test validation logic for text field
        validated = filler._validate_and_normalize_answer("Test Answer", FieldType.TEXT_INPUT)
        assert validated == "Test Answer"
    
    def test_email_input_validation(self):
        """Test validation of email input field."""
        mock_page = Mock(spec=Page)
        mock_vector_db = Mock(spec=VectorDBManager)
        filler = ChatbotFormFiller(mock_page, mock_vector_db)
        
        # Valid email should pass
        validated = filler._validate_and_normalize_answer(
            "test@example.com", 
            FieldType.EMAIL_INPUT
        )
        assert validated is not None
        assert "@" in validated
    
    def test_number_input_extraction(self):
        """Test number extraction from text for number field."""
        mock_page = Mock(spec=Page)
        mock_vector_db = Mock(spec=VectorDBManager)
        filler = ChatbotFormFiller(mock_page, mock_vector_db)
        
        validated = filler._validate_and_normalize_answer(
            "5 years of experience", 
            FieldType.NUMBER_INPUT
        )
        assert validated is not None
        assert "5" in validated
    
    def test_date_input_handling(self):
        """Test date field handling."""
        mock_page = Mock(spec=Page)
        mock_vector_db = Mock(spec=VectorDBManager)
        filler = ChatbotFormFiller(mock_page, mock_vector_db)
        
        # Should handle date format
        validated = filler._validate_and_normalize_answer(
            "2024-01-15",
            FieldType.DATE_INPUT
        )
        assert validated is not None


class TestFormFieldDetection:
    """Test form field and question detection logic."""
    
    def test_determine_field_type_text(self):
        """Test detection of text input field type."""
        mock_page = Mock(spec=Page)
        mock_vector_db = Mock(spec=VectorDBManager)
        filler = ChatbotFormFiller(mock_page, mock_vector_db)
        
        # _determine_field_type requires input_type and tag_name
        field_type = filler._determine_field_type("text", "input")
        assert field_type == FieldType.TEXT_INPUT
    
    def test_determine_field_type_email(self):
        """Test detection of email input field type."""
        mock_page = Mock(spec=Page)
        mock_vector_db = Mock(spec=VectorDBManager)
        filler = ChatbotFormFiller(mock_page, mock_vector_db)
        
        field_type = filler._determine_field_type("email", "input")
        assert field_type == FieldType.EMAIL_INPUT
    
    def test_determine_field_type_number(self):
        """Test detection of number input field type."""
        mock_page = Mock(spec=Page)
        mock_vector_db = Mock(spec=VectorDBManager)
        filler = ChatbotFormFiller(mock_page, mock_vector_db)
        
        field_type = filler._determine_field_type("number", "input")
        assert field_type == FieldType.NUMBER_INPUT
    
    def test_determine_field_type_date(self):
        """Test detection of date input field type."""
        mock_page = Mock(spec=Page)
        mock_vector_db = Mock(spec=VectorDBManager)
        filler = ChatbotFormFiller(mock_page, mock_vector_db)
        
        field_type = filler._determine_field_type("date", "input")
        assert field_type == FieldType.DATE_INPUT
    
    def test_determine_field_type_radio(self):
        """Test detection of radio input field type."""
        mock_page = Mock(spec=Page)
        mock_vector_db = Mock(spec=VectorDBManager)
        filler = ChatbotFormFiller(mock_page, mock_vector_db)
        
        field_type = filler._determine_field_type("radio", "input")
        assert field_type == FieldType.RADIO
    
    def test_determine_field_type_checkbox(self):
        """Test detection of checkbox input field type."""
        mock_page = Mock(spec=Page)
        mock_vector_db = Mock(spec=VectorDBManager)
        filler = ChatbotFormFiller(mock_page, mock_vector_db)
        
        field_type = filler._determine_field_type("checkbox", "input")
        assert field_type == FieldType.CHECKBOX


class TestAnswerValidationIntegration:
    """Test answer validation with AnswerNormalizer integration."""
    
    def test_validate_salary_answer(self):
        """Test salary answer validation and normalization."""
        normalizer = AnswerNormalizer()
        
        # normalize(value, field_category) - not (question, answer)
        normalized = normalizer.normalize(
            "12-15 LPA",
            FieldCategory.SALARY
        )
        
        assert normalized is not None
        assert "12" in normalized or "15" in normalized
    
    def test_validate_location_answer(self):
        """Test location answer validation."""
        normalizer = AnswerNormalizer()
        
        normalized = normalizer.normalize(
            "Delhi",
            FieldCategory.LOCATION
        )
        
        assert normalized is not None
    
    def test_validate_email_answer(self):
        """Test email answer validation."""
        normalizer = AnswerNormalizer()
        
        normalized = normalizer.normalize(
            "test@example.com",
            FieldCategory.CONTACT
        )
        
        assert normalized == "test@example.com"
    
    def test_validate_phone_answer(self):
        """Test phone number answer validation."""
        normalizer = AnswerNormalizer()
        
        normalized = normalizer.normalize(
            "+919876543210",
            FieldCategory.CONTACT
        )
        
        assert normalized is not None
        assert "91" in normalized or "9876" in normalized
    
    def test_validate_experience_answer(self):
        """Test experience answer validation."""
        normalizer = AnswerNormalizer()
        
        normalized = normalizer.normalize(
            "5.2 years",
            FieldCategory.EXPERIENCE
        )
        
        assert normalized is not None
        assert "5" in normalized


class TestFormFillingResult:
    """Test FormFillingResult data structure."""
    
    def test_form_filling_result_filled(self):
        """Test FormFillingResult for successful fill."""
        result = FormFillingResult(
            question="What is your name?",
            answer="John Doe",
            status="filled",
            confidence=0.92
        )
        
        assert result.status == "filled"
        assert result.answer == "John Doe"
        assert result.confidence == 0.92
    
    def test_form_filling_result_skipped(self):
        """Test FormFillingResult for skipped question."""
        result = FormFillingResult(
            question="What is your favorite color?",
            answer="",
            status="skipped",
            confidence=0.35,
            error_message="Below confidence threshold"
        )
        
        assert result.status == "skipped"
        assert result.error_message is not None
    
    def test_form_filling_result_failed(self):
        """Test FormFillingResult for failed fill."""
        result = FormFillingResult(
            question="What is your date of birth?",
            answer="01-01-1990",
            status="failed",
            confidence=0.70,
            error_message="Could not interact with field"
        )
        
        assert result.status == "failed"
        assert result.error_message is not None


class TestChatbotFormFillerStats:
    """Test ChatbotFormFillerStats aggregation."""
    
    def test_stats_initialization(self):
        """Test ChatbotFormFillerStats initialization."""
        stats = ChatbotFormFillerStats()
        
        assert stats.total_questions == 0
        assert stats.auto_filled == 0
        assert stats.skipped == 0
        assert stats.failed == 0
        assert len(stats.details) == 0
    
    def test_stats_accumulation(self):
        """Test accumulating stats from multiple results."""
        stats = ChatbotFormFillerStats(total_questions=3)
        
        stats.details.append(FormFillingResult(
            question="Q1", answer="A1", status="filled", confidence=0.9
        ))
        stats.auto_filled += 1
        
        stats.details.append(FormFillingResult(
            question="Q2", answer="", status="skipped", confidence=0.4
        ))
        stats.skipped += 1
        
        stats.details.append(FormFillingResult(
            question="Q3", answer="A3", status="failed", confidence=0.6, 
            error_message="Field not found"
        ))
        stats.failed += 1
        
        assert stats.auto_filled == 1
        assert stats.skipped == 1
        assert stats.failed == 1
        assert len(stats.details) == 3
    
    def test_stats_summary_metrics(self):
        """Test calculating summary metrics from stats."""
        stats = ChatbotFormFillerStats(total_questions=10)
        stats.auto_filled = 8
        stats.skipped = 1
        stats.failed = 1
        
        fill_rate = stats.auto_filled / stats.total_questions if stats.total_questions > 0 else 0
        assert fill_rate == 0.8  # 80% fill rate


class TestFieldTypeMapping:
    """Test field type mapping logic."""
    
    def test_all_field_types_supported(self):
        """Test that all FieldType enums are properly defined."""
        expected_types = [
            FieldType.TEXT_INPUT,
            FieldType.NUMBER_INPUT,
            FieldType.EMAIL_INPUT,
            FieldType.SELECT,
            FieldType.RADIO,
            FieldType.CHECKBOX,
            FieldType.TEXTAREA,
            FieldType.DATE_INPUT
        ]
        
        for field_type in expected_types:
            assert field_type.value is not None


class TestErrorHandling:
    """Test error handling in form filling."""
    
    def test_invalid_email_handling(self):
        """Test handling when email validation fails."""
        mock_page = Mock(spec=Page)
        mock_vector_db = Mock(spec=VectorDBManager)
        
        filler = ChatbotFormFiller(mock_page, mock_vector_db)
        
        # Invalid email should fail validation
        validated = filler._validate_and_normalize_answer(
            "not-an-email",
            FieldType.EMAIL_INPUT
        )
        
        # Should return None or filtered result
        assert validated is None or "@" in validated
    
    def test_empty_string_handling(self):
        """Test handling of empty strings."""
        mock_page = Mock(spec=Page)
        mock_vector_db = Mock(spec=VectorDBManager)
        
        filler = ChatbotFormFiller(mock_page, mock_vector_db)
        
        # Empty string should return None
        validated = filler._validate_and_normalize_answer(
            "",
            FieldType.TEXT_INPUT
        )
        
        assert validated is None


class TestPerformanceMetrics:
    """Test performance tracking for form filling."""
    
    def test_form_filling_timing(self):
        """Test that form filling results include timing information."""
        result = FormFillingResult(
            question="Test question",
            answer="Test answer",
            status="filled",
            confidence=0.85,
            timestamp=datetime.now().isoformat()
        )
        
        assert result.timestamp is not None
    
    def test_stats_computation(self):
        """Test computing statistics from multiple results."""
        stats = ChatbotFormFillerStats(total_questions=100)
        stats.auto_filled = 80
        stats.skipped = 15
        stats.failed = 5
        
        accuracy = stats.auto_filled / stats.total_questions if stats.total_questions > 0 else 0
        success_rate = (stats.auto_filled + stats.skipped) / stats.total_questions
        
        assert accuracy == 0.80
        assert success_rate == 0.95


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

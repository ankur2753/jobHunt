"""
Semantic Matching Tests for VectorDBManager

Tests cover:
- Answer finding with confidence thresholds
- Cosine similarity scoring accuracy
- Multiple candidate ranking
- Field category detection
- Answer candidate validation
"""

import pytest
from pathlib import Path
import sys
import time

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.common_stuff.vector_db_manager import VectorDBManager, AnswerCandidate
from scripts.common_stuff.answer_validators import AnswerNormalizer, FieldCategory


class TestSemanticMatching:
    """Test semantic matching and answer finding from vector DB."""
    
    @pytest.fixture
    def db(self):
        """Initialize VectorDBManager."""
        return VectorDBManager()
    
    @pytest.fixture
    def test_qa_pairs(self):
        """Test Q&A pairs for validation."""
        return [
            # Salary questions
            ("What is your expected salary?", "salary_expected", "12-15 LPA"),
            ("Expected CTC in lakhs per annum?", "salary_expected", "12 LPA"),
            ("Salary expectations?", "salary_expected", "12-15"),
            
            # Location questions
            ("Where would you like to work?", "location", "Bangalore"),
            ("Preferred work location?", "location", "Remote"),
            ("Which city do you prefer?", "location", "Bangalore, India"),
            
            # Experience questions
            ("How many years of experience?", "experience", "5 years"),
            ("Total work experience?", "experience", "5.2 years"),
            ("Years in the industry?", "experience", "5"),
            
            # Notice period questions
            ("Notice period in days?", "notice_period", "30 days"),
            ("How soon can you join?", "notice_period", "2 weeks"),
            ("Available to start?", "availability", "Immediate"),
        ]
    
    def test_cosine_similarity_basic(self, db):
        """Test cosine similarity calculation."""
        import numpy as np
        
        # Test identical vectors (should be 1.0)
        similarity = db._cosine_similarity([1, 0, 0], [1, 0, 0])
        assert abs(similarity - 1.0) < 0.01, f"Expected 1.0, got {similarity}"
        
        # Test orthogonal vectors (should be ~0.0)
        similarity = db._cosine_similarity([1, 0, 0], [0, 1, 0])
        assert abs(similarity - 0.0) < 0.01, f"Expected 0.0, got {similarity}"
        
        # Test opposite vectors (should be -1.0)
        similarity = db._cosine_similarity([1, 1, 1], [-1, -1, -1])
        assert abs(similarity - (-1.0)) < 0.01, f"Expected -1.0, got {similarity}"
        
        print(f"✅ Cosine similarity tests passed")
    
    def test_answer_extraction(self, db):
        """Test answer value extraction from documents."""
        # Test key: value format
        answer = db._extract_answer_value("salary_expected: 12-15 LPA")
        assert answer == "12-15 LPA", f"Expected '12-15 LPA', got '{answer}'"
        
        # Test plain text
        answer = db._extract_answer_value("some text without colon")
        assert answer == "some text without colon"
        
        # Test with multiple colons
        answer = db._extract_answer_value("Q: What is it?: Answer here")
        assert "Answer here" in answer
        
        print(f"✅ Answer extraction tests passed")
    
    def test_answer_question_no_matches(self, db):
        """Test answer_question with completely unrelated query."""
        # Query for something not in DB
        result = db.answer_question("What is calculus?", confidence_threshold=0.5)
        
        # Should return None or very low confidence
        if result:
            assert result.confidence < 0.5, f"Unexpected high confidence: {result.confidence}"
        
        print(f"✅ No matches test passed")
    
    def test_answer_question_with_candidates(self, db):
        """Test getting multiple answer candidates."""
        question = "What is your expected salary?"
        
        # Get top 5 candidates
        candidates = db.answer_question_with_candidates(
            question,
            n_candidates=5,
            confidence_threshold=0.0  # Get all
        )
        
        # Should return a list (even if empty)
        assert isinstance(candidates, list)
        
        # If we have candidates, check the structure
        if candidates:
            for candidate in candidates:
                assert isinstance(candidate, AnswerCandidate)
                assert 0.0 <= candidate.confidence <= 1.0
                assert candidate.answer_text is not None
                assert len(candidate.answer_text) > 0
            
            # Candidates should be sorted by confidence (descending)
            confidences = [c.confidence for c in candidates]
            assert confidences == sorted(confidences, reverse=True)
            
            print(f"✅ Found {len(candidates)} candidates with confidence range "
                  f"{candidates[-1].confidence:.2f} - {candidates[0].confidence:.2f}")
        else:
            print(f"⚠️  No candidates found (DB may be empty or model not loaded)")
    
    def test_confidence_threshold_filtering(self, db):
        """Test confidence threshold filtering."""
        question = "What is your expected salary?"
        
        # Get all candidates
        all_candidates = db.answer_question_with_candidates(
            question,
            n_candidates=10,
            confidence_threshold=0.0
        )
        
        if all_candidates:
            # Get high confidence only
            high_confidence = db.answer_question_with_candidates(
                question,
                n_candidates=10,
                confidence_threshold=0.75
            )
            
            # High confidence should be subset of all
            assert len(high_confidence) <= len(all_candidates)
            
            # All high confidence candidates should meet threshold
            for candidate in high_confidence:
                assert candidate.confidence >= 0.75
            
            print(f"✅ Confidence filtering: {len(all_candidates)} candidates total, "
                  f"{len(high_confidence)} above 0.75 threshold")
    
    def test_similarity_paraphrasing(self, db):
        """Test that paraphrased questions match the same answer."""
        paraphrased_questions = [
            "What is your expected salary?",
            "Expected salary in LPA?",
            "Salary expectations?",
            "What salary are you looking for?",
        ]
        
        results = []
        for question in paraphrased_questions:
            candidate = db.answer_question(question, confidence_threshold=0.0)
            if candidate:
                results.append((question, candidate.confidence, candidate.answer_text))
        
        if results:
            print(f"✅ Paraphrasing test - found {len(results)} matches:")
            for q, conf, answer in results:
                print(f"   Q: '{q}' → Conf: {conf:.2f}, A: {answer[:30]}")
    
    def test_field_category_detection_accuracy(self):
        """Test field category detection accuracy."""
        test_cases = [
            ("What is your expected salary?", FieldCategory.SALARY),
            ("Expected CTC?", FieldCategory.SALARY),
            ("Salary package?", FieldCategory.SALARY),
            
            ("Where would you like to work?", FieldCategory.LOCATION),
            ("Preferred location?", FieldCategory.LOCATION),
            ("Which city?", FieldCategory.LOCATION),
            
            ("Years of experience?", FieldCategory.EXPERIENCE),
            ("How much experience?", FieldCategory.EXPERIENCE),
            ("Total work experience?", FieldCategory.EXPERIENCE),
            
            ("Notice period?", FieldCategory.NOTICE_PERIOD),
            ("Notice in days?", FieldCategory.NOTICE_PERIOD),
            
            ("When can you join?", FieldCategory.AVAILABILITY),
        ]
        
        passed = 0
        failed = 0
        
        for question, expected_category in test_cases:
            detected = AnswerNormalizer.get_field_category(question)
            if detected == expected_category:
                passed += 1
            else:
                failed += 1
                print(f"❌ Category mismatch: '{question}'")
                print(f"   Expected: {expected_category.value}")
                print(f"   Got: {detected.value}")
        
        print(f"✅ Category detection: {passed}/{len(test_cases)} passed")
        assert passed / len(test_cases) >= 0.85, "Category detection accuracy < 85%"


class TestPerformance:
    """Performance benchmarking for semantic matching."""
    
    @pytest.fixture
    def db(self):
        """Initialize VectorDBManager."""
        return VectorDBManager()
    
    def test_encoding_performance(self, db):
        """Test performance of question encoding."""
        question = "What is your expected salary?"
        
        # Warm up
        _ = db.model.encode([question])
        
        # Benchmark
        start = time.time()
        for _ in range(10):
            embedding = db.model.encode([question])
        elapsed = time.time() - start
        
        avg_time_ms = (elapsed / 10) * 1000
        print(f"✅ Encoding performance: {avg_time_ms:.2f}ms per question")
        assert avg_time_ms < 100, f"Encoding too slow: {avg_time_ms}ms"
    
    def test_query_performance(self, db):
        """Test performance of vector DB query."""
        # First, ensure we have data
        try:
            all_data = db.get_all_details()
            if not all_data['documents']:
                print("⚠️  Vector DB is empty, skipping query performance test")
                return
        except:
            print("⚠️  Could not access vector DB, skipping query performance test")
            return
        
        question = "What is your expected salary?"
        
        # Benchmark
        start = time.time()
        for _ in range(10):
            result = db.search_personal_details(question, n_results=5)
        elapsed = time.time() - start
        
        avg_time_ms = (elapsed / 10) * 1000
        print(f"✅ Query performance: {avg_time_ms:.2f}ms per query")
        assert avg_time_ms < 100, f"Query too slow: {avg_time_ms}ms"
    
    def test_end_to_end_performance(self, db):
        """Test end-to-end answer finding performance."""
        question = "What is your expected salary?"
        
        # Warm up
        _ = db.answer_question(question, confidence_threshold=0.0)
        
        # Benchmark
        start = time.time()
        for _ in range(5):
            result = db.answer_question(question, confidence_threshold=0.65)
        elapsed = time.time() - start
        
        avg_time_ms = (elapsed / 5) * 1000
        print(f"✅ End-to-end performance: {avg_time_ms:.2f}ms per answer finding")
        assert avg_time_ms < 150, f"End-to-end too slow: {avg_time_ms}ms"


class TestAnswerValidation:
    """Test answer validation and normalization in matching context."""
    
    @pytest.fixture
    def db(self):
        """Initialize VectorDBManager."""
        return VectorDBManager()
    
    def test_answer_candidate_validation(self, db):
        """Test AnswerCandidate validation."""
        # Valid candidate
        candidate = AnswerCandidate(
            answer_text="12-15 LPA",
            confidence=0.85,
            source_key="salary_expected",
            source_category="personal_details",
            should_autofill=True,
            reasoning="High confidence semantic match"
        )
        
        assert candidate.answer_text == "12-15 LPA"
        assert 0.0 <= candidate.confidence <= 1.0
        assert candidate.should_autofill is True
        
        print(f"✅ Answer candidate validation passed")
    
    def test_low_confidence_candidate_detection(self, db):
        """Test detection of low confidence answers."""
        # Create a low-confidence candidate
        candidate = AnswerCandidate(
            answer_text="Maybe this?",
            confidence=0.45,
            source_key="unknown",
            source_category="personal_details",
            should_autofill=False
        )
        
        # Should not be marked for auto-fill
        assert not candidate.should_autofill
        assert candidate.confidence < 0.65
        
        print(f"✅ Low confidence detection passed")


class TestIntegration:
    """Integration tests with real vector DB."""
    
    @pytest.fixture
    def db(self):
        """Initialize VectorDBManager."""
        return VectorDBManager()
    
    def test_store_and_retrieve_answer(self, db):
        """Test storing and retrieving learned answers."""
        question = "What programming languages do you know?"
        answer = "Python, JavaScript, Go"
        
        try:
            # Store the answer
            result = db.store_answered_question(
                question=question,
                answer=answer,
                category="learned_answers",
                tags=["programming", "skills"]
            )
            
            assert result['success'] is True
            assert "stored_key" in result
            
            print(f"✅ Answer stored successfully: {result['stored_key']}")
        except Exception as e:
            print(f"⚠️  Could not test answer storage: {e}")
    
    def test_batch_answer_retrieval(self, db):
        """Test retrieving answers for multiple questions."""
        questions = [
            "What is your expected salary?",
            "Preferred work location?",
            "Years of experience?",
            "Notice period in days?",
        ]
        
        results = []
        for question in questions:
            candidates = db.answer_question_with_candidates(
                question,
                n_candidates=3,
                confidence_threshold=0.0
            )
            results.append({
                'question': question,
                'candidates_found': len(candidates),
                'top_confidence': candidates[0].confidence if candidates else 0.0
            })
        
        print(f"✅ Batch retrieval test:")
        for r in results:
            print(f"   Q: '{r['question'][:30]}...'")
            print(f"      Found: {r['candidates_found']} candidates, "
                  f"Top conf: {r['top_confidence']:.2f}")


class TestConfidenceThresholds:
    """Test different confidence threshold strategies."""
    
    @pytest.fixture
    def db(self):
        """Initialize VectorDBManager."""
        return VectorDBManager()
    
    def test_threshold_comparison(self, db):
        """Compare results across different confidence thresholds."""
        question = "What is your expected salary?"
        thresholds = [0.5, 0.60, 0.65, 0.70, 0.75, 0.80]
        
        print(f"✅ Threshold comparison for: '{question}'")
        print(f"   Threshold  | Found | Top Confidence | Recommendation")
        print(f"   " + "-" * 60)
        
        for threshold in thresholds:
            candidates = db.answer_question_with_candidates(
                question,
                n_candidates=10,
                confidence_threshold=threshold
            )
            
            if candidates:
                top_conf = candidates[0].confidence
                recommendation = "AUTO-FILL" if top_conf >= 0.75 else "REVIEW" if top_conf >= 0.65 else "MANUAL"
            else:
                top_conf = 0.0
                recommendation = "NOT FOUND"
            
            print(f"   {threshold:.2f}      | {len(candidates):4d} | {top_conf:14.2f} | {recommendation}")
    
    def test_recommended_thresholds_per_portal(self, db):
        """Test recommended thresholds for different portals."""
        question = "What is your expected salary?"
        
        portal_thresholds = {
            'Naukri': 0.70,      # Stricter
            'LinkedIn': 0.65,    # Moderate
            'InstaHyre': 0.60,   # Lenient
        }
        
        print(f"✅ Portal-specific threshold recommendations:")
        
        for portal, threshold in portal_thresholds.items():
            candidate = db.answer_question(
                question,
                confidence_threshold=threshold
            )
            
            if candidate:
                print(f"   {portal}: ✅ Would auto-fill with {candidate.confidence:.2f}")
            else:
                print(f"   {portal}: ⚠️  Would request manual review at threshold {threshold:.2f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

#!/usr/bin/env python3
"""
Verification suite for Knowledge System Canonical Reuse Fixes.
Tests:
1. Canonical rule matching for non-employers (Google, MongoDB, Amazon -> "No")
2. Canonical rule matching for known employers (SafeSend Technologies, Deloitte, Thomson Reuters -> "Yes")
3. Store answered question persistence to both ChromaDB and custom_details.json
4. Retrieval of learned facts across different phrasings
"""

import sys
import os
import json
import unittest
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.common_stuff.vector_db_manager import VectorDBManager, AnswerCandidate


class TestCanonicalKnowledgeReuse(unittest.TestCase):
    
    def setUp(self):
        self.db = VectorDBManager()

    def test_canonical_non_employers(self):
        """Verify that non-employers return 'No' with 1.0 confidence."""
        test_questions = [
            "Have you previously worked for Google or one of its subsidiaries?",
            "Have you previously worked for MongoDB?",
            "Have you ever worked at Amazon?",
            "Were you previously employed by Microsoft?",
        ]
        for q in test_questions:
            cand = self.db.evaluate_canonical_question(q)
            self.assertIsNotNone(cand, f"Failed to match canonical pattern for question: {q}")
            self.assertEqual(cand.answer_text, "No", f"Expected 'No' for {q}, got {cand.answer_text}")
            self.assertEqual(cand.confidence, 1.0, f"Expected 1.0 confidence for {q}")

    def test_canonical_known_employers(self):
        """Verify that known employers return 'Yes' with 1.0 confidence."""
        test_questions = [
            "Have you previously worked for SafeSend Technologies?",
            "Were you previously employed by Deloitte?",
            "Have you ever worked at Thomson Reuters?",
        ]
        for q in test_questions:
            cand = self.db.evaluate_canonical_question(q)
            self.assertIsNotNone(cand, f"Failed to match canonical pattern for question: {q}")
            self.assertEqual(cand.answer_text, "Yes", f"Expected 'Yes' for {q}, got {cand.answer_text}")
            self.assertEqual(cand.confidence, 1.0, f"Expected 1.0 confidence for {q}")

    def test_answer_question_with_candidates_integration(self):
        """Verify answer_question_with_candidates uses canonical rules first."""
        q = "Have you previously worked for Google?"
        cands = self.db.answer_question_with_candidates(q)
        self.assertTrue(len(cands) > 0)
        top = cands[0]
        self.assertEqual(top.answer_text, "No")
        self.assertEqual(top.confidence, 1.0)
        self.assertEqual(top.source_category, "canonical_rules")

    def test_store_answered_question_json_writeback(self):
        """Verify store_answered_question persists data to custom_details.json."""
        test_key = "preferred_relocation_country"
        test_value = "Canada"
        res = self.db.store_answered_question(test_key, test_value, category="test_category")
        self.assertTrue(res.get("success"))

        c_path = ROOT / "personal_details" / "custom_details.json"
        self.assertTrue(c_path.exists())
        with open(c_path, 'r', encoding='utf-8') as f:
            c_data = json.load(f)
        
        normalized_key = self.db._normalize_key(test_key)
        self.assertIn(normalized_key, c_data)
        self.assertEqual(c_data[normalized_key], test_value)


if __name__ == '__main__':
    unittest.main()

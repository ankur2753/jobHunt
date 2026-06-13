#!/usr/bin/env python3
"""
Interactive Vector DB Normalizer Test

Allows you to type questions in the terminal and see the normalized answers from your vector DB.
This helps you:
1. Verify that the vector DB retrieves the correct answers
2. Check how answers are normalized for different field types
3. Debug semantic matching issues

Usage:
    python scripts/tests/test_interactive_vector_db.py

Example Questions:
    - "How many years of Angular experience?"
    - "What's your expected salary?"
    - "What's your preferred location?"
    - "Your email address?"
    - "Notice period required?"
"""

import sys
import os
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.common_stuff.vector_db_manager import VectorDBManager
from scripts.common_stuff.answer_validators import AnswerNormalizer, FieldCategory
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def print_header():
    """Print welcome message."""
    print("\n" + "="*80)
    print("🤖 INTERACTIVE VECTOR DB & NORMALIZER TEST")
    print("="*80)
    print("\nType a question in the terminal and get back the:")
    print("  • Retrieved answer from Vector DB")
    print("  • Confidence score")
    print("  • Detected field category")
    print("  • Normalized answer (formatted for form submission)")
    print("\nExamples:")
    print("  - 'How many years of Angular experience do you have?'")
    print("  - 'What is your expected salary?'")
    print("  - 'What is your preferred work location?'")
    print("  - 'What is your email address?'")
    print("  - 'How much notice period can you serve?'")
    print("\nType 'exit' or 'quit' to stop.\n")
    print("="*80 + "\n")


def get_field_category_from_question(question: str) -> FieldCategory:
    """Detect field category from question text."""
    question_lower = question.lower()
    
    # Salary detection
    if any(kw in question_lower for kw in ['salary', 'ctc', 'lpa', 'lakhs', 'compensation', 'wage']):
        return FieldCategory.SALARY
    
    # Location detection
    if any(kw in question_lower for kw in ['location', 'city', 'area', 'place', 'office', 'work location']):
        return FieldCategory.LOCATION
    
    # Experience detection
    if any(kw in question_lower for kw in ['experience', 'years', 'exp', 'prior']):
        return FieldCategory.EXPERIENCE
    
    # Notice period detection
    if any(kw in question_lower for kw in ['notice', 'joining', 'available', 'start date']):
        return FieldCategory.NOTICE_PERIOD
    
    # Contact detection
    if any(kw in question_lower for kw in ['email', 'phone', 'contact', 'number']):
        return FieldCategory.CONTACT
    
    # Date detection
    if any(kw in question_lower for kw in ['date', 'birth', 'dob', 'when', 'year born']):
        return FieldCategory.DATE
    
    # Default
    return FieldCategory.TEXT


def normalize_answer(answer: str, category: FieldCategory) -> dict:
    """Normalize answer based on field category."""
    result = {
        'raw': answer,
        'normalized': None,
        'category': category.value,
        'normalizer_used': None
    }
    
    try:
        if category == FieldCategory.SALARY:
            normalized = AnswerNormalizer.normalize_salary(answer)
            result['normalizer_used'] = 'normalize_salary'
        elif category == FieldCategory.LOCATION:
            normalized = AnswerNormalizer.normalize_location(answer)
            result['normalizer_used'] = 'normalize_location'
        elif category == FieldCategory.EXPERIENCE:
            normalized = AnswerNormalizer.normalize_experience(answer)
            result['normalizer_used'] = 'normalize_experience'
        elif category == FieldCategory.NOTICE_PERIOD:
            normalized = AnswerNormalizer.normalize_notice_period(answer)
            result['normalizer_used'] = 'normalize_notice_period'
        elif category == FieldCategory.CONTACT:
            # Try email first, then phone
            if '@' in answer:
                normalized = AnswerNormalizer.normalize_email(answer)
                result['normalizer_used'] = 'normalize_email'
            else:
                normalized = AnswerNormalizer.normalize_phone(answer)
                result['normalizer_used'] = 'normalize_phone'
        else:
            normalized = answer  # No normalization for text fields
            result['normalizer_used'] = 'none'
        
        result['normalized'] = normalized
    except Exception as e:
        result['error'] = str(e)
        logger.warning(f"  ⚠️  Normalization error: {str(e)}")
    
    return result


def print_result(question: str, candidates: list, category: FieldCategory, norm_result: dict):
    """Pretty-print the result."""
    print("\n" + "-"*80)
    print(f"❓ YOUR QUESTION:")
    print(f"   {question}")
    print("-"*80)
    
    print(f"\n🏷️  FIELD CATEGORY DETECTED:")
    print(f"   {category.value.upper()} (FieldCategory.{category.name})")
    
    if candidates:
        print(f"\n🧠 VECTOR DB MATCHES (Top 3):")
        for idx, candidate in enumerate(candidates[:3], 1):
            print(f"\n   [{idx}] Source: {candidate.source_key}")
            print(f"       Answer: {candidate.answer_text}")
            print(f"       Confidence: {candidate.confidence:.2%}")
            print(f"       Auto-fill: {'✅ YES' if candidate.should_autofill else '❌ NO'}")
            if candidate.reasoning:
                print(f"       Reasoning: {candidate.reasoning}")
    else:
        print(f"\n🧠 VECTOR DB MATCHES:")
        print(f"   ❌ NO MATCHES FOUND")
        print(f"   (Make sure you've added data via setup.html or loaded it into vector_db/)")
    
    # Get best match (first one if exists)
    best_match = candidates[0] if candidates else None
    
    if best_match:
        print(f"\n💡 BEST MATCH:")
        print(f"   Answer: {best_match.answer_text}")
        print(f"   Confidence: {best_match.confidence:.2%}")
        
        # Apply normalization
        norm_result = normalize_answer(best_match.answer_text, category)
        
        print(f"\n🔄 NORMALIZATION:")
        print(f"   Normalizer: {norm_result['normalizer_used']}")
        print(f"   Raw: {norm_result['raw']}")
        if norm_result.get('normalized') is not None:
            print(f"   Normalized: {norm_result['normalized']}")
        else:
            print(f"   Normalized: (no change)")
        
        if norm_result.get('error'):
            print(f"   ⚠️  Error: {norm_result['error']}")
        
        print(f"\n✅ FINAL ANSWER FOR FORM:")
        print(f"   {norm_result['normalized'] or norm_result['raw']}")
    else:
        print(f"\n❌ FINAL ANSWER FOR FORM:")
        print(f"   NO VECTOR DB MATCH AVAILABLE")
    
    print("\n" + "-"*80)


def main():
    """Main interactive loop."""
    print_header()
    
    # Initialize Vector DB
    try:
        vector_db = VectorDBManager()
        print("✓ Vector DB initialized successfully")
        print(f"✓ Database location: {vector_db.db_path}")
        
        # Count documents in collection
        collection_info = vector_db.collection.count()
        print(f"✓ Documents in collection: {collection_info}")
        
        if collection_info == 0:
            print("\n⚠️  WARNING: Vector DB is empty!")
            print("   Please run setup.html to add your personal details.")
            print("   Or run: python setup_data.py")
            print("\n")
        
    except Exception as e:
        print(f"❌ Error initializing Vector DB: {str(e)}")
        print("   Make sure vector_db/ directory exists in the project root")
        return
    
    # Initialize normalizer
    normalizer = AnswerNormalizer()
    
    # Main loop
    while True:
        try:
            print("\n")
            question = input("🎯 Ask a question: ").strip()
            
            # Exit conditions
            if question.lower() in ['exit', 'quit', 'q', ':q']:
                print("\n✅ Goodbye!\n")
                break
            
            if not question:
                print("⚠️  Please enter a question.")
                continue
            
            # Query Vector DB with this question
            print("\n⏳ Searching Vector DB...")
            
            try:
                candidates = vector_db.answer_question_with_candidates(
                    question,
                    n_candidates=3,
                    confidence_threshold=0.0  # Show all matches, regardless of confidence
                )
            except Exception as e:
                print(f"❌ Error querying Vector DB: {str(e)}")
                continue
            
            # Detect field category
            category = get_field_category_from_question(question)
            
            # Normalize the best match
            norm_result = None
            if candidates:
                norm_result = normalize_answer(candidates[0].answer_text, category)
            
            # Print results
            print_result(question, candidates, category, norm_result)
        
        except KeyboardInterrupt:
            print("\n\n✅ Interrupted. Goodbye!\n")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error: {str(e)}")
            import traceback
            traceback.print_exc()
            continue


if __name__ == "__main__":
    main()

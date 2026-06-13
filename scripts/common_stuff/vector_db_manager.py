import argparse
import json
import os
import re
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

# Suppress verbose logging from ChromaDB and other libraries before importing
logging.getLogger('chromadb').setLevel(logging.WARNING)
logging.getLogger('sentence_transformers').setLevel(logging.WARNING)

import chromadb
from sentence_transformers import SentenceTransformer
import numpy as np


@dataclass
class AnswerCandidate:
    """Represents a potential answer to a form question."""
    answer_text: str
    confidence: float  # 0.0 to 1.0 (semantic similarity)
    source_key: str  # e.g., 'salary_expected'
    source_category: str  # e.g., 'personal_details'
    should_autofill: bool
    reasoning: str = ""


class VectorDBManager:
    KNOWN_ALIASES = {
        'expected ctc': 'salary_expected',
        'expected salary': 'salary_expected',
        'ectc': 'salary_expected',
        'current ctc': 'salary_current',
        'current salary': 'salary_current',
        'salary': 'salary',
        'preferred location': 'location',
        'location': 'location',
        'city': 'location',
        'name': 'name',
        'email': 'email',
        'phone': 'phone',
        'linkedin': 'linkedin',
        'summary': 'summary',
        'skills': 'skills',
        'experience': 'experience',
        'education': 'education',
    }

    def __init__(self, db_path=None):
        if db_path is None:
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            db_path = os.path.join(repo_root, 'vector_db')
        self.db_path = os.path.abspath(db_path)
        os.makedirs(self.db_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.client.get_or_create_collection(name='personal_details')
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def _normalize_key(self, raw_key):
        normalized = raw_key.strip().lower()
        normalized = re.sub(r'[^a-z0-9 ]+', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return self.KNOWN_ALIASES.get(normalized, normalized.replace(' ', '_'))

    def _normalize_value(self, value):
        if isinstance(value, str):
            value = value.strip()
            salary_match = re.search(
                r'([0-9]+(?:\.[0-9]+)?)(?:\s*-\s*([0-9]+(?:\.[0-9]+)?))?\s*(lpa|lakhs|lakhs per annum|lakhs p\.a\.|pa|p\.a\.)?',
                value,
                re.IGNORECASE,
            )
            if salary_match:
                lower = salary_match.group(1)
                upper = salary_match.group(2)
                if upper:
                    return f"{lower}-{upper} LPA"
                return f"{lower} LPA"
            return value
        return value

    def _flatten_data(self, data, category, parent_key=None, counter=None):
        documents = []
        metadatas = []
        ids = []
        if counter is None:
            counter = {'n': 0}

        def add_entry(key, value, sub_key=None):
            normalized_key = self._normalize_key(key)
            if sub_key:
                normalized_sub_key = self._normalize_key(sub_key)
                doc_text = f"{key} {sub_key}: {value}"
                metadata = {
                    'category': category,
                    'key': key,
                    'sub_key': sub_key,
                    'normalized_key': normalized_key,
                    'normalized_sub_key': normalized_sub_key,
                }
                doc_id = f"{category}_{normalized_key}_{normalized_sub_key}_{counter['n']}"
            else:
                doc_text = f"{key}: {value}"
                metadata = {
                    'category': category,
                    'key': key,
                    'normalized_key': normalized_key,
                }
                doc_id = f"{category}_{normalized_key}_{counter['n']}"

            counter['n'] += 1
            documents.append(str(self._normalize_value(doc_text)))
            metadatas.append(metadata)
            ids.append(doc_id)

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    documents_sub, metadatas_sub, ids_sub = self._flatten_data(value, category, parent_key=key, counter=counter)
                    documents.extend(documents_sub)
                    metadatas.extend(metadatas_sub)
                    ids.extend(ids_sub)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            documents_sub, metadatas_sub, ids_sub = self._flatten_data(item, category, parent_key=key, counter=counter)
                            documents.extend(documents_sub)
                            metadatas.extend(metadatas_sub)
                            ids.extend(ids_sub)
                        else:
                            add_entry(key, self._normalize_value(item))
                else:
                    if parent_key:
                        add_entry(parent_key, self._normalize_value(value), sub_key=key)
                    else:
                        add_entry(key, self._normalize_value(value))
        else:
            add_entry(parent_key or 'value', self._normalize_value(data))

        return documents, metadatas, ids

    def _upsert_documents(self, documents, metadatas, ids):
        embeddings = self.model.encode(documents).tolist()
        self.collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings,
        )

    def migrate_personal_details_file(self, json_path=None):
        json_path = Path(json_path or os.path.join(os.path.dirname(__file__), '..', '..', 'personal_details', 'personal_details.json')).resolve()
        if not json_path.exists():
            raise FileNotFoundError(f"Personal details file not found: {json_path}")

        with open(json_path, 'r', encoding='utf-8') as f:
            personal_details = json.load(f)

        documents, metadatas, ids = self._flatten_data(personal_details, 'personal_details')
        self._upsert_documents(documents, metadatas, ids)
        return {
            'status': 'migrated',
            'source': str(json_path),
            'document_count': len(documents),
        }

    def add_or_update_detail(self, key, value, category='personal_details'):
        normalized_key = self._normalize_key(key)
        normalized_value = self._normalize_value(value)
        documents, metadatas, ids = self._flatten_data({key: normalized_value}, category)
        self._upsert_documents(documents, metadatas, ids)
        return {
            'status': 'updated',
            'key': key,
            'normalized_key': normalized_key,
            'value': normalized_value,
        }

    def search_personal_details(self, query, n_results=5):
        query_embedding = self.model.encode([query]).tolist()[0]
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
        )
        documents = [doc for sublist in results.get('documents', []) for doc in sublist]
        metadatas = [meta for sublist in results.get('metadatas', []) for meta in sublist]
        ids = [id_ for sublist in results.get('ids', []) for id_ in sublist]
        return {
            'documents': documents,
            'metadatas': metadatas,
            'ids': ids,
        }

    def query_personal_profile(self, query, n_results=5):
        return self.search_personal_details(query, n_results=n_results)

    def answer_question(
        self,
        question: str,
        confidence_threshold: float = 0.65,
        n_candidates: int = 5
    ) -> Optional[AnswerCandidate]:
        """
        Answer a specific question using semantic matching against vector DB.
        
        Args:
            question: The question to answer (e.g., "What's your expected salary?")
            confidence_threshold: Minimum confidence score to auto-fill (0.0-1.0)
            n_candidates: Number of candidates to consider before filtering
        
        Returns:
            AnswerCandidate with best match if confidence >= threshold, else None
        """
        candidates = self.answer_question_with_candidates(
            question, 
            n_candidates=n_candidates,
            confidence_threshold=0.0  # Get all candidates first
        )
        
        if candidates and candidates[0].confidence >= confidence_threshold:
            best = candidates[0]
            best.should_autofill = True
            best.reasoning = f"High confidence match ({best.confidence:.2f})"
            return best
        
        return None

    def answer_question_with_candidates(
        self,
        question: str,
        n_candidates: int = 5,
        confidence_threshold: float = 0.65
    ) -> List[AnswerCandidate]:
        """
        Get top N answer candidates for a question with confidence scores.
        
        Args:
            question: The question to answer
            n_candidates: Number of candidates to return
            confidence_threshold: For filtering; returns all candidates with score >= this
        
        Returns:
            List of AnswerCandidate objects sorted by confidence (highest first)
        """
        # Query vector DB
        query_results = self.search_personal_details(question, n_results=n_candidates)
        
        documents = query_results.get('documents', [])
        metadatas = query_results.get('metadatas', [])
        ids = query_results.get('ids', [])
        
        # Get similarity scores from ChromaDB
        query_embedding = self.model.encode([question]).tolist()[0]
        
        candidates = []
        for doc, meta, doc_id in zip(documents, metadatas, ids):
            # Encode document to compute similarity
            doc_embedding = self.model.encode([doc]).tolist()[0]
            
            # Compute cosine similarity
            similarity = self._cosine_similarity(query_embedding, doc_embedding)
            
            # Only include if meets threshold
            if similarity >= confidence_threshold:
                source_key = meta.get('normalized_key', meta.get('key', 'unknown'))
                source_category = meta.get('category', 'personal_details')
                
                candidate = AnswerCandidate(
                    answer_text=self._extract_answer_value(doc),
                    confidence=float(similarity),
                    source_key=source_key,
                    source_category=source_category,
                    should_autofill=similarity >= 0.75,  # Threshold for auto-fill
                    reasoning=f"Semantic match from {source_key}"
                )
                candidates.append(candidate)
        
        # Sort by confidence (descending)
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        return candidates

    def _cosine_similarity(self, vec1, vec2) -> float:
        """Compute cosine similarity between two vectors (0.0 to 1.0)."""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(dot_product / (norm1 * norm2))

    def _extract_answer_value(self, document_text: str) -> str:
        """Extract the answer value from a document. Handles 'key: value' format."""
        if ':' in document_text:
            parts = document_text.split(':', 1)
            return parts[1].strip()
        return document_text.strip()
    
    def convert_answer_type(
        self, 
        answer: str, 
        answer_type: str = None, 
        options: Optional[List[str]] = None
    ) -> str:
        """
        Convert an answer to match expected answer type or available options.
        
        Examples:
            - Input: answer="one month", options=["30 days", "60 days", "90 days"]
              Output: "30 days"
            - Input: answer="5 LPA", answer_type="salary_range", options=["0-5", "5-10", "10-15"]
              Output: "5-10"
        
        Args:
            answer: The answer to convert
            answer_type: Type hint (e.g., 'duration', 'salary_range', 'experience_level')
            options: List of valid options to match against
        
        Returns:
            Converted answer if match found, else original answer
        """
        if not answer or not options:
            return answer
        
        # Normalize the answer
        answer_normalized = answer.strip().lower()
        
        # Try direct match first (case-insensitive)
        for option in options:
            if option.lower() == answer_normalized:
                return option
        
        # If answer_type is provided, try semantic conversion
        if answer_type:
            return self._convert_by_type(answer, answer_type, options)
        
        # Try semantic matching against options
        return self._find_best_matching_option(answer, options)
    
    def _convert_by_type(
        self, 
        answer: str, 
        answer_type: str, 
        options: List[str]
    ) -> str:
        """Convert answer based on specific type mapping."""
        answer_lower = answer.lower().strip()
        
        # Duration conversions (e.g., "one month" -> "30 days")
        if 'duration' in answer_type.lower() or 'notice' in answer_type.lower():
            duration_map = {
                'one month': '30',
                '1 month': '30',
                '30 days': '30',
                'two months': '60',
                '2 months': '60',
                '60 days': '60',
                'three months': '90',
                '3 months': '90',
                '90 days': '90',
                'immediate': '0',
                'two weeks': '14',
                'one week': '7',
            }
            
            # Extract numeric value from answer if present
            match = re.search(r'(\d+)', answer)
            if match:
                days = int(match.group(1))
                # Try to find matching days in options
                for option in options:
                    if str(days) in option.lower():
                        return option
            
            # Try duration_map
            if answer_lower in duration_map:
                target_days = duration_map[answer_lower]
                for option in options:
                    if target_days in option.lower():
                        return option
        
        # Salary conversions (e.g., "10 LPA" -> "10-15")
        elif 'salary' in answer_type.lower():
            salary_match = re.search(r'(\d+(?:\.\d+)?)', answer)
            if salary_match:
                salary_val = float(salary_match.group(1))
                for option in options:
                    # Check if salary falls in range (e.g., "10-15")
                    range_match = re.search(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)', option)
                    if range_match:
                        min_sal = float(range_match.group(1))
                        max_sal = float(range_match.group(2))
                        if min_sal <= salary_val <= max_sal:
                            return option
        
        # Experience conversions (e.g., "5 years" -> "5+")
        elif 'experience' in answer_type.lower():
            exp_match = re.search(r'(\d+)', answer)
            if exp_match:
                years = int(exp_match.group(1))
                for option in options:
                    opt_match = re.search(r'(\d+)', option)
                    if opt_match and int(opt_match.group(1)) == years:
                        return option
        
        # Fallback to semantic matching
        return self._find_best_matching_option(answer, options)
    
    def _find_best_matching_option(self, answer: str, options: List[str]) -> str:
        """Find best matching option using semantic similarity."""
        if not options:
            return answer
        
        if len(options) == 1:
            return options[0]
        
        try:
            # Encode answer and all options
            answer_embedding = self.model.encode([answer])[0]
            option_embeddings = self.model.encode(options)
            
            # Find most similar option
            similarities = [
                self._cosine_similarity(answer_embedding, opt_emb)
                for opt_emb in option_embeddings
            ]
            
            best_idx = similarities.index(max(similarities))
            return options[best_idx]
        except Exception as e:
            logging.debug(f"Error in semantic matching: {e}")
            return answer
    
    def get_answer_and_convert(
        self,
        question: str,
        answer_type: str = None,
        options: Optional[List[str]] = None,
        confidence_threshold: float = 0.65
    ) -> tuple:
        """
        Get answer from vector DB and convert if needed.
        
        Args:
            question: The question to answer
            answer_type: Type hint for conversion (e.g., 'duration', 'salary')
            options: Valid options to match against
            confidence_threshold: Minimum confidence for auto-fill
        
        Returns:
            Tuple of (answer, confidence, should_prompt)
            - answer: The (converted) answer string
            - confidence: Confidence score (0.0-1.0)
            - should_prompt: True if confidence < threshold and user needs to confirm
        """
        # Get candidate answers
        candidate = self.answer_question(question, confidence_threshold=0.0)
        
        if not candidate:
            return None, 0.0, True
        
        answer = candidate.answer_text
        confidence = candidate.confidence
        
        # Convert answer if options provided
        if options:
            answer = self.convert_answer_type(answer, answer_type, options)
        
        # Determine if user should be prompted
        should_prompt = confidence < confidence_threshold
        
        return answer, confidence, should_prompt

    def store_answered_question(
        self,
        question: str,
        answer: str,
        category: str = 'form_answers',
        tags: list = None
    ) -> dict:
        """
        Store a user-provided answer for a question (for learning).
        This allows the system to learn from manual corrections.
        
        Args:
            question: The original question
            answer: The user's answer
            category: Category for this answer (default: 'form_answers')
            tags: Optional tags for grouping (e.g., ['naukri', 'salary'])
        
        Returns:
            Status dict with storage details
        """
        # Create a learning document
        doc_text = f"Q: {question}\nA: {answer}"
        normalized_key = self._normalize_key(question)
        
        # Encode and store
        embedding = self.model.encode([doc_text]).tolist()[0]
        doc_id = f"{category}_{normalized_key}_{hash(answer) % 10000}"
        
        metadata = {
            'category': category,
            'key': question,
            'normalized_key': normalized_key,
            'stored_answer': answer,
            'tags': ','.join(tags) if tags else ''
        }
        
        self.collection.upsert(
            documents=[doc_text],
            metadatas=[metadata],
            ids=[doc_id],
            embeddings=[embedding]
        )
        
        return {
            'success': True,
            'stored_key': doc_id,
            'message': f"Stored answer for question: {question[:50]}..."
        }

    def get_all_details(self):
        return self.collection.get()


def _build_arg_parser():
    parser = argparse.ArgumentParser(description='Vector DB manager for personal details and job preferences.')
    subparsers = parser.add_subparsers(dest='command')

    migrate_parser = subparsers.add_parser('migrate', help='Migrate personal_details.json into the vector DB.')
    migrate_parser.add_argument('--file', type=str, help='Path to personal_details.json')

    add_parser = subparsers.add_parser('add', help='Add or update a key/value in the vector DB.')
    add_parser.add_argument('--key', type=str, required=True, help='Metadata key to add or update.')
    add_parser.add_argument('--value', type=str, required=True, help='Value for the key.')
    add_parser.add_argument('--category', type=str, default='personal_details', help='Optional category for the detail.')

    query_parser = subparsers.add_parser('query', help='Query the vector DB using a natural language prompt.')
    query_parser.add_argument('--text', type=str, required=True, help='Search query text.')
    query_parser.add_argument('--n', type=int, default=5, help='Number of results to return.')

    subparsers.add_parser('dump', help='Dump all details from the vector DB.')

    return parser


if __name__ == '__main__':
    parser = _build_arg_parser()
    args = parser.parse_args()
    manager = VectorDBManager()

    if args.command == 'migrate':
        result = manager.migrate_personal_details_file(args.file)
        print(json.dumps(result, indent=2))
    elif args.command == 'add':
        result = manager.add_or_update_detail(args.key, args.value, args.category)
        print(json.dumps(result, indent=2))
    elif args.command == 'query':
        results = manager.query_personal_profile(args.text, n_results=args.n)
        print(json.dumps(results, indent=2))
    elif args.command == 'dump':
        data = manager.get_all_details()
        print(json.dumps(data, indent=2, default=str))
    else:
        parser.print_help()

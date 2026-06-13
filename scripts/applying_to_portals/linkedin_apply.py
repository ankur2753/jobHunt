import re
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

class LinkedInApply:
    COMPENSATION_QUERIES = [
        'current ctc',
        'expected ctc',
        'salary',
        'compensation',
        'package',
        'pay'
    ]

    def __init__(self, db_manager=None):
        if db_manager is not None:
            self.db_manager = db_manager
        else:
            from scripts.common_stuff.vector_db_manager import VectorDBManager
            self.db_manager = VectorDBManager()

    @staticmethod
    def _parse_compensation_value(text):
        normalized = text.lower().replace(',', ' ').strip()

        lpa_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(lpa|lakhs?|lakh)', normalized)
        if lpa_match:
            return int(float(lpa_match.group(1)) * 100000)

        crore_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(crore|cr)', normalized)
        if crore_match:
            return int(float(crore_match.group(1)) * 10000000)

        rupee_match = re.search(r'rs\.?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)', normalized)
        if rupee_match:
            return int(float(rupee_match.group(1).replace(',', '')))

        number_match = re.search(r'([0-9]{5,})', normalized)
        if number_match:
            return int(number_match.group(1))

        return None

    def get_compensation_info(self):
        """
        Retrieve compensation-related information from the vector database.
        """
        all_docs = []
        for query in self.COMPENSATION_QUERIES:
            results = self.db_manager.search_personal_details(query, n_results=10)
            for result_doc in results.get('documents', []):
                if isinstance(result_doc, list):
                    all_docs.extend(result_doc)
                else:
                    all_docs.append(result_doc)

        compensation_values = []
        for doc in all_docs:
            value = self._parse_compensation_value(doc)
            if value is not None:
                compensation_values.append(value)

        compensation_values = sorted(set(compensation_values))
        return {
            'raw_values': compensation_values,
            'current_ctc': compensation_values[0] if compensation_values else None,
            'expected_ctc': compensation_values[-1] if len(compensation_values) > 1 else (compensation_values[0] if compensation_values else None)
        }

    def apply_to_job(self, job_url):
        """
        Placeholder for the job application logic.
        This would include browser automation to fill forms.
        """
        print(f"Applying to job at: {job_url}")
        comp_info = self.get_compensation_info()
        print(f"Retrieved compensation info: {comp_info}")
        print("Application submitted (placeholder)")

if __name__ == '__main__':
    applier = LinkedInApply()
    applier.apply_to_job('https://example.com/job')

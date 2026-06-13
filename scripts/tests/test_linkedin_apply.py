import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.applying_to_portals.linkedin_apply import LinkedInApply

class DummyVectorDBManager:
    def __init__(self, documents):
        self._documents = documents

    def search_personal_details(self, query, n_results=5):
        return {
            'documents': [self._documents],
            'metadatas': [[]],
            'ids': [[]]
        }

class TestLinkedInApply(unittest.TestCase):
    def test_get_compensation_info_parses_ctc_and_salary(self):
        applier = LinkedInApply.__new__(LinkedInApply)
        applier.db_manager = DummyVectorDBManager([
            'currentCTC: 12 LPA',
            'expectedCTC: 15 LPA',
            'salary: 1,500,000',
            'compensation: 18LPA',
            'package: 20 LPA'
        ])

        comp_info = applier.get_compensation_info()

        self.assertEqual(comp_info['current_ctc'], 1200000)
        self.assertEqual(comp_info['expected_ctc'], 2000000)
        self.assertEqual(comp_info['raw_values'], [1200000, 1500000, 1800000, 2000000])

if __name__ == '__main__':
    unittest.main()

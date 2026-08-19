"""
Unit tests for Candidate Discovery Providers.
Tests BaseDiscoveryProvider, LinkedInSearchDiscoveryProvider, LinkedInAPIDiscoveryProvider,
and LinkedInReferralHelper integration.
"""

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure root directory is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.networking.discovery_providers import (
    BaseDiscoveryProvider,
    LinkedInSearchDiscoveryProvider,
    LinkedInAPIDiscoveryProvider,
)
from scripts.networking.linkedin_referral_helper import LinkedInReferralHelper


class TestDiscoveryProviders(unittest.TestCase):

    def test_base_provider_interface(self):
        """Test that BaseDiscoveryProvider enforces the discover_candidates interface."""
        class IncompleteProvider(BaseDiscoveryProvider):
            pass

        with self.assertRaises(TypeError):
            IncompleteProvider()

        class CompleteProvider(BaseDiscoveryProvider):
            async def discover_candidates(self, company_name: str, job_title_keyword: str) -> list:
                return []

        provider = CompleteProvider()
        self.assertIsInstance(provider, BaseDiscoveryProvider)

    def test_linkedin_api_provider_initialization_with_credentials(self):
        """Test initializing LinkedInAPIDiscoveryProvider with credentials."""
        mock_client = MagicMock()
        with patch("scripts.networking.discovery_providers.Linkedin", return_value=mock_client) as mock_linkedin:
            provider = LinkedInAPIDiscoveryProvider(username="test@example.com", password="password123")
            self.assertEqual(provider.username, "test@example.com")
            self.assertEqual(provider.password, "password123")
            self.assertIsNotNone(provider.client)
            mock_linkedin.assert_called_once_with("test@example.com", "password123")

    def test_linkedin_api_provider_initialization_with_env_vars(self):
        """Test initializing LinkedInAPIDiscoveryProvider with environment variables."""
        mock_client = MagicMock()
        with patch.dict(os.environ, {"LINKEDIN_USERNAME": "env_user@example.com", "LINKEDIN_PASSWORD": "env_password"}):
            with patch("scripts.networking.discovery_providers.Linkedin", return_value=mock_client) as mock_linkedin:
                provider = LinkedInAPIDiscoveryProvider()
                self.assertEqual(provider.username, "env_user@example.com")
                self.assertEqual(provider.password, "env_password")
                self.assertIsNotNone(provider.client)
                mock_linkedin.assert_called_once_with("env_user@example.com", "env_password")

    def test_linkedin_api_provider_initialization_with_cookies_dict(self):
        """Test initializing LinkedInAPIDiscoveryProvider with cookies dictionary."""
        mock_client = MagicMock()
        mock_client.session = MagicMock()
        mock_client.session.cookies = MagicMock()
        with patch("scripts.networking.discovery_providers.Linkedin", return_value=mock_client):
            provider = LinkedInAPIDiscoveryProvider(cookies={"li_at": "AQED..."})
            self.assertIsNotNone(provider.client)
            mock_client.session.cookies.update.assert_called_once_with({"li_at": "AQED..."})

    def test_linkedin_api_provider_custom_client(self):
        """Test initializing LinkedInAPIDiscoveryProvider with custom client."""
        custom_client = MagicMock()
        provider = LinkedInAPIDiscoveryProvider(client=custom_client)
        self.assertEqual(provider.client, custom_client)

    def test_linkedin_api_provider_parse_candidate(self):
        """Test candidate parsing from various API dictionary formats."""
        provider = LinkedInAPIDiscoveryProvider(client=MagicMock())

        # Test case 1: Standard name, headline, public_id
        res1 = provider._parse_candidate({
            "name": "Jane Doe",
            "headline": "Senior Tech Recruiter at Google",
            "public_id": "jane-doe-123"
        })
        self.assertEqual(res1, {
            "name": "Jane Doe",
            "headline": "Senior Tech Recruiter at Google",
            "profile_url": "https://www.linkedin.com/in/jane-doe-123"
        })

        # Test case 2: First/last name, subline, entityUrn, degree suffix
        res2 = provider._parse_candidate({
            "firstName": "John",
            "lastName": "Smith • 2nd",
            "subline": "Staff Software Engineer at Meta",
            "entityUrn": "urn:li:fsd_profile:john-smith-456"
        })
        self.assertEqual(res2, {
            "name": "John Smith",
            "headline": "Staff Software Engineer at Meta",
            "profile_url": "https://www.linkedin.com/in/john-smith-456"
        })

        # Test case 3: Direct profile_url with tracking query params
        res3 = provider._parse_candidate({
            "name": "Alice Brown",
            "occupation": "Engineering Manager",
            "profile_url": "https://www.linkedin.com/in/alice-brown?trackingId=123"
        })
        self.assertEqual(res3, {
            "name": "Alice Brown",
            "headline": "Engineering Manager",
            "profile_url": "https://www.linkedin.com/in/alice-brown"
        })

    def test_linkedin_api_provider_discover_candidates(self):
        """Test discovery method queries both recruiters and peers and deduplicates."""
        mock_client = MagicMock()
        mock_client.search_people.side_effect = [
            # Recruiter query response
            [
                {"name": "Recruiter One", "headline": "Talent Partner", "public_id": "recruiter-1"},
                {"name": "Shared Contact", "headline": "Technical Recruiter", "public_id": "shared-1"}
            ],
            # Peer query response
            [
                {"name": "Shared Contact", "headline": "Technical Recruiter", "public_id": "shared-1"},
                {"name": "Engineer Peer", "headline": "QA Engineer", "public_id": "peer-1"}
            ]
        ]

        provider = LinkedInAPIDiscoveryProvider(client=mock_client)
        candidates = asyncio.run(provider.discover_candidates("Acme Corp", "QA"))

        self.assertEqual(len(candidates), 3)
        self.assertEqual(candidates[0]["name"], "Recruiter One")
        self.assertEqual(candidates[0]["profile_url"], "https://www.linkedin.com/in/recruiter-1")
        self.assertEqual(candidates[1]["name"], "Shared Contact")
        self.assertEqual(candidates[2]["name"], "Engineer Peer")

    def test_linkedin_api_provider_error_handling(self):
        """Test that API errors are caught and handled gracefully without crashing."""
        mock_client = MagicMock()
        mock_client.search_people.side_effect = Exception("API rate limit exceeded")

        provider = LinkedInAPIDiscoveryProvider(client=mock_client)
        candidates = asyncio.run(provider.discover_candidates("Acme Corp", "QA"))

        self.assertEqual(candidates, [])

    def test_referral_helper_with_custom_provider(self):
        """Test that LinkedInReferralHelper integrates with LinkedInAPIDiscoveryProvider."""
        mock_provider = MagicMock(spec=BaseDiscoveryProvider)
        mock_provider.discover_candidates = unittest.mock.AsyncMock(return_value=[
            {"name": "Candidate A", "headline": "Senior QA Engineer", "profile_url": "https://www.linkedin.com/in/cand-a"}
        ])

        helper = LinkedInReferralHelper(discovery_provider=mock_provider)
        self.assertEqual(helper.discovery_provider, mock_provider)


if __name__ == "__main__":
    unittest.main()

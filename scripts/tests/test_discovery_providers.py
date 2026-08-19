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
    ApifyDiscoveryProvider,
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

    def test_apify_provider_initialization_with_token(self):
        """Test initializing ApifyDiscoveryProvider with an explicit token."""
        provider = ApifyDiscoveryProvider(api_token="apify_api_token_123")
        self.assertEqual(provider.api_token, "apify_api_token_123")
        self.assertEqual(provider.actor_id, "curious_coder/linkedin-search-scraper")
        self.assertIsInstance(provider, BaseDiscoveryProvider)

    def test_apify_provider_initialization_with_env_var(self):
        """Test initializing ApifyDiscoveryProvider with APIFY_API_TOKEN environment variable."""
        with patch.dict(os.environ, {"APIFY_API_TOKEN": "env_apify_token_456"}):
            provider = ApifyDiscoveryProvider()
            self.assertEqual(provider.api_token, "env_apify_token_456")

    def test_apify_provider_missing_token(self):
        """Test that missing API token logs a warning and discover_candidates returns empty list."""
        with patch.dict(os.environ, {}, clear=True):
            if "APIFY_API_TOKEN" in os.environ:
                del os.environ["APIFY_API_TOKEN"]
            provider = ApifyDiscoveryProvider()
            self.assertIsNone(provider.api_token)
            candidates = asyncio.run(provider.discover_candidates("Google", "QA"))
            self.assertEqual(candidates, [])

    def test_apify_provider_parse_candidate(self):
        """Test parsing candidate records from various Apify actor output formats."""
        provider = ApifyDiscoveryProvider(api_token="dummy")

        # Format 1: Direct name, headline, profileUrl with query params
        res1 = provider._parse_candidate({
            "name": "Jane Recruiter • 1st",
            "headline": "Lead Technical Recruiter at Acme",
            "profileUrl": "https://www.linkedin.com/in/jane-recruiter?trk=public-profile"
        })
        self.assertEqual(res1, {
            "name": "Jane Recruiter",
            "headline": "Lead Technical Recruiter at Acme",
            "profile_url": "https://www.linkedin.com/in/jane-recruiter"
        })

        # Format 2: firstName + lastName, occupation, url
        res2 = provider._parse_candidate({
            "firstName": "Bob",
            "lastName": "Engineer",
            "occupation": "Senior Staff QA Engineer",
            "url": "https://www.linkedin.com/in/bob-engineer"
        })
        self.assertEqual(res2, {
            "name": "Bob Engineer",
            "headline": "Senior Staff QA Engineer",
            "profile_url": "https://www.linkedin.com/in/bob-engineer"
        })

        # Format 3: fullName, jobTitle, public_id
        res3 = provider._parse_candidate({
            "fullName": "Alice Developer",
            "jobTitle": "Backend Lead",
            "public_id": "alice-dev-789"
        })
        self.assertEqual(res3, {
            "name": "Alice Developer",
            "headline": "Backend Lead",
            "profile_url": "https://www.linkedin.com/in/alice-dev-789"
        })

        # Format 4: Invalid item (missing profile URL)
        res4 = provider._parse_candidate({"name": "No URL Person"})
        self.assertIsNone(res4)

    def test_apify_provider_discover_candidates_with_client(self):
        """Test discover_candidates using a client mock with dual query and deduplication."""
        mock_actor = MagicMock()
        mock_actor.call.side_effect = [
            # Recruiter query response
            [
                {"name": "Apify Recruiter 1", "headline": "Technical Recruiter", "profile_url": "https://www.linkedin.com/in/rec-1"},
                {"name": "Duplicate Contact", "headline": "Talent Sourcing", "profile_url": "https://www.linkedin.com/in/dup-1"}
            ],
            # Peer query response
            [
                {"name": "Duplicate Contact", "headline": "Talent Sourcing", "profile_url": "https://www.linkedin.com/in/dup-1"},
                {"name": "Apify QA Peer", "headline": "SDET II", "profile_url": "https://www.linkedin.com/in/peer-1"}
            ]
        ]
        mock_client = MagicMock()
        mock_client.actor.return_value = mock_actor

        provider = ApifyDiscoveryProvider(api_token="test_token", client=mock_client)
        candidates = asyncio.run(provider.discover_candidates("TestCorp", "SDET"))

        self.assertEqual(len(candidates), 3)
        self.assertEqual(candidates[0]["name"], "Apify Recruiter 1")
        self.assertEqual(candidates[0]["profile_url"], "https://www.linkedin.com/in/rec-1")
        self.assertEqual(candidates[1]["name"], "Duplicate Contact")
        self.assertEqual(candidates[2]["name"], "Apify QA Peer")

    def test_apify_provider_discover_candidates_with_requests(self):
        """Test discover_candidates using requests mock for the REST API endpoint."""
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = [
            {"name": "Recruiter One", "headline": "Recruiter", "profile_url": "https://www.linkedin.com/in/rec-one"}
        ]

        mock_response_2 = MagicMock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = [
            {"name": "Peer One", "headline": "Software Engineer", "profile_url": "https://www.linkedin.com/in/peer-one"}
        ]

        with patch("scripts.networking.discovery_providers.requests.post", side_effect=[mock_response_1, mock_response_2]) as mock_post:
            provider = ApifyDiscoveryProvider(api_token="test_apify_token")
            candidates = asyncio.run(provider.discover_candidates("TargetCompany", "Engineer"))

            self.assertEqual(len(candidates), 2)
            self.assertEqual(candidates[0]["name"], "Recruiter One")
            self.assertEqual(candidates[1]["name"], "Peer One")
            self.assertEqual(mock_post.call_count, 2)

    def test_apify_provider_error_handling(self):
        """Test that HTTP errors or network exceptions are caught gracefully."""
        with patch("scripts.networking.discovery_providers.requests.post", side_effect=Exception("Network connection timeout")):
            provider = ApifyDiscoveryProvider(api_token="test_apify_token")
            candidates = asyncio.run(provider.discover_candidates("FailingCompany", "QA"))
            self.assertEqual(candidates, [])

    def test_apify_provider_empty_company(self):
        """Test that empty company name returns an empty list without calling API."""
        provider = ApifyDiscoveryProvider(api_token="test_token")
        candidates = asyncio.run(provider.discover_candidates("", "QA"))
        self.assertEqual(candidates, [])

    def test_referral_helper_with_apify_provider(self):
        """Test LinkedInReferralHelper initialization with ApifyDiscoveryProvider."""
        provider = ApifyDiscoveryProvider(api_token="test_token")
        helper = LinkedInReferralHelper(discovery_provider=provider)
        self.assertEqual(helper.discovery_provider, provider)


if __name__ == "__main__":
    unittest.main()

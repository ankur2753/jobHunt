import argparse
import asyncio
import json
import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.networking.linkedin_referral_helper import LinkedInReferralHelper, extract_job_keyword
from scripts.networking.discovery_providers import LinkedInAPIDiscoveryProvider

logging.basicConfig(level=logging.ERROR)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", required=True)
    parser.add_argument("--role", required=True)
    args = parser.parse_args()

    company = args.company
    role = args.role

    # Initialize the API discovery provider instead of Playwright
    # It will automatically pick up cookies from personal_details/linkedin_cookies.json
    api_provider = LinkedInAPIDiscoveryProvider()
    
    # Pass the api_provider to the helper
    helper = LinkedInReferralHelper(discovery_provider=api_provider)
    
    keyword = extract_job_keyword(role)
    candidates = await helper.discovery_provider.discover_candidates(company, keyword)
    
    user_details = helper.load_user_details()

    scored = []
    for c in candidates:
        c["score"] = helper.score_candidate(c["headline"], keyword)
        scored.append(c)
        
    scored.sort(key=lambda x: x["score"], reverse=True)
    suitable = [c for c in scored if c["score"] >= 0.5][:5]
    
    final_candidates = []
    for cand in suitable:
        message = helper.generate_message(
            candidate_name=cand["name"],
            candidate_headline=cand["headline"],
            score=cand["score"],
            company_name=company,
            job_title=role,
            user_details=user_details
        )
        cand["drafted_message"] = message
        final_candidates.append(cand)
        
    print(json.dumps({"status": "success", "company": company, "role": role, "candidates": final_candidates}))

if __name__ == "__main__":
    asyncio.run(main())

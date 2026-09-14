"""
LinkedIn Referral Helper module.

Core script containing the referral discovery, scoring, and drafting logic.
Abstracts the dual-query candidate discovery behind a clean interface.
Uses externalized constants for candidate scoring rules.
"""

import csv
import json
import logging
import random
import re
from datetime import datetime
from pathlib import Path
from playwright.async_api import Page

# Import externalized constants for scoring
from scripts.networking.referral_constants import SCORING_KEYWORDS, DEFAULT_SCORE

# Import discovery providers
from scripts.networking.discovery_providers import (
    BaseDiscoveryProvider,
    LinkedInSearchDiscoveryProvider,
    LinkedInAPIDiscoveryProvider,
    ApifyDiscoveryProvider,
)

logger = logging.getLogger(__name__)


def shorten_company_name(name: str) -> str:
    """
    Shorten company names by stripping common corporate suffixes.
    e.g. 'SafeSend Technologies LLC' -> 'SafeSend'
    """
    if not name:
        return ""
    
    suffixes = [
        "technologies", "technology", "services", "solutions", "systems",
        "corporation", "corp.", "corp", "incorporated", "inc.", "inc", 
        "limited", "ltd.", "ltd", "pvt.", "pvt", "llc", "plc", "gmbh", "co."
    ]
    
    # Split by common delimiters and spaces
    parts = re.split(r'[\s,\-;\(\)]+', name)
    clean_parts = []
    for part in parts:
        part_clean = part.lower().strip(".")
        if not part_clean:
            continue
        if part_clean in suffixes:
            break
        clean_parts.append(part)
    
    if clean_parts:
        return " ".join(clean_parts)
    return name


def format_referrals_to_markdown(entries: list, title: str = "Drafted Referral Messages") -> str:
    """
    Pure function to transform a list of referral JSON entries into a formatted markdown string.
    """
    if not entries:
        return "Processed jobs, but could not find suitable referral candidates to draft messages for."
        
    response_text = f"🎯 *{title}*\n\n"
    found_drafts = False
    
    for entry in entries:
        company = entry.get('company_name', 'Unknown')
        job_title = entry.get('job_title', '')
        candidates = entry.get('candidates', [])
        
        if candidates:
            found_drafts = True
            header = f"🏢 *{company}*"
            if job_title:
                header += f" ({job_title})"
            response_text += f"{header}\n"
            
            for idx, cand in enumerate(candidates, 1):
                name = cand.get("name", "Unknown")
                profile_url = cand.get("profile_url", "#")
                draft = cand.get("drafted_message", "")
                response_text += f"*{idx}. [{name}]({profile_url})*\n```text\n{draft}\n```\n"
            response_text += "\n"
            
    if not found_drafts:
        return "Processed jobs, but could not find suitable referral candidates to draft messages for."
        
    return response_text


def shorten_job_title(title: str) -> str:
    """
    Shorten job titles to look natural in conversational outreach.
    e.g. 'QA Automation Engineer - Remote (USA)' -> 'QA Automation Engineer'
    """
    if not title:
        return ""
    
    # Remove contents of parentheses and brackets
    title = re.sub(r'\(.*?\)', '', title)
    title = re.sub(r'\[.*?\]', '', title)
    
    # Split by common delimiters and keep the first part
    delimiters = [' - ', ' | ', ' / ', ' , ']
    for delim in delimiters:
        if delim in title:
            title = title.split(delim)[0]
    
    title = title.strip()
    
    # Remove metadata words
    words_to_remove = {"remote", "hybrid", "onsite", "full-time", "part-time", "contract", "intern"}
    words = title.split()
    cleaned_words = [w for w in words if w.lower().strip(",()-") not in words_to_remove]
    
    if cleaned_words:
        return " ".join(cleaned_words)
    return title


def extract_job_keyword(job_title: str) -> str:
    """
    Extract key domain keyword from job title to search for peers on LinkedIn.
    e.g. 'QA Automation Engineer' -> 'QA'
    """
    title_lower = job_title.lower()
    if 'qa' in title_lower or 'sdet' in title_lower or 'quality' in title_lower or 'test' in title_lower:
        return 'QA'
    elif 'frontend' in title_lower or 'front-end' in title_lower or 'react' in title_lower:
        return 'Frontend'
    elif 'backend' in title_lower or 'back-end' in title_lower:
        return 'Backend'
    elif 'fullstack' in title_lower or 'full-stack' in title_lower:
        return 'Fullstack'
    elif 'data' in title_lower or 'ml' in title_lower or 'machine' in title_lower:
        return 'Data'
    elif 'software' in title_lower or 'developer' in title_lower or 'engineer' in title_lower or 'sde' in title_lower:
        return 'Software Engineer'
    else:
        words = [w for w in job_title.split() if w.isalpha()]
        for w in words:
            if w.lower() not in ["senior", "junior", "lead", "staff", "principal", "associate"]:
                return w
        if words:
            return words[0]
        return "Software Engineer"


class LinkedInReferralHelper:
    """
    Helper class for automating and managing LinkedIn referral outreach.
    """

    def __init__(self, page: Page = None, discovery_provider: BaseDiscoveryProvider = None) -> None:
        """
        Initialize the LinkedInReferralHelper instance.

        :param page: Optional Playwright page instance for browser automation.
        :param discovery_provider: Class conforming to BaseDiscoveryProvider. Defaults to LinkedInSearchDiscoveryProvider.
        """
        self.page = page
        self.project_root = Path(__file__).resolve().parents[2]
        self.csv_path = self.project_root / "personal_details" / "jobs_database.csv"
        self.json_path = self.project_root / "personal_details" / "pending_referrals.json"
        self.personal_details_path = self.project_root / "personal_details" / "personal_details.json"
        
        self.discovery_provider = discovery_provider or LinkedInSearchDiscoveryProvider(self.page)

    async def _human_pause(self, min_ms: int = 700, max_ms: int = 1600):
        if self.page:
            await self.page.wait_for_timeout(random.randint(min_ms, max_ms))

    def load_user_details(self) -> dict:
        if self.personal_details_path.exists():
            try:
                with open(self.personal_details_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading personal_details.json: {e}")
        return {
            "name": "Applicant",
            "total_experience": "3 years",
            "core_skills": ["Python", "JavaScript", "SQL"]
        }

    def read_pending_jobs(self, limit: int) -> list:
        if not self.csv_path.exists():
            # Create jobs_database.csv template if it does not exist
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['url', 'company', 'job_title', 'referral_status'])
                writer.writerow([
                    'https://www.linkedin.com/jobs/view/123456789/',
                    'SafeSend Technologies',
                    'QA Automation Engineer',
                    'Pending'
                ])
            print(f"Created a new jobs database template at {self.csv_path} with a sample job.")
            
        jobs = []
        with open(self.csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or 'url' not in reader.fieldnames:
                return []
            for row in reader:
                if 'referral_status' not in row:
                    row['referral_status'] = 'Pending'
                row['referral_status'] = row['referral_status'] or 'Pending'
                jobs.append(row)
                
        pending_jobs = [j for j in jobs if j['referral_status'] == 'Pending']
        return pending_jobs[:limit]

    def update_job_status(self, job_url: str, new_status: str):
        if not self.csv_path.exists():
            return
            
        rows = []
        fieldnames = ['url', 'company', 'job_title', 'referral_status']
        with open(self.csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                fieldnames = reader.fieldnames
            for row in reader:
                if row.get('url') == job_url:
                    row['referral_status'] = new_status
                rows.append(row)
                
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def append_pending_referral(self, referral_entry: dict):
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        data = []
        if self.json_path.exists():
            try:
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = []
            except Exception as e:
                logger.warning(f"Error reading pending_referrals.json, resetting: {e}")
                data = []
                
        # Deduplicate queue by job_url
        data = [entry for entry in data if entry.get("job_url") != referral_entry.get("job_url")]
        data.append(referral_entry)
        
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def score_candidate(self, headline: str, job_title_keyword: str) -> float:
        """
        Score candidate suitability based on profile headline and target role keyword using externalized constants.
        """
        if not headline:
            return 0.0
            
        headline_lower = headline.lower()
        keyword_lower = job_title_keyword.lower()
        
        # Check Recruiter first
        recruiter_config = SCORING_KEYWORDS.get("Recruiter", {})
        if any(kw in headline_lower for kw in recruiter_config.get("keywords", [])):
            return recruiter_config.get("score", 0.7)
            
        # Check Manager next
        manager_config = SCORING_KEYWORDS.get("Manager", {})
        if any(kw in headline_lower for kw in manager_config.get("keywords", [])):
            return manager_config.get("score", 0.6)
            
        # Check QA next
        qa_config = SCORING_KEYWORDS.get("QA", {})
        if any(kw in headline_lower for kw in qa_config.get("keywords", [])):
            return qa_config.get("score", 0.8)
            
        # Check Developer next
        dev_config = SCORING_KEYWORDS.get("Developer", {})
        if any(kw in headline_lower for kw in dev_config.get("keywords", [])):
            return dev_config.get("score", 0.5)
            
        if keyword_lower in headline_lower:
            return 0.5
            
        return DEFAULT_SCORE

    def generate_message(
        self,
        candidate_name: str,
        candidate_headline: str,
        score: float,
        company_name: str,
        job_title: str,
        user_details: dict,
    ) -> str:
        """
        Generate a personalized referral outreach message tailored to the candidate's profile and score.
        Strict 300 character limit.
        """
        first_name = "there"
        if candidate_name and candidate_name.lower() != "linkedin member":
            name_parts = candidate_name.split()
            if name_parts:
                first_name = name_parts[0]
                if first_name.lower() in ["mr.", "ms.", "dr.", "mrs.", "mr", "ms", "dr", "mrs"]:
                    if len(name_parts) > 1:
                        first_name = name_parts[1]
                        
        user_full_name = user_details.get("name", "Applicant")
        user_first_name = user_full_name.split()[0] if user_full_name else "Applicant"
        user_exp = user_details.get("total_experience", "3 years")
        
        core_skills = user_details.get("core_skills", ["C#", "JavaScript", "SQL"])
        skills_str = ", ".join(core_skills[:3])
        
        short_company = shorten_company_name(company_name)
        short_job_title = shorten_job_title(job_title)
        
        # Dynamic comparison based on scores configured in constant file
        recruiter_score = SCORING_KEYWORDS.get("Recruiter", {}).get("score", 0.7)
        qa_score = SCORING_KEYWORDS.get("QA", {}).get("score", 0.8)
        
        if score == recruiter_score:
            template = (
                f"Hi {first_name}, I applied for the {short_job_title} role at {short_company}. "
                f"With my {user_exp} in QA Automation ({skills_str}), I wanted to reach out and see if you're "
                f"the recruiter for this role or could point me to them? Thanks, {user_first_name}"
            )
        elif score == qa_score:
            template = (
                f"Hi {first_name}, I applied for the {short_job_title} role at {short_company}. "
                f"Since you also work in this space, I'd love to connect to learn about the team culture or any "
                f"tips you might have. Thanks, {user_first_name}"
            )
        else:
            template = (
                f"Hi {first_name}, I noticed you are at {short_company}. I'm interested in the "
                f"{short_job_title} role there and would love to connect to see if you have any insights or "
                f"could refer me. Thanks, {user_first_name}"
            )
            
        # Guarantee 300 character limit
        if len(template) <= 300:
            return template
            
        if score == recruiter_score:
            template = (
                f"Hi {first_name}, I applied for the {short_job_title} role at {short_company}. "
                f"With my {user_exp} of experience, I wanted to reach out and see if you're the recruiter "
                f"for this role or could point me to them? Thanks, {user_first_name}"
            )
            
        if len(template) > 300:
            template = (
                f"Hi {first_name}, I applied for the {short_job_title} role at {short_company}. "
                f"I'd love to connect and see if you could refer me or point me in the right direction. "
                f"Thanks, {user_first_name}"
            )
            
        if len(template) > 300:
            template = template[:297] + "..."
            
        return template

    async def process_jobs(self, limit: int) -> None:
        """
        Runs the full pipeline to discover candidates from pending jobs database,
        score, draft messages, and update local queue/DB.
        """
        pending_jobs = self.read_pending_jobs(limit)
        if not pending_jobs:
            logger.info("No pending jobs found to process.")
            print("No pending jobs found in jobs_database.csv to process.")
            return
            
        print(f"\n🚀 Found {len(pending_jobs)} pending jobs to process for referral outreach.")
        user_details = self.load_user_details()
        
        for idx, job in enumerate(pending_jobs, 1):
            job_url = job.get("url")
            company = job.get("company")
            job_title = job.get("job_title")
            
            print(f"\n------------------------------------------------------------")
            print(f"[{idx}/{len(pending_jobs)}] Job: '{job_title}' at '{company}'")
            print(f"URL: {job_url}")
            
            if not job_url or not company or not job_title:
                logger.warning(f"Skipping incomplete row: {job}")
                continue
                
            try:
                # Extract keyword
                job_keyword = extract_job_keyword(job_title)
                
                # Perform candidate discovery using the abstracted provider interface
                print(f"🔍 Discovering referral candidates for '{company}'...")
                candidates = await self.discovery_provider.discover_candidates(company, job_keyword)
                
                # Score all candidates
                scored = []
                for c in candidates:
                    c["score"] = self.score_candidate(c["headline"], job_keyword)
                    scored.append(c)
                    
                # Sort and filter suitable candidates (score >= 0.5)
                scored.sort(key=lambda x: x["score"], reverse=True)
                suitable = [c for c in scored if c["score"] >= 0.5][:3]
                
                if not suitable:
                    print(f"⚠️ No suitable referral candidates found (score >= 0.5). Skipping job.")
                    self.update_job_status(job_url, "Skipped")
                    continue
                    
                # Draft message for each candidate
                final_candidates = []
                for cand in suitable:
                    message = self.generate_message(
                        candidate_name=cand["name"],
                        candidate_headline=cand["headline"],
                        score=cand["score"],
                        company_name=company,
                        job_title=job_title,
                        user_details=user_details
                    )
                    cand["drafted_message"] = message
                    final_candidates.append(cand)
                    print(f"  ✍️ Message drafted for {cand['name']} ({cand['headline'][:40]}...) | Score: {cand['score']}")
                    print(f"     \"{message}\"")
                    
                # Format referral entry and append to JSON
                timestamp = datetime.now().isoformat()
                referral_entry = {
                    "job_url": job_url,
                    "job_title": job_title,
                    "company_name": company,
                    "timestamp": timestamp,
                    "candidates": final_candidates
                }
                
                self.append_pending_referral(referral_entry)
                self.update_job_status(job_url, "Drafted")
                print(f"✅ Job updated to 'Drafted'. Messages saved to queue.")
                
            except Exception as e:
                logger.error(f"Failed to process job '{job_title}' at '{company}': {e}", exc_info=True)
                print(f"❌ Error occurred while processing this job: {e}")

    async def draft_manual_outreach(self, profile_urls: list, reason: str = None) -> None:
        """
        Drafts messages for a manual list of profile URLs. DOES NOT click send.
        """
        user_details = self.load_user_details()
        drafts = []
        
        print(f"\n🚀 Drafting manual outreach messages for {len(profile_urls)} profiles...")
        
        for idx, url in enumerate(profile_urls, 1):
            url = url.strip()
            if not url:
                continue
                
            print(f"\n[{idx}/{len(profile_urls)}] Scraping profile: {url}")
            try:
                await self.page.goto(url, wait_until="domcontentloaded")
                await self._human_pause(2000, 3500)
                
                name = "there"
                name_selectors = [
                    'h1.text-heading-xlarge',
                    '.pv-text-details__left-panel h1',
                    'h1[class*="text-heading"]'
                ]
                for sel in name_selectors:
                    try:
                        locator = self.page.locator(sel).first
                        if await locator.is_visible(timeout=1000):
                            name_text = await locator.text_content()
                            if name_text:
                                name = name_text.strip()
                                break
                    except Exception:
                        continue
                        
                headline = ""
                headline_selectors = [
                    '.text-body-medium',
                    '.pv-text-details__left-panel .text-body-medium',
                    'div[class*="text-body-medium"]'
                ]
                for sel in headline_selectors:
                    try:
                        locator = self.page.locator(sel).first
                        if await locator.is_visible(timeout=1000):
                            head_text = await locator.text_content()
                            if head_text:
                                headline = head_text.strip()
                                break
                    except Exception:
                        continue
                        
                score = self.score_candidate(headline, reason or "Software")
                first_name = name.split()[0] if name and name.lower() != "there" else "there"
                user_full_name = user_details.get("name", "Applicant")
                user_first_name = user_full_name.split()[0] if user_full_name else "Applicant"
                
                if reason:
                    msg = (
                        f"Hi {first_name}, I noticed you work in {reason} and "
                        f"would love to connect. I build resilient automation tooling for QA & software teams "
                        f"and wanted to learn about your experience. Thanks, {user_first_name}"
                    )
                else:
                    msg = (
                        f"Hi {first_name}, I'd love to connect. I work in QA "
                        f"automation, building resilient web workflows and automation tooling. I would love to "
                        f"learn about your experience in the industry. Thanks, {user_first_name}"
                    )
                    
                if len(msg) > 300:
                    msg = msg[:297] + "..."
                    
                cand_draft = {
                    "name": name,
                    "headline": headline,
                    "profile_url": url,
                    "score": score,
                    "drafted_message": msg
                }
                drafts.append(cand_draft)
                
                print(f"  Name: {name}")
                print(f"  Headline: {headline}")
                print(f"  Drafted Message (length: {len(msg)}):")
                print(f"    \"{msg}\"")
                
            except Exception as e:
                logger.error(f"Failed to draft outreach for {url}: {e}")
                print(f"  ❌ Error: {e}")
                
        logs_dir = self.project_root / "logs"
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f"linkedin_cold_message_drafts_{timestamp}.json"
        
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "profiles": drafts
        }
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
            
        print(f"\n✅ Successfully saved manual outreach drafts to: {log_file}")

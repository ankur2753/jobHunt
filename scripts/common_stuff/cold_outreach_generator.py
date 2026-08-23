"""
Generic Cold Outreach Message Generator
Generates personalized outreach messages for LinkedIn DMs, Connection Notes, Cold Emails, and Referral Requests.
Uses ChromaDB VectorDBManager to pull candidate facts/profile + OpenRouter / Gemini LLM API (with fallback).
"""

import logging
import os
import json
from typing import Dict, Optional, Literal
from pathlib import Path

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncio
from scripts.common_stuff.vector_db_manager import VectorDBManager
from scripts.common_stuff.llm_fallback import query_llm_fallback

logger = logging.getLogger(__name__)

OutreachChannel = Literal["linkedin_connection_note", "linkedin_dm", "cold_email", "referral_request"]


class ColdOutreachGenerator:
    """Generates platform-agnostic personalized cold outreach messages."""

    def __init__(self, vector_db: Optional[VectorDBManager] = None):
        self.vector_db = vector_db or VectorDBManager()

    def _get_user_context(self, job_title: str = "", company_name: str = "") -> str:
        """Retrieves relevant user background/skills from ChromaDB."""
        query = f"experience skills automation projects {job_title} {company_name}".strip()
        results = self.vector_db.query_personal_profile(query, n_results=5)

        docs = results.get("documents", [])
        if docs:
            return "\n".join(docs)
        return (
            "Software Engineer specializing in Python, QA Automation, AI agents, "
            "Playwright browser automation, and resilient backend systems."
        )

    def generate_outreach(
        self,
        recipient_name: str = "Hiring Manager",
        recipient_title: str = "Engineering Leader / Recruiter",
        company_name: str = "Target Company",
        job_title: Optional[str] = None,
        job_description: Optional[str] = None,
        channel: OutreachChannel = "linkedin_dm",
        custom_note: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Generates a tailored outreach message.

        Returns:
            Dict with keys:
            - 'subject': Email subject (or blank for DMs)
            - 'message': Body of the message
            - 'character_count': Integer count of characters
        """
        user_context = self._get_user_context(job_title or "", company_name)

        system_prompt = (
            "You are an expert tech career advisor crafting high-converting, polite, concise, "
            "and natural-sounding outreach messages for a software/AI engineer based in India. "
            "Never use fluff, overly formal buzzwords ('esteemed organization'), or salesy language. "
            "Focus on direct value, technical fit, and a low-friction call to action."
        )

        unslop_path = Path(__file__).resolve().parents[2] / "Instructions" / "unslop_rules.txt"
        if unslop_path.exists():
            unslop_rules = unslop_path.read_text(encoding="utf-8")
            system_prompt += f"\n\nCRITICAL WRITING RULES (UNSLOP):\n{unslop_rules}\n"


        if channel == "linkedin_connection_note":
            prompt = f"""
Draft a LinkedIn Connection Request note (STRICTLY UNDER 280 CHARACTERS).
Recipient: {recipient_name} ({recipient_title} at {company_name})
Target Role: {job_title or 'Software Engineering roles'}
Candidate Background: {user_context[:300]}
Custom Note/Context: {custom_note or 'N/A'}

Rules:
- MUST be under 280 characters.
- Direct, friendly, state value alignment.
- Output ONLY JSON: {{"message": "..."}}
"""
        elif channel == "cold_email":
            prompt = f"""
Draft a Cold Email to a recruiter or hiring manager.
Recipient: {recipient_name} ({recipient_title} at {company_name})
Target Role: {job_title or 'Software / AI Engineer'}
Job Description snippet: {(job_description or '')[:500]}
Candidate Context: {user_context}
Custom Note/Context: {custom_note or 'N/A'}

Rules:
- Subject line must be catchy and short (e.g. "Software Engineer interested in {company_name} - [Name]").
- Body must be 3 short paragraphs:
  1. Quick Hook (Why reaching out specifically to {company_name}).
  2. Proof of fit (1-2 relevant technical achievements/projects matching the JD).
  3. Soft CTA (15-min chat or review of resume).
- Output ONLY JSON: {{"subject": "...", "message": "..."}}
"""
        elif channel == "referral_request":
            prompt = f"""
Draft a low-pressure Referral Request message to an employee at {company_name}.
Recipient: {recipient_name} ({recipient_title})
Target Role: {job_title or 'Software Engineer'}
Candidate Context: {user_context}

Rules:
- Friendly, non-entitled, polite.
- Acknowledge their time, mention why their team/company stands out.
- Ask if they'd be open to sharing your profile or referring if it feels like a good fit.
- Output ONLY JSON: {{"message": "..."}}
"""
        else:  # linkedin_dm
            prompt = f"""
Draft a direct LinkedIn Message / InMail to a recruiter or hiring manager.
Recipient: {recipient_name} ({recipient_title} at {company_name})
Target Role: {job_title or 'Software / AI Engineer'}
Job Description snippet: {(job_description or '')[:400]}
Candidate Context: {user_context}

Rules:
- Under 150 words.
- Concise, high signal, clear value proposition.
- Output ONLY JSON: {{"message": "..."}}
"""

        try:
            final_prompt = system_prompt + "\n" + prompt
            raw_response = asyncio.run(query_llm_fallback(question=final_prompt, profile_context=user_context))
            if raw_response:
                # Clean code blocks if present
                clean_resp = raw_response.strip()
                if clean_resp.startswith("```json"):
                    clean_resp = clean_resp[7:]
                if clean_resp.startswith("```"):
                    clean_resp = clean_resp[3:]
                if clean_resp.endswith("```"):
                    clean_resp = clean_resp[:-3]
                
                try:
                    data = json.loads(clean_resp.strip())
                    subject = data.get("subject", "")
                    message = data.get("message", clean_resp.strip())
                except json.JSONDecodeError:
                    subject = ""
                    message = clean_resp.strip()
            else:
                subject, message = self._fallback_template(
                    channel, recipient_name, company_name, job_title
                )
        except Exception as e:
            logger.warning(f"LLM outreach generation failed: {e}. Using fallback template.")
            subject, message = self._fallback_template(
                channel, recipient_name, company_name, job_title
            )

        return {
            "channel": channel,
            "subject": subject,
            "message": message,
            "character_count": len(message),
        }

    def _fallback_template(
        self, channel: str, recipient_name: str, company_name: str, job_title: Optional[str]
    ) -> tuple[str, str]:
        role = job_title or "Software Engineer"
        user_name = "Applicant"
        results_name = self.vector_db.query_personal_profile("name", n_results=1)
        if results_name.get("documents"):
            user_name = results_name["documents"][0]

        if channel == "linkedin_connection_note":
            return (
                "",
                f"Hi {recipient_name}, I'm an engineer specializing in Playwright automation and AI agents. Following {company_name}'s tech work and would love to connect!",
            )
        elif channel == "cold_email":
            return (
                f"{role} Application / Exploration - {user_name}",
                f"Hi {recipient_name},\n\nI've been following {company_name}'s recent work and am very interested in the {role} position.\n\nI build resilient backend microservices and Playwright automation frameworks. I'd love to share my resume and learn more about your team's current technical priorities.\n\nWould you be open to a quick 10-minute chat this week?\n\nThanks,\n{user_name}",
            )
        elif channel == "referral_request":
            return (
                "",
                f"Hi {recipient_name}, I saw an open {role} role at {company_name} and admire the team's engineering culture. If you're open to it, I'd love to share my portfolio and see if you'd be comfortable referring me. No worries either way!",
            )
        else:
            return (
                "",
                f"Hi {recipient_name}, I noticed the open {role} role at {company_name}. I specialize in QA automation and AI agent orchestration. I'd love to share my resume if your team is actively reviewing candidates!",
            )


if __name__ == "__main__":
    generator = ColdOutreachGenerator()
    result = generator.generate_outreach(
        recipient_name="Rahul Sharma",
        recipient_title="Engineering Director",
        company_name="Razorpay",
        job_title="Senior Automation Engineer",
        channel="cold_email",
    )
    print("Subject:", result["subject"])
    print("Body:\n", result["message"])

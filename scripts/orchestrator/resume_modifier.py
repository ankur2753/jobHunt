#!/usr/bin/env python3
"""
Resume Modifier Module for Automated Job Search Agent.
Dynamically tailors master resume using LLM selection, and renders
executive ATS-compliant PDFs and PNG preview screenshots.
"""

import sys
import os
import argparse
import asyncio
import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.common_stuff.generate_pretty_resume import build_resume_html

logger = logging.getLogger("resume_modifier")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def scrape_job_description(url: str) -> str:
    """Scrapes job description text from a job URL using Playwright."""
    logger.info(f"Scraping job description from: {url}")
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)
        text = await page.evaluate("() => document.body.innerText")
        await browser.close()
        return text or ""


def load_master_profile() -> dict:
    """Loads master user details from personal_details.json."""
    pd_path = PROJECT_ROOT / "personal_details" / "personal_details.json"
    if pd_path.exists():
        try:
            return json.loads(pd_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Error loading personal_details.json: {e}")

    raise ValueError("personal_details.json not found or invalid.")


def tailor_resume_data_for_job(company: str, job_title: str, jd_text: str) -> dict:
    """
    Uses the LLM via agy CLI to select the best resume items from the master bank.
    """
    master_bank = load_master_profile()
    
    prompt = f"""You are an expert technical recruiter and resume writer.
Given the following Job Description and the candidate's Master Bank of resume details, return ONLY a lightweight JSON mapping of the best items to select for this specific job. 
Ensure the total content fits on a single A4 page.
Do NOT include any extra text, only the JSON.

Job Company: {company}
Job Title: {job_title}
Job Description:
{jd_text[:4000]}

Master Bank:
{json.dumps(master_bank, indent=2)}

Return a JSON with this exact schema:
{{
  "summary_type": "string", // select the best key from Master Bank's 'summaries'
  "selected_skill_categories": ["string"], // Select 3-4 most relevant keys from 'skills'
  "experience": [
    {{
      "title": "string", // exact title from master bank experience
      "company": "string", // exact company from master bank experience
      "selected_bullet_indices": [0, 1, ...] // 3-4 indices of bullets in the Master Bank that best match the JD
    }}
  ],
  "selected_project_indices": [0, ...] // 1-2 indices of projects in Master Bank
}}"""

    logger.info("Calling LLM to select resume items...")
    from scripts.common_stuff.agent_runtime import AgentRuntime
    result = AgentRuntime.invoke(prompt)
    
    if result.returncode != 0:
        logger.error(f"agy CLI failed: {result.stderr}")
        
    output = result.stdout.strip()
    if not output and result.stderr:
        output = result.stderr.strip()
    
    # Extract JSON if markdown formatting is present
    if "```json" in output:
        output = output.split("```json")[1].split("```")[0].strip()
    elif "```" in output:
        output = output.split("```")[1].split("```")[0].strip()
        
    try:
        selection = json.loads(output)
    except json.JSONDecodeError as e:
        start = output.find('{')
        end = output.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                selection = json.loads(output[start:end+1])
            except json.JSONDecodeError as inner_e:
                logger.error(f"Failed to parse LLM output from braces: {output}")
                raise inner_e
        else:
            logger.error(f"Failed to parse LLM output as JSON: {output}")
            raise e
        
    # Assemble the final resume data
    summary_type = selection.get("summary_type")
    summary = master_bank.get("summaries", {}).get(summary_type, list(master_bank.get("summaries", {}).values())[0])
    
    skills = {}
    for cat in selection.get("selected_skill_categories", []):
        if cat in master_bank.get("skills", {}):
            skills[cat] = master_bank["skills"][cat]
            
    experience = []
    for sel_exp in selection.get("experience", []):
        for master_exp in master_bank.get("experience", []):
            if master_exp["title"] == sel_exp["title"] and master_exp["company"] == sel_exp["company"]:
                bullets = [master_exp["bullets"][i] for i in sel_exp.get("selected_bullet_indices", []) if i < len(master_exp["bullets"])]
                experience.append({
                    "title": master_exp["title"],
                    "company": master_exp["company"],
                    "duration": master_exp["duration"],
                    "bullets": bullets
                })
                break
                
    projects = []
    for idx in selection.get("selected_project_indices", []):
        if idx < len(master_bank.get("projects", [])):
            projects.append(master_bank["projects"][idx])
            
    return {
        "name": master_bank.get("name", "ANKUR KUMAR").upper(),
        "location": master_bank.get("location", "Bengaluru, Karnataka"),
        "email": master_bank.get("email", "ankur2753.ak@gmail.com"),
        "linkedin": master_bank.get("linkedin", "https://www.linkedin.com/in/shootingdragon/"),
        "github": master_bank.get("github", "https://github.com/ankur2753"),
        "summary": summary,
        "skills": skills,
        "experience": experience,
        "projects": projects,
        "education": master_bank.get("education", [])
    }


async def generate_tailored_resume(company: str, job_title: str, jd_text: str = "", jd_url: str = "") -> dict:
    """
    Main entrypoint function to generate tailored HTML, executive PDF, and preview PNG.
    """
    if jd_url and not jd_text:
        try:
            jd_text = await scrape_job_description(jd_url)
        except Exception as e:
            logger.warning(f"Could not scrape JD URL ({e}); proceeding with title matching.")

    resume_data = tailor_resume_data_for_job(company, job_title, jd_text)

    # Sanitize file paths
    safe_company = "".join(c for c in (company or "Company") if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_") or "Company"
    safe_title = "".join(c for c in (job_title or "Role") if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_") or "Role"

    out_dir = PROJECT_ROOT / "resumes" / "tailored"
    out_dir.mkdir(parents=True, exist_ok=True)

    base_name = f"Resume_{safe_company}_{safe_title}_Ankur_Kumar"
    pdf_path = out_dir / f"{base_name}.pdf"
    html_path = out_dir / f"{base_name}.html"

    # Write HTML
    html_content = build_resume_html(resume_data)
    html_path.write_text(html_content, encoding="utf-8")

    # Render PDF & PNG Preview
    from playwright.async_api import async_playwright

    scratch_dir = PROJECT_ROOT / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    png_path = scratch_dir / f"{safe_company.lower()}_resume_preview.png"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # PDF Page
        page = await browser.new_page()
        await page.set_content(html_content, wait_until="load")
        await page.pdf(
            path=str(pdf_path),
            print_background=True,
            margin={"top": "0.35in", "bottom": "0.35in", "left": "0.4in", "right": "0.4in"},
            format="A4"
        )

        # PNG Preview Page
        preview_page = await browser.new_page(viewport={"width": 850, "height": 1100})
        await preview_page.set_content(html_content, wait_until="load")
        await preview_page.screenshot(path=str(png_path), full_page=True)

        await browser.close()

    logger.info(f"Generated PDF: {pdf_path}")
    logger.info(f"Generated PNG Preview: {png_path}")

    return {
        "pdf_path": str(pdf_path.resolve()),
        "html_path": str(html_path.resolve()),
        "png_path": str(png_path.resolve()),
        "data": resume_data
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Job Search Agent - Resume Modifier")
    parser.add_argument("--company", required=True, help="Target Company Name (e.g., Apple, BrowserStack)")
    parser.add_argument("--job-title", required=True, help="Target Job Title")
    parser.add_argument("--jd-url", help="Job Posting URL")
    parser.add_argument("--jd-text", help="Raw Job Description Text")

    args = parser.parse_args()

    result = asyncio.run(generate_tailored_resume(
        company=args.company,
        job_title=args.job_title,
        jd_text=args.jd_text or "",
        jd_url=args.jd_url or ""
    ))

    print("\n✅ SUCCESS: Resume Generated!")
    print(f"PDF Path: {result['pdf_path']}")
    print(f"Preview PNG Path: {result['png_path']}")

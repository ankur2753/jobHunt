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
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.common_stuff.generate_pretty_resume import build_resume_html

logger = logging.getLogger("cli_tailor")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

OUTPUT_DIR = PROJECT_ROOT / "resumes" / "tailored"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_master_profile() -> dict:
    """Loads master user details from personal_details.json."""
    pd_path = PROJECT_ROOT / "personal_details" / "personal_details.json"
    if pd_path.exists():
        try:
            return json.loads(pd_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Error loading personal_details.json: {e}")

    raise ValueError("personal_details.json not found or invalid.")


async def fetch_job_details(url: str = None, jd_text: str = None, headed: bool = False) -> dict:
    """Extracts raw text from URL."""
    raw_text = ""
    if url:
        logger.info(f"Fetching URL content from {url}...")
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=not headed)
                page = await browser.new_page()
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    await page.wait_for_timeout(5000)
                except Exception as net_err:
                    logger.warning(f"Playwright navigation notice ({net_err}). Extracting rendered DOM content anyway...")
                
                raw_text = await page.evaluate("document.body.innerText")
                await browser.close()
        except Exception as e:
            logger.warning(f"Playwright web fetch failed: {e}. Falling back to text parsing.")

    if not raw_text and jd_text:
        raw_text = jd_text

    if not raw_text:
        raise ValueError("No job description text or reachable URL provided.")

    job_info = {
        "title": "Unknown_Role",
        "company": "Unknown_Company",
        "raw_text": raw_text
    }
    
    # Extract Title and Company from raw text
    from scripts.common_stuff.prompt_manager import load_prompt
    prompt = load_prompt("cli_tailor_extract", raw_text=raw_text[:2000])
    try:
        from scripts.common_stuff.agent_runtime import AgentRuntime
        res = AgentRuntime.invoke(prompt)
        if res.returncode == 0:
            out = res.stdout.strip()
            if "```json" in out:
                out = out.split("```json")[1].split("```")[0].strip()
            elif "```" in out:
                out = out.split("```")[1].split("```")[0].strip()
            
            try:
                parsed = json.loads(out)
            except json.JSONDecodeError:
                start = out.find('{')
                end = out.rfind('}')
                if start != -1 and end != -1 and end > start:
                    parsed = json.loads(out[start:end+1])
                else:
                    parsed = {}

            if isinstance(parsed, dict):
                title = parsed.get("title")
                company = parsed.get("company")
                if title and isinstance(title, str) and title.strip():
                    job_info["title"] = title.strip()
                if company and isinstance(company, str) and company.strip():
                    job_info["company"] = company.strip()
    except Exception as e:
        logger.warning(f"Failed to extract title/company via LLM: {e}")
        
    return job_info


def generate_cover_letter_html(name: str, company: str, title: str, letter_paragraphs: list) -> str:
    name = (name if isinstance(name, str) and name.strip() else "Candidate").strip()
    company = (company if isinstance(company, str) and company.strip() else "Unknown_Company").strip()
    title = (title if isinstance(title, str) and title.strip() else "Unknown_Role").strip()
    today_str = datetime.now().strftime("%B %d, %Y")
    paragraphs = letter_paragraphs or [
        "Dear Hiring Manager,",
        f"I am writing to express my strong interest in the <strong>{title}</strong> position at {company}.",
        "I would welcome the opportunity to discuss how my automation experience and technical problem-solving skills can support your team. Thank you for your time and consideration."
    ]
    paragraphs_html = "\n".join([f"<p>{p}</p>" if not p.startswith("<p>") else p for p in paragraphs])
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{name} - Cover Letter - {company}</title>
<style>
    @page {{ size: A4; margin: 0.5in 0.6in; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #1e293b;
        background-color: #ffffff;
        line-height: 1.5;
        font-size: 10pt;
    }}
    .header {{ border-bottom: 2px solid #0f172a; padding-bottom: 10px; margin-bottom: 20px; }}
    .header h1 {{ font-size: 22pt; font-weight: 800; color: #0f172a; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }}
    .contact-info {{ font-size: 9pt; color: #475569; font-weight: 500; }}
    .contact-info a {{ color: #0284c7; text-decoration: none; }}
    .contact-info span {{ margin: 0 6px; color: #94a3b8; }}
    .meta-date {{ font-size: 9.5pt; font-weight: 600; color: #64748b; margin-bottom: 18px; }}
    .recipient-info {{ margin-bottom: 20px; font-size: 9.5pt; color: #334155; line-height: 1.4; }}
    .recipient-info strong {{ color: #0f172a; }}
    .subject {{ font-size: 10.5pt; font-weight: 700; color: #0f172a; margin-bottom: 18px; }}
    .content p {{ margin-bottom: 14px; text-align: justify; color: #334155; }}
    .content strong {{ color: #0f172a; }}
    .signature {{ margin-top: 25px; font-size: 10pt; color: #0f172a; }}
    .signature-name {{ font-weight: 700; margin-top: 5px; }}
</style>
</head>
<body>

<div class="header">
    <h1>{name}</h1>
    <div class="contact-info">
        Bengaluru, Karnataka <span>|</span> <a href="mailto:ankur2753.ak@gmail.com">ankur2753.ak@gmail.com</a> <span>|</span> <a href="https://www.linkedin.com/in/shootingdragon/">LinkedIn</a> <span>|</span> <a href="https://github.com/ankur2753">GitHub</a>
    </div>
</div>

<div class="meta-date">{today_str}</div>

<div class="recipient-info">
    <strong>Hiring Manager / Technical Recruiting Team</strong><br>
    {company}<br>
</div>

<div class="subject">
    SUBJECT: Application for {title}
</div>

<div class="content">
{paragraphs_html}
</div>

<div class="signature">
    Sincerely,<br>
    <div class="signature-name">{name}</div>
</div>

</body>
</html>
"""


async def run_automation(url: str = None, jd_text: str = None, company_override: str = None, role_override: str = None, headed: bool = False) -> dict:
    """Full automation pipeline for resume + cover letter + linkedin message generation."""
    job_info = await fetch_job_details(url=url, jd_text=jd_text, headed=headed)
    
    company = company_override or job_info.get("company")
    role = role_override or job_info.get("title")

    if not company or not isinstance(company, str) or not company.strip():
        company = "Unknown_Company"
    else:
        company = company.strip()

    if not role or not isinstance(role, str) or not role.strip():
        role = "Unknown_Role"
    else:
        role = role.strip()
    
    master_bank = load_master_profile()
    
    from scripts.common_stuff.prompt_manager import load_prompt
    prompt = load_prompt(
        "cli_tailor_tailor",
        company=company,
        role=role,
        job_description=job_info.get('raw_text', '')[:3000],
        master_bank_json=json.dumps(master_bank, indent=2)
    )
    
    logger.info("Calling agy CLI to generate tailored data...")
    from scripts.common_stuff.agent_runtime import AgentRuntime
    result = AgentRuntime.invoke(prompt)
    if result.returncode != 0:
        logger.error(f"agy CLI failed: {result.stderr}")
        
    output = result.stdout.strip()
    if not output and result.stderr:
        output = result.stderr.strip()

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
            except Exception as inner_e:
                logger.error(f"Failed to parse LLM structured JSON from braces: {inner_e}")
                raise inner_e
        else:
            logger.error(f"Failed to parse LLM structured JSON: {e}")
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
            
    parsed_data = {
        "name": master_bank.get("name", "Ankur Kumar"),
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

    resume_html = build_resume_html(parsed_data)
    cover_html = generate_cover_letter_html(
        parsed_data["name"], 
        company, 
        role, 
        selection.get("cover_letter_paragraphs", [
            "Dear Hiring Manager,",
            f"I am writing to express my strong interest in the <strong>{role}</strong> position at {company}.",
            "I would welcome the opportunity to discuss how my automation experience and technical problem-solving skills can support your team. Thank you for your time and consideration."
        ])
    )

    safe_comp = "".join(c for c in (company or "Unknown_Company") if c.isalnum() or c in ("_", "-")).strip() or "Unknown_Company"
    safe_role = "".join(c for c in (role or "Unknown_Role") if c.isalnum() or c in ("_", "-")).strip() or "Unknown_Role"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    resume_pdf_filename = f"Resume_{safe_comp}_{safe_role}_{timestamp}.pdf"
    cover_pdf_filename = f"Cover_Letter_{safe_comp}_{safe_role}_{timestamp}.pdf"

    resume_pdf_path = OUTPUT_DIR / resume_pdf_filename
    cover_pdf_path = OUTPUT_DIR / cover_pdf_filename

    (OUTPUT_DIR / resume_pdf_filename.replace(".pdf", ".html")).write_text(resume_html, encoding="utf-8")
    (OUTPUT_DIR / cover_pdf_filename.replace(".pdf", ".html")).write_text(cover_html, encoding="utf-8")

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headed)

        page1 = await browser.new_page()
        await page1.set_content(resume_html, wait_until="load")
        await page1.pdf(path=str(resume_pdf_path), format="A4", print_background=True, margin={"top": "0.35in", "bottom": "0.35in", "left": "0.4in", "right": "0.4in"})
        await page1.close()

        page2 = await browser.new_page()
        await page2.set_content(cover_html, wait_until="load")
        await page2.pdf(path=str(cover_pdf_path), format="A4", print_background=True, margin={"top": "0.5in", "bottom": "0.5in", "left": "0.6in", "right": "0.6in"})
        await page2.close()

        await browser.close()

    result = {
        "status": "success",
        "company": company,
        "role": role,
        "resume_pdf": str(resume_pdf_path.resolve()),
        "cover_letter_pdf": str(cover_pdf_path.resolve()),
        "linkedin_dm": selection.get("linkedin_dm", "")
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Automated Resume & Cover Letter Tailoring CLI Interface for Telegram / Web Bots")
    parser.add_argument("--url", type=str, help="Target Job URL to scrape & analyze")
    parser.add_argument("--jd-text", type=str, help="Raw Job Description text")
    parser.add_argument("--company", type=str, help="Company name override")
    parser.add_argument("--role", type=str, help="Role title override")
    parser.add_argument("--json", action="store_true", help="Print result as clean JSON string")
    parser.add_argument("--headed", action="store_true", help="Run Playwright in headed mode")

    args = parser.parse_args()

    if not args.url and not args.jd_text:
        print(json.dumps({"status": "error", "message": "Either --url or --jd-text must be provided."}))
        sys.exit(1)

    result = asyncio.run(run_automation(
        url=args.url,
        jd_text=args.jd_text,
        company_override=args.company,
        role_override=args.role,
        headed=args.headed
    ))

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Company: {result['company']}")
        print(f"Role: {result['role']}")
        print(f"Resume PDF: {result['resume_pdf']}")
        print(f"Cover Letter PDF: {result['cover_letter_pdf']}")
        print(f"\nLinkedIn DM:\n{result['linkedin_dm']}")


if __name__ == "__main__":
    main()

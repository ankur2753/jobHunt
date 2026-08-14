import sys
import os
import argparse
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime

# 1. Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.common_stuff.llm_fallback import query_llm_fallback

logger = logging.getLogger("cli_tailor")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_MASTER_RESUME_PATH = PROJECT_ROOT / "resumes" / "resume_master.md"
OUTPUT_DIR = PROJECT_ROOT / "resumes" / "tailored"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def fetch_job_details(url: str = None, jd_text: str = None) -> dict:
    """Extracts job title, company name, location, and requirements from URL or raw text using LLM."""
    raw_text = ""
    if url:
        logger.info(f"Fetching URL content from {url}...")
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(3000)
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

    prompt = (
        "Extract the key job details from the following job posting text in JSON format.\n"
        "JSON keys required: 'title', 'company', 'location', 'must_have_skills', 'description_summary'\n\n"
        f"JOB POSTING TEXT:\n{raw_text[:4000]}"
    )
    
    response = await query_llm_fallback(question=prompt)
    
    job_info = {
        "title": "Software Technologist / Automation Engineer",
        "company": "Target Company",
        "location": "Bengaluru, Karnataka / Remote",
        "must_have_skills": [],
        "description_summary": raw_text[:500]
    }
    
    try:
        clean_resp = response.strip() if response else ""
        if "```json" in clean_resp:
            clean_resp = clean_resp.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_resp:
            clean_resp = clean_resp.split("```")[1].split("```")[0].strip()
        parsed = json.loads(clean_resp)
        job_info.update(parsed)
    except Exception:
        logger.warning("Could not parse LLM job JSON, using smart regex extraction fallback.")
        
    # Heuristic/Regex fallback for Company and Title if LLM did not populate them
    if job_info.get("company") == "Target Company" and raw_text:
        if "Cohesity" in raw_text:
            job_info["company"] = "Cohesity"
        elif "Philips" in raw_text:
            job_info["company"] = "Philips"
        elif "Apple" in raw_text:
            job_info["company"] = "Apple"
        elif "SafeSend" in raw_text:
            job_info["company"] = "SafeSend"

    if (job_info.get("title") in ("Target Role", "Software Technologist / Automation Engineer")) and raw_text:
        # Look for explicit job title lines in common job board formats
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        for line in lines[:50]:
            if any(kw in line for kw in ["Engineer", "Developer", "Technologist", "Architect", "SDET", "QA", "Specialist", "Manager"]):
                if len(line) < 100 and not line.startswith("http") and "VIEW" not in line and "APPLY" not in line:
                    job_info["title"] = line
                    break

    job_info["raw_text"] = raw_text
    return job_info


def generate_resume_html(data: dict) -> str:
    name = data.get("name", "Ankur Kumar")
    location = data.get("location", "Bengaluru, Karnataka")
    email = data.get("email", "ankur2753.ak@gmail.com")
    linkedin = data.get("linkedin", "https://www.linkedin.com/in/shootingdragon/")
    github = data.get("github", "https://github.com/ankur2753")
    summary = data.get("summary", "")
    skills = data.get("skills", {})
    experience = data.get("experience", [])
    projects = data.get("projects", [])
    education = data.get("education", [])

    skills_html = ""
    for category, skill_list in skills.items():
        skills_html += f"""
        <div class="skill-group">
            <span class="skill-category">{category}:</span>
            <span class="skill-items">{", ".join(skill_list)}</span>
        </div>
        """

    exp_html = ""
    for job in experience:
        bullets_list = "".join([f"<li>{b}</li>" for b in job.get("bullets", [])])
        exp_html += f"""
        <div class="job-block">
            <div class="job-header">
                <div>
                    <span class="job-title">{job.get('title')}</span>
                    <span class="job-company"> | {job.get('company')}</span>
                </div>
                <div class="job-date">{job.get('duration')}</div>
            </div>
            <ul class="job-bullets">
                {bullets_list}
            </ul>
        </div>
        """

    proj_html = ""
    if projects:
        proj_blocks = ""
        for proj in projects:
            bullets_list = "".join([f"<li>{b}</li>" for b in proj.get("bullets", [])])
            proj_blocks += f"""
            <div class="job-block">
                <div class="job-header">
                    <div><span class="job-title">{proj.get('title')}</span></div>
                    <div class="job-date">{proj.get('date', '')}</div>
                </div>
                <ul class="job-bullets">
                    {bullets_list}
                </ul>
            </div>
            """
        proj_html = f"""
        <div class="section">
            <div class="section-title">Selected Engineering Projects</div>
            {proj_blocks}
        </div>
        """

    edu_html = ""
    for edu in education:
        edu_html += f"""
        <div class="edu-block">
            <div class="edu-header">
                <div>
                    <span class="edu-degree">{edu.get('degree')}</span>
                    <span class="edu-school"> — {edu.get('school')}</span>
                </div>
                <div class="edu-year">{edu.get('year')}</div>
            </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{name} - Resume</title>
<style>
    @page {{
        size: A4;
        margin: 0.4in 0.45in;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #1e293b;
        background-color: #ffffff;
        line-height: 1.42;
        font-size: 9.5pt;
    }}
    .header {{
        text-align: center;
        border-bottom: 2px solid #0f172a;
        padding-bottom: 8px;
        margin-bottom: 14px;
    }}
    .header h1 {{
        font-size: 22pt;
        font-weight: 800;
        letter-spacing: 1px;
        color: #0f172a;
        text-transform: uppercase;
        margin-bottom: 4px;
    }}
    .contact-info {{
        font-size: 9pt;
        color: #475569;
        font-weight: 500;
    }}
    .contact-info a {{ color: #0284c7; text-decoration: none; }}
    .contact-info span {{ margin: 0 6px; color: #94a3b8; }}

    .section {{ margin-bottom: 14px; }}
    .section-title {{
        font-size: 10.5pt;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        color: #0f172a;
        border-bottom: 1.5px solid #cbd5e1;
        padding-bottom: 3px;
        margin-bottom: 8px;
    }}
    .summary-text {{ font-size: 9.5pt; color: #334155; text-align: justify; line-height: 1.45; }}
    .skill-group {{ margin-bottom: 5px; font-size: 9.3pt; line-height: 1.4; }}
    .skill-category {{ font-weight: 700; color: #0f172a; }}
    .skill-items {{ color: #334155; }}
    .job-block {{ margin-bottom: 11px; }}
    .job-header {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 3px; }}
    .job-title {{ font-size: 10pt; font-weight: 700; color: #0f172a; }}
    .job-company {{ font-size: 9.5pt; font-weight: 600; color: #0369a1; }}
    .job-date {{ font-size: 8.8pt; font-weight: 600; color: #64748b; text-align: right; }}
    .job-bullets {{ padding-left: 18px; color: #334155; }}
    .job-bullets li {{ margin-bottom: 3.5px; font-size: 9.3pt; line-height: 1.4; }}
    .job-bullets strong {{ color: #0f172a; font-weight: 600; }}
    .edu-block {{ margin-bottom: 4px; }}
    .edu-header {{ display: flex; justify-content: space-between; align-items: baseline; }}
    .edu-degree {{ font-weight: 700; font-size: 9.5pt; color: #0f172a; }}
    .edu-school {{ font-weight: 500; font-size: 9.5pt; color: #475569; }}
    .edu-year {{ font-size: 8.8pt; font-weight: 600; color: #64748b; }}
</style>
</head>
<body>

<div class="header">
    <h1>{name}</h1>
    <div class="contact-info">
        {location} <span>|</span> <a href="mailto:{email}">{email}</a> <span>|</span> <a href="{linkedin}" target="_blank">LinkedIn</a> <span>|</span> <a href="{github}" target="_blank">GitHub</a>
    </div>
</div>

<div class="section">
    <div class="section-title">Professional Summary</div>
    <div class="summary-text">{summary}</div>
</div>

<div class="section">
    <div class="section-title">Technical Skills</div>
    {skills_html}
</div>

<div class="section">
    <div class="section-title">Professional Experience</div>
    {exp_html}
</div>

{proj_html}

<div class="section">
    <div class="section-title">Education</div>
    {edu_html}
</div>

</body>
</html>
"""
    return html


def generate_cover_letter_html(name: str, company: str, title: str, letter_paragraphs: list) -> str:
    today_str = datetime.now().strftime("%B %d, %Y")
    paragraphs_html = "\n".join([f"<p>{p}</p>" if not p.startswith("<p>") else p for p in letter_paragraphs])
    
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


async def run_automation(url: str = None, jd_text: str = None, company_override: str = None, role_override: str = None) -> dict:
    """Full automation pipeline for resume + cover letter + linkedin message generation."""
    job_info = await fetch_job_details(url=url, jd_text=jd_text)
    
    company = company_override or job_info.get("company", "Target Company")
    role = role_override or job_info.get("title", "Target Role")
    
    master_md = DEFAULT_MASTER_RESUME_PATH.read_text(encoding="utf-8") if DEFAULT_MASTER_RESUME_PATH.exists() else ""
    
    prompt = (
        f"You are an expert technical recruiter and resume writer.\n"
        f"Target Job: {role} at {company}\n"
        f"Job Description: {job_info.get('raw_text', '')[:3000]}\n\n"
        f"Master Resume:\n{master_md}\n\n"
        "Generate a tailored JSON structure with keys:\n"
        "1. 'summary': 2-3 line executive summary targeted at role\n"
        "2. 'skills': dictionary of categories -> array of skill strings\n"
        "3. 'experience': array of jobs with 'title' (use 'Senior QA Engineer' for SafeSend), 'company', 'duration', 'bullets' (3-5 strong bullet strings with bold html <strong> tags for key tools/metrics)\n"
        "4. 'projects': array of 2 projects with 'title', 'date', 'bullets'\n"
        "5. 'education': array of education entries\n"
        "6. 'cover_letter_paragraphs': array of 4 paragraph strings for cover letter\n"
        "7. 'linkedin_dm': a short 3-sentence outreach message for recruiters\n\n"
        "Ensure exact JSON output only."
    )
    
    response = await query_llm_fallback(question=prompt)
    
    parsed_data = {}
    try:
        clean_resp = response.strip()
        if "```json" in clean_resp:
            clean_resp = clean_resp.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_resp:
            clean_resp = clean_resp.split("```")[1].split("```")[0].strip()
        parsed_data = json.loads(clean_resp)
    except Exception as e:
        logger.error(f"Failed to parse LLM structured JSON: {e}")
        parsed_data = {
            "summary": f"Senior QA & Software Automation Engineer with 3+ years of experience designing scalable test framework architectures, REST & SOAP API test suites, and high-performance microservices targeted at {role} at {company}. Specialized in Java (Selenium), Python (Playwright), BDD frameworks, and Azure cloud infrastructure. Proven track record in parallelizing test pipelines to reduce execution runtime by 25% and conducting deep-dive log root-cause analysis in JIRA.",
            "skills": {
                "Test Automation & BDD": ["Java", "Selenium WebDriver", "Playwright", "Pytest", "BDD (Cucumber / Behave)", "E2E Framework Design", "Cross-Browser Testing"],
                "API & Web Services Testing": ["REST API Automation", "SOAP Web Services", "Postman", "Contract Validation", "JSON/XML Payload Verification"],
                "Languages & Databases": ["Java", "Python", "C#", "JavaScript", "React.js", "ASP.NET Core", "SQL", "MSSQL", "MongoDB"],
                "Cloud, DevOps & Infrastructure": ["Azure (VMs, Pipelines)", "AWS", "Docker", "Kubernetes", "Git", "CI/CD Test Pipelines", "Virtualization Concepts"],
                "Quality Engineering & Tools": ["Test Strategy & Design", "Requirement Traceability (RTM)", "Root Cause Log Analysis", "JIRA", "Defect Lifecycle", "Agile/Scrum"]
            },
            "experience": [
                {
                    "title": "Senior QA Engineer",
                    "company": "SafeSend Technologies",
                    "duration": "Feb 2023 – Present",
                    "bullets": [
                        f"Architected and automated robust test suites using <strong>Java (Selenium)</strong> and <strong>Python (Playwright)</strong> to validate critical application workflows aligned with {role} requirements.",
                        "Implemented parallel test execution workloads across <strong>Azure VMs</strong>, achieving a <strong>25% reduction in total execution runtime</strong>.",
                        "Designed automated validation for <strong>REST and SOAP web services</strong>, executing payload structure, HTTP status, and API contract verification.",
                        "Engineered full-stack web applications from scratch featuring decoupled microservice backends, <strong>React.js</strong> single-page UI, and <strong>MSSQL</strong> databases.",
                        "Performed structured <strong>log analysis and root-cause defect investigation</strong> using <strong>JIRA</strong>, partnering with core developers to ensure rapid resolution of software defects."
                    ]
                },
                {
                    "title": "Graduate Engineering Trainee",
                    "company": "SafeSend Technologies",
                    "duration": "Jul 2022 – Feb 2023",
                    "bullets": [
                        "Engineered high-throughput <strong>ASP.NET REST APIs</strong> implementing <strong>CQRS and SAGA</strong> architectural patterns for modular backend processing.",
                        "Integrated <strong>BDD specifications (Cucumber/Behave)</strong> to align business logic requirements directly with automated regression suites.",
                        "Optimized MSSQL database performance via indexing strategies and query tuning, improving backend data retrieval speeds under heavy test loads.",
                        "Migrated legacy monolithic MVC Razor pages to component-based <strong>React.js</strong> single-page interfaces, enhancing maintainability."
                    ]
                },
                {
                    "title": "Front End Intern",
                    "company": "Deloitte",
                    "duration": "May 2022 – Jul 2022",
                    "bullets": [
                        "Developed responsive front-end interfaces with <strong>React.js</strong> and reusable UI component libraries to standardize cross-team development.",
                        "Executed cross-browser compatibility and UI validation checks to guarantee rendering consistency across browser engines."
                    ]
                }
            ],
            "projects": [
                {
                    "title": "Enterprise API & Web Services Automated Test Suite",
                    "date": "2024",
                    "bullets": ["Designed a Java-based API testing harness supporting REST and SOAP request serialization, dynamic assertion checks, and automated HTML execution reporting."]
                },
                {
                    "title": "Cloud VM Parallel Test Infrastructure",
                    "date": "2023",
                    "bullets": ["Built Dockerized test execution containers deployed to Azure Virtual Machines with integrated CI/CD trigger scripts for automated nightly regression runs."]
                }
            ],
            "education": [
                {
                    "degree": "B.E., Computer Science Engineering",
                    "school": "Sapthagiri College Of Engineering",
                    "year": "2023"
                }
            ],
            "cover_letter_paragraphs": [
                "Dear Hiring Manager,",
                f"I am writing to express my strong interest in the <strong>{role}</strong> position at {company}. With over 3 years of hands-on experience designing automated test suites, validating web services, and optimizing cloud-based test infrastructure, I am confident in my ability to deliver immediate value.",
                f"In my current role as Senior QA Engineer at SafeSend Technologies, I have built end-to-end test automation solutions using Java/Selenium and Python/Playwright to validate complex software workflows. A key highlight was implementing parallel execution workloads across Azure VMs, which reduced total suite runtime by 25%.",
                "I would welcome the opportunity to discuss how my automation experience and technical problem-solving skills can support your team. Thank you for your time and consideration."
            ],
            "linkedin_dm": f"Hi! I noticed the open {role} position at {company} and wanted to reach out. As a Senior QA Engineer specializing in Java/Selenium and Playwright test automation, I'd love to connect and share how my background fits your team's goals!"
        }

    parsed_data["name"] = "Ankur Kumar"
    parsed_data["location"] = "Bengaluru, Karnataka"
    parsed_data["email"] = "ankur2753.ak@gmail.com"
    parsed_data["linkedin"] = "https://www.linkedin.com/in/shootingdragon/"
    parsed_data["github"] = "https://github.com/ankur2753"

    resume_html = generate_resume_html(parsed_data)
    cover_html = generate_cover_letter_html("Ankur Kumar", company, role, parsed_data.get("cover_letter_paragraphs", []))

    safe_comp = "".join(c for c in company if c.isalnum() or c in ("_", "-")).strip() or "Company"
    safe_role = "".join(c for c in role if c.isalnum() or c in ("_", "-")).strip() or "Role"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    resume_pdf_filename = f"Resume_{safe_comp}_{safe_role}_{timestamp}.pdf"
    cover_pdf_filename = f"Cover_Letter_{safe_comp}_{safe_role}_{timestamp}.pdf"

    resume_pdf_path = OUTPUT_DIR / resume_pdf_filename
    cover_pdf_path = OUTPUT_DIR / cover_pdf_filename

    (OUTPUT_DIR / resume_pdf_filename.replace(".pdf", ".html")).write_text(resume_html, encoding="utf-8")
    (OUTPUT_DIR / cover_pdf_filename.replace(".pdf", ".html")).write_text(cover_html, encoding="utf-8")

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

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
        "linkedin_dm": parsed_data.get("linkedin_dm", "")
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Automated Resume & Cover Letter Tailoring CLI Interface for Telegram / Web Bots")
    parser.add_argument("--url", type=str, help="Target Job URL to scrape & analyze")
    parser.add_argument("--jd-text", type=str, help="Raw Job Description text")
    parser.add_argument("--company", type=str, help="Company name override")
    parser.add_argument("--role", type=str, help="Role title override")
    parser.add_argument("--json", action="store_true", help="Print result as clean JSON string")

    args = parser.parse_args()

    if not args.url and not args.jd_text:
        print(json.dumps({"status": "error", "message": "Either --url or --jd-text must be provided."}))
        sys.exit(1)

    result = asyncio.run(run_automation(
        url=args.url,
        jd_text=args.jd_text,
        company_override=args.company,
        role_override=args.role
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

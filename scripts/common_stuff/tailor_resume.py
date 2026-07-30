import sys
import os
import argparse
import asyncio
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

# 1. Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.common_stuff.llm_fallback import query_llm_fallback

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_MASTER_RESUME = """# Jane Doe
Bengaluru, Karnataka | jane.doe@example.com | https://www.linkedin.com/in/janedoe/

## Professional Summary
Software Engineer with 3+ years of experience in designing and building automated test suites, web applications, and scalable microservices. Specialized in Python, Playwright, React.js, and Cloud environments.

## Skills
- **Automation & Testing**: Playwright, Pytest, QA Automation, Test Framework Design, API Testing
- **Languages & Frameworks**: Python, JavaScript, React.js, Node.js, HTML5, CSS3, SQL
- **Cloud & DevOps**: AWS, Azure, Docker, Kubernetes, Git, CI/CD Pipelines
- **Architecture & DB**: Microservices Architecture, REST APIs, MSSQL, MongoDB

## Work Experience

### Software Engineer | Tech Corp
*Jan 2023 - Present*
- Developed full-stack web applications and scalable REST APIs.
- Built end-to-end automated testing pipelines with Playwright.
- Optimized database performance and reduced API response times.

## Education
- **B.E., Computer Science Engineering** - State Engineering College (2023)
"""


class ATSResumeTailor:
    def __init__(self, master_path: Optional[str] = None, output_dir: Optional[str] = None):
        project_root = Path(__file__).resolve().parents[2]
        
        if master_path:
            self.master_path = Path(master_path)
        else:
            self.master_path = project_root / "resumes" / "resume_master.md"
            
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = project_root / "resumes" / "tailored"

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure master resume exists
        self._ensure_master_resume()

    def _ensure_master_resume(self):
        """Creates resumes/resume_master.md if missing."""
        self.master_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.master_path.exists():
            logger.info(f"Creating default master resume at {self.master_path}")
            self.master_path.write_text(DEFAULT_MASTER_RESUME, encoding="utf-8")

    def _markdown_to_html(self, markdown_text: str) -> str:
        """Converts Markdown text to HTML string with ATS single-column CSS."""
        try:
            from markdown_it import MarkdownIt
            md = MarkdownIt()
            body_html = md.render(markdown_text)
        except ImportError:
            body_html = f"<pre>{markdown_text}</pre>"

        html_document = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: letter;
    margin: 0.5in;
  }}
  html, body {{
    font-family: 'Helvetica', 'Arial', sans-serif;
    font-size: 9.5pt;
    line-height: 1.4;
    color: #111111;
    background-color: #ffffff;
    margin: 0;
    padding: 0;
  }}
  body {{
    padding: 0.5in;
  }}
  h1 {{
    font-size: 16pt;
    margin-top: 0;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1.5px solid #222222;
    padding-bottom: 3px;
  }}
  h2 {{
    font-size: 11pt;
    margin-top: 10px;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid #cccccc;
    padding-bottom: 2px;
    color: #222222;
  }}
  h3 {{
    font-size: 10pt;
    margin-top: 8px;
    margin-bottom: 2px;
    font-weight: bold;
    color: #111111;
  }}
  p {{
    margin-top: 2px;
    margin-bottom: 4px;
  }}
  ul {{
    margin-top: 2px;
    margin-bottom: 6px;
    padding-left: 18px;
  }}
  li {{
    margin-bottom: 2px;
  }}
  strong {{
    font-weight: 600;
  }}
  em {{
    font-style: italic;
  }}
  a {{
    color: #111111;
    text-decoration: none;
  }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""
        return html_document

    def _clean_llm_output(self, text: str) -> str:
        """Strips markdown code blocks and excess whitespace from LLM response."""
        if not text:
            return ""
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    async def tailor_resume(self, job_description: str, job_title: str = "", company_name: str = "") -> str:
        """
        Reads master resume, queries LLM fallback to tailor skills/bullets for target job description,
        formats to HTML with single-column CSS, and outputs an ATS-compliant PDF via Playwright.
        Returns the absolute path string to the generated PDF.
        """
        if not self.master_path.exists():
            self._ensure_master_resume()

        master_md = self.master_path.read_text(encoding="utf-8")

        prompt = (
            f"You are an expert ATS Resume Optimizer.\n"
            f"Target Job Title: {job_title}\n"
            f"Target Company: {company_name}\n\n"
            f"Task:\n"
            f"Tailor the master resume provided below to match the job description:\n"
            f"1. Re-order skills to prioritize those most relevant to the target job description.\n"
            f"2. Highlight matching bullet points and emphasize relevant achievements.\n"
            f"3. Maintain clean, structured single-column Markdown formatting.\n\n"
            f"HARD GUARDRAIL:\n"
            f"NEVER invent employers, job titles, dates, or metrics not present in the master resume.\n\n"
            f"Return ONLY the tailored resume content in clean Markdown format without any markdown backtick code blocks (```) or conversational intro/outro text.\n\n"
            f"--- MASTER RESUME ---\n{master_md}\n\n"
            f"--- JOB DESCRIPTION ---\n{job_description}"
        )

        logger.info(f"Tailoring resume for '{job_title}' at '{company_name}'...")
        llm_response = await query_llm_fallback(question=prompt)
        
        tailored_md = self._clean_llm_output(llm_response) if llm_response else ""
        if not tailored_md:
            logger.warning("LLM response unavailable or empty; falling back to master resume.")
            tailored_md = master_md

        html_content = self._markdown_to_html(tailored_md)

        # Generate output PDF filename
        safe_company = "".join(c for c in company_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_") or "Company"
        safe_title = "".join(c for c in job_title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_") or "Role"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"Resume_{safe_company}_{safe_title}_{timestamp}.pdf"
        output_pdf_path = self.output_dir / pdf_filename

        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html_content, wait_until="load")
            await page.pdf(
                path=str(output_pdf_path),
                print_background=True,
                margin={"top": "0.5in", "bottom": "0.5in", "left": "0.5in", "right": "0.5in"}
            )
            await browser.close()

        abs_pdf_path = str(output_pdf_path.resolve())
        logger.info(f"Successfully generated tailored PDF: {abs_pdf_path}")
        return abs_pdf_path


async def _run_test():
    logger.info("Executing verification test for ATSResumeTailor...")
    tailor = ATSResumeTailor()
    
    sample_jd = (
        "We are looking for a Senior QA Automation Engineer skilled in Python, Playwright, "
        "and Web Application testing. Experience with Azure, CI/CD pipelines, and React.js is a strong plus."
    )
    sample_title = "QA Automation Engineer"
    sample_company = "TechCorp"

    generated_pdf = await tailor.tailor_resume(
        job_description=sample_jd,
        job_title=sample_title,
        company_name=sample_company
    )

    pdf_path = Path(generated_pdf)
    assert pdf_path.exists(), f"Generated PDF does not exist: {generated_pdf}"
    assert pdf_path.stat().st_size > 0, f"Generated PDF is empty: {generated_pdf}"

    print(f"VERIFICATION SUCCESS: Tailored PDF generated at: {generated_pdf} (Size: {pdf_path.stat().st_size} bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dynamic ATS Resume Tailor")
    parser.add_argument("--test", action="store_true", help="Run verification test")
    args = parser.parse_args()

    if args.test:
        asyncio.run(_run_test())
    else:
        print("Run with --test flag to execute verification test.")

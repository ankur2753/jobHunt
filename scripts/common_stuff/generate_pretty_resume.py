import sys
import os
from pathlib import Path
from playwright.async_api import async_playwright
import asyncio

def build_resume_html(data: dict) -> str:
    """
    Generates a world-class, professional executive/engineering ATS resume HTML.
    Enforces a strict single-page A4 layout.
    """
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
    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #1e293b;
        background-color: #ffffff;
        line-height: 1.42;
        font-size: 9.5pt;
        padding: 0.2in 0.3in;
    }}
    
    /* Header Styling */
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
    .contact-info a {{
        color: #0284c7;
        text-decoration: none;
    }}
    .contact-info span {{
        margin: 0 6px;
        color: #94a3b8;
    }}

    /* Section Styling */
    .section {{
        margin-bottom: 14px;
    }}
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

    /* Summary */
    .summary-text {{
        font-size: 9.5pt;
        color: #334155;
        text-align: justify;
        line-height: 1.45;
    }}

    /* Skills */
    .skill-group {{
        margin-bottom: 5px;
        font-size: 9.3pt;
        line-height: 1.4;
    }}
    .skill-category {{
        font-weight: 700;
        color: #0f172a;
    }}
    .skill-items {{
        color: #334155;
    }}

    /* Experience & Projects */
    .job-block {{
        margin-bottom: 11px;
    }}
    .job-header {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 3px;
    }}
    .job-title {{
        font-size: 10pt;
        font-weight: 700;
        color: #0f172a;
    }}
    .job-company {{
        font-size: 9.5pt;
        font-weight: 600;
        color: #0369a1;
    }}
    .job-date {{
        font-size: 8.8pt;
        font-weight: 600;
        color: #64748b;
        text-align: right;
    }}
    .job-bullets {{
        padding-left: 18px;
        color: #334155;
    }}
    .job-bullets li {{
        margin-bottom: 3.5px;
        font-size: 9.3pt;
        line-height: 1.4;
    }}
    .job-bullets strong {{
        color: #0f172a;
        font-weight: 600;
    }}

    /* Education */
    .edu-block {{
        margin-bottom: 4px;
    }}
    .edu-header {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
    }}
    .edu-degree {{
        font-weight: 700;
        font-size: 9.5pt;
        color: #0f172a;
    }}
    .edu-school {{
        font-weight: 500;
        font-size: 9.5pt;
        color: #475569;
    }}
    .edu-year {{
        font-size: 8.8pt;
        font-weight: 600;
        color: #64748b;
    }}
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

async def render_pdf_from_data(data: dict, output_path: str):
    html_content = build_resume_html(data)
    
    # Save preview HTML file as well
    html_path = output_path.replace(".pdf", ".html")
    Path(html_path).write_text(html_content, encoding="utf-8")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html_content, wait_until="load")
        await page.pdf(
            path=output_path,
            print_background=True,
            margin={"top": "0.35in", "bottom": "0.35in", "left": "0.4in", "right": "0.4in"},
            format="A4"
        )
        await browser.close()
    print(f"Generated professional PDF: {output_path}")

if __name__ == "__main__":
    pass

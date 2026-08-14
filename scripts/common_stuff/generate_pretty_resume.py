import sys
import os
from pathlib import Path
from playwright.async_api import async_playwright
import asyncio

def build_resume_html(data: dict) -> str:
    """
    Generates a world-class, professional executive/engineering ATS resume HTML.
    """
    name = data.get("name", "Ankur Kumar")
    location = data.get("location", "Bengaluru, Karnataka")
    email = data.get("email", "ankur2753.ak@gmail.com")
    linkedin = data.get("linkedin", "https://www.linkedin.com/in/shootingdragon/")
    summary = data.get("summary", "")
    skills = data.get("skills", {})
    experience = data.get("experience", [])
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
        size: letter;
        margin: 0.4in;
    }}
    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #0f172a;
        background-color: #ffffff;
        line-height: 1.4;
        font-size: 9.5pt;
        padding: 0.2in 0.3in;
    }}
    
    /* Header Styling */
    .header {{
        text-align: center;
        border-bottom: 2px solid #1e293b;
        padding-bottom: 10px;
        margin-bottom: 14px;
    }}
    .header h1 {{
        font-size: 22pt;
        font-weight: 700;
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
        color: #1e293b;
        border-bottom: 1px solid #cbd5e1;
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
        margin-bottom: 4px;
        font-size: 9.5pt;
    }}
    .skill-category {{
        font-weight: 700;
        color: #0f172a;
    }}
    .skill-items {{
        color: #334155;
    }}

    /* Experience */
    .job-block {{
        margin-bottom: 10px;
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
        color: #2563eb;
    }}
    .job-date {{
        font-size: 8.5pt;
        font-weight: 600;
        color: #64748b;
        text-align: right;
    }}
    .job-bullets {{
        padding-left: 16px;
        color: #334155;
    }}
    .job-bullets li {{
        margin-bottom: 3px;
        font-size: 9.2pt;
        line-height: 1.38;
    }}
    .job-bullets strong {{
        color: #0f172a;
        font-weight: 600;
    }}

    /* Education */
    .edu-block {{
        margin-bottom: 5px;
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
        font-size: 8.5pt;
        font-weight: 600;
        color: #64748b;
    }}
</style>
</head>
<body>

<div class="header">
    <h1>{name}</h1>
    <div class="contact-info">
        {location} <span>|</span> <a href="mailto:{email}">{email}</a> <span>|</span> <a href="{linkedin}" target="_blank">LinkedIn Profile</a>
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
            margin={"top": "0.3in", "bottom": "0.3in", "left": "0.3in", "right": "0.3in"},
            format="Letter"
        )
        await browser.close()
    print(f"Generated professional PDF: {output_path}")

if __name__ == "__main__":
    resume_data = {
        "name": "ANKUR KUMAR",
        "location": "Bengaluru, Karnataka",
        "email": "ankur2753.ak@gmail.com",
        "linkedin": "https://www.linkedin.com/in/shootingdragon/",
        "summary": "Experienced QA & Automation Engineer with 3+ years of expertise in architecting end-to-end automated test suites, scalable web applications, and high-performance microservices. Specialized in Python, Playwright, React.js, C#, and Azure cloud environments. Proven track record in scaling cross-browser automation, parallelizing execution pipelines to reduce runtime by 25%, and optimizing enterprise MSSQL databases.",
        "skills": {
            "Automation & Testing": ["Playwright", "Pytest", "QA Automation Framework Design", "API Testing", "Integration Testing", "UI & Cross-Browser Testing"],
            "Languages & Frameworks": ["Python", "JavaScript", "React.js", "C#", "ASP.NET Core", "Node.js", "HTML5", "CSS3", "SQL"],
            "Cloud & DevOps": ["Azure (VMs, DevOps)", "AWS", "Docker", "Kubernetes", "Git", "CI/CD Test Pipelines"],
            "Architecture & Databases": ["Microservices Architecture", "REST APIs", "CQRS", "SAGA Pattern", "MSSQL", "MongoDB"]
        },
        "experience": [
            {
                "title": "Associate Engineer",
                "company": "SafeSend Technologies",
                "duration": "Feb 2023 – Present",
                "bullets": [
                    "Designed and built end-to-end QA automation test suites using <strong>Python</strong> and <strong>Playwright</strong> to validate complex enterprise web workflows.",
                    "Implemented parallel test processing workloads on Azure VMs, achieving a <strong>25% reduction in total execution runtime</strong>.",
                    "Engineered full-stack web applications from scratch featuring decoupled microservice backends, <strong>React.js</strong> single-page UI, and <strong>MSSQL</strong> databases.",
                    "Architected modular microservices to eliminate monolithic test & deployment bottlenecks and improve system maintainability.",
                    "Collaborated closely with product managers and stakeholders to analyze requirements, define edge cases, and deliver resilient quality solutions."
                ]
            },
            {
                "title": "Graduate Engineering Trainee",
                "company": "SafeSend Technologies",
                "duration": "Jul 2022 – Feb 2023",
                "bullets": [
                    "Developed high-throughput ASP.NET REST APIs adhering to enterprise design patterns including <strong>SAGA</strong> and <strong>CQRS</strong>.",
                    "Optimized MSSQL database performance via query tuning, index optimization, and schema refactoring.",
                    "Enforced <strong>SOLID</strong> design principles across legacy and modern codebase modules to maximize testability.",
                    "Successfully migrated legacy ASP.NET MVC Razor pages into dynamic, component-driven <strong>React.js</strong> interfaces."
                ]
            },
            {
                "title": "Front End Intern",
                "company": "Deloitte",
                "duration": "May 2022 – Jul 2022",
                "bullets": [
                    "Developed responsive, accessible web applications utilizing <strong>React.js</strong> and modern CSS standards.",
                    "Designed reusable UI component libraries to establish design consistency and improve team development velocity."
                ]
            }
        ],
        "education": [
            {
                "degree": "B.E., Computer Science Engineering",
                "school": "Sapthagiri College Of Engineering",
                "year": "2023"
            },
            {
                "degree": "12th, Senior Secondary (CBSE)",
                "school": "D.A.V Public School",
                "year": "2019"
            },
            {
                "degree": "10th, Secondary (CBSE)",
                "school": "D.A.V Public School",
                "year": "2017"
            }
        ]
    }

    out_pdf = "/home/ankurkumar/ankur_code/agent/resumes/tailored/Resume_BrowserStack_SDET_Ankur_Kumar.pdf"
    asyncio.run(render_pdf_from_data(resume_data, out_pdf))

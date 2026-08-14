import os
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

RESUME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Ankur Kumar - Resume</title>
<style>
    @page {
        size: A4;
        margin: 0.35in 0.4in;
    }
    * {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #1e293b;
        background-color: #ffffff;
        line-height: 1.35;
        font-size: 9.2pt;
    }
    
    /* Header Styling */
    .header {
        text-align: center;
        border-bottom: 2px solid #0f172a;
        padding-bottom: 6px;
        margin-bottom: 10px;
    }
    .header h1 {
        font-size: 20pt;
        font-weight: 800;
        letter-spacing: 0.8px;
        color: #0f172a;
        text-transform: uppercase;
        margin-bottom: 3px;
    }
    .contact-info {
        font-size: 8.8pt;
        color: #475569;
        font-weight: 500;
    }
    .contact-info a {
        color: #0284c7;
        text-decoration: none;
    }
    .contact-info span {
        margin: 0 5px;
        color: #94a3b8;
    }

    /* Section Styling */
    .section {
        margin-bottom: 10px;
    }
    .section-title {
        font-size: 10pt;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        color: #0f172a;
        border-bottom: 1px solid #cbd5e1;
        padding-bottom: 2px;
        margin-bottom: 6px;
    }

    /* Summary */
    .summary-text {
        font-size: 9pt;
        color: #334155;
        text-align: justify;
        line-height: 1.38;
    }

    /* Skills */
    .skill-group {
        margin-bottom: 3px;
        font-size: 8.8pt;
        line-height: 1.3;
    }
    .skill-category {
        font-weight: 700;
        color: #0f172a;
    }
    .skill-items {
        color: #334155;
    }

    /* Experience & Projects */
    .job-block {
        margin-bottom: 7px;
    }
    .job-header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 2px;
    }
    .job-title {
        font-size: 9.5pt;
        font-weight: 700;
        color: #0f172a;
    }
    .job-company {
        font-size: 9.2pt;
        font-weight: 600;
        color: #0369a1;
    }
    .job-date {
        font-size: 8.5pt;
        font-weight: 600;
        color: #64748b;
        text-align: right;
    }
    .job-bullets {
        padding-left: 15px;
        color: #334155;
    }
    .job-bullets li {
        margin-bottom: 2px;
        font-size: 8.8pt;
        line-height: 1.32;
    }
    .job-bullets strong {
        color: #0f172a;
        font-weight: 600;
    }

    /* Education */
    .edu-block {
        margin-bottom: 3px;
    }
    .edu-header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
    }
    .edu-degree {
        font-weight: 700;
        font-size: 9pt;
        color: #0f172a;
    }
    .edu-school {
        font-weight: 500;
        font-size: 9pt;
        color: #475569;
    }
    .edu-year {
        font-size: 8.5pt;
        font-weight: 600;
        color: #64748b;
    }
</style>
</head>
<body>

<div class="header">
    <h1>Ankur Kumar</h1>
    <div class="contact-info">
        Bengaluru, Karnataka <span>|</span> <a href="mailto:ankur2753.ak@gmail.com">ankur2753.ak@gmail.com</a> <span>|</span> <a href="https://www.linkedin.com/in/shootingdragon/" target="_blank">linkedin.com/in/shootingdragon</a> <span>|</span> <a href="https://github.com/ankur2753" target="_blank">github.com/ankur2753</a>
    </div>
</div>

<div class="section">
    <div class="section-title">Professional Summary</div>
    <div class="summary-text">
        QA & Software Automation Engineer with 3+ years of experience designing scalable test automation frameworks, REST & SOAP web services validation suites, and enterprise microservices. Specialized in Java (Selenium WebDriver), Python (Playwright), BDD frameworks (Cucumber/Behave), and Azure cloud environments. Proven track record in parallelizing test pipelines to reduce execution runtime by 25%, conducting deep-dive log root-cause analysis in JIRA, and delivering resilient software quality in fast-paced engineering teams.
    </div>
</div>

<div class="section">
    <div class="section-title">Technical Skills</div>
    <div class="skill-group">
        <span class="skill-category">Test Automation & BDD:</span>
        <span class="skill-items">Java, Selenium WebDriver, Playwright, Pytest, BDD (Cucumber / Behave), Framework Architecture, UI & Cross-Browser Testing</span>
    </div>
    <div class="skill-group">
        <span class="skill-category">API & Web Services Testing:</span>
        <span class="skill-items">REST API Automation, SOAP Web Services, Postman, Contract Validation, JSON/XML Payload Verification</span>
    </div>
    <div class="skill-group">
        <span class="skill-category">Languages & Databases:</span>
        <span class="skill-items">Java, Python, C#, JavaScript, React.js, ASP.NET Core, SQL, MSSQL, MongoDB</span>
    </div>
    <div class="skill-group">
        <span class="skill-category">Cloud, DevOps & Virtualization:</span>
        <span class="skill-items">Azure (VMs, Pipelines), AWS, Docker, Kubernetes, Git, CI/CD Test Pipelines, Infrastructure Concepts</span>
    </div>
    <div class="skill-group">
        <span class="skill-category">Quality & Engineering Practices:</span>
        <span class="skill-items">Test Strategy & Planning, Requirement Traceability (RTM), Root Cause Log Analysis, JIRA, Defect Lifecycle, Agile/Scrum</span>
    </div>
</div>

<div class="section">
    <div class="section-title">Professional Experience</div>
    
    <div class="job-block">
        <div class="job-header">
            <div>
                <span class="job-title">Senior QA Engineer</span>
                <span class="job-company"> | SafeSend Technologies</span>
            </div>
            <div class="job-date">Feb 2023 – Present</div>
        </div>
        <ul class="job-bullets">
            <li>Architected and automated robust test suites using <strong>Java (Selenium)</strong> and <strong>Python (Playwright)</strong> to validate critical web application workflows and edge scenarios.</li>
            <li>Implemented parallel test execution workloads across <strong>Azure VMs</strong>, achieving a <strong>25% reduction in total execution runtime</strong> and accelerating release verification.</li>
            <li>Designed automated validation for <strong>REST and SOAP web services</strong>, executing payload structure, HTTP status, and API contract verification.</li>
            <li>Performed structured <strong>log analysis and root-cause defect investigation</strong> using <strong>JIRA</strong>, partnering with core developers to ensure rapid resolution of software defects.</li>
            <li>Maintained comprehensive test designs and <strong>Requirement Traceability Matrices (RTM)</strong> to ensure 100% test coverage against functional specifications.</li>
        </ul>
    </div>

    <div class="job-block">
        <div class="job-header">
            <div>
                <span class="job-title">Graduate Engineering Trainee</span>
                <span class="job-company"> | SafeSend Technologies</span>
            </div>
            <div class="job-date">Jul 2022 – Feb 2023</div>
        </div>
        <ul class="job-bullets">
            <li>Engineered high-throughput <strong>ASP.NET REST APIs</strong> implementing <strong>CQRS and SAGA</strong> architectural patterns for modular backend processing.</li>
            <li>Integrated <strong>BDD specifications (Cucumber/Behave)</strong> to align business logic requirements directly with automated regression suites.</li>
            <li>Optimized MSSQL database performance via indexing strategies and query tuning, improving backend data retrieval speeds under heavy test loads.</li>
            <li>Migrated legacy monolithic MVC Razor pages to component-based <strong>React.js</strong> single-page interfaces, enhancing maintainability.</li>
        </ul>
    </div>

    <div class="job-block">
        <div class="job-header">
            <div>
                <span class="job-title">Front End Intern</span>
                <span class="job-company"> | Deloitte</span>
            </div>
            <div class="job-date">May 2022 – Jul 2022</div>
        </div>
        <ul class="job-bullets">
            <li>Developed responsive front-end interfaces with <strong>React.js</strong> and reusable UI component libraries to standardize cross-team development.</li>
            <li>Executed cross-browser compatibility and UI validation checks to guarantee flawless rendering across major browser engines.</li>
        </ul>
    </div>
</div>

<div class="section">
    <div class="section-title">Selected Engineering Projects</div>
    
    <div class="job-block">
        <div class="job-header">
            <div>
                <span class="job-title">Enterprise API & Web Services Automated Test Suite</span>
            </div>
            <div class="job-date">2024</div>
        </div>
        <ul class="job-bullets">
            <li>Designed a Java-based API testing harness supporting REST and SOAP request serialization, dynamic assertion checks, and automated HTML execution reporting.</li>
        </ul>
    </div>

    <div class="job-block">
        <div class="job-header">
            <div>
                <span class="job-title">Cloud VM Parallel Test Infrastructure</span>
            </div>
            <div class="job-date">2023</div>
        </div>
        <ul class="job-bullets">
            <li>Built Dockerized test execution containers deployed to Azure Virtual Machines with integrated CI/CD trigger scripts for automated nightly regression runs.</li>
        </ul>
    </div>
</div>

<div class="section">
    <div class="section-title">Education</div>
    <div class="edu-block">
        <div class="edu-header">
            <div>
                <span class="edu-degree">B.E., Computer Science Engineering</span>
                <span class="edu-school"> — Sapthagiri College Of Engineering</span>
            </div>
            <div class="edu-year">2023</div>
        </div>
    </div>
</div>

</body>
</html>
"""

COVER_LETTER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Ankur Kumar - Cover Letter - Philips</title>
<style>
    @page {
        size: A4;
        margin: 0.5in 0.6in;
    }
    * {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #1e293b;
        background-color: #ffffff;
        line-height: 1.5;
        font-size: 10pt;
    }

    .header {
        border-bottom: 2px solid #0f172a;
        padding-bottom: 10px;
        margin-bottom: 20px;
    }
    .header h1 {
        font-size: 22pt;
        font-weight: 800;
        color: #0f172a;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .contact-info {
        font-size: 9pt;
        color: #475569;
        font-weight: 500;
    }
    .contact-info a {
        color: #0284c7;
        text-decoration: none;
    }
    .contact-info span {
        margin: 0 6px;
        color: #94a3b8;
    }

    .meta-date {
        font-size: 9.5pt;
        font-weight: 600;
        color: #64748b;
        margin-bottom: 18px;
    }

    .recipient-info {
        margin-bottom: 20px;
        font-size: 9.5pt;
        color: #334155;
        line-height: 1.4;
    }
    .recipient-info strong {
        color: #0f172a;
    }

    .subject {
        font-size: 10.5pt;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 18px;
    }

    .content p {
        margin-bottom: 14px;
        text-align: justify;
        color: #334155;
    }

    .content strong {
        color: #0f172a;
    }

    .signature {
        margin-top: 25px;
        font-size: 10pt;
        color: #0f172a;
    }
    .signature-name {
        font-weight: 700;
        margin-top: 5px;
    }
</style>
</head>
<body>

<div class="header">
    <h1>Ankur Kumar</h1>
    <div class="contact-info">
        Bengaluru, Karnataka <span>|</span> <a href="mailto:ankur2753.ak@gmail.com">ankur2753.ak@gmail.com</a> <span>|</span> <a href="https://www.linkedin.com/in/shootingdragon/">linkedin.com/in/shootingdragon</a> <span>|</span> <a href="https://github.com/ankur2753">github.com/ankur2753</a>
    </div>
</div>

<div class="meta-date">August 9, 2026</div>

<div class="recipient-info">
    <strong>Hiring Manager / Technical Recruiting Team</strong><br>
    Hospital Patient Monitoring (HPM) Business<br>
    Philips Innovation Campus, Bengaluru, Karnataka
</div>

<div class="subject">
    SUBJECT: Application for Software Technologist I – Testing (Requisition ID: 578298)
</div>

<div class="content">
    <p>Dear Hiring Manager,</p>

    <p>I am writing to express my strong interest in the <strong>Software Technologist I – Testing</strong> position at Philips within the Hospital Patient Monitoring (HPM) business unit in Bengaluru. With over 3 years of hands-on experience designing automated test suites, validating REST & SOAP web services, and optimizing cloud-based test infrastructure, I am eager to contribute to Philips’ mission of delivering reliable, life-critical health technology.</p>

    <p>In my current role as Senior QA Engineer at SafeSend Technologies, I have built end-to-end test automation solutions using Java/Selenium and Python/Playwright to validate complex enterprise software workflows. A key highlight of my work was implementing parallel execution workloads across Azure Virtual Machines, which reduced total suite runtime by 25% while maintaining rigorous requirement coverage. Furthermore, my strong background in REST and SOAP web services automation allows me to systematically inspect payloads, contract specifications, and backend microservice behavior.</p>

    <p>Philips’ focus on rigorous quality standards, BDD methodologies, and comprehensive log root-cause analysis aligns directly with my technical approach. I pride myself on conducting structured defect investigation in JIRA, establishing full requirement traceability, and partnering closely with cross-functional development teams to catch issues early in the software lifecycle.</p>

    <p>I would welcome the opportunity to discuss how my automation experience, technical problem-solving skills, and dedication to software quality can support the Hospital Patient Monitoring team at Philips. Thank you for your time and consideration.</p>
</div>

<div class="signature">
    Sincerely,<br>
    <div class="signature-name">Ankur Kumar</div>
</div>

</body>
</html>
"""

async def main():
    target_dir = Path("/home/ankurkumar/ankur_code/agent/resumes/tailored")
    target_dir.mkdir(parents=True, exist_ok=True)

    artifact_dir = Path("/home/ankurkumar/.gemini/antigravity-cli/brain/53f10a0e-82ce-4efb-a659-f6f1ecaa82f4")

    resume_pdf_filename = "Ankur_Kumar_Philips_Software_Technologist_I_Testing_Resume.pdf"
    cover_pdf_filename = "Ankur_Kumar_Philips_Cover_Letter.pdf"

    resume_pdf_path = target_dir / resume_pdf_filename
    cover_pdf_path = target_dir / cover_pdf_filename

    resume_html_path = target_dir / resume_pdf_filename.replace(".pdf", ".html")
    cover_html_path = target_dir / cover_pdf_filename.replace(".pdf", ".html")

    resume_html_path.write_text(RESUME_HTML, encoding="utf-8")
    cover_html_path.write_text(COVER_LETTER_HTML, encoding="utf-8")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # Render Resume
        page_res = await browser.new_page()
        await page_res.set_content(RESUME_HTML, wait_until="load")
        await page_res.pdf(
            path=str(resume_pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "0.35in", "bottom": "0.35in", "left": "0.4in", "right": "0.4in"}
        )
        await page_res.close()

        # Render Cover Letter
        page_cov = await browser.new_page()
        await page_cov.set_content(COVER_LETTER_HTML, wait_until="load")
        await page_cov.pdf(
            path=str(cover_pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "0.5in", "bottom": "0.5in", "left": "0.6in", "right": "0.6in"}
        )
        await page_cov.close()

        await browser.close()

    print(f"Generated Resume PDF: {resume_pdf_path}")
    print(f"Generated Cover Letter PDF: {cover_pdf_path}")

    # Copy to artifact directory as well
    (artifact_dir / resume_pdf_filename).write_bytes(resume_pdf_path.read_bytes())
    (artifact_dir / cover_pdf_filename).write_bytes(cover_pdf_path.read_bytes())
    print("Copied files to artifact directory.")

if __name__ == "__main__":
    asyncio.run(main())

# Resume tailoring prompt

```markdown
Write a customized one-page resume for this job description.

Rules:
1. Do not invent employers, job titles, dates, or degrees.
2. Keep the current title as "Senior QA Engineer".
3. Start bullets with direct verbs like built, wrote, designed, automated, scaled, or cut.
4. Include numbers if they exist in the source text, like "cut run time by 25%".

Tailoring levels:
- Level 1 (Safe): Rewrite to emphasize real achievements.
- Level 2 (Inference): Deduce likely skills from the existing stack. For example, if they analyze requirements, call it RTM.
- Level 3 (Under-represented): Bring up skills they have but buried, like REST and SOAP.
- Level 4 (Role-match): Add required tools like Java and Selenium alongside Playwright to pass keyword filters. You must log these additions in your report.

Output JSON:
{
  "summary": "<2-3 line executive summary>",
  "skills": {
    "<Category 1>": ["<Skill 1>", "<Skill 2>"],
    "<Category 2>": ["..."]
  },
  "experience": [
    {
      "title": "Senior QA Engineer",
      "company": "SafeSend Technologies",
      "duration": "Feb 2023 - Present",
      "bullets": [
        "Wrote test suites using <strong>Java (Selenium)</strong> and <strong>Python (Playwright)</strong>...",
        "..."
      ]
    }
  ],
  "projects": [
    {
      "title": "<Project Title>",
      "date": "<Year>",
      "bullets": ["..."]
    }
  ],
  "education": [
    {
      "degree": "B.E. Computer Science Engineering",
      "school": "Sapthagiri College Of Engineering",
      "year": "2023"
    }
  ]
}

--- MASTER RESUME ---
{master_resume}

--- TARGET JOB ---
Title: {job_title}
Company: {company}
Description: {job_description}
```

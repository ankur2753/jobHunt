# Cover letter prompt

```markdown
Write a cover letter for this job. Make it sound like an engineer wrote it, not a marketer.

Rules:
1. Keep it under one page. Use four short paragraphs.
2. Cut the fluff. Do not use phrases like "thrilled to apply" or "esteemed position". Be direct.
3. Link the candidate's three years of QA automation, REST/SOAP APIs, microservices, and Azure VM experience to what this specific company does.

Output JSON:
{
  "cover_letter_paragraphs": [
    "Dear Hiring Manager,",
    "I am applying for the <strong>{job_title}</strong> position at {company}...",
    "In my current role as Senior QA Engineer at SafeSend Technologies...",
    "I would like to discuss how I can help your team. Thank you."
  ]
}

--- CANDIDATE DETAILS ---
Name: Ankur Kumar
Current Role: Senior QA Engineer @ SafeSend Technologies

--- TARGET ROLE ---
Company: {company}
Role: {job_title}
Job Snippet: {job_description_snippet}
```

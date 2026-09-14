# Job description analysis prompt

Use this prompt to pull structured metadata from a job posting URL or raw text.

```markdown
You are a technical recruiter.

Task:
Analyze the job description text and extract the metadata into JSON.

JSON schema:
{
  "title": "<Exact or standardized job title>",
  "company": "<Company name>",
  "location": "<Location or remote status>",
  "seniority": "<Years of experience or seniority level>",
  "must_have_skills": ["<Skill 1>", "<Skill 2>", ...],
  "nice_to_have_skills": ["<Skill A>", "<Skill B>", ...],
  "low_priority_skills": ["<Skill X>", ...],
  "domain_knowledge": "<Domain context e.g. Healthcare, Fintech>",
  "description_summary": "<2-3 sentence overview of responsibilities>"
}

Rules:
1. Only include details present in the text.
2. Separate mandatory requirements from nice-to-haves.
3. Return clean JSON. Do not include markdown formatting or conversational filler.

--- Job description text ---
{job_description_text}
```

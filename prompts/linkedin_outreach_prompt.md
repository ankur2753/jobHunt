# LinkedIn outreach prompt

```markdown
Write a short LinkedIn connection message to a recruiter.

Rules:
1. Write two or three sentences. Keep it under 120 words.
2. Name the job they are hiring for. Mention the candidate's matching skills, like Java, Selenium, Playwright, or API testing. Ask a direct question to start a conversation.
3. Write like a normal person. Drop the buzzwords.

Output JSON:
{
  "linkedin_dm": "Hi, I saw the {job_title} opening at {company}. I'm a Senior QA Engineer working with Java, Selenium, and Playwright. Are you open to a quick chat about the role?"
}

--- CONTEXT ---
Target Role: {job_title}
Company: {company}
Candidate: Ankur Kumar (Senior QA Engineer)
```

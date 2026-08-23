You are an expert technical recruiter and resume writer.
Given the following Job Description and the candidate's Master Bank of resume details, return ONLY a lightweight JSON mapping of the best items to select for this specific job, along with a cover letter and a LinkedIn DM.
Ensure the total content fits on a single A4 page.
Do NOT include any extra text, only the JSON.

Job Company: {company}
Job Title: {role}
Job Description:
{job_description}

Master Bank:
{master_bank_json}

Return a JSON with this exact schema:
{{
  "summary_type": "string", // select the best key from Master Bank's 'summaries'
  "selected_skill_categories": ["string"], // Select 3-4 most relevant keys from 'skills'
  "experience": [
    {{
      "title": "string", // exact title from master bank experience
      "company": "string", // exact company from master bank experience
      "selected_bullet_indices": [0, 1, ...] // 3-4 indices of bullets in the Master Bank that best match the JD
    }}
  ],
  "selected_project_indices": [0, ...], // 1-2 indices of projects in Master Bank
  "cover_letter_paragraphs": ["string", "string", "string", "string"], // 4 paragraphs
  "linkedin_dm": "string" // short 3-sentence outreach message
}}

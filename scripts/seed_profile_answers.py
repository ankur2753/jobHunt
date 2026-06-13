#!/usr/bin/env python3
"""
Seed the vector DB with Ankur's profile answers for Naukri/job-application chatbots.

Each fact is stored under several natural recruiter phrasings so semantic matching
hits regardless of how the question is worded. Skill YOE = 3 years for everything
except Docker (1 year), per user confirmation. Run once:

    python3 scripts/seed_profile_answers.py            # store + verify
    python3 scripts/seed_profile_answers.py --verify    # verify only
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.common_stuff.logging_setup import setup_logging
setup_logging(run_name="seed_profile")

from scripts.common_stuff.vector_db_manager import VectorDBManager

TAGS = ["naukri", "profile"]

# ---------------------------------------------------------------------------
# Skill years of experience — all 3 except Docker (1).
# ---------------------------------------------------------------------------
SKILL_YEARS = {
    "C#": 3, ".NET": 3, ".NET Core": 3, "ASP.NET": 3, "ASP.NET Core": 3,
    "JavaScript": 3, "TypeScript": 3, "React": 3, "React.js": 3, "Node.js": 3,
    "SQL": 3, "MSSQL": 3, "Python": 3, "Azure": 3, "Azure DevOps": 3,
    "AWS": 3, "MongoDB": 3, "Git": 3, "Kubernetes": 3, "Docker": 1,
    "Microservices": 3, "REST APIs": 3, "Web API": 3, "Machine Learning": 3,
    "Full stack development": 3, "Frontend development": 3, "Backend development": 3,
    "Data structures and algorithms": 3, "Object oriented programming": 3,
    "Multithreading": 3, "System design": 3,
    # SDET / automation stack (frame whole 3-yr career as automation-inclusive)
    "Selenium": 3, "Selenium WebDriver": 3, "Playwright": 3,
    "Test automation": 3, "Automation testing": 3, "Manual testing": 3,
    "Functional testing": 3, "API testing": 3, "Postman": 3, "REST Assured": 3,
    "NUnit": 3, "xUnit": 3, "Pytest": 3, "SpecFlow": 3, "Cucumber": 3, "BDD": 3,
}


def skill_qas():
    qas = []
    for skill, yrs in SKILL_YEARS.items():
        ans = str(yrs)
        phrasings = [
            f"How many years of experience do you have in {skill}?",
            f"How many years of experience do you have in {skill}",
            f"Years of experience in {skill}",
            f"{skill} experience in years",
            f"Total years of experience in {skill}",
            f"How many years have you worked with {skill}?",
        ]
        for p in phrasings:
            qas.append((p, ans))
    return qas


# ---------------------------------------------------------------------------
# Screening / logistics facts — (answer, [phrasings]).
# ---------------------------------------------------------------------------
SCREENING = [
    ("3 years", [
        "What is your total experience?",
        "How many years of experience do you have?",
        "Total years of experience",
        "What is your total work experience in years?",
        "How many years of total experience do you have in backend development?",
        "How many years of total experience do you have in software development?",
    ]),
    ("30 days", [
        "What is your notice period?",
        "What is your notice period in days?",
        "How soon can you join?",
        "What is your availability to join?",
        "When is your last working day?",
        "When can you start?",
        "What is your official notice period?",
    ]),
    ("12 LPA", [
        "What is your current CTC?",
        "What is your current salary?",
        "Current CTC",
        "What is your current annual compensation?",
        "What is your current fixed CTC?",
    ]),
    ("16-20 LPA", [
        "What is your expected CTC?",
        "What is your expected salary?",
        "Expected CTC",
        "What are your salary expectations?",
        "What is your expected annual compensation?",
    ]),
    ("Bangalore", [
        "What is your current location?",
        "What is your current city?",
        "Where are you currently located?",
        "Which city do you currently live in?",
    ]),
    ("Yes, open to relocating anywhere in India", [
        "Are you willing to relocate?",
        "Are you open to relocation?",
        "Are you comfortable relocating for this role?",
        "Would you be willing to relocate to another city?",
    ]),
    ("Bangalore; open to relocate anywhere in India; open to remote", [
        "What is your preferred job location?",
        "Which locations are you open to?",
        "Preferred work location",
    ]),
    ("Yes, comfortable working from office, hybrid or remote", [
        "Are you comfortable working from office?",
        "Are you open to work from office?",
        "What is your preferred work mode?",
        "Are you okay with working from the office?",
        "Are you comfortable with a hybrid work model?",
    ]),
    ("Yes", [
        "Are you comfortable working 6 days a week?",
        "Are you okay with a 6 day work week?",
        "Are you comfortable working in a start-up culture?",
        "Are you comfortable working in a startup?",
        "Are you comfortable with rotational shifts?",
        "Are you comfortable working night shifts?",
        "Are you willing to work in shifts?",
    ]),
    ("No", [
        "Do you require sponsorship for employment?",
        "Will you now or in the future require sponsorship for employment (e.g. H-1B visa status)?",
        "Do you need a work visa sponsorship?",
        "Do you require a visa to work in India?",
        "Have you been previously employed with this company?",
        "Are you currently or have you previously been associated with this company?",
    ]),
    ("Seeking a stronger developer / full-stack role with better growth opportunities", [
        "What is your reason for job change?",
        "Why are you looking for a change?",
        "Reason for looking for a new job",
        "Why do you want to leave your current company?",
    ]),
    ("B.E. in Computer Science Engineering", [
        "What is your highest qualification?",
        "What is your highest level of education?",
        "Highest level of education obtained",
        "What is your educational qualification?",
        "What is your degree?",
    ]),
    ("Bachelor of Engineering (B.E.), Computer Science Engineering, 2023", [
        "What is your degree and specialization?",
        "Which degree do you hold?",
        "What did you study in college?",
    ]),
    ("2023", [
        "What year did you graduate?",
        "What is your year of graduation?",
        "When did you complete your graduation?",
        "What is your passing year?",
    ]),
    ("72%", [
        "What was your percentage in B.E.?",
        "What is your graduation percentage?",
        "What was your aggregate percentage in engineering?",
    ]),
    ("96%", [
        "What was your 10th percentage?",
        "What were your 10th marks?",
    ]),
    ("Thomson Reuters", [
        "What is your current company?",
        "Current company name?",
        "Current company",
        "Present company name",
        "Which company are you currently working with?",
        "Name of your current employer",
        "Where are you currently working?",
    ]),
    ("Associate Engineer", [
        "What is your current designation?",
        "What is your current job title?",
        "What is your current role?",
    ]),
    ("Ankur Kumar", [
        "What is your name?",
        "What is your full name?",
    ]),
    ("ankur2753.ak@gmail.com", [
        "What is your email address?",
        "What is your email?",
    ]),
    ("8002656334", [
        "What is your phone number?",
        "What is your contact number?",
        "What is your mobile number?",
    ]),
    ("30/01/2002", [
        "What is your date of birth?",
        "When were you born?",
    ]),
    ("https://www.linkedin.com/in/shootingdragon/", [
        "What is your LinkedIn profile?",
        "Share your LinkedIn URL",
    ]),
    ("Selenium, Playwright, Postman, REST Assured", [
        "Which test automation tools have you used?",
        "What automation tools do you know?",
        "Which automation testing tools are you proficient in?",
    ]),
    ("NUnit, xUnit, Pytest, SpecFlow, Cucumber", [
        "Which test frameworks have you used?",
        "What testing frameworks do you know?",
    ]),
    ("Azure DevOps, GitHub Actions", [
        "Which CI/CD tools have you worked with?",
        "What DevOps tools do you know?",
        "Which CI/CD pipelines have you used?",
    ]),
    ("Yes", [
        "Do you have a graduation degree?",
        "Do you have a bachelor's degree?",
        "Have you completed your graduation?",
        "Do you hold an engineering degree?",
    ]),
    ("No", [
        "Do you have any gap in your education?",
        "Do you have any employment gap?",
        "Is there any break in your career?",
    ]),
]


def all_qas():
    qas = list(skill_qas())
    for ans, phrasings in SCREENING:
        for p in phrasings:
            qas.append((p, ans))
    return qas


def store(db):
    qas = all_qas()
    print(f"Storing {len(qas)} question/answer phrasings...")
    for q, a in qas:
        db.store_answered_question(q, a, category="learned_answers", tags=TAGS)
    print(f"✅ Stored {len(qas)} entries.")


# Recruiter-style probes (deliberately phrased differently from what we stored).
VERIFY = [
    "How many years of experience do you have in Java?",          # not a skill -> closest
    "Years of exp in C#/.Net?",
    "How many years of experience in .net core",
    "Experience in React js (years)?",
    "How many years have you done SQL?",
    "Total experience in Python?",
    "How many yrs of Docker experience?",
    "Selenium automation experience in years?",
    "What is your current CTC?",
    "Expected CTC?",
    "What's your notice period?",
    "Are you willing to relocate?",
    "Comfortable working 6 days a week?",
    "Highest education qualification?",
    "Reason for job change?",
    "Current company name?",
]


def verify(db, threshold=0.6):
    print(f"\n🔎 Verifying retrieval (threshold {threshold}):\n" + "-" * 72)
    ok = weak = 0
    for q in VERIFY:
        cands = db.answer_question_with_candidates(q, n_candidates=1, confidence_threshold=0.0)
        if cands:
            c = cands[0]
            from scripts.cookie_management_login.naukri_form_filler import NaukriFormFiller
            ans = NaukriFormFiller._clean_answer(c.answer_text)
            mark = "✅" if c.confidence >= threshold else "⚠️ "
            if c.confidence >= threshold:
                ok += 1
            else:
                weak += 1
            print(f"{mark} {c.confidence:.2f}  {q:48s} → {ans[:40]}")
        else:
            weak += 1
            print(f"❌ ----  {q:48s} → (no candidate)")
    print("-" * 72)
    print(f"{ok} cleared {threshold}, {weak} below.")


if __name__ == "__main__":
    db = VectorDBManager()
    if "--verify" not in sys.argv:
        store(db)
    verify(db)

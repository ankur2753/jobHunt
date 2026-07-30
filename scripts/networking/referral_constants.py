"""
Referral constants and suitability scoring configurations.
"""

# Dict of candidate categories, their suitability scores, and matching keywords.
# Order matters: first matched category determines candidate score.
SCORING_KEYWORDS = {
    "QA": {
        "score": 0.8,
        "keywords": [
            "qa", "sdet", "quality assurance", "test automation", "testing", 
            "software engineer in test", "automation engineer", "test engineer"
        ]
    },
    "Recruiter": {
        "score": 0.7,
        "keywords": [
            "recruiter", "talent acquisition", "sourcer", "recruitment", 
            "human resources", "hr", "people team", "talent partner", 
            "talent associate", "talent manager"
        ]
    },
    "Manager": {
        "score": 0.6,
        "keywords": [
            "manager", "lead", "head of", "director", "vp", "chief", "principal"
        ]
    },
    "Developer": {
        "score": 0.5,
        "keywords": [
            "software engineer", "developer", "programmer", "coder", "sde", 
            "full stack", "backend", "frontend"
        ]
    }
}

DEFAULT_SCORE = 0.3

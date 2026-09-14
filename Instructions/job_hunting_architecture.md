# Job Hunting System Architecture

This diagram shows how the automated job hunting system fits together. It maps out the Python modules, LLMs, and `career-ops` plugins.

## System Architecture (Mermaid UML)

```mermaid
graph TD
    %% Styling
    classDef default fill:#f9f9f9,stroke:#333,stroke-width:1px;
    classDef core fill:#d4e157,stroke:#333,stroke-width:2px;
    classDef script fill:#81d4fa,stroke:#333,stroke-width:1px;
    classDef rules fill:#ffab91,stroke:#333,stroke-width:2px,stroke-dasharray: 5 5;
    classDef data fill:#bcaaa4,stroke:#333,stroke-width:1px;

    %% Data Store Layer
    subgraph DataStore["Data & Persistence Layer"]
        PersDetails[("personal_details.json")]:::data
        JobsDB[("jobs_database.csv")]:::data
        PendingRef[("pending_referrals.json")]:::data
    end

    %% Core Services
    subgraph Core["Core Engine (scripts/common_stuff)"]
        VDB["VectorDBManager"]:::core
        LLM["query_llm_fallback()"]:::core
        UnslopNet["Instructions/unslop_rules.txt"]:::rules
        
        PersDetails --> VDB
        UnslopNet -.->|Appends to System Prompt| LLM
    end

    %% Job Portals Layer
    subgraph Portals["Job Applications (scripts/applying_to_portals)"]
        NaukriApply["naukri_job_apply.py"]:::script
        LI_Apply["linkedin_apply.py"]:::script
        Scraper["linkedin_job_scraper.py"]:::script
        
        Scraper -->|Feeds URLs| LI_Apply
        VDB --> NaukriApply
        VDB --> LI_Apply
    end

    %% Networking Layer
    subgraph Networking["Networking & Outreach (scripts/networking)"]
        ColdGen["ColdOutreachGenerator"]:::core
        LI_Connect["linkedin_connect.py"]:::script
        LI_ColdMsg["linkedin_cold_message.py"]:::script
        LI_Referral["linkedin_referral_helper.py"]:::script
        Discovery["discovery_providers.py"]:::script

        LLM -->|Generates Clean Text| ColdGen
        ColdGen -->|Drafts Messages| LI_ColdMsg
        Discovery -->|Finds Candidates| LI_Referral
        LI_Connect -->|Handles Invites| LI_ColdMsg
        JobsDB -->|Pending Jobs| LI_Referral
        LI_Referral -->|Saves Drafts| PendingRef
    end

    %% Career-Ops Integration
    subgraph CareerOps["Career-Ops (CLI tool)"]
        CO_Core["career-ops engine"]:::core
        CO_Custom["modes/_custom.md (Unslop)"]:::rules
        CO_Modes["modes (cover.md, email.md, etc.)"]:::script
        
        CO_Custom -.->|Applies to all generated text| CO_Core
        CO_Core --> CO_Modes
    end
```

## Subsystems

### 1. Job portals
The `applying_to_portals/` and `job_scraping/` scripts handle Naukri and LinkedIn. They use `VectorDBManager` to pull context and answer form questions. I built it this way so the forms don't just get generic answers—they actually read the candidate's history.

### 2. Networking and cold outreach
The `networking/` scripts automate LinkedIn. They send connection requests and hunt for referrals.
- `linkedin_referral_helper.py` scans `jobs_database.csv`, finds people to ask for referrals, and drafts messages.
- `linkedin_cold_message.py` connects with recruiters and engineers. It appends an AI-drafted introduction.

Both scripts use `ColdOutreachGenerator`. This hits the LLM and applies `unslop_rules.txt`. It's critical to strip out the usual AI fluff here, otherwise recruiters spot the automation immediately.

### 3. Career-Ops plugin
`career-ops` is an independent agent framework that drafts cover letters, resumes, and emails. It hooks into the main system through `modes/_custom.md` so it shares the same unslop rules.

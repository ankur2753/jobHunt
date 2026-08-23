# Job Hunting System Architecture

This document contains the unified UML diagram for the automated job hunting system, detailing how the different Python modules, LLM integrations, and `career-ops` plugins interact.

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

## Subsystem Details

### 1. Job Portals Automation
Scripts in `applying_to_portals/` and `job_scraping/` handle the automated interaction with job boards like Naukri and LinkedIn. They pull candidate context from the `VectorDBManager` to dynamically answer form questions.

### 2. Networking and Cold Outreach
Scripts in `networking/` automate LinkedIn messaging, connection requests, and referral hunting.
- `linkedin_referral_helper.py`: Scans `jobs_database.csv`, discovers potential employees to ask for referrals, scores them, and drafts customized networking messages.
- `linkedin_cold_message.py`: Connects with recruiters and engineers, appending an AI-drafted introduction.
- Both rely heavily on `ColdOutreachGenerator`, which queries the LLM and strictly adheres to the `unslop_rules.txt` constraints to maintain a natural, human tone.

### 3. Career-Ops Plugin
The `career-ops` tool is an independent markdown-based agent framework that handles drafting cover letters, generating resumes, and writing emails. It has been integrated into the ecosystem by sharing the `unslop` principles via its local `modes/_custom.md` hook.

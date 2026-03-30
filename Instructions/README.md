# Automated Job Search Agent

This project is designed to automate the job search process using a combination of scripted automation and agentic support from Large Language Models (LLMs). The goal is to create a resilient system that can handle the complexities of job hunting across various platforms.

## Core Philosophy

The agent is built with the following principles in mind:

1.  **Script-First:** The primary mode of operation is through well-defined Python scripts that handle specific tasks like web scraping, logging in, and applying for jobs.
2.  **LLM as a Fallback:** When a script encounters an unexpected issue (e.g., a website layout change that breaks a scraper), it can call an LLM API to try and dynamically solve the problem.
3.  **Human in the Loop:** If both the script and the LLM fail to resolve an issue, the agent will notify the user via a Telegram bot, allowing for manual intervention. 

## Project Goal

The main objective is to automate the entire job search workflow:

*   **Job Scraping:** Automatically search for and collect job postings from various online portals.
*   **Personalization:** Generate customized resumes, cover letters, and outreach messages for each application.
*   **Application Submission:** Apply for jobs on different portals.
*   **Networking:** Automate cold outreach and referral requests.

## Folder Structure

*   `config/`: Contains configuration files, such as `requirements.txt`.
*   `docker_files/`: Holds Docker-related files for containerization.
*   `Instructions/`: Documentation for the project, including this `README.md`.
*   `personal_details/`: Stores personal user information, such as `user_details.json` and `job_prefrences.json`.
*   `resumes/`: A directory for storing generated resumes.
*   `scripts/`: Contains all the automation scripts.
    *   `applying_to_portals/`: Scripts for applying to jobs on specific portals.
    *   `common_stuff/`: Shared utilities and functions used across different scripts.
    *   `cookie_management_login/`: Scripts for managing logins and browser cookies.
    *   `getting_referals/`: Scripts for automating referral requests.
    *   `job_scraping/`: Scripts dedicated to scraping job postings.
    *   `networking/`: Scripts for networking-related tasks.
    -   `orchestrator/`: The main script that coordinates the execution of all other scripts.
    *   `personalize_resume_coverletter_msg/`: Scripts that use LLMs to generate personalized content.

## How it Works

The `orchestrator` script is the entry point for the agent. It will coordinate the execution of the other scripts in the `scripts/` folder to perform the job search tasks in a logical sequence. Each script is designed to be modular and handle a specific part of the workflow.

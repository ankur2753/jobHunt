import os
import json
import logging
import requests
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to load .env file if present
try:
    from dotenv import load_dotenv
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")
except ImportError:
    pass

def get_api_key_and_provider():
    """
    Checks environment variables for available LLM API keys.
    Returns: Tuple of (api_key, provider, api_url, model) or (None, None, None, None)
    """
    # 1. Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        return (
            gemini_key, 
            "gemini", 
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent", 
            "gemini-2.5-flash"
        )
    
    # 2. OpenRouter
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if openrouter_key:
        return (
            openrouter_key, 
            "openrouter", 
            "https://openrouter.ai/api/v1/chat/completions", 
            os.environ.get("OPENROUTER_MODEL", "openrouter/auto")
        )
    
    # 3. OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        return (
            openai_key, 
            "openai", 
            "https://api.openai.com/v1/chat/completions", 
            "gpt-4o-mini"
        )
        
    # 4. Anthropic
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        return (
            anthropic_key, 
            "anthropic", 
            "https://api.anthropic.com/v1/messages", 
            "claude-3-5-haiku-20241022"
        )
        
    return None, None, None, None

async def query_llm_fallback(question: str, options: List[str] = None, profile_context: str = "") -> Optional[str]:
    """
    Queries an LLM to answer a job application question based on the user's profile context.
    """
    api_key, provider, api_url, model = get_api_key_and_provider()
    if not api_key:
        logger.warning("⚠️ LLM Fallback: No API key found in environment (GEMINI_API_KEY, OPENROUTER_API_KEY, etc.)")
        return None
        
    logger.info(f"🤖 Querying LLM fallback using {provider} ({model})...")
    
    # Load structured personal details JSON if available
    json_details = ""
    try:
        repo_root = Path(__file__).resolve().parents[2]
        json_path = repo_root / "personal_details" / "personal_details.json"
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                json_details = json.dumps(json.load(f), indent=2)
    except Exception as e:
        logger.error(f"Error loading personal_details.json: {e}")

    # Build the profile context combining the full JSON details and vector DB facts
    full_context = ""
    if json_details:
        full_context += f"--- STRUCTURED RESUME/PROFILE JSON ---\n{json_details}\n\n"
    if profile_context:
        full_context += f"--- SUPPLEMENTARY PROFILE FACTS (Vector DB) ---\n{profile_context}\n"

    prompt = f"""You are an AI job application assistant. Your task is to answer a form question on a job application page on behalf of the user.
Use the user's profile details below as your single source of truth.

{full_context}
---------------------------

Question to answer:
"{question}"
"""

    if options:
        prompt += f"\n[Field Type: Multiple-Choice/Radio/Dropdown]\nYou MUST select one of the following exact options:\n"
        for opt in options:
            prompt += f"- {opt}\n"
        prompt += f"\nYour response must match one of the options above exactly."
    else:
        prompt += f"\n[Field Type: Free-Text Input Box]\nProvide a concise, direct text answer based on the profile details above. Return ONLY the answer value itself.\n"

    prompt += "\nResponse Guidelines:\n1. Return ONLY the final answer value (no conversational filler, no explanations, no formatting like bold/italics).\n2. If it is a multiple-choice question, your response must match one of the options exactly."

    try:
        if provider == "gemini":
            url = f"{api_url}?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1}
            }
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            res_data = response.json()
            answer = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            
        elif provider in ("openai", "openrouter"):
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            if provider == "openrouter":
                headers["HTTP-Referer"] = "https://github.com/ankurkumar/job-hunt-agent"
                headers["X-Title"] = "Job Hunt Agent"
                
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1
            }
            response = requests.post(api_url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            res_data = response.json()
            answer = res_data["choices"][0]["message"]["content"].strip()
            
        elif provider == "anthropic":
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            payload = {
                "model": model,
                "max_tokens": 100,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1
            }
            response = requests.post(api_url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            res_data = response.json()
            answer = res_data["content"][0]["text"].strip()
            
        # Clean quotes if model wrapped response in quotes
        if answer.startswith('"') and answer.endswith('"'):
            answer = answer[1:-1].strip()
        if answer.startswith("'") and answer.endswith("'"):
            answer = answer[1:-1].strip()
            
        logger.info(f"🤖 LLM Fallback Answer: '{answer}'")
        return answer
        
    except Exception as e:
        logger.error(f"❌ LLM Fallback API call failed: {e}")
        return None

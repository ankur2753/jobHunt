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
    Checks environment variables for available LLM API keys in flexible priority order.
    Returns: Tuple of (api_key, provider, api_url, model) or (None, None, None, None)
    """
    # 1. Custom / Generic OpenAI-compatible endpoint (Ollama, LMStudio, DeepSeek, Groq, etc.)
    generic_key = os.environ.get("LLM_API_KEY")
    generic_url = os.environ.get("LLM_BASE_URL")
    if generic_key or generic_url:
        return (
            generic_key or "dummy-key",
            "openai_compatible",
            generic_url or "https://api.openai.com/v1/chat/completions",
            os.environ.get("LLM_MODEL", "gpt-4o-mini")
        )

    # 2. Gemini API
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        gemini_url = os.environ.get("GEMINI_URL", f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent")
        return (
            gemini_key, 
            "gemini", 
            gemini_url, 
            model
        )

    # 3. OpenAI API
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        return (
            openai_key, 
            "openai", 
            "https://api.openai.com/v1/chat/completions", 
            os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        )

    # 4. OpenRouter API
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if openrouter_key:
        return (
            openrouter_key, 
            "openrouter", 
            "https://openrouter.ai/api/v1/chat/completions", 
            os.environ.get("OPENROUTER_MODEL", "openrouter/auto")
        )

    # 5. Anthropic Claude API
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        return (
            anthropic_key, 
            "anthropic", 
            "https://api.anthropic.com/v1/messages", 
            os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
        )

    return None, None, None, None


async def query_llm_fallback(question: str, options: List[str] = None, profile_context: str = "") -> Optional[str]:
    """
    Queries any configured LLM provider to process prompts and format responses.
    """
    api_key, provider, api_url, model = get_api_key_and_provider()
    if not api_key:
        logger.warning("⚠️ LLM Fallback: No API key found in environment (GEMINI_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, etc.)")
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

    full_context = ""
    if json_details:
        full_context += f"--- STRUCTURED RESUME/PROFILE JSON ---\n{json_details}\n\n"
    if profile_context:
        full_context += f"--- SUPPLEMENTARY PROFILE FACTS ---\n{profile_context}\n"

    from scripts.common_stuff.prompt_manager import load_prompt
    prompt = load_prompt("llm_fallback_base", full_context=full_context, question=question)

    if options:
        prompt += f"\n[Field Type: Multiple-Choice]\nSelect one of the following exact options:\n"
        for opt in options:
            prompt += f"- {opt}\n"
        prompt += f"\nYour response must match one of the options above exactly."
    else:
        prompt += f"\nProvide a direct, high-quality answer. Return ONLY the final output.\n"

    try:
        if provider == "gemini":
            url = f"{api_url}?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2}
            }
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            res_data = response.json()
            answer = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()

        elif provider in ("openai", "openrouter", "openai_compatible"):
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            if provider == "openrouter":
                headers["HTTP-Referer"] = os.getenv("GITHUB_REPO_URL", "https://github.com/job-hunt-agent")
                headers["X-Title"] = "Resume Tailor Agent"
                
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2
            }
            response = requests.post(api_url, headers=headers, json=payload, timeout=20)
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
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2
            }
            response = requests.post(api_url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            res_data = response.json()
            answer = res_data["content"][0]["text"].strip()

        # Clean wrapping quotes if present
        if answer.startswith('"') and answer.endswith('"'):
            answer = answer[1:-1].strip()
        if answer.startswith("'") and answer.endswith("'"):
            answer = answer[1:-1].strip()

        logger.info(f"🤖 LLM Answer received successfully ({len(answer)} chars)")
        return answer

    except Exception as e:
        logger.error(f"❌ LLM API call failed ({provider}): {e}")
        return None

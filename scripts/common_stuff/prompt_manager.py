import os
from pathlib import Path

def load_prompt(prompt_name: str, **kwargs) -> str:
    prompt_path = Path(__file__).resolve().parents[2] / "instructions" / "prompts" / f"{prompt_name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt {prompt_name}.md not found at {prompt_path}")
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if kwargs:
        for k, v in kwargs.items():
            content = content.replace("{" + k + "}", str(v))
    return content

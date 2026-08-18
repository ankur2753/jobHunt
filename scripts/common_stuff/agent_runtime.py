import subprocess
from typing import Optional
import os

class AgentRuntime:
    """
    Abstraction layer for invoking the agent runtime.
    Replaces direct subprocess.run(["agy", ...]) calls throughout the codebase.
    """
    
    @staticmethod
    def invoke(prompt: str, cwd: Optional[str] = None, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        """Invokes the agent with the given prompt."""
        cmd = ["agy", "--dangerously-skip-permissions", "--print", prompt]
        env = os.environ.copy()
        env["HOME"] = "/home/ankurkumar"
        return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)

    @staticmethod
    def invoke_with_image(prompt: str, image_path: str, cwd: Optional[str] = None, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        """Invokes the agent with the given prompt and a multimodal image by instructing it to use view_file."""
        full_prompt = f"{prompt}\n\nIMPORTANT INSTRUCTION: You MUST use your view_file tool to open and analyze the image at this absolute path before answering: {image_path}"
        cmd = ["agy", "--dangerously-skip-permissions", "--print", full_prompt]
        env = os.environ.copy()
        env["HOME"] = "/home/ankurkumar"
        return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)

    @staticmethod
    def run_command(cmd: list, cwd: Optional[str] = None, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        """Runs a generic command (useful for pre-constructed agy commands)."""
        env = os.environ.copy()
        env["HOME"] = "/home/ankurkumar"
        return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)

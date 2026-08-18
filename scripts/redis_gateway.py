import asyncio
import json
import logging
import sys
from pathlib import Path
import redis.asyncio as redis
import os

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [Gateway] %(message)s")
logger = logging.getLogger("redis_gateway")

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI_TAILOR_SCRIPT = PROJECT_ROOT / "scripts" / "cli_tailor.py"
PYTHON_EXEC = sys.executable

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
STREAM_REQUESTS = "agent.job-hunt.requests"
STREAM_RESPONSES = "agent.job-hunt.responses"

class BaseTask:
    def __init__(self, payload, envelope):
        self.payload = payload
        self.envelope = envelope
        self.url = payload.get("job_url", "")
        self.jd_text = payload.get("custom_notes", "")
        self.company = payload.get("company", "")
        self.role = payload.get("role", "")
        self.user_id = envelope.get("user_id", "unknown")

    async def _stream_output(self, stream, capture=False, log_level=None):
        output = []
        async for line in stream:
            decoded = line.decode().strip()
            if decoded:
                if log_level is not None:
                    if log_level == logging.ERROR:
                        logger.error(decoded)
                    else:
                        logger.info(decoded)
                if capture:
                    output.append(decoded)
        return "\n".join(output)

    async def execute(self):
        raise NotImplementedError

class ReferralTask(BaseTask):
    async def execute(self):
        logger.info(f"Processing referral for user {self.user_id}")
        
        if str(PROJECT_ROOT / "scripts") not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from cli_tailor import fetch_job_details
        
        job_details = {}
        target_details = {}
        
        try:
            jd_text = self.jd_text
            url = self.url
            if "|" in jd_text:
                part1, part2 = [x.strip() for x in jd_text.split("|", 1)]
                if part1.startswith("http"):
                    job_details = await fetch_job_details(url=part1, headed=True)
                    target_details = await fetch_job_details(jd_text=part2, headed=True)
                elif part2.startswith("http"):
                    job_details = await fetch_job_details(url=part2, headed=True)
                    target_details = await fetch_job_details(jd_text=part1, headed=True)
                else:
                    target_details = await fetch_job_details(jd_text=jd_text, headed=True)
            elif jd_text.startswith("http"):
                job_details = await fetch_job_details(url=jd_text, headed=True)
            else:
                target_details = await fetch_job_details(jd_text=jd_text, headed=True)
                
            company = (self.company or "").strip() if isinstance(self.company, str) else ""
            if not company:
                company = target_details.get("company") or job_details.get("company") or ""
            company = company.strip() if isinstance(company, str) else ""

            role = (self.role or "").strip() if isinstance(self.role, str) else ""
            if not role:
                role = target_details.get("title") or job_details.get("title") or ""
            role = role.strip() if isinstance(role, str) else ""
            
            if not company or not role or company == "Unknown_Company" or role == "Unknown_Role":
                return {"status": "error", "error": "Could not extract company and role for referral search."}
                
            CLI_REFERRAL_SCRIPT = PROJECT_ROOT / "scripts" / "cli_referral.py"
            cmd = [PYTHON_EXEC, str(CLI_REFERRAL_SCRIPT), "--company", company, "--role", role]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout_data, stderr_data = await asyncio.gather(
                self._stream_output(process.stdout, capture=True, log_level=None),
                self._stream_output(process.stderr, capture=False, log_level=logging.INFO)
            )
            await process.wait()
            
            if process.returncode == 0:
                data = json.loads(stdout_data.strip())
                candidates = data.get("candidates", [])
                
                if not candidates:
                    return {"status": "error", "error": f"No suitable referral candidates found for {company}."}
                    
                response_text = f"🎯 *Referral Candidates for {role} at {company}*\n\n"
                for idx, cand in enumerate(candidates, 1):
                    name = cand.get("name")
                    headline = cand.get("headline")
                    profile_url = cand.get("profile_url")
                    draft = cand.get("drafted_message")
                    score = cand.get("score")
                    
                    response_text += (
                        f"*{idx}. [{name}]({profile_url})*\n"
                        f"_{headline}_\n"
                        f"*(Score: {score})*\n"
                        f"```text\n{draft}\n```\n\n"
                    )
                return {"status": "SUCCESS", "linkedin_dm": response_text}
            else:
                return {"status": "error", "error": f"Worker failed: {stderr_data}"}
                
        except Exception as e:
            logger.error(f"ReferralTask failed: {e}")
            return {"status": "error", "error": str(e)}

class ApplyTask(BaseTask):
    async def execute(self):
        logger.info(f"Spawning worker for URL: {self.url} | User ID: {self.user_id}")
        
        cmd = [PYTHON_EXEC, str(CLI_TAILOR_SCRIPT), "--json", "--headed"]
        if self.url:
            cmd.extend(["--url", self.url])
        if self.jd_text:
            cmd.extend(["--jd-text", self.jd_text])
        if self.company and isinstance(self.company, str) and self.company.strip():
            cmd.extend(["--company", self.company.strip()])
        if self.role and isinstance(self.role, str) and self.role.strip():
            cmd.extend(["--role", self.role.strip()])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout_data, stderr_data = await asyncio.gather(
                self._stream_output(process.stdout, capture=True, log_level=None),
                self._stream_output(process.stderr, capture=False, log_level=logging.INFO)
            )
            await process.wait()
            
            if process.returncode == 0:
                logger.info("Worker completed successfully.")
                try:
                    tailor_result = json.loads(stdout_data.strip())
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse tailor JSON. Stdout: {stdout_data}")
                    return {"status": "error", "message": "Failed to parse JSON output from tailor"}
                
                if self.url:
                    APPLY_SCRIPT = PROJECT_ROOT / "scripts" / "applying_to_portals" / "apply_custom_job.py"
                    apply_cmd = [
                        PYTHON_EXEC, str(APPLY_SCRIPT),
                        "--url", self.url,
                        "--resume", tailor_result.get("resume_pdf", ""),
                        "--cover-letter", tailor_result.get("cover_letter_pdf", ""),
                        "--no-review",
                        "--json",
                        "--headed"
                    ]
                    logger.info(f"Spawning auto-apply process for {self.url}...")
                    apply_proc = await asyncio.create_subprocess_exec(
                        *apply_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    a_stdout, a_stderr = await asyncio.gather(
                        self._stream_output(apply_proc.stdout, capture=True, log_level=None),
                        self._stream_output(apply_proc.stderr, capture=False, log_level=logging.INFO)
                    )
                    await apply_proc.wait()
                    
                    if apply_proc.returncode == 0:
                        try:
                            lines = a_stdout.strip().splitlines()
                            json_str = lines[-1] if lines else "{}"
                            apply_res = json.loads(json_str)
                            status = apply_res.get("status", "SUCCESS")
                            tailor_result["status"] = status
                            if status == "LOGIN_REQUIRED":
                                tailor_result["error"] = "Login Required to apply."
                            elif status == "FAILED":
                                tailor_result["error"] = apply_res.get("error", "Application failed.")
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse apply_custom_job JSON. Stdout: {a_stdout}")
                            tailor_result["status"] = "FAILED"
                            tailor_result["error"] = "Failed to parse auto-apply output."
                    else:
                        logger.error(f"Auto-apply failed with return code {apply_proc.returncode}")
                        tailor_result["status"] = "FAILED"
                        tailor_result["error"] = "Auto-apply process failed"
                        
                return tailor_result
            else:
                logger.error(f"Worker failed with return code {process.returncode}")
                return {"status": "error", "message": f"Worker failed with return code {process.returncode}"}
                
        except Exception as e:
            logger.error(f"Failed to execute worker: {e}")
            return {"status": "error", "message": str(e)}

class JobTaskFactory:
    @staticmethod
    def create_task(action: str, payload: dict, envelope_json: dict) -> BaseTask:
        if action == "SEEK_REFERRAL":
            return ReferralTask(payload, envelope_json)
        return ApplyTask(payload, envelope_json)

async def main():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD if REDIS_PASSWORD else None, decode_responses=True)
    logger.info(f"Gateway listening on Redis stream: {STREAM_REQUESTS}")
    
    last_id = "$"
    
    while True:
        try:
            await r.ping()
            logger.info("Connected to Redis successfully.")
            break
        except Exception as e:
            logger.error(f"Could not connect to Redis: {e}. Retrying in 10 seconds...")
            await asyncio.sleep(10)

    while True:
        try:
            messages = await r.xread({STREAM_REQUESTS: last_id}, count=1, block=0)
            
            for stream, msg_list in messages:
                for msg_id, msg_data in msg_list:
                    last_id = msg_id
                    logger.info(f"Received message {msg_id}: {msg_data}")
                    
                    envelope_str = msg_data.get("envelope", "{}")
                    try:
                        envelope_json = json.loads(envelope_str)
                    except Exception:
                        envelope_json = {}
                    
                    payload = envelope_json.get("payload", {})
                    url = payload.get("job_url", "")
                    jd_text = payload.get("custom_notes", "")
                    
                    if not url and not jd_text:
                        logger.warning("Message contained no url or jd_text. Skipping.")
                        continue
                        
                    action = envelope_json.get("action", "")
                    task = JobTaskFactory.create_task(action, payload, envelope_json)
                    result = await task.execute()
                        
                    mapped_payload = {
                        "status": result.get("status", "SUCCESS").upper() if result.get("status") else "SUCCESS",
                        "pdf_path": result.get("resume_pdf"),
                        "generated_text": result.get("linkedin_dm"),
                        "error_message": result.get("error") or result.get("error_message")
                    }
                    
                    response_envelope = {
                        "message_id": envelope_json.get("message_id", f"resp_{task.user_id}"),
                        "source_agent": "job-hunt-agent",
                        "target_agent": envelope_json.get("source_agent", "my-personal-tg-bot"),
                        "action": "JOB_HUNT_RESPONSE",
                        "user_id": task.user_id,
                        "chat_id": envelope_json.get("chat_id", task.user_id),
                        "payload": mapped_payload
                    }
                    
                    await r.xadd(STREAM_RESPONSES, {"envelope": json.dumps(response_envelope)})
                    logger.info(f"Published result back to {STREAM_RESPONSES}")
                    
        except Exception as e:
            if "Timeout" in str(e):
                logger.info("Timeout waiting for messages, starting new long poll...")
                continue
            logger.error(f"Error reading from stream: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Gateway shutting down.")

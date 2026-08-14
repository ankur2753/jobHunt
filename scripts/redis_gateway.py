import asyncio
import json
import logging
import subprocess
import sys
from pathlib import Path
import redis.asyncio as redis

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [Gateway] %(message)s")
logger = logging.getLogger("redis_gateway")

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI_TAILOR_SCRIPT = PROJECT_ROOT / "scripts" / "cli_tailor.py"
PYTHON_EXEC = sys.executable

# Redis Configuration
import os
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
STREAM_REQUESTS = "agent.job-hunt.requests"
STREAM_RESPONSES = "agent.job-hunt.responses"


async def process_referral(url: str, jd_text: str, company: str, role: str, user_id: str):
    """Parses text to extract company/role and spawns cli_referral.py"""
    logger.info(f"Processing referral for user {user_id}")
    
    # We can reuse cli_tailor's fetch_job_details method to cleanly extract the role/company!
    # Because we are in an async function, we can import it and await it.
    if str(PROJECT_ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from cli_tailor import fetch_job_details
    
    job_details = {}
    target_details = {}
    
    try:
        if "|" in jd_text:
            part1, part2 = [x.strip() for x in jd_text.split("|", 1)]
            if part1.startswith("http"):
                job_details = await fetch_job_details(url=part1)
                target_details = await fetch_job_details(jd_text=part2)
            elif part2.startswith("http"):
                job_details = await fetch_job_details(url=part2)
                target_details = await fetch_job_details(jd_text=part1)
            else:
                target_details = await fetch_job_details(jd_text=jd_text)
        elif jd_text.startswith("http"):
            job_details = await fetch_job_details(url=jd_text)
        else:
            target_details = await fetch_job_details(jd_text=jd_text)
            
        company = company or target_details.get("company") or job_details.get("company")
        role = role or target_details.get("title") or job_details.get("title")
        
        if not company or not role:
            return {"status": "error", "error": "Could not extract company and role"}
            
        CLI_REFERRAL_SCRIPT = PROJECT_ROOT / "scripts" / "cli_referral.py"
        cmd = [PYTHON_EXEC, str(CLI_REFERRAL_SCRIPT), "--company", company, "--role", role]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            data = json.loads(stdout.decode().strip())
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
            return {"status": "error", "error": f"Worker failed: {stderr.decode().strip()}"}
            
    except Exception as e:
        logger.error(f"process_referral failed: {e}")
        return {"status": "error", "error": str(e)}

async def process_job(url: str, jd_text: str, company: str, role: str, user_id: str):
    """Spawns the heavy cli_tailor.py script as an ephemeral process."""
    logger.info(f"Spawning worker for URL: {url} | User ID: {user_id}")
    
    cmd = [PYTHON_EXEC, str(CLI_TAILOR_SCRIPT), "--json"]
    if url:
        cmd.extend(["--url", url])
    if jd_text:
        cmd.extend(["--jd-text", jd_text])
    if company:
        cmd.extend(["--company", company])
    if role:
        cmd.extend(["--role", role])

    try:
        # Run process, capturing stdout for the JSON result
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info("Worker completed successfully.")
            return json.loads(stdout.decode().strip())
        else:
            logger.error(f"Worker failed with return code {process.returncode}")
            logger.error(f"Stderr: {stderr.decode().strip()}")
            return {"status": "error", "message": f"Worker failed: {stderr.decode().strip()}"}
            
    except Exception as e:
        logger.error(f"Failed to execute worker: {e}")
        return {"status": "error", "message": str(e)}


async def main():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD if REDIS_PASSWORD else None, decode_responses=True)
    logger.info(f"Gateway listening on Redis stream: {STREAM_REQUESTS}")
    
    # We will use XREAD to block and listen for new messages
    last_id = "$"  # Only listen for new messages from now on
    
    while True:
        try:
            # Ping to test connection
            await r.ping()
            logger.info("Connected to Redis successfully.")
            break
        except Exception as e:
            logger.error(f"Could not connect to Redis: {e}. Retrying in 10 seconds...")
            await asyncio.sleep(10)

    while True:
        try:
            # Block for up to 0 (infinite) waiting for new messages on the stream
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
                    company = payload.get("company", "")
                    role = payload.get("role", "")
                    user_id = envelope_json.get("user_id", "unknown")
                    
                    if not url and not jd_text:
                        logger.warning("Message contained no url or jd_text. Skipping.")
                        continue
                        
                    action = envelope_json.get("action", "")
                    if action == "SEEK_REFERRAL":
                        logger.info(f"Processing SEEK_REFERRAL for URL: {url}")
                        # Use cli_tailor to parse first if we have URL + override
                        # Actually wait, jd_text contains the whole string including | maybe?
                        # Let's extract the part after | if it exists.
                        # Wait, in router.py, jd_text is text.replace("/referal", "").replace("/referral", "").strip()
                        # If the user did `/referal https://... | Google`, url is https://..., jd_text is `https://... | Google`.
                        part1, part2 = "", ""
                        if "|" in jd_text:
                            parts = [p.strip() for p in jd_text.split("|", 1)]
                            if parts[0].startswith("http"):
                                part1, part2 = parts[0], parts[1]
                            elif parts[1].startswith("http"):
                                part1, part2 = parts[1], parts[0]
                            else:
                                part2 = jd_text
                        else:
                            if not url:
                                part2 = jd_text
                                
                        # To cleanly reuse the existing parser in cli_tailor:
                        # Let's run a simple python snippet to parse via LLM or just run cli_tailor?
                        # Wait, `cli_referral.py` requires `--company` and `--role`.
                        # Let's write a small inline wrapper or just use `process_referral` function.
                        result = await process_referral(url, jd_text, company, role, user_id)
                    else:
                        # Spawn the heavy worker
                        result = await process_job(url, jd_text, company, role, user_id)
                        
                    # Transform worker result to match tg-bot expected JobHuntResponsePayload
                    mapped_payload = {
                        "status": result.get("status", "SUCCESS").upper() if result.get("status") else "SUCCESS",
                        "pdf_path": result.get("resume_pdf"),
                        "generated_text": result.get("linkedin_dm"),
                        "error_message": result.get("error") or result.get("error_message")
                    }
                    
                    response_envelope = {
                        "message_id": envelope_json.get("message_id", f"resp_{user_id}"),
                        "source_agent": "job-hunt-agent",
                        "target_agent": envelope_json.get("source_agent", "my-personal-tg-bot"),
                        "action": "JOB_HUNT_RESPONSE",
                        "user_id": user_id,
                        "chat_id": envelope_json.get("chat_id", user_id),
                        "payload": mapped_payload
                    }
                    
                    # Publish result back to responses stream
                    await r.xadd(STREAM_RESPONSES, {"envelope": json.dumps(response_envelope)})
                    logger.info(f"Published result back to {STREAM_RESPONSES}")
                    
        except Exception as e:
            if "Timeout" in str(e):
                logger.info("Timeout waiting for messages, starting new long poll...")
                continue
            logger.error(f"Error reading from stream: {e}")
            await asyncio.sleep(2)  # Wait before retrying on error

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Gateway shutting down.")

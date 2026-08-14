import asyncio
import json
import redis.asyncio as redis

async def inject():
    r = redis.Redis(host="localhost", port=6379, password="secret_redis_pass", decode_responses=True)
    
    payload = {
        "status": "SUCCESS",
        "pdf_path": "/home/ankurkumar/ankur_code/agent/resumes/tailored/Resume_Accenture_CustomSoftwareEngineer_20260812_142956.pdf",
        "generated_text": "Hi [Recruiter Name], I'm Ankur Kumar, a .Net Full Stack Developer with 3+ years of experience in C#, React, SQL, and Azure. I've built scalable microservices and optimized database performance, and I'm excited about the Custom Software Engineer role at Accenture. Would you be open to a quick chat about how I can contribute?",
        "error_message": None
    }
    
    response_envelope = {
        "message_id": "resp_899547534",
        "source_agent": "job-hunt-agent",
        "target_agent": "my-personal-tg-bot",
        "action": "JOB_HUNT_RESPONSE",
        "user_id": 899547534,
        "chat_id": 899547534,
        "payload": payload
    }
    
    try:
        await r.xadd("agent.job-hunt.responses", {"envelope": json.dumps(response_envelope)})
        print("Success!")
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    asyncio.run(inject())

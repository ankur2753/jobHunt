import base64
import json
import logging
import asyncio
import os
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

logger = logging.getLogger(__name__)

class CustomLLMAgent:
    def __init__(self, api_key=None, base_url=None):
        if not AsyncOpenAI:
            logger.error("Please run: pip install openai")
            self.client = None
            return
        
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY")
        
        # If no base_url provided, route to Google's OpenAI-compatible endpoint by default if using Gemini
        default_url = "https://api.openai.com/v1"
        if not base_url and not os.getenv("LLM_BASE_URL"):
            if os.getenv("GEMINI_API_KEY") and not os.getenv("LLM_API_KEY"):
                default_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
                
        self.base_url = base_url or os.getenv("LLM_BASE_URL", default_url)
        
        if not self.api_key:
            logger.warning("No API key found (tried LLM_API_KEY, GEMINI_API_KEY). Agent will likely fail. Please set it in .env")
            
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=120.0,
            max_retries=5
        )

    async def _get_base64_screenshot(self, page):
        try:
            screenshot_bytes = await page.screenshot(type="jpeg", quality=50)
            return base64.b64encode(screenshot_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            raise

    async def execute_loop(self, page, model_name, max_steps, prompt):
        if not self.client:
            logger.error("API client not initialized. Cannot execute LLM loop.")
            return False
            
        from scripts.common_stuff.prompt_manager import load_prompt
        messages = [
            {"role": "system", "content": load_prompt("custom_llm_agent_system")},
            {"role": "user", "content": prompt}
        ]

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "click",
                    "description": "Click an element using its element_id.",
                    "parameters": {"type": "object", "properties": {"element_id": {"type": "integer"}}, "required": ["element_id"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "type_text",
                    "description": "Type text into an input field using its element_id.",
                    "parameters": {"type": "object", "properties": {"element_id": {"type": "integer"}, "value": {"type": "string"}}, "required": ["element_id", "value"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "scroll",
                    "description": "Scroll the page up or down.",
                    "parameters": {"type": "object", "properties": {"direction": {"type": "string", "enum": ["up", "down"]}}, "required": ["direction"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "mark_done",
                    "description": "Mark the task as successfully completed."
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "mark_fail",
                    "description": "Mark the task as failed or impossible."
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "ask_user",
                    "description": "Ask the user a question and wait for their reply.",
                    "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_knowledge_base",
                    "description": "Query the user's CV, past answers, and profile to answer questions like CTC, experience, education, etc. ONLY use this when you need facts about the user.",
                    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
                }
            }
        ]

        for step in range(max_steps):
            logger.info(f"Fallback step {step + 1}/{max_steps} using {model_name}")
            
            # External domain check
            try:
                current_url = page.url
                if "linkedin.com" not in current_url and "google.com" not in current_url:
                    logger.info(f"External portal detected, escaping LLM loop: {current_url}")
                    return True  # Handle external in upper orchestrator
                
                # Check for new tabs/popups
                if len(page.context.pages) > 1:
                    latest_page = page.context.pages[-1]
                    logger.info(f"New tab opened detected, escaping LLM loop: {latest_page.url}")
                    return True
            except Exception as e:
                pass
            
            try:
                screenshot_b64 = await self._get_base64_screenshot(page)
                
                # Scrape interactive elements to provide hints with Set-of-Mark IDs
                interactables_js = """
                () => {
                    let idCounter = 1;
                    const interactables = Array.from(document.querySelectorAll('input, button, select, textarea, [role="button"], a, [tabindex="0"]'));
                    const elements = [];
                    interactables.forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (style.display !== 'none' && style.visibility !== 'hidden' && el.offsetWidth > 0 && el.offsetHeight > 0) {
                            el.setAttribute('data-agent-id', idCounter);
                            let text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().replace(/\\n/g, ' ').substring(0, 50);
                            elements.push(`[ID: ${idCounter}] ${el.tagName.toLowerCase()} - "${text}"`);
                            idCounter++;
                        }
                    });
                    return elements.join('\\n');
                }
                """
                dom_hints = await page.evaluate(interactables_js)
                if not dom_hints:
                    dom_hints = "No interactable elements found."
            except Exception as e:
                logger.error(f"Cannot proceed without screenshot/DOM. Error: {e}")
                return False
                
            # Remove images from previous messages to save tokens and avoid context limit
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") == "user" and isinstance(msg.get("content"), list):
                    msg["content"] = [item for item in msg["content"] if isinstance(item, dict) and item.get("type") != "image_url"]
            
            prompt_text = (
                f"Current screen state.\n\n"
                f"Here are some interactable elements we found on the page (not 100% accurate, use as hints):\n"
                f"{dom_hints}\n\n"
                f"What is your next action? Call a tool. If these hints are wrong and you fail, you can always rely on the screenshot."
            )
            
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"}}
                ]
            })
            
            try:
                response = await self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=tools,
                    tool_choice="required",
                    max_tokens=300
                )
                
                message = response.choices[0].message
                messages.append(message)
                
                if not message.tool_calls:
                    logger.warning("LLM didn't call any tools. It just replied with text.")
                    messages.append({"role": "user", "content": "You didn't call any tool. Please call a tool."})
                    continue

                for tool_call in message.tool_calls:
                    action = tool_call.function.name
                    logger.info(f"LLM called tool: {action}")
                    try:
                        args = json.loads(tool_call.function.arguments)
                        if action in ["click", "type_text", "scroll"]:
                            import datetime
                            record = {
                                "timestamp": datetime.datetime.now().isoformat(),
                                "url": page.url,
                                "action": action,
                                "args": args
                            }
                            os.makedirs("logs", exist_ok=True)
                            with open("logs/recorded_locators.jsonl", "a") as f:
                                f.write(json.dumps(record) + "\n")
                    except json.JSONDecodeError:
                        args = {}

                    tool_result = "Success"
                    if action == "mark_done":
                        return True
                    elif action == "mark_fail":
                        return False
                    elif action == "click":
                        element_id = args.get("element_id")
                        if element_id is not None:
                            try:
                                await page.click(f'[data-agent-id="{element_id}"]', timeout=5000)
                            except Exception as e:
                                tool_result = f"Error clicking element {element_id}: {e}"
                        else:
                            tool_result = "Error: no element_id provided"
                    elif action == "type_text":
                        element_id = args.get("element_id")
                        value = args.get("value", "")
                        if element_id is not None:
                            try:
                                await page.fill(f'[data-agent-id="{element_id}"]', value, timeout=5000)
                            except Exception as e:
                                tool_result = f"Error typing into element {element_id}: {e}"
                        else:
                            tool_result = "Error: no element_id provided"
                    elif action == "scroll":
                        direction = args.get("direction", "down")
                        try:
                            if direction == "down":
                                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                            else:
                                await page.evaluate("window.scrollBy(0, -window.innerHeight)")
                        except Exception as e:
                            tool_result = f"Error scrolling: {e}"
                    elif action == "ask_user":
                        question = args.get("question")
                        if question:
                            try:
                                import redis.asyncio as redis
                                import uuid
                                r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", 6379)), password=os.getenv("REDIS_PASSWORD", "") or None, decode_responses=True)
                                
                                response_envelope = {
                                    "message_id": f"ask_user_{uuid.uuid4().hex[:8]}",
                                    "source_agent": "job-hunt-agent",
                                    "target_agent": "my-personal-tg-bot",
                                    "action": "JOB_HUNT_RESPONSE",
                                    "user_id": "default",
                                    "chat_id": "default",
                                    "payload": {
                                        "status": "SUCCESS",
                                        "generated_text": f"❓ Question from Agent:\n{question}"
                                    }
                                }
                                await r.xadd("agent.job-hunt.responses", {"envelope": json.dumps(response_envelope)})
                                
                                logger.info("Published question to user. Polling agent.job-hunt.user_replies for response...")
                                last_id = "$"
                                user_reply = None
                                while True:
                                    messages = await r.xread({"agent.job-hunt.user_replies": last_id}, count=1, block=2000)
                                    if messages:
                                        for stream, msg_list in messages:
                                            for msg_id, msg_data in msg_list:
                                                last_id = msg_id
                                                envelope_str = msg_data.get("envelope", "{}")
                                                try:
                                                    envelope_json = json.loads(envelope_str)
                                                    payload = envelope_json.get("payload", {})
                                                    user_reply = payload.get("text", "") or envelope_json.get("text", "")
                                                    if not user_reply:
                                                        user_reply = msg_data.get("text", envelope_str)
                                                except json.JSONDecodeError:
                                                    user_reply = msg_data.get("text", envelope_str)
                                        if user_reply:
                                            break
                                tool_result = f"User replied: {user_reply}"
                            except Exception as e:
                                logger.error(f"Error in ask_user tool: {e}")
                                tool_result = f"Error asking user: {e}"
                        else:
                            tool_result = "Error: no question provided"
                    elif action == "query_knowledge_base":
                        query = args.get("query")
                        if query:
                            try:
                                from scripts.common_stuff.llm_fallback import get_fallback_answer_from_llm
                                answer = get_fallback_answer_from_llm(query)
                                tool_result = f"Knowledge base says: {answer}"
                                logger.info(f"Queried knowledge base for '{query}' -> {answer}")
                            except Exception as e:
                                logger.error(f"Error querying knowledge base: {e}")
                                tool_result = f"Error querying knowledge base: {e}"
                        else:
                            tool_result = "Error: no query provided"
                    else:
                        tool_result = f"Unknown tool: {action}"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result
                    })
                    
                await page.wait_for_timeout(2000)
                
            except Exception as e:
                logger.error(f"Error in LLM loop step: {e}")
                messages.append({"role": "user", "content": f"Action failed with error: {e}"})
                
        return False

    async def run_cascade(self, page, fast_model, expensive_model, prompt):
        logger.info(f"Initiating fallback with Fast Model ({fast_model}). Max 3 steps.")
        success = await self.execute_loop(page, fast_model, max_steps=3, prompt=prompt)
        if success:
            return True

        logger.info("Fast model failed or reached limit. Reloading page and escalating to Expensive Model.")
        await page.reload(wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        logger.info(f"Initiating fallback with Expensive Model ({expensive_model}).")
        success = await self.execute_loop(page, expensive_model, max_steps=10, prompt=prompt)
        
        return success

    async def analyze_image(self, page, prompt, model_name=None):
        if not self.client:
            logger.error("API client not initialized. Cannot analyze image.")
            return None
            
        model_name = model_name or os.getenv("FAST_MODEL", "gemini-3.6-flash")
        screenshot_b64 = await self._get_base64_screenshot(page)
        
        messages = [
            {
                "role": "user", 
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"}}
                ]
            }
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=300
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in LLM image analysis: {e}")
            return None

    async def analyze_image_from_path(self, path, prompt, model_name=None):
        if not self.client:
            logger.error("API client not initialized. Cannot analyze image from path.")
            return None
            
        model_name = model_name or os.getenv("FAST_MODEL", "gemini-3.6-flash")
        
        try:
            with open(path, "rb") as image_file:
                screenshot_b64 = base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error reading image file: {e}")
            return None
        
        messages = [
            {
                "role": "user", 
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"}}
                ]
            }
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=300
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in LLM image analysis: {e}")
            return None

    async def ask_text(self, prompt, model_name=None):
        if not self.client:
            logger.error("API client not initialized. Cannot ask text.")
            return None
            
        model_name = model_name or os.getenv("FAST_MODEL", "gemini-3.6-flash")
        
        try:
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in LLM text query: {e}")
            return None

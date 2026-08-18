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
        
        # This allows using Groq, OpenRouter, Google AI Studio via OpenAI compatible endpoints
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        
        if not self.api_key:
            logger.warning("No LLM_API_KEY found. Agent will likely fail. Please set it in .env")
            
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

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
            
        messages = [
            {"role": "system", "content": "You are a web automation agent. You have tools to interact with the page (click, type_text, scroll). Use the tools to complete the user's task. If you succeed, call mark_done. If it's impossible, call mark_fail."},
            {"role": "user", "content": prompt}
        ]

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "click",
                    "description": "Click an element using a CSS selector.",
                    "parameters": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "type_text",
                    "description": "Type text into an input field.",
                    "parameters": {"type": "object", "properties": {"selector": {"type": "string"}, "value": {"type": "string"}}, "required": ["selector", "value"]}
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
            }
        ]

        for step in range(max_steps):
            logger.info(f"Fallback step {step + 1}/{max_steps} using {model_name}")
            
            try:
                screenshot_b64 = await self._get_base64_screenshot(page)
                
                # Scrape interactive elements to provide hints
                interactables_js = """
                () => {
                    const interactables = Array.from(document.querySelectorAll('input, button, select, textarea, [role="button"], a'));
                    return interactables.filter(el => {
                        const style = window.getComputedStyle(el);
                        return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetWidth > 0;
                    }).map(el => {
                        let text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().substring(0, 30);
                        let tag = el.tagName.toLowerCase();
                        let type = el.type ? `[type="${el.type}"]` : '';
                        let id = el.id ? `#${el.id}` : '';
                        let name = el.name ? `[name="${el.name}"]` : '';
                        let selector = `${tag}${id}${name}${type}`;
                        return `Selector: \\`${selector}\\` | Label/Text: "${text}"`;
                    }).slice(0, 50).join('\\n');
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
                if msg["role"] == "user" and isinstance(msg.get("content"), list):
                    msg["content"] = [item for item in msg["content"] if item.get("type") != "image_url"]
            
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
                    tool_choice="auto",
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
                    except json.JSONDecodeError:
                        args = {}

                    tool_result = "Success"
                    if action == "mark_done":
                        return True
                    elif action == "mark_fail":
                        return False
                    elif action == "click":
                        selector = args.get("selector")
                        if selector:
                            try:
                                await page.click(selector, timeout=5000)
                            except Exception as e:
                                tool_result = f"Error clicking: {e}"
                        else:
                            tool_result = "Error: no selector provided"
                    elif action == "type_text":
                        selector = args.get("selector")
                        value = args.get("value", "")
                        if selector:
                            try:
                                await page.fill(selector, value, timeout=5000)
                            except Exception as e:
                                tool_result = f"Error typing: {e}"
                        else:
                            tool_result = "Error: no selector provided"
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
            
        model_name = model_name or os.getenv("FAST_MODEL", "gemini-1.5-flash")
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
            
        model_name = model_name or os.getenv("FAST_MODEL", "gemini-1.5-flash")
        
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
            
        model_name = model_name or os.getenv("FAST_MODEL", "gemini-1.5-flash")
        
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

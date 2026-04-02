import os
import uuid
import time
import asyncio
import threading
import json
import re
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse


API_SECRET_KEY = os.getenv("API_SECRET_KEY", "Dowedar")


class AsyncBrowserThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.loop = asyncio.new_event_loop()
        self.ready_event = threading.Event()
        self.browser = None
        self.playwright = None

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._start_browser())
        self.ready_event.set()
        print("[LITE-SERVER].....")
        self.loop.run_forever()

    async def _start_browser(self):
        from playwright.async_api import async_playwright
        print("[LITE-SERVER].....")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            channel="chrome",
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-gpu',
                '--disable-dev-shm-usage-for-fast-performance',
                '--disable-setuid-sandbox',
            ]
        )

    async def _talk_to_gemini(self, prompt: str):
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = await context.new_page()
        
        try:
            page.set_default_timeout(120000)
            print("[LITE-SERVER] Navigating to Gemini...")
            await page.goto("https://gemini.google.com/", wait_until="domcontentloaded")
            
            # 1. انتظار مربع النص وكتابة الـ Prompt
            text_area_selector = '[data-placeholder="Ask Gemini"]' 
            await page.wait_for_selector(text_area_selector, timeout=60000)
            await page.fill(text_area_selector, prompt)
            await asyncio.sleep(0.5)
            
            # 2. الضغط على زر الإرسال
            await page.fill(text_area_selector, prompt)
            await asyncio.sleep(1) # ننتظر ثانية واحدة ليتعرف الموقع على النص
            await page.keyboard.press("Enter") # نضغط إنتر مباشرة
            
            # 3. انتظار ظهور صندوق الإجابة
            response_selector = 'message-content'
            await page.wait_for_selector(response_selector, timeout=120000)
            
            last_text = ""
            unchanged_count = 0
            
            print("[LITE-SERVER] Waiting for Gemini to finish typing...")
            # 4. مراقبة انتهاء الكتابة
            while unchanged_count < 4:
                messages = await page.query_selector_all(response_selector)
                if messages:
                    current_text = await messages[-1].inner_text()
                    if current_text == last_text and current_text.strip() != "":
                        unchanged_count += 1
                    else:
                        last_text = current_text
                        unchanged_count = 0
                await asyncio.sleep(1) # تم زيادة وقت الانتظار لثانية لتناسب سرعة Gemini
                
            return last_text.strip()
            
        except Exception as e:
            print(f"[LITE-SERVER] Error: {e}")
            raise e
        finally:
            await page.close()
            await context.close()


    def process_request(self, prompt: str):
        if not self.ready_event.wait(timeout=30):
            raise Exception("Error From Browser")
            
        future = asyncio.run_coroutine_threadsafe(self._talk_to_gemini(prompt), self.loop)
        return future.result(timeout=120)

browser_engine = AsyncBrowserThread()
browser_engine.start()

# ====================================================================
# Smart Prompt Builder
# ====================================================================
def format_prompt(messages, tools=None):
    parts = []
    system_parts = []
    has_tool_results = False
    user_question = ""
    
    for msg in messages:
        role = msg.get("role", "")
        msg_type = msg.get("type", "")
        content = msg.get("content", "")
        
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    text_parts.append(item.get("text", item.get("content", str(item))))
                else:
                    text_parts.append(str(item))
            content = "\n".join(text_parts)
        
        if role == "system":
            system_parts.append(content)
        elif role == "tool":
            has_tool_results = True
            tool_name = msg.get("name", "tool")
            parts.append(f"[TOOL RESULT from '{tool_name}']:\n{content}")
        elif msg_type == "function_call_output":
            has_tool_results = True
            call_id = msg.get("call_id", "")
            output_content = msg.get("output", content)
            parts.append(f"[TOOL RESULT (call_id: {call_id})]:\n{output_content}")
        elif msg_type == "function_call":
            func_name = msg.get("name", "?")
            func_args = msg.get("arguments", "{}")
            parts.append(f"[PREVIOUS TOOL CALL: Called '{func_name}' with arguments: {func_args}]")
        elif role == "assistant":
            assistant_content = content if content else ""
            tool_calls_in_msg = msg.get("tool_calls", [])
            if tool_calls_in_msg:
                tc_descriptions = []
                for tc in tool_calls_in_msg:
                    func = tc.get("function", {})
                    tc_descriptions.append(f"Called '{func.get('name', '?')}' with: {func.get('arguments', '{}')}")
                assistant_content += "\n[Previous tool calls: " + "; ".join(tc_descriptions) + "]"
            if assistant_content.strip():
                parts.append(f"[Assistant]: {assistant_content}")
        elif role == "user" or (msg_type == "message" and role != "system"):
            user_question = content
            parts.append(content)
            has_tool_results = False
        elif content:
            parts.append(content)
    
    final = ""
    
    if system_parts:
        if tools and not has_tool_results:
            final += "=== YOUR ROLE ===\n"
            final += "\n\n".join(system_parts)
            final += "\n=== END OF ROLE ===\n\n"
        else:
            final += "=== SYSTEM INSTRUCTIONS (FOLLOW STRICTLY) ===\n"
            final += "\n\n".join(system_parts)
            final += "\n=== END OF INSTRUCTIONS ===\n\n"
    
    if tools and not has_tool_results:
        final += format_tools_instruction(tools, user_question)
    
    if has_tool_results:
        final += "=== CONTEXT FROM TOOLS ===\n"
        final += "The following information was retrieved by the tools you requested.\n"
        final += "Use ONLY this information to answer the user's question.\n\n"
    
    if parts:
        final += "\n".join(parts)
    
    if has_tool_results:
        final += "\n\n=== INSTRUCTION ===\n"
        final += "Now answer the user's question based ONLY on the tool results above.\n"
    
    return final

def format_tools_instruction(tools, user_question=""):
    instruction = "\n=== MANDATORY TOOL USAGE ===\n"
    instruction += "You MUST use one of the tools below to answer this question.\n"
    instruction += "Do NOT answer directly. Do NOT say you don't have information.\n"
    instruction += "You MUST respond with ONLY a JSON object to call the tool.\n\n"
    
    instruction += "RESPONSE FORMAT - respond with ONLY this JSON, nothing else:\n"
    instruction += '{"tool_calls": [{"name": "TOOL_NAME", "arguments": {"param": "value"}}]}\n\n'
    
    instruction += "RULES:\n"
    instruction += "- Your ENTIRE response must be valid JSON only\n"
    instruction += "- No markdown, no code blocks, no explanation\n"
    instruction += "- No text before or after the JSON\n\n"
    
    instruction += "Available tools:\n\n"
    
    for tool in tools:
        func = tool.get("function", tool)
        name = func.get("name", "unknown")
        desc = func.get("description", "No description")
        params = func.get("parameters", {})
        
        instruction += f"Tool: {name}\n"
        instruction += f"Description: {desc}\n"
        
        if params.get("properties"):
            instruction += "Parameters:\n"
            required_params = params.get("required", [])
            for param_name, param_info in params["properties"].items():
                param_type = param_info.get("type", "string")
                param_desc = param_info.get("description", "")
                is_required = "required" if param_name in required_params else "optional"
                instruction += f"  - {param_name} ({param_type}, {is_required}): {param_desc}\n"
        instruction += "\n"
    
    instruction += "=== END OF TOOLS ===\n\n"
    
    first_tool = tools[0] if tools else {}
    first_func = first_tool.get("function", first_tool)
    first_name = first_func.get("name", "tool")
    
    instruction += f'EXAMPLE: If the user asks a question, respond with:\n'
    instruction += '{"tool_calls": [{"name": "' + first_name + '", "arguments": {"input": "the user question here"}}]}\n\n'
    
    instruction += "Now respond with the JSON to call the appropriate tool:\n\n"
    return instruction

def parse_tool_calls(response_text):
    cleaned = response_text.strip()
    if "```" in cleaned:
        code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', cleaned, re.DOTALL)
        if code_block_match:
            cleaned = code_block_match.group(1).strip()
    
    json_candidates = [cleaned]
    json_match = re.search(r'\{[\s\S]*"tool_calls"[\s\S]*\}', cleaned)
    if json_match:
        json_candidates.append(json_match.group(0))
    
    for candidate in json_candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "tool_calls" in parsed:
                raw_calls = parsed["tool_calls"]
                if isinstance(raw_calls, list) and len(raw_calls) > 0:
                    formatted_calls = []
                    for call in raw_calls:
                        tool_name = call.get("name", "")
                        arguments = call.get("arguments", {})
                        if isinstance(arguments, dict):
                            arguments_str = json.dumps(arguments, ensure_ascii=False)
                        else:
                            arguments_str = str(arguments)
                        
                        formatted_calls.append({
                            "id": f"call_{uuid.uuid4().hex[:24]}",
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": arguments_str
                            }
                        })
                    return formatted_calls
        except (json.JSONDecodeError, TypeError, KeyError):
            continue
    return None

# ====================================================================
# FastAPI App
# ====================================================================
app = FastAPI(title="mse_ai_api for n8n")

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):

    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": {"message": "Invalid JSON payload"}})
    
    authorization = request.headers.get("authorization", "")

    if not authorization or authorization.replace("Bearer ", "").strip() != API_SECRET_KEY:
        return JSONResponse(status_code=401, content={"error": {"message": "Invalid API Key"}})

    messages = data.get("messages", [])
    if not messages:
        return JSONResponse(status_code=400, content={"error": {"message": "messages field is required"}})
        
    try:
        tools = data.get("tools", None)
        prompt = format_prompt(messages, tools=tools)
        
        start_time = time.time()
        print(f"[LITE-SERVER]..... ({len(prompt)} len)")
        
        response_text = browser_engine.process_request(prompt)
        
        p_tokens = len(prompt.split())
        c_tokens = len(response_text.split())
        
        tool_calls = None
        if tools:
            tool_calls = parse_tool_calls(response_text)

        if tool_calls:
            return {
                "id": f"chatcmpl-{uuid.uuid4().hex[:29]}",
                "object": "chat.completion",
                "created": int(start_time),
                "model": data.get("model", "gemini-2.0-flash"),
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tool_calls
                    },
                    "finish_reason": "tool_calls"
                }],
                "usage": {
                    "prompt_tokens": p_tokens,
                    "completion_tokens": c_tokens,
                    "total_tokens": p_tokens + c_tokens
                }
            }
        else:
            return {
                "id": f"chatcmpl-{uuid.uuid4().hex[:29]}",
                "object": "chat.completion",
                "created": int(start_time),
                "model": data.get("model", "gemini-2.0-flash"),
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": p_tokens,
                    "completion_tokens": c_tokens,
                    "total_tokens": p_tokens + c_tokens
                }
            }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/v1/responses")
async def responses(request: Request):

    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": {"message": "Invalid JSON payload"}})
        
    authorization = request.headers.get("authorization", "")
    if not authorization or authorization.replace("Bearer ", "").strip() != API_SECRET_KEY:
        return JSONResponse(status_code=401, content={"error": {"message": "Invalid API Key"}})

    input_data = data.get("input", "")
    if isinstance(input_data, str):
        messages = [{"role": "user", "content": input_data}]
    elif isinstance(input_data, list):
        messages = input_data
    else:
        messages = data.get("messages", [])

    if not messages:
        return JSONResponse(status_code=400, content={"error": {"message": "input field is required"}})

    try:
        tools = data.get("tools", None)
        instructions = data.get("instructions", "")
        if instructions:
            messages.insert(0, {"role": "system", "content": instructions})
            
        prompt = format_prompt(messages, tools=tools)
        start_time = time.time()
        
        response_text = browser_engine.process_request(prompt)
        p_tokens = len(prompt.split())
        c_tokens = len(response_text.split())

        tool_calls = None
        if tools:
            tool_calls = parse_tool_calls(response_text)

        if tool_calls:
            output_items = []
            for tc in tool_calls:
                output_items.append({
                    "type": "function_call",
                    "id": tc["id"],
                    "call_id": tc["id"],
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"],
                    "status": "completed"
                })
            
            return {
                "id": f"resp-{uuid.uuid4().hex[:29]}",
                "object": "response",
                "created_at": int(start_time),
                "model": data.get("model", "gemini-2.0-flash"),
                "status": "completed",
                "output": output_items,
                "usage": {
                    "input_tokens": p_tokens,
                    "output_tokens": c_tokens,
                    "total_tokens": p_tokens + c_tokens
                }
            }
        else:
            return {
                "id": f"resp-{uuid.uuid4().hex[:29]}",
                "object": "response",
                "created_at": int(start_time),
                "model": data.get("model", "gemini-2.0-flash"),
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": response_text}]
                    }
                ],
                "usage": {
                    "input_tokens": p_tokens,
                    "output_tokens": c_tokens,
                    "total_tokens": p_tokens + c_tokens
                }
            }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/v1/models")
async def list_models():

    return {
        "object": "list",
        "data": [{"id": "gemini-2.0-flash", "object": "model", "owned_by": "mse_ai_api"}]
    }

@app.get("/")
async def health_check():
    return {"status": "running", "message": "mse_ai_api Server is active!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7777)

import asyncio
import concurrent.futures
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from llm.llm_client import LLMClient

_SERVERS_DIR = Path(__file__).parent / "mcp_servers"

import datetime

_SYSTEM_PROMPT = """
You are helpful personal assistant that answers questions about current weather and news.
Interaction are coducted in continuous, conversational maner, rather than separate inqueries.
Format answers with Markdown.
For news always render each headline as Markdown link [title](link) -
never write headline as plain text, always use exact link from data.
For weather provide temperature both C and F values.

Rules:
- If user asks only about weather, use weather tools to request up to date weather data and provide only weather data
- If user asks only about headlines, use news tools to request up to date headlines data and provide only news data
- If user asked both weather and news, use both tools to respond and provide data for both topics
    """


class Orchestrator:
    def __init__(self, model: str = "gemini-2.5-pro"):
        self._llm = LLMClient(model=model, temperature=0.7)

    def handle(self, user_query: str, history: Optional[list] = None) -> dict:
        """
        Returns {"reply": str, "tools_called": list[str]}.
        tools_called is the actual list of MCP tool names that were invoked.
        """
        coro = self._run(user_query, history or [])
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        except Exception as exc:
            logging.exception("Orchestrator error")
            return {"reply": f"Sorry, something went wrong: {exc}", "tools_called": []}

    async def _run(self, user_query: str, history: list) -> dict:
        # Start Weather Servcer
        weather_params = StdioServerParameters(
            command=sys.executable, args=[str(_SERVERS_DIR / "weather_server.py")]
        )

        # Start News Server
        news_params = StdioServerParameters(
            command=sys.executable, args=[str(_SERVERS_DIR / "news_server.py")]
        )
        async with (
            stdio_client(weather_params) as (w_r, w_w),
            stdio_client(news_params)    as (n_r, n_w),
        ):
            async with (
                ClientSession(w_r, w_w) as weather_sess,
                ClientSession(n_r, n_w) as news_sess,
            ):
                await weather_sess.initialize()
                await news_sess.initialize()
                return await self._agent_loop(user_query, history, weather_sess, news_sess)

    async def _agent_loop(
        self,
        user_query: str,
        history: list,
        weather_sess: ClientSession,
        news_sess: ClientSession,
    ) -> dict:
        # get tools from MCP servers
        w_tools = (await weather_sess.list_tools()).tools
        n_tools  = (await news_sess.list_tools()).tools

        # map tool name
        session_map = {t.name: weather_sess for t in w_tools}
        session_map.update({t.name: news_sess for t in n_tools})

        gemini_tools = _build_gemini_tools(w_tools + n_tools)

        # track which tools were actually called during this request
        tools_called: list[str] = []

        # build conversation history for Gemini
        contents = []
        for msg in history:
            # Gemini uses "model" not "assistant"
            role = "model" if msg["role"] == "assistant" else msg["role"]
            contents.append(
                types.Content(role=role, parts=[types.Part(text=msg["content"])])
            )
        contents.append(
            types.Content(role="user", parts=[types.Part(text=user_query)])
        )

        # max 5 rounds to avoid infinite loop if something goes wrong
        for _ in range(5):
            today = datetime.date.today().strftime("%A, %B %d, %Y")
            response = self._llm.generate_with_tools(
                contents=contents,
                tools=gemini_tools,
                system_instruction=_SYSTEM_PROMPT + f"\nToday's date is {today}.",
            )

            candidate_obj = response.candidates[0]
            candidate     = candidate_obj.content
            contents.append(candidate)

            # catch real error states before doing anything else
            if candidate_obj.finish_reason not in (
                types.FinishReason.STOP,
                types.FinishReason.FINISH_REASON_UNSPECIFIED,
            ):
                return {
                    "reply": f"Could not complete: {candidate_obj.finish_reason}",
                    "tools_called": tools_called,
                }

            # this SDK version uses STOP for both tool calls and final answers,
            # so we check parts to distinguish the two cases
            fn_calls = [p for p in candidate.parts if p.function_call]
            if not fn_calls:
                reply = "".join(
                    p.text for p in candidate.parts if hasattr(p, "text") and p.text
                )
                return {"reply": reply, "tools_called": tools_called}

            # execute each tool call through its MCP session
            fn_responses = []
            for part in fn_calls:
                fc = part.function_call
                tools_called.append(fc.name)  # record the actual call
                sess   = session_map[fc.name]
                result = await sess.call_tool(fc.name, dict(fc.args))
                raw = result.content[0].text if result.content else "null"

                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"output": raw}

                # Gemini requires dict for function response, wrap list if needed
                if not isinstance(data, dict):
                    data = {"result": data}

                fn_responses.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name, response=data
                        )
                    )
                )

            contents.append(types.Content(role="user", parts=fn_responses))

        return {"reply": "Sorry, I was not able to complete this request.", "tools_called": tools_called}


# helpers to convert MCP tool schemas to Gemini function declarations

_JSON_TO_GEMINI = {
    "string": types.Type.STRING,
    "integer": types.Type.INTEGER,
    "number": types.Type.NUMBER,
    "boolean": types.Type.BOOLEAN,
    "array": types.Type.ARRAY,
    "object": types.Type.OBJECT,
}


def _json_schema_to_gemini(schema: dict) -> types.Schema:
    t = _JSON_TO_GEMINI.get(schema.get("type", "string"), types.Type.STRING)
    kwargs: dict = {"type": t}
    if "description" in schema:
        kwargs["description"] = schema["description"]
    if t == types.Type.OBJECT and "properties" in schema:
        kwargs["properties"] = {
            k: _json_schema_to_gemini(v) for k, v in schema["properties"].items()
        }
        kwargs["required"] = schema.get("required", [])
    if t == types.Type.ARRAY and "items" in schema:
        kwargs["items"] = _json_schema_to_gemini(schema["items"])
    return types.Schema(**kwargs)


def _build_gemini_tools(mcp_tools) -> list:
    declarations = []
    for tool in mcp_tools:
        schema = tool.inputSchema or {}
        props = {
            name: _json_schema_to_gemini(prop)
            for name, prop in schema.get("properties", {}).items()
        }
        declarations.append(
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description or "",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties=props,
                    required=schema.get("required", []),
                ) if props else None,
            )
        )
    return [types.Tool(function_declarations=declarations)]

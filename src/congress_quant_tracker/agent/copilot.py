"""CongressQuant AI Copilot — Multi-Provider Agent with Tool Calling & Financial Reasoning."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from congress_quant_tracker.config import settings
from congress_quant_tracker.agent.tools import TOOLS_DEFINITIONS, TOOL_EXECUTORS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are CI://COPILOT, an elite Quantitative Intelligence Analyst embedded in a Bloomberg-style Capitol Hill Financial Terminal.

DATABASE & METRICS:
- Total official congressional transactions: ~2,950 records through August 2026.
- Suspicion Score: 0-25 (Routine), 26-50 (Noteworthy), 51-75 (Suspicious), 76-100 (High Alert).
- Put/Call Ratio (P/C): Defined as (Sell Trades / Buy Trades). P/C < 0.70 is BULLISH ACCUMULATION.

MANDATORY TOOL ROUTING RULES:
1. "Quais congressistas operaram opções de compra (Calls)?" or questions about Call/Put options -> Call 'query_options_trades(option_type="call")' or 'query_options_trades(option_type="put")'.
2. "Quais foram as operações com maior score de suspeita?" or highest suspicion trades -> Call 'query_trades(sort_by="score", limit=5)'.
3. "Qual papel está com melhor putcall ratio para compra?" or bullish/bearish stocks -> Call 'get_ticker_positioning_rankings(sentiment_filter="bullish")'.
4. "Quem são os top 5 deputados com maior retorno no ranking?" -> Call 'get_leaderboard(metric="highest_returns", limit=5)'.
5. Specific ticker or politician trades -> Call 'query_trades(ticker=...)' or 'get_politician_profile(name=...)'.

RESPONSE FORMATTING:
- Always respond in Portuguese when asked in Portuguese.
- Format all analytical data with clean Markdown tables, exact metrics, percentages, dollar amounts, and politician names/parties.
- Never output generic one-line acknowledgments. Always output the full quantitative analysis.
"""


class CopilotAgent:
    """Orchestrates conversations with tool-calling across Groq, OpenAI, and Local LLM."""

    def __init__(self, provider: str = "groq"):
        self.provider = provider.lower()

    def _get_provider_config(self) -> Dict[str, Any]:
        if self.provider == "openai":
            return {
                "base_url": "https://api.openai.com/v1",
                "api_key": settings.OPENAI_API_KEY,
                "model": settings.OPENAI_MODEL or "gpt-4o-mini",
            }
        elif self.provider == "local":
            return {
                "base_url": settings.LOCAL_LLM_URL or "http://127.0.0.1:8080/v1",
                "api_key": "local",
                "model": "local-model",
            }
        else:  # default to groq
            return {
                "base_url": "https://api.groq.com/openai/v1",
                "api_key": settings.GROQ_API_KEY,
                "model": settings.GROQ_MODEL or "llama-3.3-70b-versatile",
            }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tool_iterations: int = 4,
    ) -> Dict[str, Any]:
        """Execute a full tool-calling conversational cycle."""
        config = self._get_provider_config()
        if not config["api_key"] and self.provider != "local":
            return {
                "role": "assistant",
                "content": f"⚠️ Erro de Configuração: Chave de API para '{self.provider}' não configurada no .env.",
            }

        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }

        # Prepend system prompt if not present
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [
            m for m in messages if m.get("role") != "system"
        ]

        async with httpx.AsyncClient(timeout=45.0) as client:
            for iteration in range(max_tool_iterations):
                payload = {
                    "model": config["model"],
                    "messages": full_messages,
                    "tools": TOOLS_DEFINITIONS if iteration == 0 else None,
                    "temperature": 0.2,
                }
                if iteration == 0:
                    payload["tool_choice"] = "auto"

                resp = await client.post(
                    f"{config['base_url']}/chat/completions",
                    headers=headers,
                    json=payload,
                )

                if resp.status_code != 200:
                    err_msg = resp.text
                    logger.error(f"LLM API Error ({resp.status_code}): {err_msg}")
                    # Fallback to OpenAI gpt-4o-mini if Groq rate limits (429/413)
                    if (resp.status_code in (429, 413)) and settings.OPENAI_API_KEY and config["base_url"] != "https://api.openai.com/v1":
                        logger.info("Seamlessly falling back to OpenAI gpt-4o-mini due to Groq rate limit")
                        config["base_url"] = "https://api.openai.com/v1"
                        config["api_key"] = settings.OPENAI_API_KEY
                        config["model"] = "gpt-4o-mini"
                        headers["Authorization"] = f"Bearer {config['api_key']}"
                        payload["model"] = config["model"]
                        resp = await client.post(
                            f"{config['base_url']}/chat/completions",
                            headers=headers,
                            json=payload,
                        )
                        if resp.status_code != 200:
                            return {
                                "role": "assistant",
                                "content": f"⚠️ Erro ao consultar IA: {resp.text[:200]}",
                            }
                    else:
                        return {
                            "role": "assistant",
                            "content": f"⚠️ Erro ao consultar IA ({self.provider}): {err_msg[:200]}",
                        }

                data = resp.json()
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                full_messages.append(message)

                tool_calls = message.get("tool_calls")
                content = (message.get("content") or "").strip()
                if not tool_calls:
                    # Check for text-based function calls from Llama 3.3
                    import re
                    fn_match = re.search(r"<function>(\w+)\((.*?)\)</function>", content, re.DOTALL)
                    if fn_match and iteration == 0:
                        fn_name = fn_match.group(1)
                        raw_args = fn_match.group(2)
                        try:
                            args = json.loads(raw_args)
                        except Exception:
                            args = {}
                        tool_calls = [{
                            "id": f"call_text_{iteration}",
                            "function": {"name": fn_name, "arguments": json.dumps(args)}
                        }]
                    else:
                        return {
                            "role": "assistant",
                            "content": content,
                            "provider": self.provider,
                            "model": config["model"],
                        }

                # Execute tool calls
                for tc in tool_calls:
                    call_id = tc.get("id")
                    func = tc.get("function", {})
                    fn_name = func.get("name")
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except Exception:
                        args = {}

                    executor = TOOL_EXECUTORS.get(fn_name)
                    if executor:
                        try:
                            result = executor(**args)
                        except Exception as e:
                            result = {"error": f"Tool execution error: {str(e)}"}
                    else:
                        result = {"error": f"Tool '{fn_name}' not found."}

                    full_messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": fn_name,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

            # If reached max tool iterations, summarize final
            final_resp = await client.post(
                f"{config['base_url']}/chat/completions",
                headers=headers,
                json={
                    "model": config["model"],
                    "messages": full_messages,
                    "temperature": 0.2,
                },
            )
            if final_resp.status_code == 200:
                final_content = final_resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                return {
                    "role": "assistant",
                    "content": final_content,
                    "provider": self.provider,
                    "model": config["model"],
                }
            return {
                "role": "assistant",
                "content": "Análise concluída com sucesso.",
                "provider": self.provider,
                "model": config["model"],
            }

"""
TalentLens ReAct agent.

Uses langgraph.prebuilt.create_react_agent with four tools:
  - query_risk_db      : read-only SQL queries against mart schema
  - search_hr_policy   : semantic search over HR policy docs (FAISS RAG)
  - flag_for_review    : write an HITL flag for an employee
  - generate_report    : generate a department-level risk report

The agent wraps any LLM from the provider abstraction, so the same
agent can run on Anthropic, OpenAI, or local Ollama without code changes.
"""

from __future__ import annotations

import os

# ─────────────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────────────
from llm.agent.tools.query_risk_db import query_risk_db
from llm.agent.tools.search_hr_policy import search_hr_policy
from llm.agent.tools.flag_for_review import flag_for_review
from llm.agent.tools.generate_report import generate_report

TOOLS = [query_risk_db, search_hr_policy, flag_for_review, generate_report]

MAX_ITERATIONS = 5


# ─────────────────────────────────────────────────────────────────────────────
# LLM adapter — wraps our provider abstraction as a LangChain-compatible LLM
# ─────────────────────────────────────────────────────────────────────────────

def _build_langchain_llm(provider_tier: str):
    """
    Return a LangChain-compatible LLM object for the given provider tier.

    We use the official langchain_anthropic / langchain_openai wrappers when
    available (they expose bind_tools() which langgraph needs for tool-calling).
    For the local Ollama tier we use langchain_community's ChatOllama.
    """
    if provider_tier == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. "
                "Get a free key at aistudio.google.com, then:\n"
                "  export GEMINI_API_KEY=AIza..."
            )
        return ChatGoogleGenerativeAI(
            model="gemini-flash-latest",
            temperature=0,
            google_api_key=api_key,
        )

    elif provider_tier == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. "
                "Export it before running the agent with the 'openai' tier."
            )
        return ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)

    elif provider_tier == "local":
        try:
            from langchain_community.chat_models import ChatOllama
            return ChatOllama(model="llama3", temperature=0)
        except ImportError:
            raise ImportError(
                "langchain_community is required for the 'local' tier. "
                "Install it with: pip install langchain-community"
            )

    else:  # default: anthropic
        from langchain_anthropic import ChatAnthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set. "
                "Export it before running the agent with the 'anthropic' tier."
            )
        return ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            temperature=0,
            api_key=api_key,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Agent factory
# ─────────────────────────────────────────────────────────────────────────────

def get_agent(provider_tier: str = "gemini"):
    """
    Build and return the compiled langgraph ReAct agent.

    The agent uses langgraph.prebuilt.create_react_agent with the four
    TalentLens tools and a recursion limit of MAX_ITERATIONS.

    Args:
        provider_tier: "gemini" | "anthropic" | "openai" | "local"

    Returns:
        A compiled langgraph StateGraph (CompiledGraph) instance.

    Raises:
        EnvironmentError if the required API key is missing.
    """
    from langgraph.prebuilt import create_react_agent

    llm = _build_langchain_llm(provider_tier)
    agent = create_react_agent(llm, TOOLS)
    return agent


# ─────────────────────────────────────────────────────────────────────────────
# Single-turn chat interface
# ─────────────────────────────────────────────────────────────────────────────

def chat(message: str, provider_tier: str = "gemini") -> str:
    """
    Single-turn agent invocation.

    Sends *message* to the ReAct agent and returns the final assistant
    response as a plain string.  Handles errors gracefully — if the LLM
    key is missing or a tool fails, a descriptive error string is returned
    instead of raising.

    Args:
        message:       User's natural language question or instruction.
        provider_tier: "anthropic" | "openai" | "local"

    Returns:
        Agent's final response string.
    """
    try:
        agent = get_agent(provider_tier)
    except EnvironmentError as exc:
        return f"[Agent not available] {exc}"
    except ImportError as exc:
        return f"[Missing dependency] {exc}"

    try:
        # langgraph agents accept a dict with a "messages" key
        result = agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config={"recursion_limit": MAX_ITERATIONS * 2},  # langgraph uses steps, not iterations
        )
        # Extract the last AI message content
        messages = result.get("messages", [])
        for msg in reversed(messages):
            # langgraph returns BaseMessage objects
            role = getattr(msg, "type", None) or getattr(msg, "role", "")
            if role in ("ai", "assistant"):
                content = msg.content
                # content may be a list of blocks (e.g. Anthropic tool_use)
                if isinstance(content, list):
                    texts = [
                        block if isinstance(block, str)
                        else block.get("text", "")
                        for block in content
                        if isinstance(block, (str, dict))
                    ]
                    return " ".join(t for t in texts if t).strip()
                return str(content)

        return "(no response generated)"

    except Exception as exc:
        return f"[Agent error] {type(exc).__name__}: {exc}"

"""
TalentLens LLM Agent Demo
=========================
Runs 3 sample queries through the ReAct agent.

Usage:
    python llm/run_agent_demo.py

Requirements:
    export ANTHROPIC_API_KEY=sk-ant-...   # for the default anthropic tier

To use a different provider:
    PROVIDER_TIER=openai python llm/run_agent_demo.py   # needs OPENAI_API_KEY
    PROVIDER_TIER=local  python llm/run_agent_demo.py   # needs: ollama run llama3
"""

import os
import sys
import textwrap

# Ensure project root is on sys.path so sibling packages (llm, ml, api) are importable
# when the script is invoked as: python llm/run_agent_demo.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


SAMPLE_QUERIES = [
    "Which employees are at critical risk right now?",
    "What is our HR policy for handling high-risk employees?",
    "Generate a risk report for the Engineering department",
]

DIVIDER = "=" * 65


def _print_response(query: str, response: str) -> None:
    print(DIVIDER)
    print(f"QUERY: {query}")
    print(DIVIDER)
    # Wrap long responses for readability
    for line in response.splitlines():
        if len(line) > 80:
            print(textwrap.fill(line, width=80))
        else:
            print(line)
    print()


def main() -> None:
    provider_tier = os.getenv("PROVIDER_TIER", "anthropic")

    # Check for API key before doing any heavy imports
    if provider_tier == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        print(
            "\n[TalentLens Agent Demo]\n"
            "Set ANTHROPIC_API_KEY env var to run the agent demo.\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...\n\n"
            "Alternatively, set PROVIDER_TIER=local to use Ollama (no key needed):\n"
            "  PROVIDER_TIER=local python llm/run_agent_demo.py\n"
            "  (requires: ollama run llama3)\n"
        )
        sys.exit(0)

    if provider_tier == "openai" and not os.getenv("OPENAI_API_KEY"):
        print(
            "\n[TalentLens Agent Demo]\n"
            "PROVIDER_TIER=openai requires OPENAI_API_KEY to be set.\n"
            "  export OPENAI_API_KEY=sk-...\n"
        )
        sys.exit(0)

    print(f"\n{'=' * 65}")
    print(f"  TalentLens ReAct Agent Demo  |  provider: {provider_tier}")
    print(f"{'=' * 65}\n")

    # Lazy import — avoids loading heavy dependencies if key is missing
    from llm.agent.react_agent import chat

    for i, query in enumerate(SAMPLE_QUERIES, 1):
        print(f"[{i}/{len(SAMPLE_QUERIES)}] Sending query...")
        response = chat(query, provider_tier=provider_tier)
        _print_response(query, response)

    print("Demo complete.")


if __name__ == "__main__":
    main()

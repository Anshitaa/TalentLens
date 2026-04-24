"""
LangChain tool: search_hr_policy

Retrieves relevant HR policy chunks from the FAISS vector index
and returns them as labelled context for the agent.
"""

from langchain_core.tools import tool


@tool
def search_hr_policy(query: str) -> str:
    """
    Search TalentLens HR policy documents for information relevant to the query.

    Uses semantic similarity search over three policy documents:
      - hr_attrition_policy.md  (risk thresholds, manager notifications, 90-day plans)
      - compensation_policy.md  (pay bands, equity review triggers, gap thresholds)
      - performance_management.md  (PIP procedures, review cadence, escalation paths)

    Returns the top 3 most relevant text chunks with source labels.

    Args:
        query: Natural language question about HR policy.
    """
    try:
        from llm.rag.retriever import search_with_sources
        hits = search_with_sources(query, k=3)
    except FileNotFoundError:
        return (
            "[HR Policy index not found. Run llm.rag.indexer.build_index() "
            "to build the FAISS index before using this tool.]"
        )
    except Exception as exc:
        return f"[HR Policy search error: {exc}]"

    if not hits:
        return "No relevant HR policy sections found for that query."

    parts = []
    for hit in hits:
        parts.append(
            f"[Source: {hit['source']} | Rank {hit['rank']}]\n{hit['text']}"
        )

    return "\n\n---\n\n".join(parts)

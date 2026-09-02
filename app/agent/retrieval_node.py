from app.agent.state import AgentState
from app.retrieval.factory import get_embedding_client
from app.retrieval.retriever import Retriever


def retrieve_context(state: AgentState) -> dict:
    """Retrieve relevant business knowledge for the user's question."""

    client = get_embedding_client()

    retriever = Retriever(client)

    results = retriever.search(
        state["question"],
        top_k=3
    )

    context_parts = []

    for result in results:
        context_parts.append(
            f"SOURCE: {result['source']}\n"
            f"{result['content']}"
        )

    retrieved_context = "\n\n---\n\n".join(context_parts)

    return {
        "retrieved_context": retrieved_context
    }
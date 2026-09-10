import asyncio

from mcp.server import MCPServer

from app.agent.graph import agent_graph


# ============================================================
# MCP SERVER
# ============================================================

server = MCPServer(
    name="sql-agent",
    version="1.0.0",
    description="MCP interface for the self-correcting SQL agent",
)


# ============================================================
# MCP TOOL
# ============================================================

@server.tool(
    name="ask_database",
    description=(
        "Ask a natural-language question about the database. "
        "The request is processed by the self-correcting SQL agent, "
        "including safety checks, schema grounding, SQL generation, "
        "execution, criticism, and retries."
    ),
)
def ask_database(question: str) -> str:
    """
    Send a natural-language database question
    through the existing LangGraph SQL agent.
    """

    initial_state = {
        # ----------------------------------------------------
        # User input
        # ----------------------------------------------------
        "question": question,

        # ----------------------------------------------------
        # Intent / safety
        # ----------------------------------------------------
        "is_destructive": False,

        # ----------------------------------------------------
        # Grounding
        # ----------------------------------------------------
        "schema": "",
        "retrieved_context": "",

        # ----------------------------------------------------
        # SQL
        # ----------------------------------------------------
        "sql": None,
        "previous_sql": None,

        # ----------------------------------------------------
        # Execution
        # ----------------------------------------------------
        "query_result": None,
        "error": None,

        # ----------------------------------------------------
        # Critic
        # ----------------------------------------------------
        "sql_valid": False,
        "critique": "",

        # ----------------------------------------------------
        # Retry
        # ----------------------------------------------------
        "retry_count": 0,

        # ----------------------------------------------------
        # Final answer
        # ----------------------------------------------------
        "final_answer": None,
    }

    try:
        result = agent_graph.invoke(initial_state)

        # -----------------------------------------------
        # Successful final answer
        # -----------------------------------------------

        final_answer = result.get("final_answer")

        if final_answer:
            return final_answer

        # -----------------------------------------------
        # Agent execution error
        # -----------------------------------------------

        error = result.get("error")

        if error:
            return f"Agent failed: {error}"

        # -----------------------------------------------
        # Critic rejected the SQL
        # -----------------------------------------------

        critique = result.get("critique")

        if critique:
            return (
                "The agent could not produce a valid answer.\n"
                f"Critique: {critique}"
            )

        return "The agent completed without producing a final answer."

    except Exception as e:
        return f"Agent error: {str(e)}"


# ============================================================
# ENTRY POINT
# ============================================================

async def main():
    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
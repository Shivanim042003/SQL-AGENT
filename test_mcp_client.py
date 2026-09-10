import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():

    # ========================================================
    # Configure the MCP server
    # ========================================================

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "app.mcp_server.server"],
    )

    # ========================================================
    # Start MCP server and connect through stdio
    # ========================================================

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            # ------------------------------------------------
            # Initialize MCP connection
            # ------------------------------------------------

            await session.initialize()

            print("\nConnected to MCP server.\n")

            # ------------------------------------------------
            # List available tools
            # ------------------------------------------------

            tools = await session.list_tools()

            print("Available tools:")

            for tool in tools.tools:
                print(f" - {tool.name}")

            # ------------------------------------------------
            # Call our SQL agent
            # ------------------------------------------------

            print("\nCalling ask_database...\n")

            result = await session.call_tool(
                "ask_database",
                {
                    "question": "How many purchase events are there?"
                },
            )

            print("MCP RESULT:")
            print(result)


if __name__ == "__main__":
    asyncio.run(main())
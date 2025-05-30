import sys
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("Demo")



# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    print(f"Resource called with name: {name}", file=sys.stderr)
    return f"Hello, {name}!"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

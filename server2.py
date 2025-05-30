import json
import sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Application Signals MCP Server", version="0.0.1")


@mcp.tool("listApplicationSignalServices", "Lists the names of all services managed under AWS CloudWatch Application Signals")
def listApplicationSignalServices():
    return ['xray', 'slo', 'adot']

@mcp.tool("add", "adds 2 integer numbers together")
def add(a: int, b: int):
    return a + b

@mcp.resource(uri="greeting://{name}", name="testing")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    print(f"Resource called with name: {name}", file=sys.stderr)
    return f"Hello, {name}!"

@mcp.resource("greeting://{name}")
def get_greeting2222(name: str) -> str:
    """Get a personalized greeting"""
    print(f"Resource called with name: {name}", file=sys.stderr)
    return f"Hello, {name}!"

server_info = {
    "name": "Application Signals MCP Server",
    "version": "0.0.1"
}
def main():
    mcp.run('stdio')
    # for line in sys.stdin:
    #     try:
    #         parse = json.loads(line)
    #         if "jsonrpc" in parse and parse["jsonrpc"] == "2.0":
    #             if "method" in parse:
    #                 if parse["method"] == "initialize":
    #                     send_response(parse["id"], {
    #                         "protocolVersion": "2025-03-26", 
    #                         "capabilities": {
    #                             "tools": {"listChanged": True},
    #                             "resources": {"listChanged": True}
    #                         }, 
    #                         "serverInfo": server_info
    #                     })
    #                 if parse["method"] == "tools/list":
    #                     send_response(parse["id"], {
    #                         "tools": list(mcp.tools.keys()),
    #                     })
    #                 if parse["method"] == "tools/call":
    #                     params = parse.get("params", {})
    #                     tool_name = params.get("name")
    #                     tool_args = params.get("arguments", {})

    #                     tool_func = mcp.tools[tool_name]
    #                     result = tool_func(**tool_args)
    #                     send_response(parse["id"], {
    #                         "result": result
    #                     })

                    # if parse["method"] == "resources/list":
                    #     # Simply pass the resources as strings
                    #     resources = list(mcp.list_resources())
                    #     send_response(parse["id"], {
                    #         "resources": [mcp.list_resources()[0]],
                    #     })

                    # if parse["method"] == "resources/read":
                    #     uri = parse["params"]["uri"]
                    #     resource = mcp.read_resource(uri)     
                    #     send_response(parse["id"], {
                    #         "resource": resource.get(),
                    #     })      

def send_response(id: int, result):
    response = {
        "jsonrpc": "2.0",
        "result": result,
        "id": id
    }

    print(json.dumps(response))

if __name__ == "__main__":
    main()

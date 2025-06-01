# MCP Server for AWS Application Signals

MCP server for interacting with AWS Application Signals and S3.

## Development

```bash
uv pip install -e .
```


## Configuration

```json
{
    "mcpServers": {
        "appsignals": {
            "command": "uv",
            "args": [
                "--directory",
                "/PATH/TO/appsignals-mcp/src/mcp_server_appsignals",
                "run",
                "server.py"
            ],
            "env": {
                "AWS_PROFILE": "aws-profile",
                "AWS_REGION": "aws-region",
            }
        }
    }
}
```

### Temporary Credentials

```json
{
    "mcpServers": {
        "appsignals": {
            "command": "uv",
            "args": [
                "--directory",
                "/PATH/TO/appsignals-mcp/src/mcp_server_appsignals",
                "run",
                "server.py"
            ],
            "env": {
                "AWS_ACCESS_KEY_ID": "temporary-access-key",
                "AWS_SECRET_ACCESS_KEY": "temporary-secret-key",
                "AWS_SESSION_TOKEN": "temporary-session-token",
                "AWS_REGION": "aws-region",
            }
        }
    }
}
```
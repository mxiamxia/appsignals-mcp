# MCP Server for AWS Application Signals

MCP server for interacting with AWS Application Signals.

## Quick Setup

### Prerequisites
- AWS credentials configured (via `aws configure` or environment variables)
- Claude Desktop app installed
- `uv` package manager installed ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))
  - Note: `uvx` is included with `uv` installation

### Installation

You can install this MCP server in Claude Desktop using either method:

#### Method 1: Direct from GitHub (Recommended)
Add this configuration to your Claude Desktop settings:

```json
{
  "mcpServers": {
    "appsignals": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/mxiamxia/appsignals-mcp.git",
        "mcp-server-appsignals"
      ]
    }
  }
}
```

#### Method 2: Local Installation
1. Clone this repository
2. Install dependencies (if needed):
   ```bash
   uv pip install -e .
   ```
3. Add to Claude Desktop configuration:
   ```json
   {
     "mcpServers": {
       "appsignals": {
         "command": "uv",
         "args": [
           "--directory",
           "/path/to/appsignals-mcp",
           "run",
           "mcp-server-appsignals"
         ]
       }
     }
   }
   ```

#### Amazon Q Integration
Amazon Q integration is similiar to Claude Desktop setup. First to install 
[Amazon Q Developer](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/command-line-installing.html) 
and you will just add the following to your `~/.aws/amazonq/mcp.json` file:
```
{
    "mcpServers": {
        "appsignals": {
            "command": "uvx",
            "args": [
                "--from",
                "git+https://github.com/mxiamxia/appsignals-mcp.git",
                "mcp-server-appsignals"
            ],
            "env": {
                "AWS_ACCESS_KEY_ID": "<aws_access_key>",
                "AWS_SECRET_ACCESS_KEY": "<aws_secret_access_key>"
            },
            "timeout": 60000
        }
    }
}
```

### Available Tools

This server provides tools to interact with AWS Application Signals:
- `list_application_signals_services` - List all services monitored by AWS Application Signals
- `get_service_details` - Get detailed information about a specific service
- `get_service_metrics` - Query CloudWatch metrics for a service
- `get_sli_status` - Get SLI status and SLO compliance for all services
- `query_xray_traces` - Query AWS X-Ray traces for distributed tracing analysis
- `daily_health_check` - Generate comprehensive daily health reports for all monitored services
- `troubleshoot_service` - Systematic troubleshooting workflow for specific services

## Development

```bash
uv pip install -e .
```

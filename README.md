# MCP Server for AWS Application Signals

An MCP (Model Context Protocol) server that provides tools for monitoring, analyzing, and troubleshooting AWS Application Signals services. 

This server enables AI assistants to interact with AWS Application Signals to track service health, monitor SLOs (Service Level Objectives), analyze metrics, and investigate issues using distributed tracing.

## Available Tools

This server provides the following tools to interact with AWS Application Signals:

- **`list_application_signals_services`** - Lists all services monitored by AWS Application Signals

- **`get_service_details`** - Gets comprehensive information about a specific service

- **`get_service_metrics`** - Queries CloudWatch metrics for a specific service

- **`get_sli_status`** - Monitors SLI (Service Level Indicator) status and SLO compliance across all services

- **`get_service_level_objective`** - Retrieves detailed configuration for a specific SLO

- **`query_xray_traces`** - Queries AWS X-Ray traces for distributed tracing analysis

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

## Development

```bash
uv pip install -e .
```

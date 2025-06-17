# Debugging with Logs

The AppSignals MCP server includes logging to help debug issues. Logs are written to stderr to avoid interfering with the MCP protocol.

## Quick Start

Enable debug logging by setting an environment variable:
```bash
export MCP_APPSIGNALS_LOG_LEVEL=DEBUG
```

## Log Levels

- **DEBUG**: Detailed information for troubleshooting
- **INFO**: General operation status (default)
- **ERROR**: Failures and exceptions with stack traces

## What's Logged

- Tool execution start/completion with timing
- AWS API errors with details
- Service/metric counts and query parameters
- Performance metrics (execution time)

## Example Output

**Successful operation:**
```
2024-06-11 20:30:15 - INFO - Starting list_application_signals_services request
2024-06-11 20:30:15 - INFO - Retrieved 5 services from Application Signals
2024-06-11 20:30:15 - INFO - list_application_signals_services completed in 0.355s
```

**Error with details:**
```
2024-06-11 20:31:22 - ERROR - AWS ClientError in get_service_details for 'unknown-service': ResourceNotFoundException - The specified service does not exist
```

## Troubleshooting Tips

1. **Enable debug mode** when something isn't working:
   ```bash
   export MCP_APPSIGNALS_LOG_LEVEL=DEBUG
   ```

2. **Check for errors** in the output:
   - Look for "ERROR" messages
   - AWS error codes explain what went wrong
   - Stack traces show where failures occurred

3. **Monitor performance** by looking for "completed in X.XXXs" messages
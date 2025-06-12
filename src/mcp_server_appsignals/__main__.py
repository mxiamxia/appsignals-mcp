import logging
import sys

from mcp_server_appsignals.server import mcp

# Configure logging for main entry point
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the AppSignals MCP server."""
    try:
        logger.info("Starting AppSignals MCP server via stdio transport")
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server shutdown requested via keyboard interrupt")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

import logging
import os

# Constants
MAX_SERVICES = 100
SERVICE_STATUS = ("healthy", "unhealthy")

logger = logging.getLogger('appsignals-mcp')
logger.setLevel(os.environ.get('APPSIGNALS_MCP_LOG_LEVEL', 'INFO'))
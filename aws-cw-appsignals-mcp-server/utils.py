from enum import Enum
import logging
import os
from typing import Tuple

# Constants
MAX_SERVICES = 100

logger = logging.getLogger('appsignals-mcp')
logger.setLevel(os.environ.get('APPSIGNALS_MCP_LOG_LEVEL', 'INFO'))


class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    UNHEALTHY = "unhealthy"
    
    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return tuple(item.value for item in cls)

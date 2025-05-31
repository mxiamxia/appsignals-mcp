import datetime
import logging
from typing import Any, List, Literal
from aws_clients import ApplicationSignalsClient
from mcp.server.fastmcp import Context, FastMCP
from typing import Dict

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)

SERVICE_STATUS = ("healthy", "unhealthy")

mcp = FastMCP(
    'aws-cw-appsignals-mcp-server',
    dependencies=[
        'boto3',
    ],
)

app_signals_client = ApplicationSignalsClient().application_signals_client

@mcp.tool("map_services_by_status", "Puts each service on an AWS account to a bucket of healthy or unhealthy. If no input is given for the start and end date, will process services from the last 24 hours")
async def map_services_by_status(
    start_date: datetime.datetime | None, 
    end_date: datetime.datetime | None) -> Dict[str, List[Any]]:
    
    """ services by status"""

    result = {status: [] for status in SERVICE_STATUS}

    if start_date is None:
        start_date = datetime.datetime.now() - datetime.timedelta(days=1)

    if end_date is None:
        end_date = datetime.datetime.now()
    
    try:
        all_services: Dict[str, Any] = app_signals_client.list_services(
            StartTime=start_date,
            EndTime=end_date
        )

        for service in all_services['ServiceSummaries']:
            service_type = service['KeyAttributes']['Type']
            is_service = service_type == 'Service' or service_type == 'RemoteService' or service_type == 'AWS::Service'
            service_name = service['KeyAttributes']['Name']  

            if is_service and service_name:
                if _is_service_healthy(service_name):
                    result['healthy'].append(service_name)
                else:
                    result['unhealthy'].append(service_name)
    
    except Exception as e:
        _logger.error(f'Failed to list services: {str(e)}')
    
    return result

# TODO: add healthy service check
def _is_service_healthy(service_name):
    return True

def main():
    _logger.info('Starting up Application Signals MCP Server with stdio transport')
    mcp.run()

if __name__ == '__main__':
    main()
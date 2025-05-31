from datetime import datetime, timedelta
import json
import logging
from typing import Any, List, Optional, Union
from aws_clients import ApplicationSignalsClient, CloudWatchClient
from mcp.server.fastmcp import FastMCP
from typing import Dict
from utils import SERVICE_STATUS, MAX_SERVICES
from tools import MAP_SERVICES_BY_STATUS


_logger = logging.getLogger(__name__)
_logger.setLevel(logging.ERROR)

mcp = FastMCP(
    'aws-cw-appsignals-mcp-server',
    dependencies=[
        'boto3',
    ],
)

app_signals_client = ApplicationSignalsClient().application_signals_client
cw_client = CloudWatchClient().cloudwatch_client

@mcp.tool(name=MAP_SERVICES_BY_STATUS['name'], description=MAP_SERVICES_BY_STATUS['description'])
def map_services_by_status(
    start_date: Optional[datetime], 
    end_date: Optional[datetime],
    max_services: int = MAX_SERVICES) -> Union[Dict[str, List[Any]], str]:
    
    """Categorizes services by status"""

    result = {status: [] for status in SERVICE_STATUS}

    if start_date is None:
        start_date = datetime.now() - timedelta(hours=24)

    if end_date is None:
        end_date = datetime.now()
    
    try:
        all_services: Dict[str, Any] = app_signals_client.list_services(
            StartTime=start_date,
            EndTime=end_date,
            MaxResults=max_services
        )

        for service in all_services['ServiceSummaries']:
            service_type = service['KeyAttributes']['Type']
            is_service = service_type == 'Service' or service_type == 'RemoteService' or service_type == 'AWS::Service'
            service_name = service['KeyAttributes']['Name']  

            if is_service and service_name:
                if _is_service_healthy(service['KeyAttributes'], start_date, end_date):
                    if len(result['healthy']) < max_services:
                        result['healthy'].append(service_name)
                else:
                    if len(result['unhealthy']) < max_services:
                        result['unhealthy'].append(service_name)
    
    except Exception as e:
        _logger.error(f'Failed to list services: {str(e)}')
        return str(e)
    
    return result

def _is_service_healthy(key_attributes, start_time, end_time):
    slos = app_signals_client.list_service_level_objectives(
        KeyAttributes=key_attributes
    )

    slo_summaries = slos['SloSummaries']

    for summary in slo_summaries:
        slo_arn = summary['Arn']
        slo_response = app_signals_client.get_service_level_objective(
            Id=slo_arn
        )
        slo = slo_response['Slo']
        goal = slo['Goal']['AttainmentGoal']

        if slo['EvaluationType'] == 'RequestBased':
            metric = slo['RequestBasedSli']['RequestBasedSliMetric']['MonitoredRequestCountMetric']['GoodCountMetric']

            data = cw_client.get_metric_data(
                StartTime=start_time,
                EndTime=end_time,
                MetricDataQueries=metric)
            
            for result in data['MetricDataResults']:
                values = result['Values']
                for value in values:
                    if value < goal:
                        return False
    return True

def main():
    _logger.info('Starting up Application Signals MCP Server with stdio transport')
    mcp.run()

if __name__ == '__main__':
    main()
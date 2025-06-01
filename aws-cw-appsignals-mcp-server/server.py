from datetime import datetime, timedelta
from typing import Any, List, Optional, Union
from aws_clients import ApplicationSignalsClient, CloudWatchClient
from mcp.server.fastmcp import FastMCP
from typing import Dict
from utils import ServiceStatus, logger, MAX_SERVICES
from tools import MAP_SERVICES_BY_STATUS

mcp = FastMCP(
    'aws-cw-appsignals-mcp-server',
    dependencies=[
        'boto3',
    ],
)

app_signals_client = ApplicationSignalsClient().application_signals_client
cw_client = CloudWatchClient().cloudwatch_client

@mcp.tool(name=MAP_SERVICES_BY_STATUS['name'], description=MAP_SERVICES_BY_STATUS['description'])
async def map_services_by_status(
    start_time: Optional[datetime], 
    end_time: Optional[datetime],
    max_services: Optional[int]) -> Union[Dict[ServiceStatus, List[Any]], str]:
    
    """Categorizes services by status"""

    result = {status: [] for status in ServiceStatus.values()}

    if start_time is None:
        start_time = datetime.now() - timedelta(hours=24)

    if end_time is None:
        end_time = datetime.now()

    if max_services is None:
        max_services = MAX_SERVICES

    try:
        all_services: Dict[str, Any] = app_signals_client.list_services(
            StartTime=start_time,
            EndTime=end_time,
            MaxResults=max_services
        )

        for service in all_services['ServiceSummaries']:
            service_type = service['KeyAttributes']['Type']
            is_service = service_type == 'Service' or service_type == 'RemoteService' or service_type == 'AWS::Service'
            service_name = service['KeyAttributes']['Name']  

            if is_service and service_name:
                health = _get_status_for_service(service['KeyAttributes'], start_time, end_time)
                result[health].append(service_name)
    
    except Exception as e:
        logger.error(f'Failed to list services: {str(e)}')
        return str(e)
    
    return result

def _get_status_for_service(key_attributes, start_time, end_time) -> ServiceStatus:
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
        warning = slo['Goal']['WarningThreshold']

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
                        return ServiceStatus.UNHEALTHY
    return ServiceStatus.HEALTHY

def main():
    logger.info('Starting up Application Signals MCP Server with stdio transport')
    mcp.run()

if __name__ == '__main__':
    main()
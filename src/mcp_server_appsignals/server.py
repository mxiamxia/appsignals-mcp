"""AppSignals MCP Server - Core server implementation."""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from time import perf_counter as timer
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError
from mcp.server.fastmcp import FastMCP

from .sli_report_client import AWSConfig, SLIReportClient

# Initialize FastMCP server
mcp = FastMCP("appsignals")

# Configure logging
log_level = os.environ.get("MCP_APPSIGNALS_LOG_LEVEL", "INFO").upper()

# Configure root logger for the module
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr)  # Log to stderr to avoid interference with MCP protocol
    ],
)

# Initialize module logger
logger = logging.getLogger(__name__)
logger.info(f"AppSignals MCP Server initialized with log level: {log_level}")

# Get AWS region from environment variable or use default
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
logger.info(f"Using AWS region: {AWS_REGION}")

# Initialize AWS clients with logging
try:
    logs_client = boto3.client("logs", region_name=AWS_REGION)
    logger.info("AWS CloudWatch Logs client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize AWS CloudWatch Logs client: {str(e)}")
    raise


def remove_null_values(data: dict) -> dict:
    """Remove keys with None values from a dictionary.

    Args:
        data: Dictionary to clean

    Returns:
        Dictionary with None values removed
    """
    return {k: v for k, v in data.items() if v is not None}


@mcp.tool()
async def list_monitored_services(include_linked_accounts: bool = True) -> str:
    """List all services monitored by AWS Application Signals.

    Use this tool to:
    - Get an overview of all monitored services
    - See service names, types, and key attributes
    - Identify which services are being tracked
    - Count total number of services in your environment
    - View services across multiple linked AWS accounts (when include_linked_accounts=True)

    Returns a formatted list showing:
    - Service name and type
    - Key attributes (Environment, Platform, etc.)
    - AWS Account ID (available in KeyAttributes as AwsAccountId)
    - Total count of services

    This is typically the first tool to use when starting monitoring or investigation.
    
    Args:
        include_linked_accounts: Whether to include services from linked AWS accounts (default: True)
    """
    start_time_perf = timer()
    logger.info(f"Starting list_application_signals_services request (include_linked_accounts={include_linked_accounts})")

    try:
        appsignals = boto3.client("application-signals", region_name=AWS_REGION)
        logger.debug("Application Signals client created")

        # Calculate time range (last 24 hours)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)

        # Get all services
        logger.debug(f"Querying services for time range: {start_time} to {end_time}")
        response = appsignals.list_services(
            StartTime=start_time, 
            EndTime=end_time, 
            MaxResults=100,
            IncludeLinkedAccounts=include_linked_accounts
        )
        services = response.get("ServiceSummaries", [])
        logger.debug(f"Retrieved {len(services)} services from Application Signals")

        if not services:
            logger.warning("No services found in Application Signals")
            return "No services found in Application Signals."

        result = f"Application Signals Services ({len(services)} total):\n\n"

        for service in services:
            # Extract service name from KeyAttributes
            key_attrs = service.get("KeyAttributes", {})
            service_name = key_attrs.get("Name", "Unknown")
            service_type = key_attrs.get("Type", "Unknown")

            result += f"• Service: {service_name}\n"
            result += f"  Type: {service_type}\n"

            # Add key attributes
            if key_attrs:
                result += "  Key Attributes:\n"
                for key, value in key_attrs.items():
                    result += f"    {key}: {value}\n"

            result += "\n"

        elapsed_time = timer() - start_time_perf
        logger.info(f"list_monitored_services completed in {elapsed_time:.3f}s")
        return result

    except ClientError as e:
        logger.error(
            f"AWS ClientError in list_monitored_services: {e.response['Error']['Code']} - {e.response['Error']['Message']}"
        )
        return f"AWS Error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error in list_monitored_services: {str(e)}", exc_info=True)
        return f"Error: {str(e)}"


@mcp.tool()
async def get_service_detail(service_name: str, include_linked_accounts: bool = True) -> str:
    """Get detailed information about a specific Application Signals service.

    Use this tool when you need to:
    - Understand a service's configuration and setup
    - Understand where this servive is deployed and where it is running such as EKS, Lambda, etc.
    - See what metrics are available for a service
    - Find log groups associated with the service
    - Get service metadata and attributes

    Returns comprehensive details including:
    - Key attributes (Type, Environment, Platform)
    - Available CloudWatch metrics with namespaces
    - Metric dimensions and types
    - Associated log groups for debugging

    This tool is essential before querying specific metrics, as it shows
    which metrics are available for the service.

    Args:
        service_name: Name of the service to get details for (case-sensitive)
        include_linked_accounts: Whether to include services from linked AWS accounts (default: True)
    """
    start_time_perf = timer()
    logger.info(f"Starting get_service_healthy_detail request for service: {service_name} (include_linked_accounts={include_linked_accounts})")

    try:
        appsignals = boto3.client("application-signals", region_name="us-east-1")
        logger.debug("Application Signals client created")

        # Calculate time range (last 24 hours)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)

        # First, get all services to find the one we want
        services_response = appsignals.list_services(
            StartTime=start_time, 
            EndTime=end_time, 
            MaxResults=100,
            IncludeLinkedAccounts=include_linked_accounts
        )

        # Find the service with matching name
        target_service = None
        for service in services_response.get("ServiceSummaries", []):
            key_attrs = service.get("KeyAttributes", {})
            if key_attrs.get("Name") == service_name:
                target_service = service
                break

        if not target_service:
            logger.warning(f"Service '{service_name}' not found in Application Signals")
            return f"Service '{service_name}' not found in Application Signals."

        # Get detailed service information
        logger.debug(f"Getting detailed information for service: {service_name}")
        service_response = appsignals.get_service(
            StartTime=start_time, EndTime=end_time, KeyAttributes=target_service["KeyAttributes"]
        )

        service_details = service_response["Service"]

        # Build detailed response
        result = f"Service Details: {service_name}\n\n"

        # Key Attributes
        key_attrs = service_details.get("KeyAttributes", {})
        if key_attrs:
            result += "Key Attributes:\n"
            for key, value in key_attrs.items():
                result += f"  {key}: {value}\n"
            result += "\n"

        # Attribute Maps (Platform, Application, Telemetry info)
        attr_maps = service_details.get("AttributeMaps", [])
        if attr_maps:
            result += "Additional Attributes:\n"
            for attr_map in attr_maps:
                for key, value in attr_map.items():
                    result += f"  {key}: {value}\n"
            result += "\n"

        # Metric References
        metric_refs = service_details.get("MetricReferences", [])
        if metric_refs:
            result += f"Metric References ({len(metric_refs)} total):\n"
            for metric in metric_refs:
                result += f"  • {metric.get('Namespace', '')}/{metric.get('MetricName', '')}\n"
                result += f"    Type: {metric.get('MetricType', '')}\n"
                dimensions = metric.get("Dimensions", [])
                if dimensions:
                    result += "    Dimensions: "
                    dim_strs = [f"{d['Name']}={d['Value']}" for d in dimensions]
                    result += ", ".join(dim_strs) + "\n"
                result += "\n"

        # Log Group References
        log_refs = service_details.get("LogGroupReferences", [])
        if log_refs:
            result += f"Log Group References ({len(log_refs)} total):\n"
            for log_ref in log_refs:
                log_group = log_ref.get("Identifier", "Unknown")
                result += f"  • {log_group}\n"
            result += "\n"

        elapsed_time = timer() - start_time_perf
        logger.info(f"get_service_detail completed for '{service_name}' in {elapsed_time:.3f}s")
        return result

    except ClientError as e:
        logger.error(
            f"AWS ClientError in get_service_healthy_detail for '{service_name}': {e.response['Error']['Code']} - {e.response['Error']['Message']}"
        )
        return f"AWS Error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error in get_service_healthy_detail for '{service_name}': {str(e)}", exc_info=True)
        return f"Error: {str(e)}"


@mcp.tool()
async def query_service_metrics(
    service_name: str, 
    metric_name: str, 
    statistic: str = "Average", 
    extended_statistic: str = "p99", 
    hours: int = 1,
    include_linked_accounts: bool = True
) -> str:
    """Get CloudWatch metrics for a specific Application Signals service.

    Use this tool to:
    - Analyze service performance (latency, throughput)
    - Check error rates and reliability
    - View trends over time
    - Get both standard statistics (Average, Max) and percentiles (p99, p95)

    Common metric names:
    - 'Latency': Response time in milliseconds
    - 'Error': Percentage of failed requests
    - 'Fault': Percentage of server errors (5xx)

    Returns:
    - Summary statistics (latest, average, min, max)
    - Recent data points with timestamps
    - Both standard and percentile values when available

    The tool automatically adjusts the granularity based on time range:
    - Up to 3 hours: 1-minute resolution
    - Up to 24 hours: 5-minute resolution
    - Over 24 hours: 1-hour resolution

    Args:
        service_name: Name of the service to get metrics for
        metric_name: Specific metric name (if empty, lists available metrics)
        statistic: Standard statistic type (Average, Sum, Maximum, Minimum, SampleCount)
        extended_statistic: Extended statistic (p99, p95, p90, p50, etc)
        hours: Number of hours to look back (default 1, max 168 for 1 week)
        include_linked_accounts: Whether to include services from linked AWS accounts (default: True)
    """
    start_time_perf = timer()
    logger.info(
        f"Starting query_service_metrics request - service: {service_name}, metric: {metric_name}, hours: {hours}, include_linked_accounts: {include_linked_accounts}"
    )

    try:
        appsignals = boto3.client("application-signals", region_name=AWS_REGION)
        cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)
        logger.debug("AWS clients created")

        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # Get service details to find metrics
        services_response = appsignals.list_services(
            StartTime=start_time, 
            EndTime=end_time, 
            MaxResults=100,
            IncludeLinkedAccounts=include_linked_accounts
        )

        # Find the target service
        target_service = None
        for service in services_response.get("ServiceSummaries", []):
            key_attrs = service.get("KeyAttributes", {})
            if key_attrs.get("Name") == service_name:
                target_service = service
                break

        if not target_service:
            logger.warning(f"Service '{service_name}' not found in Application Signals")
            return f"Service '{service_name}' not found in Application Signals."

        # Get detailed service info for metric references
        service_response = appsignals.get_service(
            StartTime=start_time, EndTime=end_time, KeyAttributes=target_service["KeyAttributes"]
        )

        metric_refs = service_response["Service"].get("MetricReferences", [])

        if not metric_refs:
            logger.warning(f"No metrics found for service '{service_name}'")
            return f"No metrics found for service '{service_name}'."

        # If no specific metric requested, show available metrics
        if not metric_name:
            result = f"Available metrics for service '{service_name}':\n\n"
            for metric in metric_refs:
                result += f"• {metric.get('MetricName', 'Unknown')}\n"
                result += f"  Namespace: {metric.get('Namespace', 'Unknown')}\n"
                result += f"  Type: {metric.get('MetricType', 'Unknown')}\n"
                result += "\n"
            return result

        # Find the specific metric
        target_metric = None
        for metric in metric_refs:
            if metric.get("MetricName") == metric_name:
                target_metric = metric
                break

        if not target_metric:
            available = [m.get("MetricName", "Unknown") for m in metric_refs]
            return f"Metric '{metric_name}' not found for service '{service_name}'. Available: {', '.join(available)}"

        # Calculate appropriate period based on time range
        if hours <= 3:
            period = 60  # 1 minute
        elif hours <= 24:
            period = 300  # 5 minutes
        else:
            period = 3600  # 1 hour

        # Check if we need to specify an AccountId for cross-account metrics
        account_id = None
        
        # First check if the metric reference has an AccountId
        if hasattr(target_metric, "AccountId") and target_metric.get("AccountId"):
            account_id = target_metric.get("AccountId")
        # If not, try to get it from the service's KeyAttributes
        elif "KeyAttributes" in service_response["Service"] and service_response["Service"]["KeyAttributes"].get("AwsAccountId"):
            account_id = service_response["Service"]["KeyAttributes"].get("AwsAccountId")
        
        # Build metric data query for standard statistic
        metric_query_standard = {
            "Id": "m1",
            "MetricStat": {
                "Metric": {
                    "Namespace": target_metric["Namespace"],
                    "MetricName": target_metric["MetricName"],
                    "Dimensions": target_metric.get("Dimensions", [])
                },
                "Period": period,
                "Stat": statistic
            },
            "ReturnData": True
        }
        
        # Add AccountId to the metric query if available
        if account_id:
            metric_query_standard["AccountId"] = account_id
        
        # Build metric data query for extended statistic (percentile)
        metric_query_extended = {
            "Id": "m2",
            "MetricStat": {
                "Metric": {
                    "Namespace": target_metric["Namespace"],
                    "MetricName": target_metric["MetricName"],
                    "Dimensions": target_metric.get("Dimensions", [])
                },
                "Period": period,
                "Stat": extended_statistic
            },
            "ReturnData": True
        }
        
        # Add AccountId to the extended metric query if available
        if account_id:
            metric_query_extended["AccountId"] = account_id
        
        # Build parameters for CloudWatch call
        params = {
            "MetricDataQueries": [metric_query_standard, metric_query_extended],
            "StartTime": start_time,
            "EndTime": end_time
        }
        
        # Note: AccountId is added to each individual MetricDataQuery, not at the top level
            
        # Get both standard and extended statistics in a single call using get_metric_data
        response = cloudwatch.get_metric_data(**params)
        
        # Process the response which has a different format than get_metric_statistics
        metric_results = response.get("MetricDataResults", [])
        
        # Convert to a format similar to what we had with get_metric_statistics
        datapoints = []
        
        # Get timestamps from the first result (they should be the same for both)
        if metric_results and len(metric_results) > 0 and metric_results[0].get("Timestamps"):
            timestamps = metric_results[0].get("Timestamps", [])
            
            # Create datapoints with both statistics
            for i, timestamp in enumerate(timestamps):
                datapoint = {"Timestamp": timestamp}
                
                # Add standard statistic if available
                if len(metric_results) > 0 and i < len(metric_results[0].get("Values", [])):
                    datapoint[statistic] = metric_results[0]["Values"][i]
                
                # Add extended statistic if available
                if len(metric_results) > 1 and i < len(metric_results[1].get("Values", [])):
                    datapoint[extended_statistic] = metric_results[1]["Values"][i]
                
                datapoints.append(datapoint)

        if not datapoints:
            logger.warning(
                f"No data points found for metric '{metric_name}' on service '{service_name}' in the last {hours} hour(s)"
            )
            return f"No data points found for metric '{metric_name}' on service '{service_name}' in the last {hours} hour(s)."

        # Sort by timestamp (already sorted by CloudWatch, but just to be sure)
        datapoints.sort(key=lambda x: x["Timestamp"])

        # Build response
        result = f"Metrics for {service_name} - {metric_name}\n"
        result += f"Time Range: Last {hours} hour(s)\n"
        result += f"Period: {period} seconds\n\n"

        # Calculate summary statistics for both standard and extended statistics
        standard_values = [dp.get(statistic) for dp in datapoints if dp.get(statistic) is not None]
        extended_values = [dp.get(extended_statistic) for dp in datapoints if dp.get(extended_statistic) is not None]

        result += "Summary:\n"

        if standard_values:
            latest_standard = datapoints[-1].get(statistic)
            avg_of_standard = sum(standard_values) / len(standard_values)
            max_standard = max(standard_values)
            min_standard = min(standard_values)

            result += f"{statistic} Statistics:\n"
            result += f"• Latest: {latest_standard:.2f}\n"
            result += f"• Average: {avg_of_standard:.2f}\n"
            result += f"• Maximum: {max_standard:.2f}\n"
            result += f"• Minimum: {min_standard:.2f}\n\n"

        if extended_values:
            latest_extended = datapoints[-1].get(extended_statistic)
            avg_extended = sum(extended_values) / len(extended_values)
            max_extended = max(extended_values)
            min_extended = min(extended_values)

            result += f"{extended_statistic} Statistics:\n"
            result += f"• Latest: {latest_extended:.2f}\n"
            result += f"• Average: {avg_extended:.2f}\n"
            result += f"• Maximum: {max_extended:.2f}\n"
            result += f"• Minimum: {min_extended:.2f}\n\n"

        result += f"• Data Points: {len(datapoints)}\n\n"

        # Show recent values (last 10) with both metrics
        result += "Recent Values:\n"
        for dp in datapoints[-10:]:
            timestamp = dp["Timestamp"].strftime("%m/%d %H:%M")
            unit = dp.get("Unit", "")

            values_str = []
            if dp.get(statistic) is not None:
                values_str.append(f"{statistic}: {dp[statistic]:.2f}")
            if dp.get(extended_statistic) is not None:
                values_str.append(f"{extended_statistic}: {dp[extended_statistic]:.2f}")

            result += f"• {timestamp}: {', '.join(values_str)} {unit}\n"

        elapsed_time = timer() - start_time_perf
        logger.info(f"query_service_metrics completed for '{service_name}/{metric_name}' in {elapsed_time:.3f}s")
        return result

    except ClientError as e:
        logger.error(
            f"AWS ClientError in query_service_metrics for '{service_name}/{metric_name}': {e.response['Error']['Code']} - {e.response['Error']['Message']}"
        )
        return f"AWS Error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(
            f"Unexpected error in query_service_metrics for '{service_name}/{metric_name}': {str(e)}", exc_info=True
        )
        return f"Error: {str(e)}"


def get_trace_summaries_paginated(xray_client, start_time, end_time, filter_expression, max_traces: int = 100) -> list:
    """Get trace summaries with pagination to avoid exceeding response size limits.

    Args:
        xray_client: Boto3 X-Ray client
        start_time: Start time for trace query
        end_time: End time for trace query
        filter_expression: X-Ray filter expression
        max_traces: Maximum number of traces to retrieve (default 100)

    Returns:
        List of trace summaries
    """
    all_traces = []
    next_token = None
    logger.debug(f"Starting paginated trace retrieval - filter: {filter_expression}, max_traces: {max_traces}")

    try:
        while len(all_traces) < max_traces:
            # Build request parameters
            kwargs = {
                "StartTime": start_time,
                "EndTime": end_time,
                "FilterExpression": filter_expression,
                "Sampling": True,
                "TimeRangeType": "Service",
            }

            if next_token:
                kwargs["NextToken"] = next_token

            # Make request
            response = xray_client.get_trace_summaries(**kwargs)

            # Add traces from this page
            traces = response.get("TraceSummaries", [])
            all_traces.extend(traces)
            logger.debug(f"Retrieved {len(traces)} traces in this page, total so far: {len(all_traces)}")

            # Check if we have more pages
            next_token = response.get("NextToken")
            if not next_token:
                break

            # If we've collected enough traces, stop
            if len(all_traces) >= max_traces:
                all_traces = all_traces[:max_traces]
                break

        logger.info(f"Successfully retrieved {len(all_traces)} traces")
        return all_traces

    except Exception as e:
        # Return what we have so far if there's an error
        logger.error(f"Error during paginated trace retrieval: {str(e)}", exc_info=True)
        logger.info(f"Returning {len(all_traces)} traces retrieved before error")
        return all_traces


@mcp.tool()
async def get_slo(slo_id: str) -> str:
    """Get detailed information about a specific Service Level Objective (SLO).

    Use this tool to:
    - Get comprehensive SLO configuration details
    - Understand what metrics the SLO monitors
    - See threshold values and comparison operators
    - Extract operation names and key attributes for trace queries
    - Identify dependency configurations
    - Review attainment goals and burn rate settings

    Returns detailed information including:
    - SLO name, description, and metadata
    - Metric configuration (for period-based or request-based SLOs)
    - Key attributes and operation names
    - Metric type (LATENCY or AVAILABILITY)
    - Threshold values and comparison operators
    - Goal configuration (attainment percentage, time interval)
    - Burn rate configurations

    This tool is essential for:
    - Understanding why an SLO was breached
    - Getting the exact operation name to query traces
    - Identifying the metrics and thresholds being monitored
    - Planning remediation based on SLO configuration

    Args:
        slo_id: The ARN or name of the SLO to retrieve
    """
    start_time_perf = timer()
    logger.info(f"Starting get_service_level_objective request for SLO: {slo_id}")

    try:
        appsignals = boto3.client("application-signals", region_name="us-east-1")
        logger.debug("Application Signals client created")

        response = appsignals.get_service_level_objective(Id=slo_id)
        slo = response.get("Slo", {})

        if not slo:
            logger.warning(f"No SLO found with ID: {slo_id}")
            return f"No SLO found with ID: {slo_id}"

        result = "Service Level Objective Details\n"
        result += "=" * 50 + "\n\n"

        # Basic info
        result += f"Name: {slo.get('Name', 'Unknown')}\n"
        if slo.get("Description"):
            result += f"Description: {slo['Description']}\n"
        result += f"Evaluation Type: {slo.get('EvaluationType', 'Unknown')}\n"
        result += f"Created: {slo.get('CreatedTime', 'Unknown')}\n"
        result += f"Last Updated: {slo.get('LastUpdatedTime', 'Unknown')}\n\n"

        # Goal configuration
        goal = slo.get("Goal", {})
        if goal:
            result += "Goal Configuration:\n"
            result += f"• Attainment Goal: {goal.get('AttainmentGoal', 99)}%\n"
            result += f"• Warning Threshold: {goal.get('WarningThreshold', 50)}%\n"

            interval = goal.get("Interval", {})
            if "RollingInterval" in interval:
                rolling = interval["RollingInterval"]
                result += f"• Interval: Rolling {rolling.get('Duration')} {rolling.get('DurationUnit')}\n"
            elif "CalendarInterval" in interval:
                calendar = interval["CalendarInterval"]
                result += f"• Interval: Calendar {calendar.get('Duration')} {calendar.get('DurationUnit')} starting {calendar.get('StartTime')}\n"
            result += "\n"

        # Period-based SLI
        if "Sli" in slo:
            sli = slo["Sli"]
            result += "Period-Based SLI Configuration:\n"

            sli_metric = sli.get("SliMetric", {})
            if sli_metric:
                # Key attributes - crucial for trace queries
                key_attrs = sli_metric.get("KeyAttributes", {})
                if key_attrs:
                    result += "• Key Attributes:\n"
                    for k, v in key_attrs.items():
                        result += f"  - {k}: {v}\n"

                # Operation name - essential for trace filtering
                if sli_metric.get("OperationName"):
                    result += f"• Operation Name: {sli_metric['OperationName']}\n"
                    result += f'  (Use this in trace queries: annotation[aws.local.operation]="{sli_metric["OperationName"]}")\n'

                result += f"• Metric Type: {sli_metric.get('MetricType', 'Unknown')}\n"

                # MetricDataQueries - detailed metric configuration
                metric_queries = sli_metric.get("MetricDataQueries", [])
                if metric_queries:
                    result += "• Metric Data Queries:\n"
                    for query in metric_queries:
                        query_id = query.get("Id", "Unknown")
                        result += f"  Query ID: {query_id}\n"

                        # MetricStat details
                        metric_stat = query.get("MetricStat", {})
                        if metric_stat:
                            metric = metric_stat.get("Metric", {})
                            if metric:
                                result += f"    Namespace: {metric.get('Namespace', 'Unknown')}\n"
                                result += f"    MetricName: {metric.get('MetricName', 'Unknown')}\n"

                                # Dimensions - crucial for understanding what's being measured
                                dimensions = metric.get("Dimensions", [])
                                if dimensions:
                                    result += "    Dimensions:\n"
                                    for dim in dimensions:
                                        result += (
                                            f"      - {dim.get('Name', 'Unknown')}: {dim.get('Value', 'Unknown')}\n"
                                        )

                            result += f"    Period: {metric_stat.get('Period', 'Unknown')} seconds\n"
                            result += f"    Stat: {metric_stat.get('Stat', 'Unknown')}\n"
                            if metric_stat.get("Unit"):
                                result += f"    Unit: {metric_stat['Unit']}\n"

                        # Expression if present
                        if query.get("Expression"):
                            result += f"    Expression: {query['Expression']}\n"

                        result += f"    ReturnData: {query.get('ReturnData', True)}\n"

                # Dependency config
                dep_config = sli_metric.get("DependencyConfig", {})
                if dep_config:
                    result += "• Dependency Configuration:\n"
                    dep_attrs = dep_config.get("DependencyKeyAttributes", {})
                    if dep_attrs:
                        result += "  Key Attributes:\n"
                        for k, v in dep_attrs.items():
                            result += f"    - {k}: {v}\n"
                    if dep_config.get("DependencyOperationName"):
                        result += f"  - Dependency Operation: {dep_config['DependencyOperationName']}\n"
                        result += f'    (Use in traces: annotation[aws.remote.operation]="{dep_config["DependencyOperationName"]}")\n'

            result += f"• Threshold: {sli.get('MetricThreshold', 'Unknown')}\n"
            result += f"• Comparison: {sli.get('ComparisonOperator', 'Unknown')}\n\n"

        # Request-based SLI
        if "RequestBasedSli" in slo:
            rbs = slo["RequestBasedSli"]
            result += "Request-Based SLI Configuration:\n"

            rbs_metric = rbs.get("RequestBasedSliMetric", {})
            if rbs_metric:
                # Key attributes
                key_attrs = rbs_metric.get("KeyAttributes", {})
                if key_attrs:
                    result += "• Key Attributes:\n"
                    for k, v in key_attrs.items():
                        result += f"  - {k}: {v}\n"

                # Operation name
                if rbs_metric.get("OperationName"):
                    result += f"• Operation Name: {rbs_metric['OperationName']}\n"
                    result += f'  (Use this in trace queries: annotation[aws.local.operation]="{rbs_metric["OperationName"]}")\n'

                result += f"• Metric Type: {rbs_metric.get('MetricType', 'Unknown')}\n"

                # MetricDataQueries - detailed metric configuration
                metric_queries = rbs_metric.get("MetricDataQueries", [])
                if metric_queries:
                    result += "• Metric Data Queries:\n"
                    for query in metric_queries:
                        query_id = query.get("Id", "Unknown")
                        result += f"  Query ID: {query_id}\n"

                        # MetricStat details
                        metric_stat = query.get("MetricStat", {})
                        if metric_stat:
                            metric = metric_stat.get("Metric", {})
                            if metric:
                                result += f"    Namespace: {metric.get('Namespace', 'Unknown')}\n"
                                result += f"    MetricName: {metric.get('MetricName', 'Unknown')}\n"

                                # Dimensions - crucial for understanding what's being measured
                                dimensions = metric.get("Dimensions", [])
                                if dimensions:
                                    result += "    Dimensions:\n"
                                    for dim in dimensions:
                                        result += (
                                            f"      - {dim.get('Name', 'Unknown')}: {dim.get('Value', 'Unknown')}\n"
                                        )

                            result += f"    Period: {metric_stat.get('Period', 'Unknown')} seconds\n"
                            result += f"    Stat: {metric_stat.get('Stat', 'Unknown')}\n"
                            if metric_stat.get("Unit"):
                                result += f"    Unit: {metric_stat['Unit']}\n"

                        # Expression if present
                        if query.get("Expression"):
                            result += f"    Expression: {query['Expression']}\n"

                        result += f"    ReturnData: {query.get('ReturnData', True)}\n"

                # Dependency config
                dep_config = rbs_metric.get("DependencyConfig", {})
                if dep_config:
                    result += "• Dependency Configuration:\n"
                    dep_attrs = dep_config.get("DependencyKeyAttributes", {})
                    if dep_attrs:
                        result += "  Key Attributes:\n"
                        for k, v in dep_attrs.items():
                            result += f"    - {k}: {v}\n"
                    if dep_config.get("DependencyOperationName"):
                        result += f"  - Dependency Operation: {dep_config['DependencyOperationName']}\n"
                        result += f'    (Use in traces: annotation[aws.remote.operation]="{dep_config["DependencyOperationName"]}")\n'

            result += f"• Threshold: {rbs.get('MetricThreshold', 'Unknown')}\n"
            result += f"• Comparison: {rbs.get('ComparisonOperator', 'Unknown')}\n\n"

        # Burn rate configurations
        burn_rates = slo.get("BurnRateConfigurations", [])
        if burn_rates:
            result += "Burn Rate Configurations:\n"
            for br in burn_rates:
                result += f"• Look-back window: {br.get('LookBackWindowMinutes')} minutes\n"

        elapsed_time = timer() - start_time_perf
        logger.info(f"get_service_level_objective completed for '{slo_id}' in {elapsed_time:.3f}s")
        return result

    except ClientError as e:
        logger.error(
            f"AWS ClientError in get_service_level_objective for '{slo_id}': {e.response['Error']['Code']} - {e.response['Error']['Message']}"
        )
        return f"AWS Error: {e.response['Error']['Message']}"
    except Exception as e:
        logger.error(f"Unexpected error in get_service_level_objective for '{slo_id}': {str(e)}", exc_info=True)
        return f"Error: {str(e)}"


@mcp.tool()
async def search_transaction_spans(
    log_group_name: str = "",
    start_time: str = "",
    end_time: str = "",
    query_string: str = "",
    limit: Optional[int] = None,
    max_timeout: int = 30,
) -> Dict:
    """Executes a CloudWatch Logs Insights query for transaction search (100% sampled trace data).

    IMPORTANT: If log_group_name is not provided use 'aws/spans' as default cloudwatch log group name.
    The volume of returned logs can easily overwhelm the agent context window. Always include a limit in the query
    (| limit 50) or using the limit parameter.

    Usage:
    "aws/spans" log group stores OpenTelemetry Spans data with many attributes for all monitored services.
    This provides 100% sampled data vs X-Ray's 5% sampling, giving more accurate results.
    User can write CloudWatch Logs Insights queries to group, list attribute with sum, avg.

    ```
    FILTER attributes.aws.local.service = "customers-service-java" and attributes.aws.local.environment = "eks:demo/default" and attributes.aws.remote.operation="InvokeModel"
    | STATS sum(`attributes.gen_ai.usage.output_tokens`) as `avg_output_tokens` by `attributes.gen_ai.request.model`, `attributes.aws.local.service`,bin(1h)
    | DISPLAY avg_output_tokens, `attributes.gen_ai.request.model`, `attributes.aws.local.service`
    ```

    Returns:
    --------
        A dictionary containing the final query results, including:
            - status: The current status of the query (e.g., Scheduled, Running, Complete, Failed, etc.)
            - results: A list of the actual query results if the status is Complete.
            - statistics: Query performance statistics
            - messages: Any informational messages about the query
            - transaction_search_status: Information about transaction search availability
    """
    start_time_perf = timer()
    logger.info(f"Starting search_transactions - log_group: {log_group_name}, start: {start_time}, end: {end_time}")
    logger.debug(f"Query string: {query_string}")

    # Check if transaction search is enabled
    is_enabled, destination, status = check_transaction_search_enabled(AWS_REGION)

    if not is_enabled:
        logger.warning(f"Transaction Search not enabled - Destination: {destination}, Status: {status}")
        return {
            "status": "Transaction Search Not Available",
            "transaction_search_status": {"enabled": False, "destination": destination, "status": status},
            "message": (
                "⚠️ Transaction Search is not enabled for this account. "
                f"Current configuration: Destination={destination}, Status={status}. "
                "Transaction Search requires sending traces to CloudWatch Logs (destination='CloudWatchLogs' and status='ACTIVE'). "
                "Without Transaction Search, you only have access to 5% sampled trace data through X-Ray. "
                "To get 100% trace visibility, please enable Transaction Search in your X-Ray settings. "
                "As a fallback, you can use query_sampled_traces() but results may be incomplete due to sampling."
            ),
            "fallback_recommendation": "Use query_sampled_traces() with X-Ray filter expressions for 5% sampled data.",
        }

    try:
        # Use default log group if none provided
        if log_group_name == "" or log_group_name is None:
            log_group_name = "aws/spans"
            logger.debug("Using default log group: aws/spans")
        # Start query
        kwargs = {
            "startTime": int(datetime.fromisoformat(start_time.replace('Z', '+00:00')).timestamp()),
            "endTime": int(datetime.fromisoformat(end_time.replace('Z', '+00:00')).timestamp()),
            "queryString": query_string,
            "logGroupNames": [log_group_name],
            "limit": limit,
        }

        logger.debug(f"Starting CloudWatch Logs query with limit: {limit}")
        start_response = logs_client.start_query(**remove_null_values(kwargs))
        query_id = start_response["queryId"]
        logger.info(f"Started CloudWatch Logs query with ID: {query_id}")

        # Seconds
        poll_start = timer()
        while poll_start + max_timeout > timer():
            response = logs_client.get_query_results(queryId=query_id)
            status = response["status"]

            if status in {"Complete", "Failed", "Cancelled"}:
                elapsed_time = timer() - start_time_perf
                logger.info(f"Query {query_id} finished with status {status} in {elapsed_time:.3f}s")

                if status == "Failed":
                    logger.error(f"Query failed: {response.get('statistics', {})}")
                elif status == "Complete":
                    logger.debug(f"Query returned {len(response.get('results', []))} results")

                return {
                    "queryId": query_id,
                    "status": status,
                    "statistics": response.get("statistics", {}),
                    "results": [
                        {field["field"]: field["value"] for field in line} for line in response.get("results", [])
                    ],
                    "transaction_search_status": {
                        "enabled": True,
                        "destination": "CloudWatchLogs",
                        "status": "ACTIVE",
                        "message": "✅ Using 100% sampled trace data from Transaction Search",
                    },
                }

            await asyncio.sleep(1)

        elapsed_time = timer() - start_time_perf
        msg = f"Query {query_id} did not complete within {max_timeout} seconds. Use get_query_results with the returned queryId to try again to retrieve query results."
        logger.warning(f"Query timeout after {elapsed_time:.3f}s: {msg}")
        return {
            "queryId": query_id,
            "status": "Polling Timeout",
            "message": msg,
        }

    except Exception as e:
        logger.error(f"Error in search_transactions: {str(e)}", exc_info=True)
        raise


@mcp.tool()
async def list_slis(hours: int = 24, include_linked_accounts: bool = True) -> str:
    """Get SLI (Service Level Indicator) status and SLO compliance for all services.

    Use this tool to:
    - Check overall system health at a glance
    - Identify services with breached SLOs (Service Level Objectives)
    - See which specific SLOs are failing
    - Prioritize which services need immediate attention
    - Monitor SLO compliance trends
    - View services across multiple linked AWS accounts (when include_linked_accounts=True)

    Returns a comprehensive report showing:
    - Summary counts (total, healthy, breached, insufficient data)
    - Detailed list of breached services with:
      - Service name and environment
      - Number and names of breached SLOs
      - Specific SLO violations
    - List of healthy services
    - Services with insufficient data

    This is the primary tool for health monitoring and should be used:
    - At the start of each day
    - During incident response
    - For regular health checks
    - When investigating "what is the root cause of breaching SLO" questions

    Status meanings:
    - OK: All SLOs are being met
    - BREACHED: One or more SLOs are violated
    - INSUFFICIENT_DATA: Not enough data to determine status

    To investigate breached SLOs, follow these steps:
    1. Call get_service_level_objective() with SLO name to get the detailed SLI data including Metric statistics
    2. Find the fault metrics from SLI under the breached SLO
    3. Build trace query filters using metric dimensions (Operation, RemoteOperation, etc.):
        - For availability: `service("service-name"){fault = true} AND annotation[aws.local.operation]="operation-name"`
        - For latency: `service("service-name") AND annotation[aws.local.operation]="operation-name" AND duration > threshold`
    4. Query traces:
        - If Transaction Search is enabled: Use search_transaction_spans() for 100% trace visibility
        - If not enabled: Use query_sampled_traces() with X-Ray (only 5% sampled data - may miss issues)
    5. The query time window should default to last 3 hours if not specified. Max query time window length is 6 hours
    6. Analyze the root causes from Exception data in traces
    7. Include findings in the report and give fix and mitigation suggestions

    Args:
        hours: Number of hours to look back (default 24, typically use 24 for daily checks)
        include_linked_accounts: Whether to include services from linked AWS accounts (default: True)
    """
    start_time_perf = timer()
    logger.info(f"Starting get_sli_status request for last {hours} hours (include_linked_accounts={include_linked_accounts})")

    try:
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        logger.debug(f"Time range: {start_time} to {end_time}")

        # Initialize AWS Application Signals client
        appsignals = boto3.client("application-signals", region_name="us-east-1")

        # Get all services (AWS API expects Unix timestamps as integers)
        services_response = appsignals.list_services(
            StartTime=int(start_time.timestamp()), 
            EndTime=int(end_time.timestamp()), 
            MaxResults=100,
            IncludeLinkedAccounts=include_linked_accounts
        )
        services = services_response.get("ServiceSummaries", [])

        if not services:
            logger.warning("No services found in Application Signals")
            return "No services found in Application Signals."

        # Get SLI reports for each service
        reports = []
        logger.debug(f"Generating SLI reports for {len(services)} services")
        for service in services:
            try:
                # Create config for this service
                service_name = service["KeyAttributes"].get("Name", "Unknown")
                service_environment = service["KeyAttributes"].get("Environment", "Unknown")
                service_type = service["KeyAttributes"].get("Type", "Service")
                # Extract AWS account ID from service attributes
                aws_account_id = service["KeyAttributes"].get("AwsAccountId", "")

                # Create custom config with the service's key attributes
                config = AWSConfig(
                    region="us-east-1",
                    period_in_hours=hours, 
                    service_name=service_name, 
                    service_environment = service_environment,
                    service_type=service_type,
                    aws_account_id = aws_account_id)
                
                # If there are other attributes in KeyAttributes that need to be used,
                # we can access them directly from service["KeyAttributes"] when needed

                # Generate SLI report
                client = SLIReportClient(config)
                sli_report = client.generate_sli_report()

                # Convert to expected format
                report = {
                    "BreachedSloCount": sli_report.breached_slo_count,
                    "BreachedSloNames": sli_report.breached_slo_names,
                    "EndTime": sli_report.end_time.timestamp(),
                    "OkSloCount": sli_report.ok_slo_count,
                    "ReferenceId": {"KeyAttributes": service["KeyAttributes"]},
                    "SliStatus": "BREACHED" if sli_report.sli_status == "CRITICAL" else sli_report.sli_status,
                    "StartTime": sli_report.start_time.timestamp(),
                    "TotalSloCount": sli_report.total_slo_count,
                }
                reports.append(report)

            except Exception as e:
                # Log error but continue with other services
                logger.error(f"Failed to get SLI report for service {service_name}: {str(e)}", exc_info=True)
                # Add a report with insufficient data status
                report = {
                    "BreachedSloCount": 0,
                    "BreachedSloNames": [],
                    "EndTime": end_time.timestamp(),
                    "OkSloCount": 0,
                    "ReferenceId": {"KeyAttributes": service["KeyAttributes"]},
                    "SliStatus": "INSUFFICIENT_DATA",
                    "StartTime": start_time.timestamp(),
                    "TotalSloCount": 0,
                }
                reports.append(report)

        # Check transaction search status
        is_tx_search_enabled, tx_destination, tx_status = check_transaction_search_enabled(AWS_REGION)

        # Build response
        result = f"SLI Status Report - Last {hours} hours\n"
        result += f"Time Range: {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%Y-%m-%d %H:%M')}\n\n"

        # Add transaction search status
        if is_tx_search_enabled:
            result += "✅ Transaction Search: ENABLED (100% trace visibility available)\n\n"
        else:
            result += f"⚠️ Transaction Search: NOT ENABLED (only 5% sampled traces available)\n"
            result += f"   Current config: Destination={tx_destination}, Status={tx_status}\n"
            result += "   Enable Transaction Search for accurate root cause analysis\n\n"

        # Count by status
        status_counts = {
            "OK": sum(1 for r in reports if r["SliStatus"] == "OK"),
            "BREACHED": sum(1 for r in reports if r["SliStatus"] == "BREACHED"),
            "INSUFFICIENT_DATA": sum(1 for r in reports if r["SliStatus"] == "INSUFFICIENT_DATA"),
        }

        result += "Summary:\n"
        result += f"• Total Services: {len(reports)}\n"
        result += f"• Healthy (OK): {status_counts['OK']}\n"
        result += f"• Breached: {status_counts['BREACHED']}\n"
        result += f"• Insufficient Data: {status_counts['INSUFFICIENT_DATA']}\n\n"

        # Group by status
        if status_counts["BREACHED"] > 0:
            result += "⚠️  BREACHED SERVICES:\n"
            for report in reports:
                if report["SliStatus"] == "BREACHED":
                    name = report["ReferenceId"]["KeyAttributes"]["Name"]
                    env = report["ReferenceId"]["KeyAttributes"]["Environment"]
                    breached_count = report["BreachedSloCount"]
                    total_count = report["TotalSloCount"]
                    breached_names = report["BreachedSloNames"]

                    result += f"\n• {name} ({env})\n"
                    result += f"  SLOs: {breached_count}/{total_count} breached\n"
                    if breached_names:
                        result += "  Breached SLOs:\n"
                        for slo_name in breached_names:
                            result += f"    - {slo_name}\n"

        if status_counts["OK"] > 0:
            result += "\n✅ HEALTHY SERVICES:\n"
            for report in reports:
                if report["SliStatus"] == "OK":
                    name = report["ReferenceId"]["KeyAttributes"]["Name"]
                    env = report["ReferenceId"]["KeyAttributes"]["Environment"]
                    ok_count = report["OkSloCount"]

                    result += f"• {name} ({env}) - {ok_count} SLO(s) healthy\n"

        if status_counts["INSUFFICIENT_DATA"] > 0:
            result += "\n❓ INSUFFICIENT DATA:\n"
            for report in reports:
                if report["SliStatus"] == "INSUFFICIENT_DATA":
                    name = report["ReferenceId"]["KeyAttributes"]["Name"]
                    env = report["ReferenceId"]["KeyAttributes"]["Environment"]

                    result += f"• {name} ({env})\n"

        # Remove the auto-investigation feature

        elapsed_time = timer() - start_time_perf
        logger.info(
            f"get_sli_status completed in {elapsed_time:.3f}s - Total: {len(reports)}, Breached: {status_counts['BREACHED']}, OK: {status_counts['OK']}"
        )
        return result

    except Exception as e:
        logger.error(f"Error in get_sli_status: {str(e)}", exc_info=True)
        return f"Error getting SLI status: {str(e)}"


def check_transaction_search_enabled(region: str = "us-east-1") -> tuple[bool, str, str]:
    """Internal function to check if AWS X-Ray Transaction Search is enabled.

    Returns:
        tuple: (is_enabled: bool, destination: str, status: str)
    """
    try:
        xray_client = boto3.client("xray", region_name=region)
        response = xray_client.get_trace_segment_destination()

        destination = response.get("Destination", "Unknown")
        status = response.get("Status", "Unknown")

        is_enabled = destination == "CloudWatchLogs" and status == "ACTIVE"
        logger.debug(f"Transaction Search check - Enabled: {is_enabled}, Destination: {destination}, Status: {status}")

        return is_enabled, destination, status

    except Exception as e:
        logger.error(f"Error checking transaction search status: {str(e)}")
        return False, "Unknown", "Error"


@mcp.tool()
async def query_sampled_traces(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    filter_expression: Optional[str] = None,
    region: str = "us-east-1",
) -> str:
    """Query AWS X-Ray traces (5% sampled data) to investigate errors and performance issues.

    ⚠️ IMPORTANT: This tool uses X-Ray's 5% sampled trace data. For 100% trace visibility,
    enable Transaction Search and use search_transaction_spans() instead.

    Use this tool to:
    - Find root causes of errors and faults (with 5% sampling limitations)
    - Analyze request latency and identify bottlenecks
    - Understand the requests across multiple services with traces
    - Debug timeout and dependency issues
    - Understand service-to-service interactions
    - Find customer impact from trace result such as Users data or trace attributes such as owner id


    Common filter expressions:
    - 'service("service-name"){fault = true}': Find all traces with faults (5xx errors) for a service
    - 'service("service-name")': Filter by specific service
    - 'duration > 5': Find slow requests (over 5 seconds)
    - 'http.status = 500': Find specific HTTP status codes
    - 'annotation[aws.local.operation]="GET /owners/*/lastname"': Filter by specific operation (from metric dimensions)
    - 'annotation[aws.remote.operation]="ListOwners"': Filter by remote operation name
    - Combine filters: 'service("api"){fault = true} AND annotation[aws.local.operation]="POST /visits"'

    IMPORTANT: When investigating SLO breaches, use annotation filters with the specific dimension values
    from the breached metric (e.g., Operation, RemoteOperation) to find traces for that exact operation.

    Returns JSON with trace summaries including:
    - Trace ID for detailed investigation
    - Duration and response time
    - Error/fault/throttle status
    - HTTP information (method, status, URL)
    - Service interactions
    - User information if available
    - Exception root causes (ErrorRootCauses, FaultRootCauses, ResponseTimeRootCauses)

    Best practices:
    - Start with recent time windows (last 1-3 hours)
    - Use filter expressions to narrow down issues and query Fault and Error traces for high priority
    - Look for patterns in errors or very slow requests

    Args:
        start_time: Start time in ISO format (e.g., '2024-01-01T00:00:00Z'). Defaults to 3 hours ago
        end_time: End time in ISO format (e.g., '2024-01-01T01:00:00Z'). Defaults to current time
        filter_expression: X-Ray filter expression to narrow results (see examples above)
        region: AWS region (default: us-east-1)

    Returns:
        JSON string containing trace summaries with error status, duration, and service details
    """
    start_time_perf = timer()
    logger.info(f"Starting query_sampled_traces - region: {region}, filter: {filter_expression}")

    try:
        xray_client = boto3.client("xray", region_name=region)
        logger.debug("X-Ray client created")

        # Default to past 3 hours if times not provided
        if not end_time:
            end_datetime = datetime.utcnow()
        else:
            end_datetime = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        if not start_time:
            start_datetime = end_datetime - timedelta(hours=3)
        else:
            start_datetime = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

        # Validate time window to ensure it's not too large (max 6 hours)
        time_diff = end_datetime - start_datetime
        logger.debug(
            f"Query time window: {start_datetime} to {end_datetime} ({time_diff.total_seconds() / 3600:.1f} hours)"
        )
        if time_diff > timedelta(hours=6):
            logger.warning(f"Time window too large: {time_diff.total_seconds() / 3600:.1f} hours")
            return json.dumps(
                {
                    "error": "Time window too large. Maximum allowed is 6 hours.",
                    "requested_hours": time_diff.total_seconds() / 3600,
                },
                indent=2,
            )

        # Use pagination helper with a reasonable limit
        traces = get_trace_summaries_paginated(
            xray_client,
            start_datetime,
            end_datetime,
            filter_expression or "",
            max_traces=100,  # Limit to prevent response size issues
        )

        # Convert response to JSON-serializable format
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        trace_summaries = []
        for trace in traces:
            # Create a simplified trace data structure to reduce size
            trace_data = {
                "Id": trace.get("Id"),
                "Duration": trace.get("Duration"),
                "ResponseTime": trace.get("ResponseTime"),
                "HasError": trace.get("HasError"),
                "HasFault": trace.get("HasFault"),
                "HasThrottle": trace.get("HasThrottle"),
                "Http": trace.get("Http", {}),
            }

            # Only include root causes if they exist (to save space)
            if trace.get("ErrorRootCauses"):
                trace_data["ErrorRootCauses"] = trace.get("ErrorRootCauses", [])[:3]  # Limit to first 3
            if trace.get("FaultRootCauses"):
                trace_data["FaultRootCauses"] = trace.get("FaultRootCauses", [])[:3]  # Limit to first 3
            if trace.get("ResponseTimeRootCauses"):
                trace_data["ResponseTimeRootCauses"] = trace.get("ResponseTimeRootCauses", [])[:3]  # Limit to first 3

            # Include limited annotations for key operations
            annotations = trace.get("Annotations", {})
            if annotations:
                # Only include operation-related annotations
                filtered_annotations = {}
                for key in ["aws.local.operation", "aws.remote.operation"]:
                    if key in annotations:
                        filtered_annotations[key] = annotations[key]
                if filtered_annotations:
                    trace_data["Annotations"] = filtered_annotations

            # Include user info if available
            if trace.get("Users"):
                trace_data["Users"] = trace.get("Users", [])[:2]  # Limit to first 2 users

            # Convert any datetime objects to ISO format strings
            for key, value in trace_data.items():
                trace_data[key] = convert_datetime(value)
            trace_summaries.append(trace_data)

        # Check transaction search status
        is_tx_search_enabled, tx_destination, tx_status = check_transaction_search_enabled(region)

        result_data = {
            "TraceSummaries": trace_summaries,
            "TraceCount": len(trace_summaries),
            "Message": f"Retrieved {len(trace_summaries)} traces (limited to prevent size issues)",
            "SamplingNote": "⚠️ This data is from X-Ray's 5% sampling. Results may not show all errors or issues.",
            "TransactionSearchStatus": {
                "enabled": is_tx_search_enabled,
                "recommendation": (
                    "Transaction Search is available! Use search_transaction_spans() for 100% trace visibility."
                    if is_tx_search_enabled
                    else "Enable Transaction Search for 100% trace visibility instead of 5% sampling."
                ),
            },
        }

        elapsed_time = timer() - start_time_perf
        logger.info(f"query_sampled_traces completed in {elapsed_time:.3f}s - retrieved {len(trace_summaries)} traces")
        return json.dumps(result_data, indent=2)

    except Exception as e:
        logger.error(f"Error in query_sampled_traces: {str(e)}", exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")

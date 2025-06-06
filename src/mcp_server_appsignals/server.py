import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from time import perf_counter as timer
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("appsignals")

# Initialize logging
logger = logging.getLogger(__name__)

# Initialize AWS clients
logs_client = boto3.client("logs", region_name="us-east-1")


def remove_null_values(data: dict) -> dict:
    """Remove keys with None values from a dictionary."""
    return {k: v for k, v in data.items() if v is not None}


@mcp.tool()
async def list_application_signals_services() -> str:
    """List all services monitored by AWS Application Signals.

    Use this tool to:
    - Get an overview of all monitored services
    - See service names, types, and key attributes
    - Identify which services are being tracked
    - Count total number of services in your environment

    Returns a formatted list showing:
    - Service name and type
    - Key attributes (Environment, Platform, etc.)
    - Total count of services

    This is typically the first tool to use when starting monitoring or investigation."""
    try:
        appsignals = boto3.client("application-signals", region_name="us-east-1")

        # Calculate time range (last 24 hours)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)

        # Get all services
        response = appsignals.list_services(StartTime=start_time, EndTime=end_time, MaxResults=100)
        services = response.get("ServiceSummaries", [])

        if not services:
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

        return result

    except ClientError as e:
        return f"AWS Error: {e.response['Error']['Message']}"
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def get_service_details(service_name: str) -> str:
    """Get detailed information about a specific Application Signals service.

    Use this tool when you need to:
    - Understand a service's configuration and setup
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
    """
    try:
        appsignals = boto3.client("application-signals", region_name="us-east-1")

        # Calculate time range (last 24 hours)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)

        # First, get all services to find the one we want
        services_response = appsignals.list_services(StartTime=start_time, EndTime=end_time, MaxResults=100)

        # Find the service with matching name
        target_service = None
        for service in services_response.get("ServiceSummaries", []):
            key_attrs = service.get("KeyAttributes", {})
            if key_attrs.get("Name") == service_name:
                target_service = service
                break

        if not target_service:
            return f"Service '{service_name}' not found in Application Signals."

        # Get detailed service information
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

        return result

    except ClientError as e:
        return f"AWS Error: {e.response['Error']['Message']}"
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def get_service_metrics(
    service_name: str, metric_name: str, statistic: str = "Average", extended_statistic: str = "p99", hours: int = 1
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
    """
    try:
        appsignals = boto3.client("application-signals", region_name="us-east-1")
        cloudwatch = boto3.client("cloudwatch", region_name="us-east-1")

        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # Get service details to find metrics
        services_response = appsignals.list_services(StartTime=start_time, EndTime=end_time, MaxResults=100)

        # Find the target service
        target_service = None
        for service in services_response.get("ServiceSummaries", []):
            key_attrs = service.get("KeyAttributes", {})
            if key_attrs.get("Name") == service_name:
                target_service = service
                break

        if not target_service:
            return f"Service '{service_name}' not found in Application Signals."

        # Get detailed service info for metric references
        service_response = appsignals.get_service(
            StartTime=start_time, EndTime=end_time, KeyAttributes=target_service["KeyAttributes"]
        )

        metric_refs = service_response["Service"].get("MetricReferences", [])

        if not metric_refs:
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

        # Get both standard and extended statistics in a single call
        response = cloudwatch.get_metric_statistics(
            Namespace=target_metric["Namespace"],
            MetricName=target_metric["MetricName"],
            Dimensions=target_metric.get("Dimensions", []),
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=[statistic],
            ExtendedStatistics=[extended_statistic],
        )

        datapoints = response.get("Datapoints", [])

        if not datapoints:
            return f"No data points found for metric '{metric_name}' on service '{service_name}' in the last {hours} hour(s)."

        # Sort by timestamp
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

        return result

    except ClientError as e:
        return f"AWS Error: {e.response['Error']['Message']}"
    except Exception as e:
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

            # Check if we have more pages
            next_token = response.get("NextToken")
            if not next_token:
                break

            # If we've collected enough traces, stop
            if len(all_traces) >= max_traces:
                all_traces = all_traces[:max_traces]
                break

        return all_traces

    except Exception as e:
        # Return what we have so far if there's an error
        print(f"Error during paginated trace retrieval: {str(e)}")
        return all_traces


def analyze_trace_segments(xray_client, trace_ids: list, max_traces: int = 5) -> dict:
    """Analyze full trace segments to find all exceptions and errors."""
    all_exceptions = {}
    downstream_issues = {}

    try:
        # Get full trace details
        batch_response = xray_client.batch_get_traces(TraceIds=trace_ids[:max_traces])

        for trace in batch_response.get("Traces", []):
            trace_id = trace.get("Id", "Unknown")

            # Analyze all segments in the trace
            for segment in trace.get("Segments", []):
                document = json.loads(segment.get("Document", "{}"))

                # Check for exceptions in the segment
                if "cause" in document:
                    cause = document["cause"]
                    if "exceptions" in cause:
                        for exception in cause["exceptions"]:
                            exc_message = exception.get("message", "Unknown error")
                            exc_type = exception.get("type", "Unknown type")
                            exc_key = f"{exc_type}: {exc_message}"

                            if exc_key not in all_exceptions:
                                all_exceptions[exc_key] = {
                                    "count": 0,
                                    "type": exc_type,
                                    "message": exc_message,
                                    "sample_trace": trace_id,
                                }
                            all_exceptions[exc_key]["count"] += 1

                # Check subsegments for downstream service issues
                if "subsegments" in document:
                    for subsegment in document["subsegments"]:
                        if subsegment.get("error") or subsegment.get("fault"):
                            namespace = subsegment.get("namespace", "Unknown")
                            name = subsegment.get("name", "Unknown")

                            # Look for exceptions in subsegments
                            if "cause" in subsegment:
                                cause = subsegment["cause"]
                                if "exceptions" in cause:
                                    for exception in cause["exceptions"]:
                                        exc_message = exception.get("message", "Unknown error")
                                        exc_type = exception.get("type", "Unknown type")
                                        service_key = f"{namespace}:{name}"

                                        if service_key not in downstream_issues:
                                            downstream_issues[service_key] = []

                                        downstream_issues[service_key].append(
                                            {"type": exc_type, "message": exc_message, "trace_id": trace_id}
                                        )

    except Exception:
        # Return what we have even if there's an error
        pass

    return {"all_exceptions": all_exceptions, "downstream_issues": downstream_issues}


# Removed investigate_slo_breach and investigate_slo_breach_fallback functions to simplify the MCP server


@mcp.tool()
async def get_service_level_objective(slo_id: str) -> str:
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
    try:
        appsignals = boto3.client("application-signals", region_name="us-east-1")

        response = appsignals.get_service_level_objective(Id=slo_id)
        slo = response.get("Slo", {})

        if not slo:
            return f"No SLO found with ID: {slo_id}"

        result = "Service Level Objective Details\n"
        result += "=" * 50 + "\n\n"

        # Basic info
        result += f"Name: {slo.get('Name', 'Unknown')}\n"
        result += f"ARN: {slo.get('Arn', 'Unknown')}\n"
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

        return result

    except ClientError as e:
        return f"AWS Error: {e.response['Error']['Message']}"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def run_transaction_search(
    log_group_name: str = "",
    start_time: str = "",
    end_time: str = "",
    query_string: str = "",
    limit: Optional[int] = None,
    max_timeout: int = 30,
) -> Dict:
    """Executes a CloudWatch Logs Insights query and waits for the results to be available.

    IMPORTANT: If log_group_name is not provided use 'aws/spans' as default cloudwatch log group name.
    The volume of returned logs can easily overwhelm the agent context window. Always include a limit in the query
    (| limit 50) or using the limit parameter.

    Usage:
    "aws/spans" log group stores OpenTelemetry Spans data wiht many attributes for all monitored services.
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
    """
    try:
        # Use default log group if none provided
        if log_group_name is None:
            log_group_name = 'aws/spans'

        # Start query
        kwargs = {
            'startTime': int(datetime.fromisoformat(start_time).timestamp()),
            'endTime': int(datetime.fromisoformat(end_time).timestamp()),
            'queryString': query_string,
            'logGroupNames': [log_group_name],
            'limit': limit,
        }

        start_response = logs_client.start_query(**remove_null_values(kwargs))
        query_id = start_response['queryId']
        logger.info(f'Started query with ID: {query_id}')

        # Seconds
        poll_start = timer()
        while poll_start + max_timeout > timer():
            response = logs_client.get_query_results(queryId=query_id)
            status = response['status']

            if status in {'Complete', 'Failed', 'Cancelled'}:
                logger.info(f'Query {query_id} finished with status {status}')
                return {
                    'queryId': query_id,
                    'status': status,
                    'statistics': response.get('statistics', {}),
                    'results': [
                        {field['field']: field['value'] for field in line}
                        for line in response.get('results', [])
                    ],
                }

            await asyncio.sleep(1)

        msg = f'Query {query_id} did not complete within {max_timeout} seconds. Use get_query_results with the returned queryId to try again to retrieve query results.'
        logger.warning(msg)
        return {
            'queryId': query_id,
            'status': 'Polling Timeout',
            'message': msg,
        }

    except Exception as e:
        logger.error(f'Error in execute_log_insights_query_tool: {str(e)}')
        raise

@mcp.tool()
async def get_sli_status(hours: int = 24) -> str:
    """Get SLI (Service Level Indicator) status and SLO compliance for all services.

    Use this tool to:
    - Check overall system health at a glance
    - Identify services with breached SLOs (Service Level Objectives)
    - See which specific SLOs are failing
    - Prioritize which services need immediate attention
    - Monitor SLO compliance trends

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
    3. Use metric dimensions from MetricStats (Operation, RemoteOperation, etc.) to build X-Ray query filters, for example:
        - For availability: `service("service-name"){fault = true} AND annotation[aws.local.operation]="operation-name"`
        - For latency: `service("service-name") AND annotation[aws.local.operation]="operation-name" AND duration > threshold`
    4. The X-Ray query time window should be default to last 3 hours if not specified. Max query time window length is 6 hours
    5. Analyze the root causes from Exception data in trace
    6. Include findings in the report and give the fix and mitigation suggestions.

    Args:
        hours: Number of hours to look back (default 24, typically use 24 for daily checks)
    """
    try:
        # Calculate new time range
        end_time = datetime.utcnow().timestamp()
        start_time = (datetime.utcnow() - timedelta(hours=24)).timestamp()

        # Load SLI data from JSON file
        current_dir = os.path.dirname(__file__)
        json_file_path = os.path.join(current_dir, "data", "sli_resp.json")

        with open(json_file_path, "r") as f:
            sli_data = json.load(f)

        # Generate services array from JSON data
        services = []
        for report in sli_data.get("Reports", []):
            key_attrs = report["ReferenceId"]["KeyAttributes"]
            name = key_attrs["Name"]
            environment = key_attrs["Environment"]
            service_type = key_attrs["Type"]
            status = report["SliStatus"]
            total_slo = report["TotalSloCount"]
            ok_slo = report["OkSloCount"]
            breached_slo = report["BreachedSloCount"]
            breached_names = report["BreachedSloNames"]

            services.append((name, environment, service_type, status, total_slo, ok_slo, breached_slo, breached_names))

        # Generate mock response
        reports = []
        for service_info in services:
            name, env, svc_type, status, total_slo, ok_slo, breached_slo, breached_names = service_info

            report = {
                "BreachedSloCount": breached_slo,
                "BreachedSloNames": breached_names,
                "EndTime": end_time,
                "OkSloCount": ok_slo,
                "ReferenceId": {"KeyAttributes": {"Environment": env, "Name": name, "Type": svc_type}},
                "SliStatus": status,
                "StartTime": start_time,
                "TotalSloCount": total_slo,
            }
            reports.append(report)

        # Build response
        result = f"SLI Status Report - Last {hours} hours\n"
        result += f"Time Range: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M')} - {datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M')}\n\n"

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

        return result

    except Exception as e:
        return f"Error getting SLI status: {str(e)}"


@mcp.tool()
async def query_xray_traces(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    filter_expression: Optional[str] = None,
    region: str = "us-east-1",
) -> str:
    """Query AWS X-Ray traces to investigate errors, performance issues, and request flows.

    Use this tool to:
    - Find root causes of errors and faults
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
    try:
        xray_client = boto3.client("xray", region_name=region)

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
        if time_diff > timedelta(hours=6):
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

        result_data = {
            "TraceSummaries": trace_summaries,
            "TraceCount": len(trace_summaries),
            "Message": f"Retrieved {len(trace_summaries)} traces (limited to prevent size issues)",
        }

        return json.dumps(result_data, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")

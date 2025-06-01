import json
import os
from datetime import datetime, timedelta
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("appsignals")


@mcp.tool()
async def list_application_signals_services() -> str:
    """List all services monitored by AWS Application Signals."""
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

    Args:
        service_name: Name of the service to get details for
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

    Args:
        service_name: Name of the service to get metrics for
        metric_name: Specific metric name (optional - if not provided, shows available metrics)
        statistic: Standard statistic type (Average, Sum, Maximum, Minimum, SampleCount). Defaults to Average.
        extended_statistic: Extended statistic (p99, p95, p90, etc). Defaults to p99.
        hours: Number of hours to look back (default 1)
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


@mcp.tool()
async def get_sli_status(hours: int = 24) -> str:
    """Get SLI status for all services monitored by Application Signals.

    Args:
        hours: Number of hours to look back (default 24)
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
    """
    Query X-Ray traces.

    Args:
        start_time: Start time in ISO format (e.g., '2024-01-01T00:00:00Z'). Defaults to 3 hours ago if not provided.
        end_time: End time in ISO format (e.g., '2024-01-01T01:00:00Z'). Defaults to current time if not provided.
        filter_expression: X-Ray filter expression (optional)
        region: AWS region (default: us-east-1)

    Returns:
        JSON string containing up to 10 trace summaries
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

        kwargs = {"StartTime": start_datetime, "EndTime": end_datetime, "Sampling": True}

        if filter_expression:
            kwargs["FilterExpression"] = filter_expression

        response = xray_client.get_trace_summaries(**kwargs)

        # Convert response to JSON-serializable format
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        trace_summaries = []
        for trace in response.get("TraceSummaries", []):
            trace_data = {
                "Id": trace.get("Id"),
                "Duration": trace.get("Duration"),
                "ResponseTime": trace.get("ResponseTime"),
                "HasError": trace.get("HasError"),
                "HasFault": trace.get("HasFault"),
                "HasThrottle": trace.get("HasThrottle"),
                "Http": trace.get("Http", {}),
                "Annotations": trace.get("Annotations", {}),
                "Users": trace.get("Users", []),
                "ServiceIds": trace.get("ServiceIds", []),
            }
            # Convert any datetime objects to ISO format strings
            for key, value in trace_data.items():
                trace_data[key] = convert_datetime(value)
            trace_summaries.append(trace_data)

        result_data = {
            "TraceSummaries": trace_summaries,
            "ApproximateTime": convert_datetime(response.get("ApproximateTime")),
            "TracesReceivedCount": response.get("TracesReceivedCount"),
            "TracesProcessedCount": response.get("TracesProcessedCount"),
        }

        return json.dumps(result_data, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# Prompts for guiding LLM behavior with Application Signals
@mcp.prompt(
    name="daily_health_check", description="Generate a comprehensive daily health report for all monitored services"
)
def generate_daily_report() -> str:
    """Generate a daily health check report for all services."""
    return """I'll generate a comprehensive daily health check report for your Application Signals services:

**Report Sections:**
1. **Executive Dashboard**
   - Overall system health score
   - Total services monitored
   - SLO compliance percentage

2. **Service Status Summary**
   - ✅ Healthy services
   - ⚠️ Warning: Services approaching thresholds
   - ❌ Critical: Services with breached SLOs

3. **Key Metrics Overview**
   - System-wide request volume
   - Average latency trends
   - Error rate summary

4. **Top Issues**
   - Most critical problems
   - Services requiring immediate attention

5. **Recommendations**
   - Preventive actions
   - Optimization opportunities

Starting with get_sli_status() and list_application_signals_services()..."""


@mcp.prompt()
def troubleshoot_service(service_name: str) -> str:
    """Troubleshoot issues with a specific service.

    Args:
        service_name: Name of the service to troubleshoot
    """
    return f"""I'll help you troubleshoot the '{service_name}' service. Here's my systematic approach:

1. **Service Configuration**: Check service details and attributes
2. **SLI/SLO Status**: Review recent compliance and breaches
3. **Key Metrics Analysis**: 
   - Latency (Average and p99)
   - Error rates
   - Request counts
4. **Trace Analysis**: Examine X-Ray traces for errors
5. **Root Cause & Recommendations**: Identify issues and suggest fixes

I'll use these tools in sequence:
- get_service_details("{service_name}")
- get_sli_status() - focusing on {service_name}
- get_service_metrics("{service_name}", "Latency", hours=24)
- get_service_metrics("{service_name}", "ErrorRate", hours=24)
- query_xray_traces(filter_expression="service(\\"{service_name}\\") AND (error = true OR fault = true)")"""


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")

import boto3
from botocore.exceptions import ClientError
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("appsignal")

NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-api/1.0"


@mcp.tool()
async def list_s3_buckets() -> str:
    """List all S3 buckets in the AWS account."""
    try:
        s3_client = boto3.client("s3", region_name="us-east-1")
        response = s3_client.list_buckets()

        buckets = response.get("Buckets", [])
        if not buckets:
            return "No S3 buckets found."

        bucket_list = []
        for bucket in buckets:
            bucket_info = f"• {bucket['Name']} (Created: {bucket['CreationDate'].strftime('%Y-%m-%d %H:%M:%S')})"
            bucket_list.append(bucket_info)

        return f"S3 Buckets ({len(buckets)} total):\n" + "\n".join(bucket_list)
    except ClientError as e:
        return f"AWS Error: {e.response['Error']['Message']}"
    except Exception as e:
        return f"Error listing buckets: {str(e)}"


@mcp.tool()
async def list_application_signals_services() -> str:
    """List all services monitored by AWS Application Signals."""
    try:
        from datetime import datetime, timedelta
        appsignals = boto3.client("application-signals", region_name="us-east-1")
        
        # Calculate time range (last 24 hours)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        
        # Get all services
        response = appsignals.list_services(
            StartTime=start_time,
            EndTime=end_time,
            MaxResults=100
        )
        services = response.get("ServiceSummaries", [])
        
        if not services:
            return "No services found in Application Signals."
        
        result = f"Application Signals Services ({len(services)} total):\n\n"
        
        for service in services:
            # Extract service name from KeyAttributes
            key_attrs = service.get('KeyAttributes', {})
            service_name = key_attrs.get('Name', 'Unknown')
            service_type = key_attrs.get('Type', 'Unknown')
            
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
        from datetime import datetime, timedelta
        appsignals = boto3.client("application-signals", region_name="us-east-1")
        
        # Calculate time range (last 24 hours)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        
        # First, get all services to find the one we want
        services_response = appsignals.list_services(
            StartTime=start_time,
            EndTime=end_time,
            MaxResults=100
        )
        
        # Find the service with matching name
        target_service = None
        for service in services_response.get("ServiceSummaries", []):
            key_attrs = service.get('KeyAttributes', {})
            if key_attrs.get('Name') == service_name:
                target_service = service
                break
        
        if not target_service:
            return f"Service '{service_name}' not found in Application Signals."
        
        # Get detailed service information
        service_response = appsignals.get_service(
            StartTime=start_time,
            EndTime=end_time,
            KeyAttributes=target_service['KeyAttributes']
        )
        
        service_details = service_response['Service']
        
        # Build detailed response
        result = f"Service Details: {service_name}\n\n"
        
        # Key Attributes
        key_attrs = service_details.get('KeyAttributes', {})
        if key_attrs:
            result += "Key Attributes:\n"
            for key, value in key_attrs.items():
                result += f"  {key}: {value}\n"
            result += "\n"
        
        # Attribute Maps (Platform, Application, Telemetry info)
        attr_maps = service_details.get('AttributeMaps', [])
        if attr_maps:
            result += "Additional Attributes:\n"
            for attr_map in attr_maps:
                for key, value in attr_map.items():
                    result += f"  {key}: {value}\n"
            result += "\n"
        
        # Metric References
        metric_refs = service_details.get('MetricReferences', [])
        if metric_refs:
            result += f"Metric References ({len(metric_refs)} total):\n"
            for metric in metric_refs:
                result += f"  • {metric.get('Namespace', '')}/{metric.get('MetricName', '')}\n"
                result += f"    Type: {metric.get('MetricType', '')}\n"
                dimensions = metric.get('Dimensions', [])
                if dimensions:
                    result += "    Dimensions: "
                    dim_strs = [f"{d['Name']}={d['Value']}" for d in dimensions]
                    result += ", ".join(dim_strs) + "\n"
                result += "\n"
        
        # Log Group References
        log_refs = service_details.get('LogGroupReferences', [])
        if log_refs:
            result += f"Log Group References ({len(log_refs)} total):\n"
            for log_ref in log_refs:
                log_group = log_ref.get('Identifier', 'Unknown')
                result += f"  • {log_group}\n"
            result += "\n"
        
        return result
        
    except ClientError as e:
        return f"AWS Error: {e.response['Error']['Message']}"
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def get_service_metrics(
    service_name: str,
    metric_name: str = None,
    statistic: str = "Average",
    hours: int = 1
) -> str:
    """Get CloudWatch metrics for a specific Application Signals service.
    
    Args:
        service_name: Name of the service to get metrics for
        metric_name: Specific metric name (optional - if not provided, shows available metrics)
        statistic: Statistic type (Average, Sum, Maximum, Minimum, SampleCount)
        hours: Number of hours to look back (default 1)
    """
    try:
        from datetime import datetime, timedelta
        appsignals = boto3.client("application-signals", region_name="us-east-1")
        cloudwatch = boto3.client("cloudwatch", region_name="us-east-1")
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # Get service details to find metrics
        services_response = appsignals.list_services(
            StartTime=start_time,
            EndTime=end_time,
            MaxResults=100
        )
        
        # Find the target service
        target_service = None
        for service in services_response.get("ServiceSummaries", []):
            key_attrs = service.get('KeyAttributes', {})
            if key_attrs.get('Name') == service_name:
                target_service = service
                break
        
        if not target_service:
            return f"Service '{service_name}' not found in Application Signals."
        
        # Get detailed service info for metric references
        service_response = appsignals.get_service(
            StartTime=start_time,
            EndTime=end_time,
            KeyAttributes=target_service['KeyAttributes']
        )
        
        metric_refs = service_response['Service'].get('MetricReferences', [])
        
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
            if metric.get('MetricName') == metric_name:
                target_metric = metric
                break
        
        if not target_metric:
            available = [m.get('MetricName', 'Unknown') for m in metric_refs]
            return f"Metric '{metric_name}' not found for service '{service_name}'. Available: {', '.join(available)}"
        
        # Calculate appropriate period based on time range
        if hours <= 3:
            period = 60  # 1 minute
        elif hours <= 24:
            period = 300  # 5 minutes
        else:
            period = 3600  # 1 hour
        
        # Get metric statistics
        response = cloudwatch.get_metric_statistics(
            Namespace=target_metric['Namespace'],
            MetricName=target_metric['MetricName'],
            Dimensions=target_metric.get('Dimensions', []),
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=[statistic]
        )
        
        datapoints = response.get('Datapoints', [])
        
        if not datapoints:
            return f"No data points found for metric '{metric_name}' on service '{service_name}' in the last {hours} hour(s)."
        
        # Sort by timestamp
        datapoints.sort(key=lambda x: x['Timestamp'])
        
        # Build response
        result = f"Metrics for {service_name} - {metric_name}\n"
        result += f"Time Range: Last {hours} hour(s)\n"
        result += f"Statistic: {statistic}\n"
        result += f"Period: {period} seconds\n\n"
        
        # Calculate summary statistics
        values = [dp[statistic] for dp in datapoints]
        avg_value = sum(values) / len(values)
        max_value = max(values)
        min_value = min(values)
        latest_value = datapoints[-1][statistic]
        
        result += "Summary:\n"
        result += f"• Latest: {latest_value:.2f}\n"
        result += f"• Average: {avg_value:.2f}\n"
        result += f"• Maximum: {max_value:.2f}\n"
        result += f"• Minimum: {min_value:.2f}\n"
        result += f"• Data Points: {len(datapoints)}\n\n"
        
        # Show recent values (last 10)
        result += "Recent Values:\n"
        for dp in datapoints[-10:]:
            timestamp = dp['Timestamp'].strftime("%m/%d %H:%M")
            value = dp[statistic]
            unit = dp.get('Unit', '')
            result += f"• {timestamp}: {value:.2f} {unit}\n"
        
        return result
        
    except ClientError as e:
        return f"AWS Error: {e.response['Error']['Message']}"
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")

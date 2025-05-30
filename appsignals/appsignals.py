from typing import Any
import boto3
import httpx
from botocore.exceptions import ClientError
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("appsignal")

NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-api/1.0"


async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get("event", "Unknown")}
Area: {props.get("areaDesc", "Unknown")}
Severity: {props.get("severity", "Unknown")}
Description: {props.get("description", "No description available")}
Instructions: {props.get("instruction", "No specific instructions provided")}
"""


@mcp.tool()
async def list_s3_buckets() -> str:
    """List all S3 buckets in the AWS account."""
    try:
        s3_client = boto3.client("s3")
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
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US State.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)


@mcp.tool()
async def get_weather_forecast(latitude: float, longitude: float, days: int = 7) -> str:
    """Get extended weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
        days: Number of days to forecast (default 7, max 14)
    """
    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []

    # NWS API returns day/night periods, so days#2 for full coverage
    period_count = min(days * 2, len(periods))

    for period in periods[:period_count]:
        forecast = f"""
  {period["name"]}:
  Temperature: {period["temperature"]}°{period["temperatureUnit"]}
  Wind: {period["windSpeed"]} {period["windDirection"]}
  Forecast: {period["detailedForecast"]}
  """
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")

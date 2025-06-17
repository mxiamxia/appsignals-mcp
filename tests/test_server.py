"""Tests for AppSignals MCP Server."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from mcp_server_appsignals.server import (
    list_monitored_services,
    get_service_healthy_detail,
    query_service_metrics,
    get_service_level_objective,
    get_sli_status,
    query_sampled_traces,
    search_transactions,
)


@pytest.mark.asyncio
async def test_list_monitored_services():
    """Test listing Application Signals services."""
    with patch("mcp_server_appsignals.server.boto3.client") as mock_boto:
        # Mock the client
        mock_client = Mock()
        mock_boto.return_value = mock_client

        # Mock the response
        mock_client.list_services.return_value = {
            "ServiceSummaries": [
                {"KeyAttributes": {"Name": "test-service", "Type": "Service", "Environment": "production"}}
            ]
        }

        # Call the function
        result = await list_monitored_services()

        # Verify
        assert "test-service" in result
        assert "production" in result
        mock_client.list_services.assert_called_once()


@pytest.mark.asyncio
async def test_get_service_healthy_detail():
    """Test getting service details."""
    with patch("mcp_server_appsignals.server.boto3.client") as mock_boto:
        # Mock the client
        mock_client = Mock()
        mock_boto.return_value = mock_client

        # Mock list_services response
        mock_client.list_services.return_value = {
            "ServiceSummaries": [{"KeyAttributes": {"Name": "test-service", "Type": "Service"}}]
        }

        # Mock get_service response
        mock_client.get_service.return_value = {
            "Service": {
                "KeyAttributes": {"Name": "test-service"},
                "MetricReferences": [
                    {"Namespace": "AWS/ApplicationSignals", "MetricName": "Latency", "MetricType": "LATENCY"}
                ],
            }
        }

        # Call the function
        result = await get_service_healthy_detail("test-service")

        # Verify
        assert "test-service" in result
        assert "Latency" in result
        mock_client.get_service.assert_called_once()


@pytest.mark.asyncio
async def test_get_sli_status():
    """Test getting SLI status."""
    with patch("mcp_server_appsignals.server.boto3.client") as mock_boto:
        # Mock the client
        mock_client = Mock()
        mock_boto.return_value = mock_client

        # Mock list_services response
        mock_client.list_services.return_value = {
            "ServiceSummaries": [
                {"KeyAttributes": {"Name": "test-service", "Type": "Service", "Environment": "production"}}
            ]
        }

        # Call the function
        result = await get_sli_status(hours=24)

        # Verify
        assert "SLI Status Report" in result
        assert "24 hours" in result
        mock_client.list_services.assert_called_once()


# Add more tests as needed

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from mcp_server_appsignals.server import (
    list_tools,
    call_tool,
    ListS3BucketsArgs,
    ListApplicationSignalsServicesArgs,
    GetServiceMetricsArgs,
)


@pytest.mark.asyncio
async def test_list_tools():
    """Test that all tools are properly listed."""
    tools = await list_tools()
    assert len(tools) == 3
    
    tool_names = [tool.name for tool in tools]
    assert "list_s3_buckets" in tool_names
    assert "list_application_signals_services" in tool_names
    assert "get_service_metrics" in tool_names


@pytest.mark.asyncio
async def test_list_s3_buckets_success():
    """Test successful S3 bucket listing."""
    mock_response = {
        "Buckets": [
            {"Name": "test-bucket-1", "CreationDate": datetime(2024, 1, 1)},
            {"Name": "test-bucket-2", "CreationDate": datetime(2024, 1, 2)},
        ]
    }
    
    with patch("boto3.client") as mock_boto:
        mock_s3 = Mock()
        mock_s3.list_buckets.return_value = mock_response
        mock_boto.return_value = mock_s3
        
        result = await call_tool("list_s3_buckets", {})
        
        assert len(result) == 1
        assert "S3 Buckets (2 total):" in result[0].text
        assert "test-bucket-1" in result[0].text
        assert "test-bucket-2" in result[0].text


@pytest.mark.asyncio
async def test_list_s3_buckets_empty():
    """Test S3 bucket listing when no buckets exist."""
    mock_response = {"Buckets": []}
    
    with patch("boto3.client") as mock_boto:
        mock_s3 = Mock()
        mock_s3.list_buckets.return_value = mock_response
        mock_boto.return_value = mock_s3
        
        result = await call_tool("list_s3_buckets", {})
        
        assert len(result) == 1
        assert result[0].text == "No S3 buckets found."


@pytest.mark.asyncio
async def test_list_application_signals_services_success():
    """Test successful Application Signals service listing."""
    mock_response = {
        "Services": [
            {
                "ServiceType": {"Type": "web-service"},
                "KeyAttributes": {"Environment": "prod", "Region": "us-east-1"}
            },
            {
                "ServiceType": {"Type": "api-gateway"},
                "KeyAttributes": {"Stage": "v1"}
            }
        ]
    }
    
    with patch("boto3.client") as mock_boto:
        mock_appsignals = Mock()
        mock_appsignals.list_services.return_value = mock_response
        mock_boto.return_value = mock_appsignals
        
        result = await call_tool("list_application_signals_services", {})
        
        assert len(result) == 1
        assert "Application Signals Services (2 total):" in result[0].text
        assert "web-service" in result[0].text
        assert "api-gateway" in result[0].text


@pytest.mark.asyncio
async def test_get_service_metrics_with_default_metrics():
    """Test getting service metrics with default metric list."""
    with patch("boto3.client") as mock_boto:
        mock_appsignals = Mock()
        mock_appsignals.batch_get_service_level_objective_budget_report.return_value = {
            "Reports": [{"BudgetStatus": "OK"}]
        }
        mock_boto.return_value = mock_appsignals
        
        result = await call_tool("get_service_metrics", {"service_name": "test-service"})
        
        assert len(result) == 1
        assert "Metrics for service 'test-service':" in result[0].text
        # Should query default metrics
        assert mock_appsignals.batch_get_service_level_objective_budget_report.call_count == 4


@pytest.mark.asyncio
async def test_get_service_metrics_with_custom_metrics():
    """Test getting service metrics with custom metric list."""
    with patch("boto3.client") as mock_boto:
        mock_appsignals = Mock()
        mock_appsignals.batch_get_service_level_objective_budget_report.return_value = {
            "Reports": [{"BudgetStatus": "WARNING"}]
        }
        mock_boto.return_value = mock_appsignals
        
        result = await call_tool(
            "get_service_metrics", 
            {"service_name": "test-service", "metrics": ["Latency", "ErrorRate"]}
        )
        
        assert len(result) == 1
        assert "Metrics for service 'test-service':" in result[0].text
        # Should query only specified metrics
        assert mock_appsignals.batch_get_service_level_objective_budget_report.call_count == 2


@pytest.mark.asyncio
async def test_unknown_tool():
    """Test calling an unknown tool."""
    result = await call_tool("unknown_tool", {})
    
    assert len(result) == 1
    assert "Unknown tool: unknown_tool" in result[0].text


@pytest.mark.asyncio
async def test_aws_error_handling():
    """Test proper handling of AWS errors."""
    from botocore.exceptions import ClientError
    
    error_response = {"Error": {"Message": "Access Denied"}}
    
    with patch("boto3.client") as mock_boto:
        mock_s3 = Mock()
        mock_s3.list_buckets.side_effect = ClientError(error_response, "ListBuckets")
        mock_boto.return_value = mock_s3
        
        result = await call_tool("list_s3_buckets", {})
        
        assert len(result) == 1
        assert "AWS Error: Access Denied" in result[0].text
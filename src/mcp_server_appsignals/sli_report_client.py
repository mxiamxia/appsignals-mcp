"""
AWS Service Level Indicator (SLI) Reporting Tool

This module provides functionality to generate SLI reports for AWS services by monitoring
Service Level Objectives (SLOs) using AWS Application Signals and CloudWatch metrics.
It helps track service health and performance against defined objectives.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import boto3
from botocore.client import BaseClient


@dataclass
class AWSConfig:
    """
    Configuration class for AWS settings and service parameters.

    Attributes:
        region (str): AWS region identifier (default: us-west-1)
        period_in_hours (int): Time period for metrics collection (max 24 hours)
        service_name (str): Name of the AWS service to monitor
    """

    region: str
    period_in_hours: int
    service_name: str

    def __init__(self, region: str = "us-east-1", period_in_hours: int = 24, service_name: str = "TestService"):
        self.region = region
        self.period_in_hours = min(period_in_hours, 24)  # Ensure period doesn't exceed 24 hours
        self.service_name = service_name

    @property
    def key_attributes(self) -> Dict[str, str]:
        """Returns the key attributes used to identify the service in AWS."""
        return {"Name": self.service_name, "Type": "Service", "Environment": self.region}


@dataclass
class SLOSummary:
    """
    Data class representing a Service Level Objective summary.

    Attributes:
        name (str): Name of the SLO
        arn (str): Amazon Resource Name
        key_attributes (Dict): Service identification attributes
        operation_name (str): Name of the monitored operation
        created_time (datetime): When the SLO was created
    """

    name: str
    arn: str
    key_attributes: Dict[str, str]
    operation_name: str
    created_time: datetime


@dataclass
class MetricDataResult:
    """
    Data class holding CloudWatch metric data results.

    Attributes:
        timestamps (List[datetime]): Timestamps of metric data points
        values (List[float]): Corresponding metric values
    """

    timestamps: List[datetime]
    values: List[float]


class SLIReport:
    """
    Class representing an SLI report with various metrics and status information.

    Provides read-only access to report data including start/end times,
    SLI status, and counts of total, successful, and breached SLOs.
    """

    def __init__(
        self,
        start_time: datetime,
        end_time: datetime,
        sli_status: str,
        total_slo_count: int,
        ok_slo_count: int,
        breached_slo_count: int,
        breached_slo_names: List[str],
    ):
        self._start_time = start_time
        self._end_time = end_time
        self._sli_status = sli_status
        self._total_slo_count = total_slo_count
        self._ok_slo_count = ok_slo_count
        self._breached_slo_count = breached_slo_count
        self._breached_slo_names = breached_slo_names

    # Property getters for all attributes
    @property
    def start_time(self) -> datetime:
        """Start time of the reporting period."""
        return self._start_time

    @property
    def end_time(self) -> datetime:
        """End time of the reporting period."""
        return self._end_time

    @property
    def sli_status(self) -> str:
        """Overall SLI status (OK/CRITICAL)."""
        return self._sli_status

    @property
    def total_slo_count(self) -> int:
        """Total number of SLOs monitored."""
        return self._total_slo_count

    @property
    def ok_slo_count(self) -> int:
        """Number of SLOs meeting their objectives."""
        return self._ok_slo_count

    @property
    def breached_slo_count(self) -> int:
        """Number of SLOs failing to meet their objectives."""
        return self._breached_slo_count

    @property
    def breached_slo_names(self) -> List[str]:
        """Names of SLOs that failed to meet their objectives."""
        return self._breached_slo_names.copy()


class SLIReportClient:
    """
    Client for generating SLI reports using AWS Application Signals and CloudWatch.

    Handles interaction with AWS services to collect and analyze SLO data.
    """

    def __init__(self, config: AWSConfig):
        self.config = config
        # Initialize AWS service clients
        self.signals_client = boto3.client("application-signals", region_name=config.region)
        self.cloudwatch_client = boto3.client("cloudwatch", region_name=config.region)

    def get_slo_summaries(self) -> List[SLOSummary]:
        """Fetches SLO summaries from AWS Application Signals."""
        response = self.signals_client.list_service_level_objectives(
            KeyAttributes=self.config.key_attributes, MetricSourceTypes=["ServiceOperation"], IncludeLinkedAccounts=True
        )

        return [
            SLOSummary(
                name=slo["Name"],
                arn=slo["Arn"],
                key_attributes=slo.get("KeyAttributes", {}),
                operation_name=slo.get("OperationName", "N/A"),
                created_time=slo["CreatedTime"],
            )
            for slo in response["SloSummaries"]
        ]

    def create_metric_queries(self, slo_summaries: List[SLOSummary]) -> List[Dict[str, Any]]:
        """Creates CloudWatch metric queries for each SLO."""
        return [
            {
                "Id": f"slo{i}",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/ApplicationSignals",
                        "MetricName": "BreachedCount",
                        "Dimensions": [{"Name": "SloName", "Value": slo.name}],
                    },
                    "Period": self.config.period_in_hours * 60 * 60,
                    "Stat": "Maximum",
                },
                "ReturnData": True,
            }
            for i, slo in enumerate(slo_summaries)
        ]

    def get_metric_data(
        self, queries: List[Dict[str, Any]], start_time: datetime, end_time: datetime
    ) -> List[MetricDataResult]:
        """Retrieves metric data from CloudWatch using the specified queries."""
        response = self.cloudwatch_client.get_metric_data(
            MetricDataQueries=queries, StartTime=start_time, EndTime=end_time
        )

        return [
            MetricDataResult(timestamps=result["Timestamps"], values=result["Values"])
            for result in response["MetricDataResults"]
        ]

    def get_sli_status(self, num_breaching: int) -> str:
        """Determines overall SLI status based on number of breaching SLOs."""
        return "CRITICAL" if num_breaching > 0 else "OK"

    def generate_sli_report(self) -> SLIReport:
        """
        Generates a comprehensive SLI report.

        Collects SLO data, analyzes metrics, and produces a report containing
        the overall status and details about breaching/healthy SLOs.
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=self.config.period_in_hours)

        slo_summaries = self.get_slo_summaries()

        # If no SLOs found, return empty report
        if not slo_summaries:
            return SLIReport(
                start_time=start_time,
                end_time=end_time,
                sli_status="OK",  # No SLOs means nothing can be breached
                total_slo_count=0,
                ok_slo_count=0,
                breached_slo_count=0,
                breached_slo_names=[],
            )

        metric_queries = self.create_metric_queries(slo_summaries)
        metric_results = self.get_metric_data(metric_queries, start_time, end_time)

        healthy_slos = []
        breaching_slos = []

        for i, result in enumerate(metric_results):
            # Check if we have any values and if the SLO is breached
            if result.values and len(result.values) > 0 and result.values[0] > 0:
                breaching_slos.append(slo_summaries[i].name)
            else:
                healthy_slos.append(slo_summaries[i].name)

        return SLIReport(
            start_time=start_time,
            end_time=end_time,
            sli_status=self.get_sli_status(len(breaching_slos)),
            total_slo_count=len(slo_summaries),
            ok_slo_count=len(healthy_slos),
            breached_slo_count=len(breaching_slos),
            breached_slo_names=breaching_slos,
        )

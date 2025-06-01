import os
import boto3.session
import logging

AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
AWS_PROFILE = os.environ.get('AWS_PROFILE', 'default')
CONFIG = boto3.session.Config(connect_timeout=15, read_timeout=15, retries={'max_attempts': 3})

_logger = logging.getLogger(__name__)

class ApplicationSignalsClient:
    """Wrapper for AWS Application Signals Client"""

    def __init__(self):
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)

        try:
            self.application_signals_client = session.client('application-signals', config=CONFIG)
            _logger.debug(f'AWS Application Signals client initialized for region {AWS_REGION}')
        except Exception as e:
            raise RuntimeError(f'Failed to initialize AWS Application Signals client: {str(e)}')


class CloudWatchClient:
    """Wrapper for AWS CloudWatch Client"""

    def __init__(self):
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        
        try:
            self.cloudwatch_client = session.client('cloudwatch', config=CONFIG)
            _logger.debug(f'AWS CloudWatch client initialized for region {AWS_REGION}')
        except Exception as e:
            raise RuntimeError(f'Failed to initialize AWS CloudWatch client: {str(e)}')


class XRayClient:
    """Wrapper for AWS CloudWatch X-Ray Client"""

    def __init__(self):
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)

        try:
            self.xray_client = session.client('xray', config=CONFIG)
            _logger.debug(f'AWS CloudWatch client initialized for region {AWS_REGION}')
        except Exception as e:
            raise RuntimeError(f'Failed to initialize AWS X-Ray client: {str(e)}')

import os
import boto3
import boto3.session
import logging

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)


AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
AWS_PROFILE = os.environ.get('AWS_PROFILE', 'default')
CONFIG = boto3.session.Config(connect_timeout=15, read_timeout=15, retries={'max_attempts': 3})

class ApplicationSignalsClient:
    """Wrapper for AWS Application Signals Client"""

    def __init__(self):
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        self.application_signals_client = None

        try:
            self.application_signals_client = session.client('application-signals', config=CONFIG)
            _logger.debug(f'AWS Application Signals client initialized for region {AWS_REGION}')
        except Exception as e:
            _logger.error(f'Failed to initialize AWS Application Signals client: {str(e)}')


class CloudWatchClient:
    """Wrapper for AWS CloudWatch Client"""

    def __init__(self):
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        self.cloudwatch_client = None

        try:
            self.cloudwatch_client = session.client('cloudwatch', config=CONFIG)
            _logger.debug(f'AWS CloudWatch client initialized for region {AWS_REGION}')
        except Exception as e:
            _logger.error(f'Failed to initialize AWS CloudWatch client: {str(e)}')
import os
import boto3
import boto3.session
import logging

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)

class ApplicationSignalsClient:
    """Wrapper for AWS Application Signals Client"""

    def __init__(self):
        aws_region = os.environ.get('AWS_REGION', 'us-east-1')
        profile = os.environ.get('AWS_PROFILE', 'default')
        config = boto3.session.Config(
            connect_timeout=15, read_timeout=15, retries={'max_attempts': 3}
        )
        session = boto3.Session(profile_name=profile, region_name=aws_region)
        self.application_signals_client = None

        try:
            self.application_signals_client = session.client('application-signals', config=config)
            _logger.debug(f'AWS Application Signals client initialized for region {aws_region}')
        except Exception as e:
            _logger.error(f'Failed to initialize AWS Application Signals client: {str(e)}')
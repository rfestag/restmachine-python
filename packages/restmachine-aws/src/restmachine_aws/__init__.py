"""
AWS Lambda adapter for RestMachine.

This package provides an adapter for running RestMachine applications on AWS Lambda
with API Gateway proxy integration.
"""

from .adapter import AwsApiGatewayAdapter

__all__ = ["AwsApiGatewayAdapter"]
__version__ = "0.1.0"

"""
AWS Lambda adapter for RestMachine.

This package provides an adapter for running RestMachine applications on AWS Lambda
with API Gateway proxy integration.

It also includes a Lambda Extension for automatic shutdown handler execution.
"""

from .adapter import AwsApiGatewayAdapter
from .extension import ShutdownExtension, main as extension_main

__all__ = ["AwsApiGatewayAdapter", "ShutdownExtension", "extension_main"]
__version__ = "0.1.0"

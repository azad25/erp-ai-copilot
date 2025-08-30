"""
Auth Service gRPC Client.

This module provides a client to interact with the Auth Service gRPC server.
"""

from .client import AuthServiceClient, get_auth_service_client, close_auth_service_client

__all__ = [
    'AuthServiceClient',
    'get_auth_service_client',
    'close_auth_service_client',
]

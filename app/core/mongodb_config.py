"""
MongoDB configuration to prevent synchronous client background tasks.
"""
import os
from typing import Dict, Any


def get_mongodb_config() -> Dict[str, Any]:
    """
    Get MongoDB configuration that minimizes background operations
    and prevents synchronous client creation.
    """
    return {
        # Connection timeouts
        'serverSelectionTimeoutMS': 30000,
        'connectTimeoutMS': 30000,
        'socketTimeoutMS': 30000,
        
        # Pool configuration
        'maxPoolSize': int(os.getenv('MONGODB_MAX_POOL_SIZE', '10')),
        'minPoolSize': 1,  # Minimal pool size
        'maxIdleTimeMS': 300000,  # 5 minutes
        'waitQueueTimeoutMS': 30000,
        
        # Retry configuration
        'retryWrites': True,
        'retryReads': True,
        
        # Heartbeat and monitoring
        'heartbeatFrequencyMS': 120000,  # 2 minutes between heartbeats
        'serverMonitoringMode': 'stream',  # Use streaming instead of polling
        
        # Application identification
        'appname': 'ai_copilot_async',
        
        # Connection behavior
        'directConnection': False,
        
        # Disable automatic background operations
        'compressors': [],  # Disable compression to reduce overhead
        
        # Event listeners (disable to reduce background tasks)
        'event_listeners': [],
    }


def get_motor_client_config() -> Dict[str, Any]:
    """Get Motor-specific configuration for AsyncIOMotorClient."""
    config = get_mongodb_config()
    
    # Motor-specific settings
    config.update({
        # Use asyncio event loop
        'io_loop': None,  # Use current event loop
        
        # Disable background monitoring threads
        'connect': False,  # Don't connect immediately
    })
    
    return config

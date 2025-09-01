"""
Server configuration and settings management.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import structlog

class ServerConfig:
    """Server configuration manager."""
    
    def __init__(self, mode: str = "simple", config_path: Optional[str] = None):
        """Initialize server configuration.
        
        Args:
            mode: Server mode (simple, full, grpc, interactive)
            config_path: Optional path to config file
        """
        self.mode = mode
        self.config_path = config_path or self._get_default_config_path()
        self.settings = self._load_config()
        self._configure_logging()
    
    def _get_default_config_path(self) -> str:
        """Get the default configuration file path."""
        return str(Path(__file__).parent.parent / "config" / "server_config.json")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or use defaults."""
        default_config = {
            "server": {
                "host": "0.0.0.0",
                "port": 8000,
                "reload": False,
                "workers": 1,
                "log_level": "info"
            },
            "grpc": {
                "port": 50051,
                "max_workers": 10,
                "max_message_length": 100 * 1024 * 1024  # 100MB
            },
            "llm": {
                "default_provider": "openai",
                "default_model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2000
            }
        }
        
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    file_config = json.load(f)
                    # Deep merge default config with file config
                    return self._deep_merge(default_config, file_config)
        except Exception as e:
            logging.warning(f"Failed to load config file: {e}")
        
        return default_config
    
    def _deep_merge(self, d1: Dict, d2: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = d1.copy()
        for k, v in d2.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = v
        return result
    
    def _configure_logging(self) -> None:
        """Configure structured logging."""
        log_level = self.settings.get("server", {}).get("log_level", "info").upper()
        
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer()
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()]
        )
    
    def get_server_settings(self) -> Dict[str, Any]:
        """Get server-specific settings."""
        return self.settings.get("server", {})
    
    def get_grpc_settings(self) -> Dict[str, Any]:
        """Get gRPC-specific settings."""
        return self.settings.get("grpc", {})
    
    def get_llm_settings(self) -> Dict[str, Any]:
        """Get LLM-specific settings."""
        return self.settings.get("llm", {})
    
    def get_rest_settings(self) -> Dict[str, Any]:
        """Get REST API-specific settings."""
        return self.settings.get("server", {})
    
    def update_from_args(self, args: Dict[str, Any]) -> None:
        """Update settings from command line arguments."""
        if hasattr(args, "port") and args.port:
            self.settings["server"]["port"] = args.port
        if hasattr(args, "host") and args.host:
            self.settings["server"]["host"] = args.host
        if hasattr(args, "reload") and args.reload:
            self.settings["server"]["reload"] = args.reload
        if hasattr(args, "workers") and args.workers:
            self.settings["server"]["workers"] = args.workers
        if hasattr(args, "grpc_port") and args.grpc_port:
            self.settings["grpc"]["port"] = args.grpc_port
        if hasattr(args, "model") and args.model:
            self.settings["llm"]["default_model"] = args.model
        if hasattr(args, "provider") and args.provider:
            self.settings["llm"]["default_provider"] = args.provider

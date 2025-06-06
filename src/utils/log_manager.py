"""Centralized logging configuration and management."""
import logging
import logging.handlers
from pathlib import Path
import datetime
from typing import Optional, Dict, Any
import json

class ConsoleFormatter(logging.Formatter):
    """Custom formatter for console output with colors."""
    
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    
    FORMATS = {
        logging.DEBUG: grey + "[%(levelname)s] %(asctime)s - %(message)s" + reset,
        logging.INFO: grey + "[%(levelname)s] %(asctime)s - %(message)s" + reset,
        logging.WARNING: yellow + "[%(levelname)s] %(asctime)s - %(message)s" + reset,
        logging.ERROR: red + "[%(levelname)s] %(asctime)s - %(message)s" + reset,
        logging.CRITICAL: bold_red + "[%(levelname)s] %(asctime)s - %(message)s" + reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for log files."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON.
        
        Args:
            record: The log record to format
            
        Returns:
            JSON formatted string
        """
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage()
        }
        
        # Add extra fields from the record
        if hasattr(record, 'request_id'):
            log_obj['request_id'] = getattr(record, 'request_id')
        if hasattr(record, 'duration_ms'):
            log_obj['duration_ms'] = getattr(record, 'duration_ms')
            
        # Add any extra attributes from record
        if record.__dict__.get('extra'):
            for key, value in record.__dict__['extra'].items():
                log_obj[key] = value
                
        return json.dumps(log_obj)

class LogManager:
    """Manages logging configuration and provides logging utilities."""
    
    def __init__(self, name: str = "AMV", log_dir: str = "logs"):
        """Initialize the log manager.
        
        Args:
            name: Base name for the logger
            log_dir: Directory to store log files
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create base logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Remove any existing handlers
        self.logger.handlers.clear()
        
        # Add handlers
        self._setup_file_handlers()
        self._setup_console_handler()
        
    def _setup_file_handlers(self) -> None:
        """Set up file handlers for different log levels."""
        # Debug log - includes all messages
        debug_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "debug.log",
            maxBytes=10_000_000,  # 10MB
            backupCount=5
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(debug_handler)
        
        # Error log - only error and critical messages
        error_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "error.log",
            maxBytes=10_000_000,  # 10MB
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(error_handler)
        
        # API log - for API-related messages
        api_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "api.log",
            maxBytes=10_000_000,  # 10MB
            backupCount=5
        )
        api_handler.setLevel(logging.INFO)
        api_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(api_handler)
        
    def _setup_console_handler(self) -> None:
        """Set up console handler for terminal output."""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ConsoleFormatter())
        self.logger.addHandler(console_handler)
        
    def get_logger(self, module_name: Optional[str] = None) -> logging.Logger:
        """Get a logger instance.
        
        Args:
            module_name: Module name for the logger.
                       If not provided, uses the base logger.
                       
        Returns:
            Configured logger instance
        """
        if module_name:
            return logging.getLogger(f"{self.name}.{module_name}")
        return self.logger
        
    def log_api_request(self, method: str, path: str, status_code: int, 
                       duration: float, details: Optional[Dict[str, Any]] = None) -> None:
        """Log an API request with relevant details.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path
            status_code: Response status code
            duration: Request duration in seconds
            details: Additional request/response details
        """
        duration_ms = round(duration * 1000, 2)
        status_word = "SUCCESS" if status_code < 400 else "FAILED"
        message = f"{method} {path} {status_code} {status_word} ({duration_ms:.2f}ms)"
        
        # Create extra fields for structured logging
        extra = {
            "type": "api_request",
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "request_id": details.get("request_id") if details else None
        }
        
        if details:
            extra.update(details)
        
        if status_code >= 500:
            self.logger.error(message, extra=extra)
        elif status_code >= 400:
            self.logger.warning(message, extra=extra)
        else:
            self.logger.info(message, extra=extra)

# Global log manager instance
log_manager = LogManager()

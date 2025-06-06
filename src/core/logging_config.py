"""Configure logging for the application."""
import logging
from ..utils.log_manager import log_manager

def setup_logging(name: str = "AMV") -> logging.Logger:
    """Set up logging configuration.
    
    Args:
        name (str): Name for the logger, defaults to "AMV"
        
    Returns:
        logging.Logger: Configured logger instance
    """
    return log_manager.get_logger(name)

"""Logging configuration for Wall Assembly LCA Optimizer.

This module provides centralized logging configuration for the entire application.
Supports both console and file logging with configurable levels.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    log_level: int = logging.INFO,
    log_file: Optional[Path] = None,
    console_output: bool = True
) -> logging.Logger:
    """Configure logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file. If None, logs to console only.
        console_output: Whether to output to console (default: True)
    
    Returns:
        Configured logger instance
    """
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    handlers = []
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        handlers.append(console_handler)
    
    # File handler (optional)
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)  # Always debug to file
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,  # Capture all messages
        handlers=handlers,
        force=True  # Override any existing configuration
    )
    
    # Return module-specific logger
    return logging.getLogger(__name__)


# Convenience function for getting loggers
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module.
    
    Args:
        name: Module name (typically __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

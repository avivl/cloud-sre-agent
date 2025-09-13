# gemini_sre_agent/core/logging/manager.py
"""
Logging manager for centralized logging configuration.

This module provides a centralized logging manager that handles
configuration, setup, and management of all logging components.
"""

import logging
import logging.config
from pathlib import Path

from .config import LoggingConfig
from .exceptions import ConfigurationError
from .handlers import create_console_handler, create_file_handler


class LoggingManager:
    """Centralized logging manager."""

    def __init__(self, config: LoggingConfig | None = None):
        """Initialize the logging manager.
        
        Args:
            config: Logging configuration. Uses default if None.
        """
        self.config = config or LoggingConfig()
        self._configured = False
        self._loggers: dict[str, logging.Logger] = {}

    def configure(self) -> None:
        """Configure the logging system."""
        try:
            # Clear existing configuration
            logging.getLogger().handlers.clear()

            # Configure root logger
            root_logger = logging.getLogger()
            level = self.config.level
            if hasattr(level, "value"):  # Handle LogLevel enum
                level = level.value
            root_logger.setLevel(level)

            # Add handlers
            for handler_config in self.config.handlers:
                handler = self._create_handler(handler_config)
                if handler:
                    root_logger.addHandler(handler)

            self._configured = True

        except Exception as e:
            raise ConfigurationError(
                f"Failed to configure logging: {e!s}",
                config_key="logging_config"
            ) from e

    def _create_handler(self, handler_config) -> logging.Handler | None:
        """Create a handler from configuration.
        
        Args:
            handler_config: Handler configuration.
            
        Returns:
            Configured handler or None if creation fails.
        """
        try:
            from .config import OutputDestination

            if handler_config.destination == OutputDestination.CONSOLE:
                return create_console_handler(
                    formatter_type=(
                        handler_config.format.value 
                        if hasattr(handler_config.format, "value") 
                        else "structured"
                    ),
                    colorize=handler_config.colorize
                )

            elif handler_config.destination == OutputDestination.FILE:
                return create_file_handler(
                    filename=handler_config.file_path or "app.log",
                    formatter_type=(
                        handler_config.format.value 
                        if hasattr(handler_config.format, "value") 
                        else "json"
                    ),
                    max_bytes=handler_config.max_file_size_mb * 1024 * 1024,
                    backup_count=handler_config.backup_count
                )

            elif handler_config.destination == OutputDestination.SYSLOG:
                from .handlers import create_syslog_handler
                return create_syslog_handler(
                    facility=handler_config.syslog_facility,
                    address=handler_config.syslog_address,
                    formatter_type=(
                        handler_config.format.value 
                        if hasattr(handler_config.format, "value") 
                        else "json"
                    )
                )

            elif handler_config.destination == OutputDestination.REMOTE:
                from .handlers import create_remote_handler
                return create_remote_handler(
                    url=handler_config.remote_url,
                    headers=handler_config.remote_headers,
                    timeout=handler_config.remote_timeout,
                    formatter_type=(
                        handler_config.format.value 
                        if hasattr(handler_config.format, "value") 
                        else "json"
                    )
                )

            else:
                print(f"Warning: Unknown handler destination: {handler_config.destination}")
                return None

        except Exception as e:
            print(f"Warning: Failed to create handler {handler_config.name}: {e}")
            return None

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger by name.
        
        Args:
            name: Logger name.
            
        Returns:
            Logger instance.
        """
        if not self._configured:
            self.configure()

        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(name)

        return self._loggers[name]

    def add_handler(self, handler: logging.Handler) -> None:
        """Add a handler to all loggers.
        
        Args:
            handler: Handler to add.
        """
        # Add to root logger
        logging.getLogger().addHandler(handler)

        # Add to existing loggers
        for logger in self._loggers.values():
            logger.addHandler(handler)

    def remove_handler(self, handler: logging.Handler) -> None:
        """Remove a handler from all loggers.
        
        Args:
            handler: Handler to remove.
        """
        # Remove from root logger
        logging.getLogger().removeHandler(handler)

        # Remove from existing loggers
        for logger in self._loggers.values():
            logger.removeHandler(handler)

    def set_level(self, level: str | int) -> None:
        """Set the logging level for all loggers.
        
        Args:
            level: Logging level.
        """
        if hasattr(level, "value"):  # Handle LogLevel enum
            level = level.value

        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)

        # Set root logger level
        logging.getLogger().setLevel(level)

        # Set existing loggers level
        for logger in self._loggers.values():
            logger.setLevel(level)

    def get_loggers(self) -> dict[str, logging.Logger]:
        """Get all configured loggers.
        
        Returns:
            Dictionary of logger names to logger instances.
        """
        return self._loggers.copy()

    def clear_loggers(self) -> None:
        """Clear all configured loggers."""
        self._loggers.clear()

    def shutdown(self) -> None:
        """Shutdown the logging system."""
        logging.shutdown()
        self._configured = False
        self._loggers.clear()


# Global logging manager instance
_logging_manager: LoggingManager | None = None


def get_logging_manager() -> LoggingManager:
    """Get the global logging manager.
    
    Returns:
        Global logging manager instance.
    """
    global _logging_manager
    if _logging_manager is None:
        _logging_manager = LoggingManager()
    return _logging_manager


def configure_logging(config: LoggingConfig | None = None) -> None:
    """Configure the global logging system.
    
    Args:
        config: Logging configuration. Uses default if None.
    """
    global _logging_manager
    _logging_manager = LoggingManager(config)
    _logging_manager.configure()


def get_logger(name: str) -> logging.Logger:
    """Get a logger by name.
    
    Args:
        name: Logger name.
        
    Returns:
        Logger instance.
    """
    manager = get_logging_manager()
    return manager.get_logger(name)


def set_logging_level(level: str | int) -> None:
    """Set the logging level for all loggers.
    
    Args:
        level: Logging level.
    """
    manager = get_logging_manager()
    manager.set_level(level)


def add_logging_handler(handler: logging.Handler) -> None:
    """Add a handler to all loggers.
    
    Args:
        handler: Handler to add.
    """
    manager = get_logging_manager()
    manager.add_handler(handler)


def remove_logging_handler(handler: logging.Handler) -> None:
    """Remove a handler from all loggers.
    
    Args:
        handler: Handler to remove.
    """
    manager = get_logging_manager()
    manager.remove_handler(handler)


def shutdown_logging() -> None:
    """Shutdown the global logging system."""
    global _logging_manager
    if _logging_manager:
        _logging_manager.shutdown()
        _logging_manager = None


def setup_basic_logging(
    level: str | int = logging.INFO,
    format_string: str | None = None,
    filename: str | Path | None = None
) -> None:
    """Set up basic logging configuration.
    
    Args:
        level: Logging level.
        format_string: Log format string.
        filename: Log file path.
    """
    if hasattr(level, "value"):  # Handle LogLevel enum
        level = level.value

    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    if format_string is None:
        format_string = "%(asctime)s [%(levelname)8s] %(name)s: %(message)s"

    # Configure basic logging
    logging.basicConfig(
        level=level,
        format=format_string,
        filename=filename,
        filemode="a"
    )


def setup_structured_logging(
    level: str | int = logging.INFO,
    formatter_type: str = "json",
    filename: str | Path | None = None
) -> None:
    """Set up structured logging configuration.
    
    Args:
        level: Logging level.
        formatter_type: Type of formatter to use.
        filename: Log file path.
    """
    if hasattr(level, "value"):  # Handle LogLevel enum
        level = level.value

    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    # Create configuration
    config = LoggingConfig(
        level=level,
        handlers=[
            {
                "type": "console",
                "formatter": formatter_type,
                "colorize": True
            }
        ]
    )

    if filename:
        config.handlers.append({
            "type": "file",
            "filename": str(filename),
            "formatter": formatter_type
        })

    # Configure logging
    configure_logging(config)


def setup_development_logging() -> None:
    """Set up logging for development environment."""
    setup_structured_logging(
        level=logging.DEBUG,
        formatter_type="structured",
        filename="logs/development.log"
    )


def setup_production_logging() -> None:
    """Set up logging for production environment."""
    setup_structured_logging(
        level=logging.INFO,
        formatter_type="json",
        filename="logs/production.log"
    )


def setup_test_logging() -> None:
    """Set up logging for test environment."""
    setup_structured_logging(
        level=logging.WARNING,
        formatter_type="compact"
    )

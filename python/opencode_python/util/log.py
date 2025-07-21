"""Logging utilities for OpenCode Python."""

import json
import logging
import os
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, TextIO

from platformdirs import user_data_dir


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class Logger:
    """Enhanced logger with tagging and timing capabilities."""
    
    def __init__(self, tags: Optional[Dict[str, Any]] = None):
        self.tags = tags or {}
        self._last_time = datetime.now()
        
    def _build_message(self, message: Any, extra: Optional[Dict[str, Any]] = None) -> str:
        """Build formatted log message."""
        all_tags = {**self.tags, **(extra or {})}
        prefix = " ".join(f"{k}={v}" for k, v in all_tags.items() if v is not None)
        
        now = datetime.now()
        diff = int((now - self._last_time).total_seconds() * 1000)
        self._last_time = now
        
        parts = [
            now.isoformat().split('.')[0],
            f"+{diff}ms",
            prefix,
            str(message)
        ]
        return " ".join(filter(None, parts))
    
    def debug(self, message: Any = None, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log debug message."""
        if Log.should_log(LogLevel.DEBUG):
            Log._write("DEBUG " + self._build_message(message, extra))
    
    def info(self, message: Any = None, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log info message."""
        if Log.should_log(LogLevel.INFO):
            Log._write("INFO  " + self._build_message(message, extra))
    
    def warn(self, message: Any = None, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log warning message."""
        if Log.should_log(LogLevel.WARN):
            Log._write("WARN  " + self._build_message(message, extra))
    
    def error(self, message: Any = None, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log error message."""
        if Log.should_log(LogLevel.ERROR):
            Log._write("ERROR " + self._build_message(message, extra))
    
    def tag(self, key: str, value: str) -> "Logger":
        """Add a tag to this logger."""
        self.tags[key] = value
        return self
    
    def clone(self) -> "Logger":
        """Create a copy of this logger."""
        return Logger(self.tags.copy())
    
    def time(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Time an operation."""
        start_time = datetime.now()
        self.info(message, {"status": "started", **(extra or {})})
        
        class Timer:
            def __init__(self, logger: Logger):
                self.logger = logger
                self.stopped = False
            
            def stop(self):
                if not self.stopped:
                    duration = int((datetime.now() - start_time).total_seconds() * 1000)
                    self.logger.info(message, {
                        "status": "completed",
                        "duration": duration,
                        **(extra or {})
                    })
                    self.stopped = True
            
            def __enter__(self):
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                self.stop()
        
        return Timer(self)


class Log:
    """Global logging configuration and utilities."""
    
    _current_level = LogLevel.INFO
    _loggers: Dict[str, Logger] = {}
    _log_file: Optional[TextIO] = None
    _log_path = ""
    
    @classmethod
    def set_level(cls, level: LogLevel) -> None:
        """Set the current log level."""
        cls._current_level = level
    
    @classmethod
    def get_level(cls) -> LogLevel:
        """Get the current log level."""
        return cls._current_level
    
    @classmethod
    def should_log(cls, level: LogLevel) -> bool:
        """Check if a level should be logged."""
        level_priority = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARN: 2,
            LogLevel.ERROR: 3,
        }
        return level_priority[level] >= level_priority[cls._current_level]
    
    @classmethod
    def file(cls) -> str:
        """Get the current log file path."""
        return cls._log_path
    
    @classmethod
    async def init(cls, print_logs: bool = False, level: Optional[LogLevel] = None) -> None:
        """Initialize logging."""
        if level:
            cls.set_level(level)
        
        if print_logs:
            return
        
        # Create log directory
        log_dir = Path(user_data_dir("opencode")) / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Cleanup old logs
        await cls._cleanup_logs(log_dir)
        
        # Create new log file
        timestamp = datetime.now().isoformat().split('.')[0].replace(':', '')
        cls._log_path = str(log_dir / f"{timestamp}.log")
        
        cls._log_file = open(cls._log_path, 'w', encoding='utf-8')
    
    @classmethod
    async def _cleanup_logs(cls, log_dir: Path) -> None:
        """Clean up old log files."""
        log_files = list(log_dir.glob("*.log"))
        if len(log_files) <= 5:
            return
        
        # Sort by modification time and keep only the 10 most recent
        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        for old_file in log_files[10:]:
            try:
                old_file.unlink()
            except OSError:
                pass
    
    @classmethod
    def _write(cls, message: str) -> None:
        """Write message to log output."""
        full_message = message + "\n"
        if cls._log_file:
            cls._log_file.write(full_message)
            cls._log_file.flush()
        else:
            sys.stderr.write(full_message)
    
    @classmethod
    def create(cls, tags: Optional[Dict[str, Any]] = None) -> Logger:
        """Create a new logger with optional tags."""
        tags = tags or {}
        
        service = tags.get("service")
        if service and isinstance(service, str):
            cached = cls._loggers.get(service)
            if cached:
                return cached
        
        logger = Logger(tags)
        
        if service and isinstance(service, str):
            cls._loggers[service] = logger
        
        return logger
    
    @classmethod
    def close(cls) -> None:
        """Close log file."""
        if cls._log_file:
            cls._log_file.close()
            cls._log_file = None


# Default logger
Default = Log.create({"service": "default"})
"""Core application context and state management."""

import json
import os
import socket
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

from pydantic import BaseModel

from .global_config import Path as GlobalPath
from .util.context import Context
from .util.filesystem import Filesystem
from .util.log import Log

T = TypeVar('T')


class AppInfo(BaseModel):
    """Application information and paths."""
    user: str
    hostname: str
    git: bool
    path: Dict[str, str]
    time: Dict[str, Optional[int]]


class ServiceEntry:
    """Service registry entry."""
    
    def __init__(self, state: Any, shutdown: Optional[Callable[[Any], Awaitable[None]]] = None):
        self.state = state
        self.shutdown = shutdown


class App:
    """Core application context manager."""
    
    _context: Context[Dict[str, Any]] = Context("app")
    _log = Log.create({"service": "app"})
    
    @classmethod
    def use(cls) -> Dict[str, Any]:
        """Get current app context."""
        return cls._context.use()
    
    @classmethod
    def info(cls) -> AppInfo:
        """Get current app info."""
        return cls._context.use()["info"]
    
    @classmethod
    async def provide(cls, cwd: str, callback: Callable[[AppInfo], Awaitable[T]]) -> T:
        """Provide app context for the duration of the callback."""
        cls._log.info("creating", {"cwd": cwd})
        
        # Find git root
        git_file, git_root = Filesystem.find_up(".git", cwd)
        cls._log.info("git", {"git": git_root})
        
        # Determine project directory
        if git_root:
            project_dir = cls._directory_name(git_root)
        else:
            project_dir = "global"
        
        data_path = GlobalPath.data / "project" / project_dir
        data_path.mkdir(parents=True, exist_ok=True)
        
        # Load/create app state
        app_json_path = data_path / "app.json"
        try:
            with open(app_json_path, 'r') as f:
                state = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            state = {}
        
        # Save state
        with open(app_json_path, 'w') as f:
            json.dump(state, f)
        
        services: Dict[Any, ServiceEntry] = {}
        root = git_root or cwd
        
        info = AppInfo(
            user=os.getenv("USER", "unknown"),
            hostname=socket.gethostname(),
            time={"initialized": state.get("initialized")},
            git=git_root is not None,
            path={
                "config": str(GlobalPath.config),
                "state": str(GlobalPath.state),
                "data": str(data_path),
                "root": root,
                "cwd": cwd,
            }
        )
        
        app_context = {
            "services": services,
            "info": info,
        }
        
        async def run_callback():
            try:
                return await callback(info)
            finally:
                # Shutdown services
                for key, entry in services.items():
                    if entry.shutdown:
                        cls._log.info("shutdown", {"name": str(key)})
                        try:
                            await entry.shutdown(entry.state)
                        except Exception as e:
                            cls._log.error("shutdown error", {"name": str(key), "error": str(e)})
        
        return await cls._context.provide_async(app_context, run_callback)
    
    @classmethod
    def state(
        cls,
        key: Any,
        init: Callable[[AppInfo], T],
        shutdown: Optional[Callable[[T], Awaitable[None]]] = None
    ) -> Callable[[], T]:
        """Register a service with the app context."""
        def get_service() -> T:
            app = cls._context.use()
            services = app["services"]
            
            if key not in services:
                cls._log.info("registering service", {"name": str(key)})
                state = init(app["info"])
                services[key] = ServiceEntry(state, shutdown)
            
            return services[key].state
        
        return get_service
    
    @classmethod
    async def initialize(cls) -> None:
        """Initialize the application."""
        app = cls._context.use()
        info = app["info"]
        
        info.time["initialized"] = int(datetime.now().timestamp() * 1000)
        
        app_json_path = Path(info.path["data"]) / "app.json"
        with open(app_json_path, 'w') as f:
            json.dump({
                "initialized": info.time["initialized"]
            }, f)
    
    @staticmethod
    def _directory_name(path: str) -> str:
        """Convert path to safe directory name."""
        return Path(path).name.replace(" ", "-").replace("/", "-").replace("\\", "-")
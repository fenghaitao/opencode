"""LSP client implementation."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pylsp_jsonrpc import streams
from pylsp_jsonrpc.endpoint import Endpoint

from ..app import App
from ..util.log import Log
from .language import get_language_id


class LSPDiagnostic:
    """LSP diagnostic information."""
    
    def __init__(self, data: Dict[str, Any]):
        self.data = data
    
    @property
    def message(self) -> str:
        return self.data.get("message", "")
    
    @property
    def severity(self) -> int:
        return self.data.get("severity", 1)
    
    @property
    def line(self) -> int:
        return self.data.get("range", {}).get("start", {}).get("line", 0)
    
    @property
    def character(self) -> int:
        return self.data.get("range", {}).get("start", {}).get("character", 0)
    
    @property
    def source(self) -> Optional[str]:
        return self.data.get("source")
    
    @property
    def code(self) -> Optional[str]:
        code = self.data.get("code")
        return str(code) if code is not None else None
    
    def pretty(self) -> str:
        """Format diagnostic for display."""
        severity_names = {1: "ERROR", 2: "WARN", 3: "INFO", 4: "HINT"}
        severity = severity_names.get(self.severity, "UNKNOWN")
        
        parts = [f"[{severity}]"]
        
        if self.source:
            parts.append(f"({self.source})")
        
        if self.code:
            parts.append(f"[{self.code}]")
        
        parts.append(f"Line {self.line + 1}:{self.character + 1}")
        parts.append(self.message)
        
        return " ".join(parts)


class LSPClient:
    """LSP client for a specific language server."""
    
    def __init__(self, server_id: str, command: List[str], root_path: str):
        self.server_id = server_id
        self.command = command
        self.root_path = root_path
        self.process: Optional[asyncio.subprocess.Process] = None
        self.endpoint: Optional[Endpoint] = None
        self.diagnostics: Dict[str, List[LSPDiagnostic]] = {}
        self.opened_files: Dict[str, int] = {}  # file_path -> version
        self._log = Log.create({"service": "lsp.client", "server": server_id})
    
    async def start(self) -> None:
        """Start the LSP server."""
        self._log.info("Starting LSP server", {"command": " ".join(self.command)})
        
        try:
            self.process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.root_path
            )
            
            # Create JSON-RPC endpoint
            self.endpoint = Endpoint(
                streams.JsonRpcStreamReader(self.process.stdout),
                streams.JsonRpcStreamWriter(self.process.stdin)
            )
            
            # Set up notification handlers
            self.endpoint.set_notification_handler(
                "textDocument/publishDiagnostics",
                self._handle_diagnostics
            )
            
            # Initialize the server
            await self._initialize()
            
            self._log.info("LSP server started successfully")
            
        except Exception as e:
            self._log.error("Failed to start LSP server", {"error": str(e)})
            raise
    
    async def stop(self) -> None:
        """Stop the LSP server."""
        if self.endpoint:
            try:
                await self.endpoint.request("shutdown", {})
                await self.endpoint.notify("exit", {})
            except Exception:
                pass
        
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        
        self._log.info("LSP server stopped")
    
    async def open_file(self, file_path: str) -> None:
        """Open a file in the LSP server."""
        if not self.endpoint:
            return
        
        file_path = os.path.abspath(file_path)
        
        # Close file if already open
        if file_path in self.opened_files:
            await self.close_file(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self._log.error("Failed to read file", {"file": file_path, "error": str(e)})
            return
        
        language_id = get_language_id(file_path)
        
        await self.endpoint.notify("textDocument/didOpen", {
            "textDocument": {
                "uri": f"file://{file_path}",
                "languageId": language_id,
                "version": 0,
                "text": content
            }
        })
        
        self.opened_files[file_path] = 0
        self._log.info("Opened file", {"file": file_path, "language": language_id})
    
    async def close_file(self, file_path: str) -> None:
        """Close a file in the LSP server."""
        if not self.endpoint or file_path not in self.opened_files:
            return
        
        await self.endpoint.notify("textDocument/didClose", {
            "textDocument": {
                "uri": f"file://{file_path}"
            }
        })
        
        del self.opened_files[file_path]
        if file_path in self.diagnostics:
            del self.diagnostics[file_path]
        
        self._log.info("Closed file", {"file": file_path})
    
    async def get_diagnostics(self, file_path: str) -> List[LSPDiagnostic]:
        """Get diagnostics for a file."""
        return self.diagnostics.get(os.path.abspath(file_path), [])
    
    async def _initialize(self) -> None:
        """Initialize the LSP server."""
        if not self.endpoint:
            return
        
        init_params = {
            "processId": os.getpid(),
            "rootUri": f"file://{self.root_path}",
            "capabilities": {
                "textDocument": {
                    "synchronization": {
                        "didOpen": True,
                        "didChange": True,
                        "didClose": True
                    },
                    "publishDiagnostics": {
                        "versionSupport": True
                    }
                },
                "workspace": {
                    "configuration": True
                }
            },
            "workspaceFolders": [{
                "uri": f"file://{self.root_path}",
                "name": "workspace"
            }]
        }
        
        await self.endpoint.request("initialize", init_params)
        await self.endpoint.notify("initialized", {})
    
    def _handle_diagnostics(self, params: Dict[str, Any]) -> None:
        """Handle diagnostic notifications."""
        uri = params.get("uri", "")
        if not uri.startswith("file://"):
            return
        
        file_path = uri[7:]  # Remove "file://" prefix
        diagnostics_data = params.get("diagnostics", [])
        
        self.diagnostics[file_path] = [
            LSPDiagnostic(diag) for diag in diagnostics_data
        ]
        
        self._log.info("Received diagnostics", {
            "file": file_path,
            "count": len(diagnostics_data)
        })


class LSPManager:
    """Manages multiple LSP clients."""
    
    _clients: Dict[str, LSPClient] = {}
    _log = Log.create({"service": "lsp.manager"})
    
    # Default LSP server configurations
    _server_configs = {
        "python": {
            "command": ["pylsp"],
            "extensions": [".py", ".pyi", ".pyw"]
        },
        "typescript": {
            "command": ["typescript-language-server", "--stdio"],
            "extensions": [".ts", ".tsx", ".js", ".jsx"]
        },
        "rust": {
            "command": ["rust-analyzer"],
            "extensions": [".rs"]
        },
        "go": {
            "command": ["gopls"],
            "extensions": [".go"]
        },
    }
    
    @classmethod
    async def get_client(cls, server_id: str) -> Optional[LSPClient]:
        """Get or create an LSP client."""
        if server_id in cls._clients:
            return cls._clients[server_id]
        
        if server_id not in cls._server_configs:
            return None
        
        config = cls._server_configs[server_id]
        app_info = App.info()
        
        client = LSPClient(
            server_id=server_id,
            command=config["command"],
            root_path=app_info.path["root"]
        )
        
        try:
            await client.start()
            cls._clients[server_id] = client
            return client
        except Exception as e:
            cls._log.error("Failed to start LSP client", {
                "server": server_id,
                "error": str(e)
            })
            return None
    
    @classmethod
    async def touch_file(cls, file_path: str, wait_for_diagnostics: bool = False) -> None:
        """Touch a file with appropriate LSP server."""
        ext = Path(file_path).suffix.lower()
        
        # Find appropriate server
        server_id = None
        for sid, config in cls._server_configs.items():
            if ext in config["extensions"]:
                server_id = sid
                break
        
        if not server_id:
            return
        
        client = await cls.get_client(server_id)
        if client:
            await client.open_file(file_path)
            
            if wait_for_diagnostics:
                # Wait a bit for diagnostics to arrive
                await asyncio.sleep(1.0)
    
    @classmethod
    async def get_diagnostics(cls) -> Dict[str, List[LSPDiagnostic]]:
        """Get all diagnostics from all clients."""
        all_diagnostics = {}
        
        for client in cls._clients.values():
            all_diagnostics.update(client.diagnostics)
        
        return all_diagnostics
    
    @classmethod
    async def shutdown_all(cls) -> None:
        """Shutdown all LSP clients."""
        for client in cls._clients.values():
            await client.stop()
        cls._clients.clear()
"""System prompt management for OpenCode Python."""

import os
from pathlib import Path
from typing import List, Optional

from ..app import App
from ..config import Config
from ..util.filesystem import Filesystem


class SystemPrompt:
    """System prompt management."""
    
    # Load prompt files
    _PROMPT_DIR = Path(__file__).parent / "prompt"
    
    @classmethod
    def _load_prompt(cls, filename: str) -> str:
        """Load a prompt file."""
        try:
            with open(cls._PROMPT_DIR / filename, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""
    
    @classmethod
    def provider(cls, model_id: str) -> List[str]:
        """Get provider-specific system prompts based on model."""
        if any(x in model_id for x in ["gpt-", "o1", "o3"]):
            return [cls._load_prompt("beast.txt")]
        elif "gemini-" in model_id:
            return [cls._load_prompt("gemini.txt")]
        else:
            return [cls._load_prompt("anthropic.txt")]
    
    @classmethod
    async def environment(cls) -> List[str]:
        """Get environment context information."""
        app_info = App.info()
        
        # Build project tree if in git repo
        project_tree = ""
        if app_info.git:
            try:
                # Simple directory tree - could be enhanced with ripgrep equivalent
                project_tree = cls._build_simple_tree(app_info.path["cwd"])
            except Exception:
                project_tree = ""
        
        env_info = [
            "Here is some useful information about the environment you are running in:",
            "<env>",
            f"  Working directory: {app_info.path['cwd']}",
            f"  Is directory a git repo: {'yes' if app_info.git else 'no'}",
            f"  Platform: {os.name}",
            f"  Today's date: {__import__('datetime').date.today().strftime('%A, %B %d, %Y')}",
            "</env>",
            "<project>",
            project_tree,
            "</project>",
        ]
        
        return ["\n".join(env_info)]
    
    @classmethod
    def _build_simple_tree(cls, cwd: str, max_depth: int = 3) -> str:
        """Build a simple directory tree."""
        try:
            lines = []
            root_path = Path(cwd)
            
            def add_path(path: Path, prefix: str = "", depth: int = 0):
                if depth > max_depth:
                    return
                
                # Skip common ignore patterns
                if path.name.startswith('.') and path.name not in ['.env', '.gitignore']:
                    return
                if path.name in ['node_modules', '__pycache__', '.git', 'dist', 'build']:
                    return
                
                rel_path = path.relative_to(root_path)
                lines.append(f"{prefix}{rel_path}")
                
                if path.is_dir() and depth < max_depth:
                    try:
                        children = sorted(path.iterdir())[:20]  # Limit to 20 items
                        for child in children:
                            add_path(child, prefix + "  ", depth + 1)
                    except PermissionError:
                        pass
            
            add_path(root_path)
            return "\n".join(lines[:200])  # Limit total lines
        except Exception:
            return ""
    
    @classmethod
    async def custom(cls) -> List[str]:
        """Load custom instruction files."""
        app_info = App.info()
        config = await Config.get()
        found = []
        
        # Standard custom files
        custom_files = ["AGENTS.md", "CLAUDE.md", "CONTEXT.md"]
        
        for filename in custom_files:
            try:
                # Look for file in current directory and up the tree
                matches = Filesystem.find_up(filename, app_info.path["cwd"])
                if matches:
                    with open(matches[0], 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            found.append(content)
            except Exception:
                continue
        
        # Global AGENTS.md
        try:
            global_agents = Path(app_info.path["config"]) / "AGENTS.md"
            if global_agents.exists():
                with open(global_agents, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        found.append(content)
        except Exception:
            pass
        
        # Home directory CLAUDE.md
        try:
            home_claude = Path.home() / ".claude" / "CLAUDE.md"
            if home_claude.exists():
                with open(home_claude, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        found.append(content)
        except Exception:
            pass
        
        # Custom instructions from config
        if hasattr(config, 'instructions') and config.instructions:
            for instruction in config.instructions:
                try:
                    # Simple glob-like matching - could be enhanced
                    instruction_path = Path(app_info.path["cwd"]) / instruction
                    if instruction_path.exists():
                        with open(instruction_path, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                            if content:
                                found.append(content)
                except Exception:
                    continue
        
        return found
    
    @classmethod
    def summarize(cls, provider_id: str) -> List[str]:
        """Get summarization prompts."""
        if provider_id == "anthropic":
            return [
                cls._load_prompt("anthropic_spoof.txt"),
                cls._load_prompt("summarize.txt")
            ]
        else:
            return [cls._load_prompt("summarize.txt")]
    
    @classmethod
    def title(cls, provider_id: str) -> List[str]:
        """Get title generation prompts."""
        if provider_id == "anthropic":
            return [
                cls._load_prompt("anthropic_spoof.txt"),
                cls._load_prompt("title.txt")
            ]
        else:
            return [cls._load_prompt("title.txt")]
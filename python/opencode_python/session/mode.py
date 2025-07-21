"""Mode system for different AI interaction modes."""

from typing import Dict, List, Optional

from pydantic import BaseModel

from ..config import Config


class ModeInfo(BaseModel):
    """Information about an interaction mode."""
    
    name: str
    description: str
    system_prompt: str
    model: Optional[Dict[str, str]] = None  # provider_id, model_id
    tools: List[str] = []
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class Mode:
    """Mode management system."""
    
    _default_modes = {
        "default": ModeInfo(
            name="default",
            description="Default coding assistant mode",
            system_prompt="""You are an AI coding assistant. You help users with programming tasks, code review, debugging, and software development. You have access to various tools to read, write, and modify files, execute commands, and search through codebases.

Key principles:
- Be helpful, accurate, and concise
- Always explain your reasoning
- Ask for clarification when needed
- Use tools appropriately to gather information
- Follow best practices and coding standards
- Be security-conscious""",
            tools=["bash", "read", "write", "edit", "grep"],
        ),
        "review": ModeInfo(
            name="review",
            description="Code review and analysis mode",
            system_prompt="""You are a code reviewer focused on analyzing code quality, identifying issues, and suggesting improvements. You examine code for:

- Logic errors and bugs
- Performance issues
- Security vulnerabilities
- Code style and best practices
- Architecture and design patterns
- Documentation and comments

Provide constructive feedback with specific suggestions for improvement.""",
            tools=["read", "grep"],
        ),
        "debug": ModeInfo(
            name="debug",
            description="Debugging and troubleshooting mode",
            system_prompt="""You are a debugging specialist. Help users identify and fix issues in their code. Your approach:

1. Understand the problem and symptoms
2. Analyze relevant code and logs
3. Form hypotheses about the cause
4. Test hypotheses systematically
5. Provide clear explanations and solutions

Use tools to examine code, run tests, and gather diagnostic information.""",
            tools=["bash", "read", "edit", "grep"],
        ),
        "refactor": ModeInfo(
            name="refactor",
            description="Code refactoring and improvement mode",
            system_prompt="""You are a refactoring specialist focused on improving code structure, readability, and maintainability while preserving functionality. You help with:

- Extracting functions and classes
- Reducing code duplication
- Improving naming and organization
- Applying design patterns
- Optimizing performance
- Modernizing legacy code

Always ensure changes maintain the original behavior.""",
            tools=["read", "write", "edit", "grep", "bash"],
        ),
    }
    
    @classmethod
    async def get(cls, name: str) -> ModeInfo:
        """Get a mode by name."""
        config = await Config.get()
        
        # Check custom modes first
        if name in config.modes:
            mode_data = config.modes[name]
            return ModeInfo(**mode_data)
        
        # Check default modes
        if name in cls._default_modes:
            return cls._default_modes[name]
        
        raise ValueError(f"Mode '{name}' not found")
    
    @classmethod
    async def list(cls) -> List[ModeInfo]:
        """List all available modes."""
        config = await Config.get()
        modes = []
        
        # Add default modes
        for mode in cls._default_modes.values():
            modes.append(mode)
        
        # Add custom modes
        for name, mode_data in config.modes.items():
            if name not in cls._default_modes:
                modes.append(ModeInfo(name=name, **mode_data))
        
        return modes
    
    @classmethod
    async def create(cls, mode: ModeInfo) -> None:
        """Create or update a custom mode."""
        config = await Config.get()
        config.modes[mode.name] = mode.model_dump(exclude={"name"})
        await Config.save(config)
    
    @classmethod
    async def delete(cls, name: str) -> None:
        """Delete a custom mode."""
        if name in cls._default_modes:
            raise ValueError(f"Cannot delete default mode '{name}'")
        
        config = await Config.get()
        if name in config.modes:
            del config.modes[name]
            await Config.save(config)
        else:
            raise ValueError(f"Mode '{name}' not found")
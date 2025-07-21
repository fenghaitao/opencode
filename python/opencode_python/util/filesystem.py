"""Filesystem utilities."""

import os
from pathlib import Path
from typing import List, Optional, Tuple


class Filesystem:
    """Filesystem utility functions."""
    
    @staticmethod
    def find_up(filename: str, start_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Find a file by walking up the directory tree.
        
        Returns:
            Tuple of (file_path, directory_containing_file) or (None, None) if not found
        """
        current_path = Path(start_path).resolve()
        
        while True:
            target_file = current_path / filename
            if target_file.exists():
                return str(target_file), str(current_path)
            
            parent = current_path.parent
            if parent == current_path:  # Reached root
                break
            current_path = parent
        
        return None, None
    
    @staticmethod
    def find_files(pattern: str, directory: str, max_depth: int = 10) -> List[str]:
        """
        Find files matching a pattern in a directory.
        
        Args:
            pattern: Glob pattern to match
            directory: Directory to search in
            max_depth: Maximum depth to search
            
        Returns:
            List of matching file paths
        """
        base_path = Path(directory)
        if not base_path.exists():
            return []
        
        matches = []
        try:
            for path in base_path.rglob(pattern):
                # Check depth
                relative_path = path.relative_to(base_path)
                if len(relative_path.parts) <= max_depth:
                    matches.append(str(path))
        except (OSError, ValueError):
            pass
        
        return matches
    
    @staticmethod
    def is_binary_file(file_path: str) -> bool:
        """
        Check if a file is binary.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if the file appears to be binary
        """
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\0' in chunk
        except (OSError, IOError):
            return True
    
    @staticmethod
    def get_file_size(file_path: str) -> int:
        """
        Get file size in bytes.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File size in bytes, or 0 if file doesn't exist
        """
        try:
            return os.path.getsize(file_path)
        except (OSError, IOError):
            return 0
    
    @staticmethod
    def ensure_directory(directory: str) -> None:
        """
        Ensure a directory exists, creating it if necessary.
        
        Args:
            directory: Directory path to ensure exists
        """
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def get_relative_path(file_path: str, base_path: str) -> str:
        """
        Get relative path from base to file.
        
        Args:
            file_path: Target file path
            base_path: Base directory path
            
        Returns:
            Relative path from base to file
        """
        try:
            return str(Path(file_path).relative_to(Path(base_path)))
        except ValueError:
            return file_path
    
    @staticmethod
    def normalize_path(path: str) -> str:
        """
        Normalize a file path.
        
        Args:
            path: Path to normalize
            
        Returns:
            Normalized absolute path
        """
        return str(Path(path).resolve())
    
    @staticmethod
    def is_text_file(file_path: str) -> bool:
        """
        Check if a file is a text file based on extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if the file appears to be a text file
        """
        text_extensions = {
            '.txt', '.md', '.py', '.js', '.ts', '.html', '.css', '.json',
            '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
            '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
            '.c', '.cpp', '.h', '.hpp', '.java', '.kt', '.rs', '.go',
            '.php', '.rb', '.pl', '.lua', '.r', '.sql', '.dockerfile',
            '.gitignore', '.gitattributes', '.editorconfig', '.env'
        }
        
        ext = Path(file_path).suffix.lower()
        return ext in text_extensions or not ext  # Files without extension might be text
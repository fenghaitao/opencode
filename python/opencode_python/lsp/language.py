"""Language identification for LSP."""

from typing import Dict, Optional

# Mapping of file extensions to language IDs
LANGUAGE_EXTENSIONS: Dict[str, str] = {
    # Python
    ".py": "python",
    ".pyi": "python",
    ".pyw": "python",
    
    # JavaScript/TypeScript
    ".js": "javascript",
    ".jsx": "javascriptreact",
    ".ts": "typescript",
    ".tsx": "typescriptreact",
    ".mjs": "javascript",
    ".cjs": "javascript",
    
    # Web
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".vue": "vue",
    
    # C/C++
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".hh": "cpp",
    
    # Java
    ".java": "java",
    
    # C#
    ".cs": "csharp",
    
    # Go
    ".go": "go",
    
    # Rust
    ".rs": "rust",
    
    # PHP
    ".php": "php",
    ".phtml": "php",
    
    # Ruby
    ".rb": "ruby",
    ".rbw": "ruby",
    
    # Shell
    ".sh": "shellscript",
    ".bash": "shellscript",
    ".zsh": "shellscript",
    ".fish": "fish",
    
    # PowerShell
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".psd1": "powershell",
    
    # Batch
    ".bat": "bat",
    ".cmd": "bat",
    
    # SQL
    ".sql": "sql",
    
    # JSON
    ".json": "json",
    ".jsonc": "jsonc",
    
    # YAML
    ".yaml": "yaml",
    ".yml": "yaml",
    
    # TOML
    ".toml": "toml",
    
    # XML
    ".xml": "xml",
    ".xsd": "xml",
    ".xsl": "xml",
    ".xslt": "xml",
    
    # Markdown
    ".md": "markdown",
    ".markdown": "markdown",
    ".mdown": "markdown",
    ".mkd": "markdown",
    ".mkdn": "markdown",
    
    # Configuration
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "ini",
    ".config": "ini",
    
    # Docker
    ".dockerfile": "dockerfile",
    
    # Makefile
    ".makefile": "makefile",
    
    # R
    ".r": "r",
    ".R": "r",
    
    # Lua
    ".lua": "lua",
    
    # Perl
    ".pl": "perl",
    ".pm": "perl",
    
    # Swift
    ".swift": "swift",
    
    # Kotlin
    ".kt": "kotlin",
    ".kts": "kotlin",
    
    # Scala
    ".scala": "scala",
    ".sc": "scala",
    
    # Dart
    ".dart": "dart",
    
    # Elixir
    ".ex": "elixir",
    ".exs": "elixir",
    
    # Erlang
    ".erl": "erlang",
    ".hrl": "erlang",
    
    # Haskell
    ".hs": "haskell",
    ".lhs": "haskell",
    
    # F#
    ".fs": "fsharp",
    ".fsi": "fsharp",
    ".fsx": "fsharp",
    
    # OCaml
    ".ml": "ocaml",
    ".mli": "ocaml",
    
    # Clojure
    ".clj": "clojure",
    ".cljs": "clojure",
    ".cljc": "clojure",
    ".edn": "clojure",
    
    # Julia
    ".jl": "julia",
    
    # Nim
    ".nim": "nim",
    ".nims": "nim",
    
    # Crystal
    ".cr": "crystal",
    
    # Zig
    ".zig": "zig",
    
    # V
    ".v": "v",
    
    # Assembly
    ".asm": "asm",
    ".s": "asm",
    ".S": "asm",
}


def get_language_id(file_path: str) -> str:
    """
    Get language ID for a file path.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Language ID or "plaintext" if not recognized
    """
    import os
    
    # Handle special cases
    filename = os.path.basename(file_path).lower()
    
    # Special filenames
    special_files = {
        "dockerfile": "dockerfile",
        "makefile": "makefile",
        "rakefile": "ruby",
        "gemfile": "ruby",
        "vagrantfile": "ruby",
        "cmakelists.txt": "cmake",
        ".gitignore": "ignore",
        ".gitattributes": "ignore",
        ".dockerignore": "ignore",
        ".eslintrc": "json",
        ".prettierrc": "json",
        ".babelrc": "json",
        "tsconfig.json": "jsonc",
        "jsconfig.json": "jsonc",
        "package.json": "json",
        "composer.json": "json",
        "cargo.toml": "toml",
        "pyproject.toml": "toml",
    }
    
    if filename in special_files:
        return special_files[filename]
    
    # Check extension
    _, ext = os.path.splitext(file_path)
    return LANGUAGE_EXTENSIONS.get(ext.lower(), "plaintext")
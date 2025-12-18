"""Language configuration and extension mapping.

This module provides:
- Extension to language mapping for auto-detection
- Extension to run command mapping
- List of supported languages
"""

# Map file extensions to language names (must match tree-sitter language names)
EXTENSION_TO_LANGUAGE = {
    # Python
    ".py": "python",
    ".pyw": "python",
    ".pyi": "python",

    # JavaScript / TypeScript
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",

    # Web
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",

    # Systems
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".rs": "rust",
    ".go": "go",
    ".zig": "zig",

    # JVM
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",

    # Shell
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "fish",

    # Config
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".xml": "xml",

    # Data
    ".sql": "sql",
    ".graphql": "graphql",
    ".gql": "graphql",

    # Documentation
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "rst",
    ".tex": "latex",

    # Ruby
    ".rb": "ruby",
    ".erb": "ruby",

    # PHP
    ".php": "php",

    # Lua
    ".lua": "lua",

    # Elixir / Erlang
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",

    # Haskell
    ".hs": "haskell",

    # OCaml
    ".ml": "ocaml",
    ".mli": "ocaml",

    # Misc
    ".vim": "vim",
    ".dockerfile": "dockerfile",
    ".r": "r",
    ".jl": "julia",
    ".swift": "swift",
    ".dart": "dart",
    ".cs": "c_sharp",
    ".fs": "fsharp",
    ".clj": "clojure",
    ".el": "elisp",
    ".lisp": "commonlisp",
    ".rkt": "racket",
    ".nim": "nim",
    ".asm": "asm",
    ".s": "asm",
    ".make": "make",
    ".cmake": "cmake",
    ".gradle": "groovy",
    ".groovy": "groovy",
    ".pl": "perl",
    ".pm": "perl",
}

# Special filenames that map to languages
FILENAME_TO_LANGUAGE = {
    "Dockerfile": "dockerfile",
    "Makefile": "make",
    "CMakeLists.txt": "cmake",
    "Gemfile": "ruby",
    "Rakefile": "ruby",
    ".gitignore": "gitignore",
    ".bashrc": "bash",
    ".zshrc": "bash",
    ".profile": "bash",
    "requirements.txt": "requirements",
    "Cargo.toml": "toml",
    "pyproject.toml": "toml",
    "package.json": "json",
    "tsconfig.json": "json",
}


def get_language_for_file(file_path: str) -> str | None:
    """
    Determine the language for a file based on its extension or name.

    Args:
        file_path: Path to the file

    Returns:
        Language name or None if unknown
    """
    from pathlib import Path

    path = Path(file_path)
    filename = path.name
    extension = path.suffix.lower()

    # Check filename first (for special files like Dockerfile, Makefile)
    if filename in FILENAME_TO_LANGUAGE:
        return FILENAME_TO_LANGUAGE[filename]

    # Then check extension
    if extension in EXTENSION_TO_LANGUAGE:
        return EXTENSION_TO_LANGUAGE[extension]

    return None


# Map file extensions to run commands
# {file} will be replaced with the actual file path
EXTENSION_TO_RUN_COMMAND = {
    # Python
    ".py": "python3 {file}",
    ".pyw": "python3 {file}",

    # JavaScript / TypeScript
    ".js": "node {file}",
    ".mjs": "node {file}",
    ".cjs": "node {file}",
    ".ts": "npx ts-node {file}",
    ".tsx": "npx ts-node {file}",

    # Shell
    ".sh": "bash {file}",
    ".bash": "bash {file}",
    ".zsh": "zsh {file}",
    ".fish": "fish {file}",

    # Compiled (compile and run)
    ".c": "gcc {file} -o /tmp/a.out && /tmp/a.out",
    ".cpp": "g++ {file} -o /tmp/a.out && /tmp/a.out",
    ".cc": "g++ {file} -o /tmp/a.out && /tmp/a.out",
    ".cxx": "g++ {file} -o /tmp/a.out && /tmp/a.out",
    ".rs": "rustc {file} -o /tmp/a.out && /tmp/a.out",
    ".go": "go run {file}",
    ".java": "java {file}",
    ".kt": "kotlinc {file} -include-runtime -d /tmp/out.jar && java -jar /tmp/out.jar",
    ".scala": "scala {file}",
    ".zig": "zig run {file}",

    # Ruby
    ".rb": "ruby {file}",

    # PHP
    ".php": "php {file}",

    # Lua
    ".lua": "lua {file}",

    # Elixir / Erlang
    ".ex": "elixir {file}",
    ".exs": "elixir {file}",

    # Haskell
    ".hs": "runhaskell {file}",

    # Perl
    ".pl": "perl {file}",
    ".pm": "perl {file}",

    # R
    ".r": "Rscript {file}",

    # Julia
    ".jl": "julia {file}",

    # Dart
    ".dart": "dart run {file}",

    # Swift
    ".swift": "swift {file}",

    # Nim
    ".nim": "nim r {file}",

    # Clojure
    ".clj": "clojure {file}",

    # Racket
    ".rkt": "racket {file}",

    # Common Lisp
    ".lisp": "sbcl --script {file}",

    # Elisp
    ".el": "emacs --script {file}",

    # Groovy
    ".groovy": "groovy {file}",
}

# Special filenames to run commands
FILENAME_TO_RUN_COMMAND = {
    "Makefile": "make",
    "Dockerfile": "docker build -f {file} .",
}


def get_run_command(file_path: str) -> str | None:
    """
    Get the run command for a file based on its extension or name.

    Args:
        file_path: Path to the file

    Returns:
        Run command with {file} placeholder, or None if unknown
    """
    from pathlib import Path

    path = Path(file_path)
    filename = path.name
    extension = path.suffix.lower()

    # Check filename first
    if filename in FILENAME_TO_RUN_COMMAND:
        return FILENAME_TO_RUN_COMMAND[filename]

    # Then check extension
    if extension in EXTENSION_TO_RUN_COMMAND:
        return EXTENSION_TO_RUN_COMMAND[extension]

    return None

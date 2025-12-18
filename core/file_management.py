import os
from typing import List


def read_file(file_path: str) -> str:
    """Read a file and return its lines.

    Args:
        file_path: Path to the file to read.

    Returns:
        A list of lines from the file.
    """
    with open(file_path, "r") as f:
        content = f.readlines()
    return "".join(content)


def save_file(file_path: str, content: List[str]) -> None:
    """Write the given lines to a file, overwriting any existing content.

    Args:
        file_path: Path to the file to write.
        content: Iterable of strings to write (lines).
    """
    # Ensure parent directory exists
    parent = os.path.dirname(file_path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

    with open(file_path, "w") as f:
        f.writelines(content)


def delete_file(file_path: str) -> bool:
    """Delete the given file if it exists.

    Args:
        file_path: Path to the file to delete.

    Returns:
        True if the file was deleted, False if it did not exist.
    """
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    else:
        return False


from git import Repo, InvalidGitRepositoryError
from pathlib import Path

def get_repo(file_path: str):
    path = Path(file_path).resolve()
    try:
        repo = Repo(path, search_parent_directories=True)
        return repo
    except InvalidGitRepositoryError:
        return None
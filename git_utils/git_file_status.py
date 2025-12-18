from pathlib import Path
from git import Repo

def get_file_git_status(repo: Repo, file_path: str):
    """Return status: 'modified', 'staged', 'untracked', 'clean'"""
    file_path = Path(file_path).resolve()
    repo_path = Path(repo.working_tree_dir).resolve()

    try:
        rel_path = file_path.relative_to(repo_path).as_posix()
    except ValueError:
        # file is outside repo? fallback to name
        rel_path = file_path.name

    if rel_path in repo.untracked_files:
        return "U"
    elif rel_path in [item.a_path for item in repo.index.diff(None)]:
        return "M"
    elif rel_path in [item.a_path for item in repo.index.diff("HEAD")]:
        return "S"
    else:
        return ""

if __name__ == "__main__":
    # Open the repo at the working tree folder, not the .git folder
    repo = Repo(".")  # or Repo("/home/juxtaa/coding/mt-code")
    print(get_file_git_status(repo, "app.py"))

from git import Repo
from textual.widgets import TextArea

def git_add_commit_push(repo: Repo, commit_message: str):
    try:
        repo.git.add(".")  # add all changes
        repo.index.commit(commit_message)
        repo.git.push("origin", "main")
        return True
    except:
        return False
def git_add(repo: Repo):
    try:
        repo.git.add(".")
        return True
    except:
        return False
def git_commit(repo: Repo, commit_message: str):
    try:
        repo.index.commit(commit_message)
        return True
    except:
        return False
def git_push_origin_main(repo):
    try:
        repo.git.push("origin", "main")
        return True
    except:
        return False
    
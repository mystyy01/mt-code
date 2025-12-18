import os
import requests

REPOS_URL = "https://raw.githubusercontent.com/grantjenks/py-tree-sitter-languages/a6d4f7c903bf647be1bdcfa504df967d13e40427/repos.txt"
OUTDIR = "/home/juxtaa/coding/mt-code/language_highlighting"
os.makedirs(OUTDIR, exist_ok=True)

def fetch_repos_list():
    resp = requests.get(REPOS_URL)
    resp.raise_for_status()
    return resp.text.strip().split()

# parse repo links, ignoring commit hashes
repos = fetch_repos_list()
repo_urls = [r for r in repos if r.startswith("https://github.com/")]

supported = []

for repo_url in repo_urls:
    # infer lang name: last segment after /
    lang = repo_url.rstrip("/").split("/")[-1]
    # raw path to highlights.scm
    raw_url = repo_url.replace("github.com", "raw.githubusercontent.com")
    scm_url = f"{raw_url}/main/queries/highlights.scm"

    try:
        r = requests.get(scm_url)
        if r.status_code == 200:
            path = os.path.join(OUTDIR, f"{lang}.scm")
            with open(path, "w", encoding="utf-8") as f:
                f.write(r.text)
                print(f"Saved to {os.path.join(OUTDIR, lang)}")
            print(f"[OK ] {lang}")
            supported.append(lang)
        else:
            print(f"[NOH] {lang} — no highlights.scm")
    except Exception as e:
        print(f"[ERR] {lang} — {e}")

print("\nSupported languages:", supported)

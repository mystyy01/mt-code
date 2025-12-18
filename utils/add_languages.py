import os
from textual.widgets import TextArea
from tree_sitter_language_pack import get_language

HIGHLIGHT_DIR = "language_highlighting"


def register_supported_languages(text_area: TextArea) -> list[str]:
    supported = []

    for filename in os.listdir(HIGHLIGHT_DIR):
        if not filename.endswith(".scm"):
            continue

        lang = filename.removesuffix(".scm")
        lang = lang.removeprefix("tree-sitter-")

        # 1️⃣ Try to load tree-sitter parser
        try:
            parser = get_language(lang)
        except Exception:
            print(f"[SKIP] {lang}: no tree-sitter parser")
            continue

        # 2️⃣ Load highlight query
        scm_path = os.path.join(HIGHLIGHT_DIR, filename)
        with open(scm_path, "r", encoding="utf-8") as f:
            highlight_query = f.read()

        # 3️⃣ Register globally
        text_area.register_language(name=lang, language=parser, highlight_query=highlight_query)

        supported.append(lang)
        print(f"[REGISTERED] {lang}")

    return supported

if __name__ == "__main__":
    text_area = TextArea()
    print(text_area.available_languages)
    register_supported_languages(text_area)
    print(text_area.available_languages)
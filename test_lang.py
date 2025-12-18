from tree_sitter_language_pack import get_binding, get_language, get_parser
import inspect

# brute way — try a bunch of likely names
candidates = [
    "python","java","javascript","bash","c","cpp","css","html","rust","go",
    "php","lua","typescript","ruby","dart","sql","yaml","json"
]

available = []
for name in candidates:
    try:
        lang = get_language(name)
        available.append(name)
    except Exception:
        pass

print("Available:", available)
if available == candidates:
    print("All available")

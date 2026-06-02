import os

def search_files(directory):
    for root, dirs, files in os.walk(directory):
        if "user_data" in root or ".git" in root or "__pycache__" in root or ".vscode" in root or ".gemini" in root:
            continue
        for file in files:
            if file.endswith((".py", ".bat", ".sh", ".json", ".js", ".html")):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if "MOCK_YOUTUBE" in content:
                        print(f"Found MOCK_YOUTUBE in: {path}")
                        # print the lines containing it
                        for i, line in enumerate(content.split("\n"), 1):
                            if "MOCK_YOUTUBE" in line:
                                print(f"  Line {i}: {line.strip()}")
                except Exception as e:
                    pass

search_files(".")

import ast

with open('server.py', 'r', encoding='utf-8') as f:
    tree = ast.parse(f.read())

for node in tree.body:
    if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
        if any(name in node.name for name in ['browser', 'core', 'playlist', 'video']):
            print(f"Line {node.lineno}: {type(node).__name__} - {node.name}")

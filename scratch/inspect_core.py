import ast

with open('core.py', 'r', encoding='utf-8') as f:
    tree = ast.parse(f.read())

for node in tree.body:
    if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
        print(f"Line {node.lineno}: {type(node).__name__} - {getattr(node, 'name', '')}")
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    print(f"  Line {sub.lineno}: def {sub.name}")

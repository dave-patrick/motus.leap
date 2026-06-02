import os, re

for root, dirs, files in os.walk('.'):
    if 'node_modules' in root or '.git' in root or '.system_generated' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            content = open(path, encoding='utf-8', errors='ignore').read()
            matches = [m.start() for m in re.finditer('get_browser', content)]
            if matches:
                print(f"{path}: matches at {matches}")

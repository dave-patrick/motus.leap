import os

log_path = "agent_run.log"
if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    import re
    matches = [m.start() for m in re.finditer("Scanning", content)]
    print(f"Total Scanning log entries: {len(matches)}")
    for m in matches[-15:]:
        start = max(0, m - 50)
        end = min(len(content), m + 150)
        print("---")
        print(content[start:end].strip())
else:
    print("agent_run.log not found")

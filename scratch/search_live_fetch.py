import os

log_path = "agent_run.log"
if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # search for Live Fetch
    import re
    matches = [m.start() for m in re.finditer("Live Fetch", content)]
    print(f"Total Live Fetch log entries: {len(matches)}")
    for m in matches[-10:]:
        # print 200 chars around match
        start = max(0, m - 100)
        end = min(len(content), m + 200)
        print("---")
        print(content[start:end].strip())
else:
    print("agent_run.log not found")

import os

log_path = "agent_run.log"
if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    print(f"Total lines: {len(lines)}")
    print("Last 30 lines:")
    for line in lines[-30:]:
        print(line.strip())
else:
    print("agent_run.log not found")

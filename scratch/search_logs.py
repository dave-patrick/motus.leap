import os

logs_path = r"C:\Users\davem\.gemini\antigravity\brain\00730e68-a4c2-47ed-ae72-33f5b3a129c9\.system_generated\logs\transcript.jsonl"
if not os.path.exists(logs_path):
    print("Logs file not found.")
else:
    with open(logs_path, "r", encoding="utf-8") as f:
        for line in f:
            if "discord" in line.lower() or "webhook" in line.lower() or "http" in line.lower():
                # print lines containing potential webhooks
                if "webhooks/" in line:
                    print(line[:300] + "...")

import json
import os

transcript_path = r"C:\Users\davem\.gemini\antigravity\brain\00730e68-a4c2-47ed-ae72-33f5b3a129c9\.system_generated\logs\transcript.jsonl"
if not os.path.exists(transcript_path):
    print("Transcript not found")
    exit(1)

with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            data = json.loads(line)
            step_index = data.get("step_index")
            if 1688 <= step_index <= 1705:
                source = data.get("source")
                content = data.get("content") or ""
                print(f"\n================ STEP {step_index} ({source}) ================")
                print(content)
        except Exception as e:
            pass

import json

log_path = r"C:\Users\davem\.gemini\antigravity\brain\00730e68-a4c2-47ed-ae72-33f5b3a129c9\.system_generated\logs\transcript.jsonl"
with open(log_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        try:
            obj = json.loads(line)
            step = obj.get('step_index')
            if step is not None and 1660 <= step <= 1705:
                print(f"--- STEP {step} ({obj.get('source')}, {obj.get('type')}) ---")
                content = obj.get('content') or ""
                print(content)
        except Exception as e:
            print(f"Error: {e}")

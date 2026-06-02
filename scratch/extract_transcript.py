import json

log_path = r"C:\Users\davem\.gemini\antigravity\brain\00730e68-a4c2-47ed-ae72-33f5b3a129c9\.system_generated\logs\transcript.jsonl"
with open(log_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        try:
            obj = json.loads(line)
            if obj.get('type') == 'USER_INPUT':
                print(f"Step {obj.get('step_index')}: {obj.get('content')}")
        except Exception as e:
            print(f"Error parsing line {i}: {e}")

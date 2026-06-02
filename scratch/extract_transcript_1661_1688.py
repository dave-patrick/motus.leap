import json

log_path = r"C:\Users\davem\.gemini\antigravity\brain\00730e68-a4c2-47ed-ae72-33f5b3a129c9\.system_generated\logs\transcript.jsonl"
with open(log_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        try:
            obj = json.loads(line)
            step = obj.get('step_index')
            if step is not None and 1661 <= step <= 1688:
                print(f"--- STEP {step} ({obj.get('source')}, {obj.get('type')}) ---")
                content = obj.get('content') or ""
                # Print first 500 chars
                if len(content) > 500:
                    print(content[:500] + "\n...[TRUNCATED]...")
                else:
                    print(content)
                tool_calls = obj.get('tool_calls')
                if tool_calls:
                    print(f"Tool calls: {json.dumps(tool_calls, indent=2)}")
        except Exception as e:
            print(f"Error: {e}")

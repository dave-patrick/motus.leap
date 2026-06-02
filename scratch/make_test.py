import json
with open('priority_actions.json', 'r', encoding='utf-8') as f:
    actions = json.load(f)
with open('priority_test.json', 'w', encoding='utf-8') as f:
    json.dump(actions[:5], f, indent=2, ensure_ascii=False)

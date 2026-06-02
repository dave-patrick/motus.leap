import json
import os

def filter_priority():
    with open('maintenance_actions.json', 'r', encoding='utf-8') as f:
        actions = json.load(f)
        
    priority = [a for a in actions if a.get('to') in ['Mobile', 'Tech'] or 'ereader' in a['title'].lower() or 'gadget' in a['title'].lower()]
    duplicates = [a for a in actions if a['type'] == 'DUPLICATE']
    
    print(f"Priority (Mobile/Tech): {len(priority)}")
    print(f"Duplicates: {len(duplicates)}")
    
    with open('priority_actions.json', 'w', encoding='utf-8') as f:
        json.dump(priority, f, indent=2, ensure_ascii=False)
        
    with open('duplicate_actions.json', 'w', encoding='utf-8') as f:
        json.dump(duplicates, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    filter_priority()

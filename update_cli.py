import os

with open('cli.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix the Star Wars keywords
old_sw_rule = 'elif matches(["star wars", "vader", "kenobi", "darth", "jedi", "maul", "coruscant", "skywalker", "ahsoka", "mandalorian", "grogu", "yoda", "sith", "empire", "rebellion", "lightsaber"]):'
new_sw_rule = 'elif matches(["star wars", "vader", "kenobi", "darth", "jedi", "maul", "coruscant", "skywalker", "ahsoka", "mandalorian", "grogu", "yoda", "sith", "lightsaber"]):'
content = content.replace(old_sw_rule, new_sw_rule)

# 2. Extract and reorganize the logic block
# Find start of rule 1
start_idx = content.find('# Rule 1: Arizona keywords')
# Find the end of the channel mapping rule
end_idx = content.find('if target_cat and target_cat in category_to_id:')

if start_idx != -1 and end_idx != -1:
    rules_block = content[start_idx:end_idx]
    
    # We will build the new block
    new_block = """channel_lower = channel.lower()
            channel_map_lower = {k.lower(): v for k, v in channel_map.items()}
            
            # 1. Exact channel mapping (Highest Priority)
            if channel_lower in channel_map_lower:
                target_cat = channel_map_lower[channel_lower]
                
            # 2. Keyword rules
            if not target_cat:
                """
    
    # We need to extract the keyword rules part and indent it.
    kw_start = rules_block.find('# Rule 1: Arizona keywords')
    kw_end = rules_block.find('# Rule 9: Channel mapping')
    
    if kw_start != -1 and kw_end != -1:
        kw_rules = rules_block[kw_start:kw_end]
        
        # Change the first 'if matches' to 'if matches' since it's now inside 'if not target_cat:'
        # Actually it's 'if matches' already! We just need to add indentation.
        indented_kw_rules = ""
        for line in kw_rules.splitlines():
            if line.strip():
                indented_kw_rules += "    " + line + "\n"
            else:
                indented_kw_rules += "\n"
                
        new_block += indented_kw_rules.strip() + "\n"
        
        new_block += """
            # 3. Partial channel mapping (Lowest Priority)
            if not target_cat:
                for ch_key, cat in channel_map.items():
                    if ch_key and ch_key.lower() in channel_lower:
                        target_cat = cat
                        break
            
            """
        
        content = content[:start_idx] + new_block + content[end_idx:]
        
        with open('cli.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("cli.py updated successfully.")
    else:
        print("Failed to find keyword rules boundaries.")
else:
    print("Failed to find logic block boundaries.")

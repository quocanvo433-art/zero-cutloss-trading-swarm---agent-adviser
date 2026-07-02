import re

def search_file(filepath, pattern, context_lines=3):
    print(f"\n--- Searching in {filepath} for '{pattern}' ---")
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if re.search(pattern, line):
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                print(f"Match around line {i+1}:")
                for j in range(start, end):
                    prefix = ">> " if j == i else "   "
                    print(f"{prefix}{j+1}: {lines[j].strip()}")
                print("-" * 20)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")

search_file('/home/newuser/Zero_Cutloss_Public/agents/logic/a11_intent_analyzer.py', r'DATA_RECENTLY')
search_file('/home/newuser/Zero_Cutloss_Public/agents/logic/a11_intent_analyzer.py', r'composite_score.*=.*0')
search_file('/home/newuser/Zero_Cutloss_Public/agents/logic/a12_detective.py', r'Commander A05 should SKIP')
search_file('/home/newuser/Zero_Cutloss_Public/agents/logic/a04_brain.py', r'NARRATIVE_LENS')
search_file('/home/newuser/Zero_Cutloss_Public/agents/logic/a10_signal_collector.py', r'NARRATIVE_LENS')

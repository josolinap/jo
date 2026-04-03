#!/usr/bin/env python3
import json
import sys
from pathlib import Path

print('=== SYSTEM DATA FILES VALIDATION ===\n')

# Check episodes.jsonl
print('1. episodes.jsonl (JSONL format)')
episodes_file = Path('.jo_data/memory/episodes.jsonl')
if not episodes_file.exists():
    print('   ❌ File not found')
else:
    try:
        episodes = []
        count = 0
        with open(episodes_file, 'r') as f:
            for line in f:
                count += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    episodes.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f'   ❌ JSON decode error at line {count}: {e}')
                    print(f'      First 100 chars: {line[:100]}...')
                    sys.exit(1)
        print(f'   ✅ Valid JSONL: {count} entries')
        if episodes:
            latest = episodes[-1]
            print(f'   Latest timestamp: {latest.get("ts", "N/A")}')
            print(f'   Sample keys: {list(latest.keys())}')
    except Exception as e:
        print(f'   ❌ Error reading file: {e}')
        sys.exit(1)

# Check tool_patterns.json
print('\n2. tool_patterns.json (JSON object)')
patterns_file = Path('.jo_data/tool_patterns.json')
if not patterns_file.exists():
    print('   ❌ File not found')
else:
    try:
        with open(patterns_file, 'r') as f:
            data = json.load(f)
        print(f'   ✅ Valid JSON: {type(data).__name__}')
        if isinstance(data, dict):
            print(f'   Keys: {list(data.keys())}')
            if 'patterns' in data:
                print(f'   Number of patterns: {len(data["patterns"])}')
    except json.JSONDecodeError as e:
        print(f'   ❌ JSON decode error: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'   ❌ Error reading file: {e}')
        sys.exit(1)

print('\n✅ All data files are valid!')
import os, sys
from pathlib import Path

# Find all files using the old model name
project_root = Path('.')
old_model = 'llama-3.1-8b-instant'
new_model = 'llama-3.1-8b-instant'

files_updated = []
for ext in ['*.py', '*.yaml', '*.yml', '*.json', '*.env']:
    for f in project_root.rglob(ext):
        if '.venv' in str(f) or 'node_modules' in str(f):
            continue
        try:
            content = f.read_text(encoding='utf-8', errors='ignore')
            if old_model in content:
                new_content = content.replace(old_model, new_model)
                f.write_text(new_content, encoding='utf-8')
                files_updated.append(str(f))
                print(f'Updated: {f}')
        except Exception:
            continue

print(f'\nTotal files updated: {len(files_updated)}')
print(f'Model changed: {old_model} -> {new_model}')

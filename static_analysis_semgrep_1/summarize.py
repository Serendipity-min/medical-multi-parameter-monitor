import json
import glob
from pathlib import Path

findings = []
for f in glob.glob('static_analysis_semgrep_1/findings_*.json'):
    try:
        with open(f, 'r', encoding='utf-8') as fp:
            d = json.load(fp)
        for r in d.get('results', []):
            findings.append({
                'source_file': Path(f).name,
                'check_id': r.get('check_id'),
                'path': r.get('path'),
                'line': r.get('start', {}).get('line'),
                'message': r.get('extra', {}).get('message', '').strip()
            })
    except Exception as exc:
        print(f"Error loading {f}: {exc}")

print(f"Total findings across JSONs: {len(findings)}")
for item in findings:
    print(f"[{item['check_id']}] {item['path']}:{item['line']}")
    print(f"  Message: {item['message'][:100]}")

with open('static_analysis_semgrep_1/merged_findings.json', 'w', encoding='utf-8') as out:
    json.dump(findings, out, indent=2, ensure_ascii=False)
print("Saved to static_analysis_semgrep_1/merged_findings.json")

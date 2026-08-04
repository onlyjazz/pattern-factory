#!/usr/bin/env python3
from pathlib import Path
import yaml, sys
root=Path(__file__).resolve().parents[1]
key=sys.argv[1]
for f in root.glob("*/cycle-*.yaml"):
 d=yaml.safe_load(f.read_text())
 for t in d.get("tasks",[]):
  if t["plan_key"]==key:
   base=(root/"prompts/base.md").read_text(); typ=(root/f"prompts/{t['execution']['agent_template']}.md").read_text()
   print(base+"\n"+typ+f"\n# Task {key}: {t['title']}\n\n## Objective\n{t['objective']}\n\n## Context\n{t.get('context','')}\n\n## Inputs\n"+"\n".join(f"- {x}" for x in t.get('inputs',[]))+"\n\n## Required outputs\n"+"\n".join(f"- {x}" for x in t.get('outputs',[]))+"\n\n## Requirements\n"+"\n".join(f"- {x}" for x in t.get('requirements',[]))+"\n\n## Acceptance criteria\n"+"\n".join(f"- {x}" for x in t.get('acceptance_criteria',[]))+"\n\n## Validation\n"+"\n".join(f"- {x}" for x in t.get('validation',[])))
   raise SystemExit
raise SystemExit(f"Unknown plan key: {key}")

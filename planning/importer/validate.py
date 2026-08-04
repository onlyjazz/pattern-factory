#!/usr/bin/env python3
from pathlib import Path
import yaml, sys
root=Path(__file__).resolve().parents[1]
files=list(root.glob("pattern-factory/cycle-*.yaml"))+list(root.glob("editorial-system/cycle-*.yaml"))+list(root.glob("experiment-platform/cycle-*.yaml"))+list(root.glob("gtm-engine/cycle-*.yaml"))
tasks=[]
for f in files: tasks += yaml.safe_load(f.read_text()).get("tasks",[])
keys=[t["plan_key"] for t in tasks]
errors=[]
if len(keys)!=len(set(keys)): errors.append("Duplicate plan_key")
known=set(keys)
for t in tasks:
  for d in t.get("depends_on",[]):
    if d not in known: errors.append(f"{t['plan_key']}: unknown dependency {d}")
  if len(t['title'])>80: errors.append(f"{t['plan_key']}: title exceeds 80 characters")
print(f"Validated {len(tasks)} tasks across {len(files)} files")
if errors:
  print("\n".join(errors)); sys.exit(1)

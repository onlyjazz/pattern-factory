# backend/db/log.py
from backend.db.connection import get_db
import json

def log_event(event, agent=None, level="INFO", context=None):
    ctx = json.dumps(context or {})
    with get_db() as db:
        db.execute("""
            INSERT INTO system_log (event, agent, level, context)
            VALUES (%s, %s, %s, %s)
        """, (event, agent, level, ctx))

'''
# agents call
from backend.db.log import log_event
log_event("expand_ruleset completed", agent="expand_ruleset", context={"rows": 120})
'''


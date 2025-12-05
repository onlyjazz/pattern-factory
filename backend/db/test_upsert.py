import json
import os
import psycopg
from dotenv import load_dotenv

# ------------------------------------------
# CONFIGURE CONNECTION
# ------------------------------------------
# -------------------------------------------------------------------------
# Environment
# -------------------------------------------------------------------------
load_dotenv()

PGHOST      = os.getenv("PGHOST", "127.0.0.1")
PGPORT      = os.getenv("PGPORT", "5432")
PGUSER      = os.getenv("PGUSER", "pattern_factory")
PGDATABASE  = os.getenv("PGDATABASE", "pattern_factory")
PGPASSWORD  = os.getenv("PGPASSWORD", "314159")

conn = psycopg.connect(
    f"dbname=pattern-factory user={PGUSER} password={PGPASSWORD} host={PGHOST} port={PGPORT}"
)

def call_upsert(payload):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT upsert_pattern_factory_entities(%s::jsonb)
        """, (json.dumps(payload),))
        result = cur.fetchone()[0]
        return result

# ------------------------------------------
# SAMPLE PAYLOAD FOR TESTING
# ------------------------------------------

payload = {
    "orgs": [
        {
            "name": "HelixBio",
            "description": "AI-first biotech CRO",
            "keywords": ["ai", "biotech"],
            "content_url": "https://example.com/post",
            "content_source": "substack"
        }
    ],

    "guests": [
        {
            "name": "Alice Smith",
            "description": "Founder and CEO of HelixBio",
            "job_description": "CEO",
            "org_name": "HelixBio",
            "keywords": ["automation", "clinical"],
            "content_url": "https://example.com/post",
            "content_source": "substack"
        }
    ],

    "posts": [
        {
            "name": "Automation in Biotech",
            "description": "A deep dive into automation trends in next-gen biotech.",
            "keywords": ["automation", "labs", "ai"],
            "content_url": "https://example.com/post",
            "content_source": "substack",
            "published_at": None
        }
    ],

    "patterns": [
        {
            "name": "Process Power",
            "description": "Efficiency grows when workflows become structured and repeatable.",
            "kind": "pattern",
            "keywords": ["process", "efficiency", "systems"],
            "metadata": {"source": "LLM extraction test"},
            "highlights": ["Structured workflows", "Repeatability"],
            "content_source": "substack"
        }
    ],

    "pattern_post_link": [
        {
            "pattern_name": "Process Power",
            "post_name": "Automation in Biotech"
        }
    ],

    "pattern_org_link": [
        {
            "pattern_name": "Process Power",
            "org_name": "HelixBio"
        }
    ],

    "pattern_guest_link": [
        {
            "pattern_name": "Process Power",
            "guest_name": "Alice Smith"
        }
    ]
}


# ------------------------------------------
# RUN TEST
# ------------------------------------------
if __name__ == "__main__":
    result = call_upsert(payload)
    conn.commit()
    print(json.dumps(result, indent=2))

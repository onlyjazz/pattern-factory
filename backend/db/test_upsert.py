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
            CALL upsert_pattern_factory_entities(%s::jsonb, NULL::jsonb)
        """, (json.dumps(payload),))
        result = cur.fetchone()
        if result:
            result = result[0]
        conn.commit()
        return result

# ------------------------------------------
# SAMPLE PAYLOAD FOR TESTING
# ------------------------------------------

payload = {
  "orgs": [
    {
      "name": "Merck",
      "description": "",
      "content_url": "https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling",
      "content_source": "substack"
    },
    {
      "name": "IQVIA",
      "description": "",
      "content_url": "https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling",
      "content_source": "substack"
    },
    {
      "name": "Medtronic",
      "description": "",
      "content_url": "https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling",
      "content_source": "substack"
    },
    {
      "name": "Flatiron Health",
      "description": "",
      "content_url": "https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling",
      "content_source": "substack"
    },
    {
      "name": "Debiopharm",
      "description": "",
      "content_url": "https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling",
      "content_source": "substack"
    }
  ],
  "guests": [
    {
      "name": "Bar Rafaeli",
      "description": "Israeli supermodel and co-founder of Carolina Lemke Berlin.",
      "job_description": "Co-founder",
      "org_name": "Carolina Lemke Berlin",
      "content_url": "https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling",
      "content_source": "substack"
    },
    {
      "name": "Martin Rapaport",
      "description": "Founder of the Rapaport Diamond Report.",
      "job_description": "Founder",
      "org_name": "Rapaport Diamond Report",
      "content_url": "https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling",
      "content_source": "substack"
    }
  ],
  "posts": [
    {
      "name": "The 5 step hack to Brand Power if you’re a super model",
      "description": "Why do we buy Brands: For good feeling or good value?",
      "content_url": "https://newsletter.dannylieberman.com/p/why-do-we-buy-brands-for-good-feeling",
      "content_source": "substack",
      "published_at": "Nov 07, 2025"
    }
  ],
  "patterns": [
    {
      "name": "Branding",
      "description": "Customers attribute higher value based on reputation and trust, not just product features.",
      "kind": "pattern",
      "content_source": "substack"
    },
    {
      "name": "Counter-Positioning",
      "description": "A newcomer adopts a superior business model that incumbents can’t copy without damaging their existing business.",
      "kind": "pattern",
      "content_source": "substack"
    }
  ],
  "pattern_post_link": [
    {
      "pattern_name": "Branding",
      "post_name": "The 5 step hack to Brand Power if you’re a super model"
    },
    {
      "pattern_name": "Counter-Positioning",
      "post_name": "The 5 step hack to Brand Power if you’re a super model"
    }
  ],
  "pattern_org_link": [
    {
      "pattern_name": "Branding",
      "org_name": "Merck"
    },
    {
      "pattern_name": "Branding",
      "org_name": "IQVIA"
    },
    {
      "pattern_name": "Branding",
      "org_name": "Medtronic"
    },
    {
      "pattern_name": "Branding",
      "org_name": "Flatiron Health"
    },
    {
      "pattern_name": "Branding",
      "org_name": "Debiopharm"
    },
    {
      "pattern_name": "Counter-Positioning",
      "org_name": "Carolina Lemke Berlin"
    }
  ],
  "pattern_guest_link": [
    {
      "pattern_name": "Branding",
      "guest_name": "Bar Rafaeli"
    },
    {
      "pattern_name": "Counter-Positioning",
      "guest_name": "Martin Rapaport"
    }
  ]
}

# ------------------------------------------
# RUN TEST
# ------------------------------------------
if __name__ == "__main__":
    result = call_upsert(payload)
    print(json.dumps(result, indent=2))

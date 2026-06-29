#!/usr/bin/env python3
"""
Test upsert_risk_model procedure to verify threats have separate name and description fields.
"""
import json
import os
import sys
import uuid
import psycopg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PGHOST = os.getenv("PGHOST", "127.0.0.1")
PGPORT = os.getenv("PGPORT", "5432")
PGUSER = os.getenv("PGUSER", "pattern_factory")
PGDATABASE = os.getenv("PGDATABASE", "pattern-factory")
PGPASSWORD = os.getenv("PGPASSWORD", "314159")


def get_connection():
    """Create a database connection."""
    return psycopg.connect(
        f"dbname={PGDATABASE} user={PGUSER} password={PGPASSWORD} host={PGHOST} port={PGPORT}"
    )


def call_upsert_risk_model(conn, payload):
    """Call the upsert_risk_model procedure."""
    with conn.cursor() as cur:
        cur.execute(
            "CALL threat.upsert_risk_model(%s::jsonb, NULL::jsonb)",
            (json.dumps(payload),)
        )
        result = cur.fetchone()
        conn.commit()
        return result[0] if result else None


def test_threat_separate_name_and_description():
    """Test that threat name and description are stored separately."""
    conn = get_connection()
    
    try:
        # Create a test card first (required by FK constraint)
        card_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.cards (id, name, description, story) VALUES (%s, %s, %s, %s)",
                (card_id, "Test Card", "Test Description", "# Test")
            )
            conn.commit()
        
        # Create a test model
        model_id = 999
        
        # Prepare payload with threat having separate name and description
        payload = {
            "model_id": model_id,
            "card_id": card_id,
            "assets": [
                {
                    "tag": "A1",
                    "name": "Patient Safety",
                    "fixed_value": 100,
                    "recurring_value": 50,
                    "description": "Protection of patient wellbeing"
                }
            ],
            "threats": [
                {
                    "tag": "R1",
                    "name": "Missed aortic aneurysm due to image quality degradation",
                    "description": "Misdiagnosis that didn't find aortic aneurysm because of a degraded image quality",
                    "domain": "CLINICAL",
                    "probability": 0.15
                },
                {
                    "tag": "R2",
                    "name": "False positive diagnosis",
                    "description": "Incorrect diagnosis leading to unnecessary treatment",
                    "domain": "CLINICAL",
                    "probability": 0.10
                }
            ],
            "vulnerabilities": [],
            "countermeasures": [],
            "asset_threat": [],
            "vulnerability_threat": [],
            "countermeasure_threat": []
        }
        
        # Call upsert
        result = call_upsert_risk_model(conn, payload)
        print("✅ Upsert succeeded")
        print(json.dumps(result, indent=2))
        
        # Verify threats were inserted with correct name and description
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tag, name, description FROM threat.threats WHERE model_id = %s ORDER BY tag",
                (model_id,)
            )
            threats = cur.fetchall()
        
        print("\n✅ Threats in database:")
        for tag, name, desc in threats:
            print(f"  {tag}:")
            print(f"    name: {name}")
            print(f"    description: {desc}")
        
        # Verify R1 has correct separate name and description
        r1_found = False
        for tag, name, desc in threats:
            if tag == "R1":
                r1_found = True
                expected_name = "Missed aortic aneurysm due to image quality degradation"
                expected_desc = "Misdiagnosis that didn't find aortic aneurysm because of a degraded image quality"
                
                assert name == expected_name, f"R1 name mismatch: got '{name}'"
                assert desc == expected_desc, f"R1 description mismatch: got '{desc}'"
                print(f"\n✅ R1 name and description are correctly separated")
        
        assert r1_found, "Threat R1 not found in database"
        
        # Cleanup
        with conn.cursor() as cur:
            cur.execute("DELETE FROM threat.threats WHERE model_id = %s", (model_id,))
            cur.execute("DELETE FROM threat.assets WHERE model_id = %s", (model_id,))
            cur.execute("DELETE FROM public.cards WHERE id = %s", (card_id,))
            conn.commit()
        
        print("\n✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = test_threat_separate_name_and_description()
    sys.exit(0 if success else 1)

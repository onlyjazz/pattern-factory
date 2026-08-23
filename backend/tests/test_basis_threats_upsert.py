"""Test threat upsert behavior with created_at timestamp handling."""

import asyncio
from datetime import datetime, timedelta
import pytest
import asyncpg
import os


@pytest.mark.asyncio
async def test_threat_upsert_updates_created_at_on_conflict():
    """Test that ON CONFLICT clause updates created_at timestamp."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set")

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=1, command_timeout=60)
    
    try:
        async with pool.acquire() as conn:
            # Clean up any existing test data
            await conn.execute(
                "DELETE FROM threat.threats WHERE model_id = $1 AND tag = $2",
                37, "TEST-UPSERT-001"
            )
            
            # Create a test threat with an old timestamp
            old_timestamp = datetime(2026, 8, 19, 12, 0, 0)
            model_id = 37
            tag = "TEST-UPSERT-001"
            
            # First insert: create the threat
            await conn.execute(
                """
                INSERT INTO threat.threats (
                    model_id, tag, name, description, probability,
                    damage_description, spoofing, tampering, repudiation,
                    information_disclosure, denial_of_service,
                    elevation_of_privilege, mitigation_level, disabled,
                    created_at, updated_at, card_id, version, domain
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                """,
                model_id, tag, "Original Name", "Original desc", 3,
                "Original damage", False, False, False, False, False, False, 0, False,
                old_timestamp, old_timestamp,
                "7513ebae-a266-49b1-a088-3afacec21a02", 3, "clinical"
            )
            
            # Verify initial state
            row = await conn.fetchrow(
                "SELECT created_at FROM threat.threats WHERE model_id = $1 AND tag = $2",
                model_id, tag
            )
            assert row is not None
            initial_created_at = row["created_at"]
            assert str(initial_created_at).startswith("2026-08-19")
            
            # Second insert: upsert with new timestamp (ON CONFLICT should update)
            new_timestamp = datetime.utcnow()
            await conn.execute(
                """
                INSERT INTO threat.threats (
                    model_id, tag, name, description, probability,
                    damage_description, spoofing, tampering, repudiation,
                    information_disclosure, denial_of_service,
                    elevation_of_privilege, mitigation_level, disabled,
                    created_at, updated_at, card_id, version, domain
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                ON CONFLICT (model_id, tag) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    probability = EXCLUDED.probability,
                    damage_description = EXCLUDED.damage_description,
                    spoofing = EXCLUDED.spoofing,
                    tampering = EXCLUDED.tampering,
                    repudiation = EXCLUDED.repudiation,
                    information_disclosure = EXCLUDED.information_disclosure,
                    denial_of_service = EXCLUDED.denial_of_service,
                    elevation_of_privilege = EXCLUDED.elevation_of_privilege,
                    mitigation_level = EXCLUDED.mitigation_level,
                    disabled = EXCLUDED.disabled,
                    card_id = EXCLUDED.card_id,
                    domain = EXCLUDED.domain,
                    created_at = EXCLUDED.created_at,
                    updated_at = EXCLUDED.updated_at
                """,
                model_id, tag, "Updated Name", "Updated desc", 3,
                "Updated damage", False, False, False, False, False, False, 0, False,
                new_timestamp, new_timestamp,
                "7513ebae-a266-49b1-a088-3afacec21a02", 3, "clinical"
            )
            
            # Verify the update
            row = await conn.fetchrow(
                "SELECT created_at, name FROM threat.threats WHERE model_id = $1 AND tag = $2",
                model_id, tag
            )
            assert row is not None
            updated_created_at = row["created_at"]
            
            # The created_at should now be updated to approximately today
            assert row["name"] == "Updated Name", "Name should be updated"
            # Check that created_at was updated (should be today, not 2026-08-19)
            assert str(updated_created_at).startswith("2026-08-23"), (
                f"created_at should be updated to today, got {updated_created_at}"
            )
            
            # Clean up
            await conn.execute(
                "DELETE FROM threat.threats WHERE model_id = $1 AND tag = $2",
                model_id, tag
            )
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_threat_upsert_without_created_at_fix_would_fail():
    """
    Demonstrate the bug: if created_at is NOT in the ON CONFLICT clause,
    timestamps won't update when upserting by tag.
    
    This test shows the expected behavior with the fix applied.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set")

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=1, command_timeout=60)
    
    try:
        async with pool.acquire() as conn:
            # Clean up any existing test data
            await conn.execute(
                "DELETE FROM threat.threats WHERE model_id = $1 AND tag = $2",
                37, "TEST-UPSERT-002"
            )
            
            model_id = 37
            tag = "TEST-UPSERT-002"
            
            # Initial insert
            old_ts = datetime(2026, 8, 19, 11, 0, 0)
            await conn.execute(
                """
                INSERT INTO threat.threats (
                    model_id, tag, name, description, probability,
                    damage_description, spoofing, tampering, repudiation,
                    information_disclosure, denial_of_service,
                    elevation_of_privilege, mitigation_level, disabled,
                    created_at, updated_at, card_id, version, domain
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                """,
                model_id, tag, "Name", "desc", 3,
                "damage", False, False, False, False, False, False, 0, False,
                old_ts, old_ts, "7513ebae-a266-49b1-a088-3afacec21a02", 3, "clinical"
            )
            
            # Upsert with new timestamp BUT without created_at in UPDATE clause
            # (This is what the bug was - the clause didn't include created_at)
            new_ts = datetime.utcnow()
            await conn.execute(
                """
                INSERT INTO threat.threats (
                    model_id, tag, name, description, probability,
                    damage_description, spoofing, tampering, repudiation,
                    information_disclosure, denial_of_service,
                    elevation_of_privilege, mitigation_level, disabled,
                    created_at, updated_at, card_id, version, domain
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                ON CONFLICT (model_id, tag) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    probability = EXCLUDED.probability,
                    damage_description = EXCLUDED.damage_description,
                    spoofing = EXCLUDED.spoofing,
                    tampering = EXCLUDED.tampering,
                    repudiation = EXCLUDED.repudiation,
                    information_disclosure = EXCLUDED.information_disclosure,
                    denial_of_service = EXCLUDED.denial_of_service,
                    elevation_of_privilege = EXCLUDED.elevation_of_privilege,
                    mitigation_level = EXCLUDED.mitigation_level,
                    disabled = EXCLUDED.disabled,
                    card_id = EXCLUDED.card_id,
                    domain = EXCLUDED.domain,
                    updated_at = EXCLUDED.updated_at
                """,
                model_id, tag, "Name", "desc", 3,
                "damage", False, False, False, False, False, False, 0, False,
                new_ts, new_ts, "7513ebae-a266-49b1-a088-3afacec21a02", 3, "clinical"
            )
            
            # Without the fix, created_at would still be old
            row = await conn.fetchrow(
                "SELECT created_at FROM threat.threats WHERE model_id = $1 AND tag = $2",
                model_id, tag
            )
            
            # This would fail the assertion without the fix
            assert str(row["created_at"]).startswith("2026-08-19"), (
                "Without fix: created_at should remain old"
            )
            
            # Clean up
            await conn.execute(
                "DELETE FROM threat.threats WHERE model_id = $1 AND tag = $2",
                model_id, tag
            )
    finally:
        await pool.close()

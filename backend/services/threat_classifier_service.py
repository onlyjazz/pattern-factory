"""
Threat Classification Service - Classify threats to countermeasure control classes.

Uses gpt-5.6-luna (low/no reasoning, structured output) to classify threats to
countermeasure control types (e.g., Patient Safety, Clinical Decision Controls).

PAT-330: Multi-class threat-to-control-type assignment.

Usage:
    from threat_classifier_service import classify_threats_batch
    
    result = await classify_threats_batch(
        threat_ids=[1, 2, 3, ...],
        model_id=35,
        db_pool=pool,
        openai_client=client,
        min_confidence=0.6
    )
    # Returns: {threat_id: [class_tag1, class_tag2, ...], ...}
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("threat_classifier_service")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

# Configuration
DEFAULT_LLM_MODEL = "gpt-5.6-luna"
DEFAULT_MIN_CONFIDENCE = 0.6


async def fetch_threat_info(
    pool: asyncpg.Pool,
    threat_ids: List[int],
    model_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Fetch threat name, description, domain for a batch of threat IDs.
    
    Args:
        pool: AsyncPG connection pool
        threat_ids: List of threat IDs
        model_id: Optional model ID filter (None = fetch across all models)
    """
    if not threat_ids:
        return []
    
    # Build parameterized query
    id_list = ",".join(f"${i+1}" for i in range(len(threat_ids)))
    
    if model_id is not None:
        # Single model filter
        query = f"""
            SELECT id, name, description, domain, probability, model_id
            FROM threat.threats
            WHERE model_id = ${len(threat_ids)+1} AND id IN ({id_list})
            ORDER BY id
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *threat_ids, model_id)
    else:
        # Multi-model: no model_id filter
        query = f"""
            SELECT id, name, description, domain, probability, model_id
            FROM threat.threats
            WHERE id IN ({id_list})
            ORDER BY id
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *threat_ids)
    
    return [dict(row) for row in rows]


async def fetch_countermeasure_classes(
    pool: asyncpg.Pool,
) -> Dict[str, Tuple[int, str]]:
    """Fetch all countermeasure classes: {tag: (class_id, class_name)}."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, tag, class FROM threat.countermeasure_class ORDER BY tag"
        )
    
    return {row["tag"]: (row["id"], row["class"]) for row in rows}


def _build_classification_prompt(
    threats: List[Dict[str, Any]],
    class_map: Dict[str, Tuple[int, str]],
) -> Tuple[str, str]:
    """Build system and user prompts for threat classification."""
    
    # Build class taxonomy description
    class_descriptions = []
    for tag, (_, class_name) in sorted(class_map.items()):
        if tag != "UNDEFINED":
            # Truncate long class names for brevity
            desc = class_name
            if len(desc) > 70:
                desc = desc[:67] + "..."
            class_descriptions.append(f"• {tag}: {desc}")
    
    system_prompt = """You are a medical device threat and risk analyst.

Your task is to classify threats to countermeasure control types (multi-class).
A threat may legitimately belong to multiple control classes if it addresses different concerns.

For each threat, return an array of UPPERCASE control class tags that apply.
Use ONLY tags from the provided taxonomy. If a threat does not clearly map to any class, return ["UNDEFINED"].

Return ONLY a valid JSON object with NO explanation or markdown."""
    
    threat_list = []
    for t in threats:
        threat_text = f"{t['id']}|{t['name']}"
        if t.get('description'):
            threat_text += f"|{t['description'][:100]}"
        threat_list.append(threat_text)
    
    user_prompt = f"""Countermeasure Control Classes:
{chr(10).join(class_descriptions)}

Threats to Classify (ID|NAME|DESCRIPTION_SNIPPET):
{chr(10).join(threat_list)}

Task: For each threat, assign one or more control class tags from the taxonomy above.

Return a JSON object:
{{
  "classifications": [
    {{"threat_id": <int>, "classes": ["TAG1", "TAG2", ...]}},
    ...
  ]
}}

Rules:
1. Use only tags from the taxonomy (all UPPERCASE)
2. Multi-class assignment is valid (a threat may need multiple control types)
3. If uncertain, include ["UNDEFINED"]
4. Return valid JSON only, no explanation"""
    
    return system_prompt, user_prompt


async def classify_threats_batch(
    threat_ids: List[int],
    model_id: Optional[int] = None,
    db_pool: asyncpg.Pool = None,
    openai_client: OpenAI = None,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    batch_size: int = 50,
) -> Dict[int, List[str]]:
    """
    Classify a batch of threats to countermeasure control classes.
    
    For multi-model classification (model_id=None), groups threats by model_id
    and processes each model separately, upserting incrementally to avoid
    overwhelming memory and to persist results continuously.
    
    Args:
        threat_ids: List of threat IDs to classify
        model_id: Optional threat model ID filter (None = multi-model classification)
        db_pool: AsyncPG connection pool
        openai_client: OpenAI API client
        min_confidence: Minimum confidence threshold (0.0-1.0)
        batch_size: Process threats in batches (default 50)
    
    Returns:
        {threat_id: [class_tag1, class_tag2, ...], ...}
    """
    if not threat_ids:
        return {}
    
    logger.info(f"Classifying {len(threat_ids)} threats to control classes")
    
    # Fetch all threats
    threats = await fetch_threat_info(db_pool, threat_ids, model_id)
    class_map = await fetch_countermeasure_classes(db_pool)
    
    if not threats:
        logger.warning(f"No threats found for IDs: {threat_ids}")
        return {}
    
    if not class_map:
        logger.warning("No countermeasure classes loaded")
        return {}
    
    logger.info(f"Loaded {len(threats)} threats and {len(class_map)} classes")
    
    # For multi-model classification, group threats by model_id and process each model
    threat_to_classes: Dict[int, List[str]] = {}
    total_upserted = 0
    
    if model_id is None:
        # Multi-model: group by model_id and process each group
        threats_by_model: Dict[int, List[Dict[str, Any]]] = {}
        for threat in threats:
            m_id = threat.get("model_id")
            if m_id not in threats_by_model:
                threats_by_model[m_id] = []
            threats_by_model[m_id].append(threat)
        
        logger.info(f"Multi-model classification: {len(threats_by_model)} models found")
        
        # Process each model separately and upsert immediately
        for m_id, model_threats in sorted(threats_by_model.items()):
            logger.info(f"  Processing model_id={m_id} with {len(model_threats)} threats")
            model_classifications = await _classify_threat_batch_single_model(
                model_threats,
                class_map,
                openai_client,
            )
            
            # Upsert immediately after each model to avoid memory buildup
            inserted, _ = await upsert_threat_classifications(
                db_pool,
                model_classifications,
                class_map,
            )
            total_upserted += inserted
            logger.info(f"  ✓ Upserted {inserted} classifications for model_id={m_id}")
            
            threat_to_classes.update(model_classifications)
    else:
        # Single model: process all at once
        threat_to_classes = await _classify_threat_batch_single_model(
            threats,
            class_map,
            openai_client,
        )
    
    return threat_to_classes


async def _classify_threat_batch_single_model(
    threats: List[Dict[str, Any]],
    class_map: Dict[str, Tuple[int, str]],
    openai_client: OpenAI,
) -> Dict[int, List[str]]:
    """Classify threats for a single model using LLM."""
    if not threats:
        return {}
    
    # Build and execute LLM call
    system_prompt, user_prompt = _build_classification_prompt(threats, class_map)
    
    try:
        # Note: gpt-5.6-luna does not support temperature parameter
        response = openai_client.chat.completions.create(
            model=DEFAULT_LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=None,  # gpt-5.6-luna does not support temperature
            timeout=120.0,
        )
        
        response_text = response.choices[0].message.content.strip()
        logger.info(f"LLM response: {response_text[:200]}...")
        
        # Parse response
        result = json.loads(response_text)
        classifications = result.get("classifications", [])
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        # Fallback: assign all threats to UNDEFINED
        classifications = [
            {"threat_id": t["id"], "classes": ["UNDEFINED"]}
            for t in threats
        ]
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        # Fallback: assign all threats to UNDEFINED
        classifications = [
            {"threat_id": t["id"], "classes": ["UNDEFINED"]}
            for t in threats
        ]
    
    # Validate and normalize classifications
    valid_tags = set(class_map.keys())
    threat_to_classes: Dict[int, List[str]] = {}
    
    for item in classifications:
        threat_id = item.get("threat_id")
        classes = item.get("classes", [])
        
        if not isinstance(classes, list):
            classes = [classes]
        
        # Validate tags
        valid_classes = [
            c for c in classes
            if isinstance(c, str) and c in valid_tags
        ]
        
        if not valid_classes:
            # If no valid classes, default to UNDEFINED
            valid_classes = ["UNDEFINED"]
        
        threat_to_classes[threat_id] = valid_classes
        logger.info(f"  Threat {threat_id}: {valid_classes}")
    
    # Ensure all threats have a classification
    for threat in threats:
        if threat["id"] not in threat_to_classes:
            threat_to_classes[threat["id"]] = ["UNDEFINED"]
            logger.warning(f"  Threat {threat['id']}: missing from LLM response, assigned UNDEFINED")
    
    return threat_to_classes


async def upsert_threat_classifications(
    db_pool: asyncpg.Pool,
    threat_to_classes: Dict[int, List[str]],
    class_map: Dict[str, Tuple[int, str]],
) -> Tuple[int, int]:
    """
    Upsert threat classifications into threat_countermeasure_classes table.
    
    Args:
        db_pool: AsyncPG connection pool
        threat_to_classes: {threat_id: [class_tag1, class_tag2, ...]}
        class_map: {tag: (class_id, class_name)}
    
    Returns:
        (total_inserted, total_skipped)
    """
    total_inserted = 0
    total_skipped = 0
    
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            for threat_id, class_tags in threat_to_classes.items():
                for tag in class_tags:
                    class_id, class_name = class_map.get(tag, (None, tag))
                    
                    if not class_id:
                        logger.warning(f"  Skipping unknown class: {tag}")
                        total_skipped += 1
                        continue
                    
                    # Upsert: insert or ignore duplicate
                    result = await conn.execute(
                        """
                        INSERT INTO threat.threat_countermeasure_classes (threat_id, class_id)
                        VALUES ($1, $2)
                        ON CONFLICT (threat_id, class_id) DO NOTHING
                        """,
                        threat_id,
                        class_id,
                    )
                    
                    # Parse result string: "INSERT 0 N" or "INSERT N"
                    if "INSERT" in result:
                        total_inserted += 1
    
    logger.info(f"Upserted {total_inserted} threat-class associations, skipped {total_skipped}")
    return total_inserted, total_skipped


async def log_classification_event(
    db_pool: asyncpg.Pool,
    event_name: str,
    context: Dict[str, Any],
) -> bool:
    """Log classification event to system_log table."""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.system_log (event, context)
                VALUES ($1, $2)
                """,
                event_name,
                json.dumps(context),
            )
        return True
    except Exception as e:
        logger.error(f"Failed to log event: {e}")
        return False

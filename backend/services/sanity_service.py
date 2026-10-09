"""
Sanity content seam (PAT-380: Send to Close) — STUBBED, NOT INTEGRATED.

Sanity is **not** integrated yet. This module is a deliberate, read-only seam so
the activation flow can pin content briefs without a live Sanity dependency.
Every function here is deterministic, performs **no network I/O**, and returns
stub data derived solely from the ``content_id`` it is given.

Environment (read for forward compatibility, not used for any request yet):
    SANITY_PROJECT_ID
    SANITY_DATASET
    SANITY_API_TOKEN   (never logged)

Stub contract:
    * ``get_brief(content_id)`` returns a dict with ``_id``, ``_rev``,
      ``status`` and ``approved`` keys, or ``None`` when ``content_id`` is falsy.
    * A content id beginning with ``"draft"`` (case-insensitive) yields
      ``status == "draft"`` / ``approved == False``; anything else yields
      ``status == "approved"`` / ``approved == True``. This gives callers a
      deterministic way to exercise the "refuse unapproved step" path.
    * ``is_approved(brief)`` returns True only for an approved brief.
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Read for forward compatibility. No network request is made with these values.
SANITY_PROJECT_ID = os.getenv("SANITY_PROJECT_ID")
SANITY_DATASET = os.getenv("SANITY_DATASET")
# The token is intentionally never logged or returned.
SANITY_API_TOKEN = os.getenv("SANITY_API_TOKEN")

STUB_SOURCE = "sanity-stub"


def _stub_rev(content_id: str) -> str:
    """Deterministic stub revision derived from the content id."""
    digest = hashlib.sha1(str(content_id).encode("utf-8")).hexdigest()
    return f"stub-{digest[:12]}"


def get_brief(content_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return a deterministic stub brief for ``content_id`` (no network).

    Returns ``None`` for a falsy ``content_id``. See the module docstring for the
    stub contract.
    """
    if not content_id:
        return None
    cid = str(content_id)
    approved = not cid.strip().lower().startswith("draft")
    return {
        "_id": cid,
        "_rev": _stub_rev(cid),
        "_type": "brief",
        "title": f"Stub brief {cid}",
        "status": "approved" if approved else "draft",
        "approved": approved,
        "source": STUB_SOURCE,
    }


def is_approved(brief: Optional[Dict[str, Any]]) -> bool:
    """Return True only when ``brief`` represents approved content."""
    if not isinstance(brief, dict):
        return False
    if "approved" in brief:
        return bool(brief["approved"])
    return brief.get("status") == "approved"

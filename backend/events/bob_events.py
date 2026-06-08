from __future__ import annotations
import httpx
from datetime import datetime, timezone
from loguru import logger
from backend.config import KARPATHYS_URL


async def _emit(endpoint: str, payload: dict) -> None:
    if not KARPATHYS_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(f"{KARPATHYS_URL}/{endpoint}", json=payload)
    except Exception as e:
        logger.warning("bob_event_failed endpoint={} error={}", endpoint, str(e))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_bob_scored(lead_id: str, score: int, reason_codes: list, packet_state: str) -> None:
    import asyncio
    try:
        asyncio.get_event_loop().create_task(_emit("bob/scored", {
            "lead_id": lead_id,
            "score": score,
            "reason_codes": reason_codes,
            "packet_state": packet_state,
            "occurred_at": _now(),
        }))
    except Exception:
        pass


def emit_call_brief_created(lead_id: str, phase: str, missing_box: str, mood: str, confidence: float) -> None:
    import asyncio
    try:
        asyncio.get_event_loop().create_task(_emit("bob/brief-created", {
            "lead_id": lead_id,
            "phase": phase,
            "missing_box": missing_box,
            "mood": mood,
            "confidence": confidence,
            "occurred_at": _now(),
        }))
    except Exception:
        pass


def emit_lead_ready_for_call(lead_id: str, priority_score: int, situation_label: str) -> None:
    import asyncio
    try:
        asyncio.get_event_loop().create_task(_emit("bob/lead-ready", {
            "lead_id": lead_id,
            "priority_score": priority_score,
            "situation_label": situation_label,
            "occurred_at": _now(),
        }))
    except Exception:
        pass

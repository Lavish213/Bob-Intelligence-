from __future__ import annotations
from datetime import datetime, timezone
from loguru import logger


def log_decision(
    lead_id: str,
    decision_type: str,
    inputs: dict,
    output: dict,
    reason_codes: list[str],
    confidence: float,
    version: str = "1.0",
) -> None:
    record = {
        "lead_id": lead_id,
        "decision_type": decision_type,
        "inputs_used": inputs,
        "output": output,
        "reason_codes": reason_codes,
        "confidence": confidence,
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        from backend.db.client import save_decision_record
        save_decision_record(record)
        logger.debug("decision_logged lead_id={} type={}", lead_id, decision_type)
    except Exception as e:
        logger.warning("decision_logger failed lead_id={} type={} error={}", lead_id, decision_type, str(e))

from __future__ import annotations
import time
from loguru import logger
from backend.config import BOB_WORKER_INTERVAL_MINUTES, BOB_BATCH_SIZE
from backend.db.client import (
    get_leads_needing_brief,
    save_call_brief,
    load_intel_packet,
    get_seller_memory,
)
from backend.call_planner.brief_generator import generate_call_brief
from backend.decisions.decision_logger import log_decision
from backend.events.bob_events import emit_call_brief_created, emit_lead_ready_for_call


def _get_situation_label(lead: dict, prop: dict) -> str:
    distress = (prop.get("distress_type") or "").lower()
    mapping = {
        "preforeclosure":  "preforeclosure",
        "pre_foreclosure": "preforeclosure",
        "probate":         "probate",
        "inherited":       "inherited_property",
        "vacant":          "vacant_property",
        "landlord":        "tired_landlord",
        "divorce":         "divorce",
        "tax":             "tax_delinquent",
        "code":            "code_violation",
    }
    for key, label in mapping.items():
        if key in distress:
            return label
    return "unknown"


def run_once() -> dict:
    logger.info("bob_worker run_once starting")
    leads = get_leads_needing_brief(BOB_BATCH_SIZE)
    logger.info("bob_worker leads_to_process count={}", len(leads))

    results = {"processed": 0, "briefs_created": 0, "errors": 0}

    for lead in leads:
        lead_id = lead.get("id")
        if not lead_id:
            continue

        results["processed"] += 1
        prop = lead.get("properties") or {}

        try:
            intel_packet = load_intel_packet(lead_id) or {}
            seller_memory = get_seller_memory(lead_id)
            situation_label = _get_situation_label(lead, prop)
            initial_trust = float(lead.get("initial_trust_score") or 5.0)
            is_outbound = True

            brief = generate_call_brief(
                lead_id=lead_id,
                lead=lead,
                prop=prop,
                intel_packet=intel_packet,
                seller_memory=seller_memory,
                situation_label=situation_label,
                initial_trust=initial_trust,
                is_outbound=is_outbound,
            )

            if not brief:
                results["errors"] += 1
                continue

            brief_dict = brief.to_dict()
            save_call_brief(lead_id, brief_dict)

            log_decision(
                lead_id=lead_id,
                decision_type="call_brief",
                inputs={
                    "situation_label": situation_label,
                    "call_count": len((seller_memory.get("call_summaries") or [])),
                    "packet_state": intel_packet.get("packet_state", "missing"),
                },
                output=brief_dict,
                reason_codes=[
                    f"missing:{brief.missing_box}",
                    f"phase:{brief.phase}",
                    f"mood:{brief.mood}",
                ],
                confidence=brief.confidence,
            )

            results["briefs_created"] += 1
            try:
                emit_call_brief_created(
                    lead_id=lead_id,
                    phase=brief.phase,
                    missing_box=brief.missing_box,
                    mood=brief.mood,
                    confidence=brief.confidence,
                )
                emit_lead_ready_for_call(
                    lead_id=lead_id,
                    priority_score=int(prop.get("distress_score") or 50),
                    situation_label=situation_label,
                )
            except Exception as _ee:
                logger.warning("bob_emit_failed lead_id={} error={}", lead_id, str(_ee))
            logger.info(
                "brief_saved lead_id={} phase={} box={} mood={}",
                lead_id, brief.phase, brief.missing_box, brief.mood,
            )

        except Exception as e:
            results["errors"] += 1
            logger.error("bob_worker lead_failed lead_id={} error={}", lead_id, str(e))

    logger.info("bob_worker run_once complete results={}", results)
    return results


def run_loop() -> None:
    logger.info("bob_worker starting interval={}min", BOB_WORKER_INTERVAL_MINUTES)
    while True:
        try:
            run_once()
        except Exception as e:
            logger.error("bob_worker loop_error error={}", str(e))
        time.sleep(BOB_WORKER_INTERVAL_MINUTES * 60)

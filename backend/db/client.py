from __future__ import annotations
from functools import lru_cache
from supabase import create_client, Client
from backend.config import SUPABASE_URL, SUPABASE_SERVICE_KEY

@lru_cache(maxsize=1)
def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def get_leads_needing_brief(batch_size: int = 20) -> list[dict]:
    client = get_client()
    resp = (
        client.table("leads")
        .select("*, properties!properties_lead_id_fkey(*)")
        .eq("opted_out", False)
        .eq("dnc_blocked", False)
        .neq("stage", "dead")
        .or_("call_brief.is.null,call_brief_generated_at.lt.2026-06-07T21:26:06.932595+00:00")
        .gte("properties.distress_score", 50)
        .limit(batch_size)
        .execute()
    )
    rows = resp.data or []
    for r in rows:
        if isinstance(r.get("properties"), list):
            r["properties"] = r["properties"][0] if r["properties"] else {}
    return rows

def save_call_brief(lead_id: str, brief: dict) -> None:
    from datetime import datetime, timezone
    client = get_client()
    client.table("leads").update({
        "call_brief": brief,
        "call_brief_generated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", lead_id).execute()

def load_intel_packet(lead_id: str) -> dict | None:
    client = get_client()
    resp = client.table("lead_intel_packets").select("*").eq("lead_id", lead_id).limit(1).execute()
    return resp.data[0] if resp.data else None

def save_intel_packet(packet: dict) -> None:
    client = get_client()
    client.table("lead_intel_packets").upsert(packet, on_conflict="lead_id").execute()

def save_decision_record(record: dict) -> None:
    client = get_client()
    client.table("decision_records").insert(record).execute()

def get_seller_memory(lead_id: str) -> dict:
    client = get_client()
    resp = (
        client.table("seller_memory")
        .select("*")
        .eq("lead_id", lead_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else {}

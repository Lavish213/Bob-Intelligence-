from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta

SCHEMA_VERSION = '2.0'
CHECKBOX_PRIORITY = ['right_person', 'property_confirmed', 'occupancy', 'condition', 'timeline', 'motivation', 'next_step']
PHASE_TO_STAGE = {'VERIFY': 'STAGE_1_QUALIFY', 'LIGHT_DISCOVERY': 'STAGE_2_DISCOVER', 'QUALIFY': 'STAGE_3_PRECLOSE', 'NEXT_STEP': 'STAGE_4_CLOSE', 'WRAP': 'STAGE_5_WRAP'}


@dataclass
class CallBrief:
    lead_id: str
    phase: str
    objective: str
    missing_box: str
    mood: str
    avoid: list[str] = field(default_factory=list)
    escalation_rules: list[str] = field(default_factory=list)
    opener_hint: str | None = None
    confidence: float = 0.0
    source: str = 'bob_rules'
    schema_version: str = SCHEMA_VERSION
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = field(default_factory=lambda: (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat())
    evidence: dict = field(default_factory=dict)
    blocked_reasons: list[str] = field(default_factory=list)
    ready_for_call: bool = False

    def to_dict(self):
        return asdict(self)

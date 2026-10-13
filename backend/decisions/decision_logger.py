from __future__ import annotations
from datetime import datetime, timezone


def decision_record(lead_id, brief, source_fingerprint):
    return {'lead_id': lead_id, 'decision_type': 'call_brief', 'version': '2.0', 'source_fingerprint': source_fingerprint, 'reason_codes': [f"missing:{brief['missing_box']}", f"phase:{brief['phase']}", *brief['blocked_reasons']], 'confidence': brief['confidence'], 'confidence_meaning': brief['evidence']['confidence_meaning'], 'created_at': datetime.now(timezone.utc).isoformat()}

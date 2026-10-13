from datetime import datetime, timezone


def health_status(metrics, interval_seconds=300):
    worker = metrics.get('worker') or {}
    try:
        completed = datetime.fromisoformat(worker['completed_at'].replace('Z', '+00:00'))
        age = (datetime.now(timezone.utc)-completed).total_seconds()
        current = completed.tzinfo is not None and 0 <= age <= interval_seconds*2+60 and worker.get('errors') == 0
    except (KeyError, TypeError, ValueError, AttributeError):
        current = False
    return 'ok' if current and not metrics.get('quarantined_jobs') and not metrics.get('dead_events') and not metrics.get('stale_briefs') else 'degraded'

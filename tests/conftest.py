import os
os.environ['SUPABASE_URL'] = 'https://example.supabase.co'
os.environ['SUPABASE_SERVICE_KEY'] = 'test-only-placeholder'
os.environ['KARPATHYS_URL'] = ''
os.environ['BOB_BATCH_SIZE'] = '20'
os.environ['KARPATHYS_WEBHOOK_SECRET'] = ''

import pytest


@pytest.fixture(autouse=True)
def offline_heartbeat(monkeypatch):
    from backend.worker import loop
    from backend import main
    monkeypatch.setattr(loop, 'report_worker_run', lambda result: None)
    monkeypatch.setattr(main, 'integration_health', lambda: {'contract_version': '2.1', 'backend': 'REI-AGENT'})

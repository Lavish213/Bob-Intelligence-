import pytest

from backend.config import settings


def test_shared_source_origin_derives_the_actual_bob_ingress(monkeypatch):
    monkeypatch.delenv('BOB_EVENT_URL', raising=False)
    monkeypatch.setenv('REI_COMMAND_URL', 'https://source.example.invalid/')
    assert settings().event_url == 'https://source.example.invalid/api/ingest/bob/brief-created'
    monkeypatch.setenv('BOB_EVENT_URL', 'https://explicit.example.invalid/events')
    assert settings().event_url == 'https://explicit.example.invalid/events'


@pytest.mark.parametrize('source', ['http://source.invalid', 'https://user:secret@source.invalid', 'https://source.invalid/api', 'https://source.invalid?secret=yes', 'https://source.invalid#fragment'])
def test_source_alias_cannot_hide_credentials_or_a_wrong_route(monkeypatch, source):
    monkeypatch.setenv('REI_COMMAND_URL', source)
    with pytest.raises(ValueError, match='service origin'):
        settings()

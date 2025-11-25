import requests
from helpers.nse_data import MarketSentiment


def test_get_live_sentiment_ssl_failure(monkeypatch):
    ms = MarketSentiment()
    # Simulate failed network fetch by making _safe_get return None
    monkeypatch.setattr(ms, '_safe_get', lambda url, timeout=10: None)
    result = ms.get_live_sentiment()
    assert isinstance(result, dict)
    assert result == {}


def test_safe_get_ssl_fallback(monkeypatch):
    from requests.exceptions import SSLError

    ms = MarketSentiment(trust_all_ssl=True)

    calls = {'count': 0}

    class FakeResponse:
        def __init__(self):
            self.status_code = 200
            self.content = b'<html><span class="hm-time">Updated: 2025-11-25</span><div class="col-sm-6"><p>1</p></div><div class="col-sm-6"><p>2</p></div><div class="col-sm-6"><p>3</p></div><div class="col-sm-6"><p>4</p></div><div class="col-sm-6"><p>5</p></div></html>'
        def raise_for_status(self):
            return

    def fake_get(self_, url, timeout=10, verify=True):
        calls['count'] += 1
        if calls['count'] == 1 and verify:
            raise SSLError('cert verify failed')
        return FakeResponse()

    monkeypatch.setattr(requests.Session, 'get', fake_get)
    res = ms._safe_get('https://example.com')
    assert res is not None
    assert calls['count'] == 2


def test_check_ca_helper():
    ms = MarketSentiment()
    res = ms.check_ca()
    assert 'installed' in res and 'ca_bundle' in res and 'message' in res
    # message expected to be a string and installed is a bool
    assert isinstance(res['installed'], bool)
    assert isinstance(res['message'], str)

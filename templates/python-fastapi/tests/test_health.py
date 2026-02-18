from app.main import health

def test_health():
    assert health()["ok"] is True

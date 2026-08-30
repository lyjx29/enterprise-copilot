"""M3 企业层测试：API Key 鉴权（401）+ 限流（429）。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _fresh_client(monkeypatch, **env) -> TestClient:
    """用指定环境变量构造独立 app（避免污染全局 app）。"""
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    from app.main import create_app

    client = TestClient(create_app())
    get_settings.cache_clear()
    return client


def test_auth_disabled_by_default(monkeypatch) -> None:
    """未配置 API_KEYS 时鉴权关闭，请求正常通过。"""
    monkeypatch.delenv("API_KEYS", raising=False)
    client = _fresh_client(monkeypatch)
    resp = client.post("/v1/threads")
    assert resp.status_code == 200


def test_auth_401_without_key(monkeypatch) -> None:
    client = _fresh_client(monkeypatch, API_KEYS='["test-key"]')
    resp = client.post("/v1/threads")
    assert resp.status_code == 401


def test_auth_200_with_bearer(monkeypatch) -> None:
    client = _fresh_client(monkeypatch, API_KEYS='["test-key"]')
    resp = client.post("/v1/threads", headers={"Authorization": "Bearer test-key"})
    assert resp.status_code == 200


def test_auth_200_with_x_api_key(monkeypatch) -> None:
    client = _fresh_client(monkeypatch, API_KEYS='["test-key"]')
    resp = client.post("/v1/threads", headers={"X-API-Key": "test-key"})
    assert resp.status_code == 200


def test_auth_health_exempt(monkeypatch) -> None:
    """健康检查豁免鉴权。"""
    client = _fresh_client(monkeypatch, API_KEYS='["test-key"]')
    resp = client.get("/v1/health")
    assert resp.status_code == 200


def test_rate_limit_429(monkeypatch) -> None:
    """超频 → 429。"""
    client = _fresh_client(monkeypatch, RATE_LIMIT_PER_MINUTE="2")
    codes = [client.post("/v1/threads").status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_request_id_header(monkeypatch) -> None:
    client = _fresh_client(monkeypatch)
    resp = client.get("/v1/health")
    assert "X-Request-ID" in resp.headers

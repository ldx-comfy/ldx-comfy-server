import json
import time
import importlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def make_client(tmp_path: Path, monkeypatch, cfg: dict) -> TestClient:
    """
    创建仅挂载鉴权路由的最小应用，并基于给定配置生成客户端。
    - 写入临时 auth.json
    - 通过 AUTH_CONFIG_PATH 指向该文件
    - 重新加载 auth.config 以应用配置
    """
    cfg_path = tmp_path / "auth.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    # 确保不受外部环境 JWT_SECRET 干扰（除非测试用例主动设置）
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("AUTH_CONFIG_PATH", str(cfg_path))

    # 重新加载配置模块（在同一模块对象上执行，路由中的引用保持有效）
    import auth.config as auth_config
    importlib.reload(auth_config)

    # 构建仅包含鉴权路由的最小应用
    app = FastAPI()
    from routers.auth import router as auth_router
    app.include_router(auth_router)
    return TestClient(app)


def test_password_login_success(tmp_path, monkeypatch):
    cfg = {
        "jwt_secret": "test-secret",
        "jwt_expires_seconds": 3600,
        "users": [{"username": "demo", "password": "demo123"}],
        "codes": [],
    }
    client = make_client(tmp_path, monkeypatch, cfg)

    resp = client.post("/api/v1/auth/login", json={"username": "demo", "password": "demo123"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 3600

    # 校验 JWT claims
    from auth import jwt as jwt_lib
    claims = jwt_lib.decode(data["access_token"], "test-secret")
    assert claims["sub"] == "demo"
    assert claims["login_mode"] == "password"
    assert isinstance(claims["exp"], int) and claims["exp"] > int(time.time())


def test_password_login_failure(tmp_path, monkeypatch):
    cfg = {
        "jwt_secret": "test-secret",
        "users": [{"username": "demo", "password": "demo123"}],
        "codes": [],
    }
    client = make_client(tmp_path, monkeypatch, cfg)

    resp = client.post("/api/v1/auth/login", json={"username": "demo", "password": "wrong"})
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers
    assert resp.json().get("detail")


def test_code_login_success(tmp_path, monkeypatch):
    cfg = {
        "jwt_secret": "test-secret",
        "jwt_expires_seconds": 1800,
        "users": [],
        "codes": [{"code": "TEST-CODE", "expires_at": "2099-12-31T23:59:59Z"}],
    }
    client = make_client(tmp_path, monkeypatch, cfg)

    resp = client.post("/api/v1/auth/code", json={"code": "TEST-CODE"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800

    from auth import jwt as jwt_lib
    claims = jwt_lib.decode(data["access_token"], "test-secret")
    assert claims["sub"] == "TEST-CODE"
    assert claims["login_mode"] == "code"


def test_code_login_expired(tmp_path, monkeypatch):
    cfg = {
        "jwt_secret": "test-secret",
        "users": [],
        "codes": [{"code": "OLD", "expires_at": "2000-01-01T00:00:00Z"}],
    }
    client = make_client(tmp_path, monkeypatch, cfg)

    resp = client.post("/api/v1/auth/code", json={"code": "OLD"})
    assert resp.status_code == 401
    assert resp.json().get("detail") in ("Code expired", "Invalid code")


def test_me_success(tmp_path, monkeypatch):
    cfg = {
        "jwt_secret": "abc123",
        "jwt_expires_seconds": 600,
        "users": [{"username": "alice", "password": "p@ss"}],
        "codes": [],
    }
    client = make_client(tmp_path, monkeypatch, cfg)

    # 先登录拿 token
    login = client.post("/api/v1/auth/login", json={"username": "alice", "password": "p@ss"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    # 调用 /me
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    claims = me.json()
    for k in ("sub", "login_mode", "iat", "exp"):
        assert k in claims
    assert claims["sub"] == "alice"
    assert claims["login_mode"] == "password"


def test_me_invalid_signature(tmp_path, monkeypatch):
    # 服务端配置使用 right-secret
    cfg = {
        "jwt_secret": "right-secret",
        "users": [],
        "codes": [],
        "jwt_expires_seconds": 3600,
    }
    client = make_client(tmp_path, monkeypatch, cfg)

    # 客户端伪造一个使用 wrong-secret 的令牌
    from auth import jwt as jwt_lib
    iat = int(time.time())
    payload = {"sub": "mallory", "login_mode": "password", "iat": iat, "exp": iat + 3600}
    forged = jwt_lib.encode(payload, "wrong-secret")

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert me.status_code == 401
    assert "WWW-Authenticate" in me.headers


def test_me_expired_token(tmp_path, monkeypatch):
    cfg = {
        "jwt_secret": "expire-secret",
        "users": [],
        "codes": [],
    }
    client = make_client(tmp_path, monkeypatch, cfg)

    # 构造一个已过期 token
    from auth import jwt as jwt_lib
    now = int(time.time())
    expired = jwt_lib.encode({"sub": "u", "login_mode": "password", "iat": now - 100, "exp": now - 1}, "expire-secret")

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert me.status_code == 401

def test_default_admin_generated(tmp_path, monkeypatch):
    cfg = {
        "jwt_secret": "sec",
        "users": [],
        "codes": [],
    }
    client = make_client(tmp_path, monkeypatch, cfg)

    import auth.config as auth_config
    snap = auth_config.get_effective_config_snapshot()
    admins = [u for u in snap["users"] if isinstance(u, dict) and u.get("username") == "admin"]
    assert len(admins) == 1
    pw = admins[0].get("password")
    assert isinstance(pw, str) and len(pw) == 16
    import re as _re
    assert _re.fullmatch(r"[A-Za-z0-9]{16}", pw)


def test_password_login_with_roles_groups(tmp_path, monkeypatch):
    cfg = {
        "jwt_secret": "test-secret",
        "jwt_expires_seconds": 3600,
        "groups_map": {
            "viewer": ["wf:view"],
            "admin": ["admin"]
        },
        "users": [
            {"username": "demo", "password": "demo123", "groups": ["viewer"], "roles": ["wf:run"]}
        ],
        "codes": [],
    }
    client = make_client(tmp_path, monkeypatch, cfg)

    resp = client.post("/api/v1/auth/login", json={"username": "demo", "password": "demo123"})
    assert resp.status_code == 200, resp.text
    data = resp.json()

    from auth import jwt as jwt_lib
    claims = jwt_lib.decode(data["access_token"], "test-secret")
    assert claims["sub"] == "demo"
    assert claims["login_mode"] == "password"
    assert "roles" in claims and "groups" in claims
    # roles = explicit ['wf:run'] U expanded from groups ['viewer'] -> ['wf:view']
    assert set(claims["roles"]) >= {"wf:run", "wf:view"}
    assert set(claims["groups"]) == {"viewer"}


def test_code_login_with_roles_groups(tmp_path, monkeypatch):
    cfg = {
        "jwt_secret": "code-secret",
        "jwt_expires_seconds": 1800,
        "groups_map": {
            "admin": ["admin"]
        },
        "users": [],
        "codes": [
            {"code": "ADMIN-ONCALL", "expires_at": "2099-12-31T23:59:59Z", "groups": ["admin"]}
        ],
    }
    client = make_client(tmp_path, monkeypatch, cfg)

    resp = client.post("/api/v1/auth/code", json={"code": "ADMIN-ONCALL"})
    assert resp.status_code == 200, resp.text
    data = resp.json()

    from auth import jwt as jwt_lib
    claims = jwt_lib.decode(data["access_token"], "code-secret")
    assert claims["sub"] == "ADMIN-ONCALL"
    assert claims["login_mode"] == "code"
    assert set(claims.get("groups", [])) == {"admin"}
    assert "admin" in set(claims.get("roles", []))


def test_code_login_inherit_default_groups(tmp_path, monkeypatch):
    # code 未指定 roles/groups 时继承 default_user_groups，并经 groups_map 展开为 roles
    cfg = {
        "jwt_secret": "inherit-secret",
        "jwt_expires_seconds": 900,
        "groups_map": {
            "viewer": ["wf:view"]
        },
        "default_user_groups": ["viewer"],
        "users": [],
        "codes": [
            {"code": "VIEW-ONLY", "expires_at": "2099-12-31T23:59:59Z"}
        ],
    }
    client = make_client(tmp_path, monkeypatch, cfg)
    resp = client.post("/api/v1/auth/code", json={"code": "VIEW-ONLY"})
    assert resp.status_code == 200, resp.text

    from auth import jwt as jwt_lib
    claims = jwt_lib.decode(resp.json()["access_token"], "inherit-secret")
    assert set(claims.get("groups", [])) == {"viewer"}
    assert set(claims.get("roles", [])) == {"wf:view"}


def test_require_roles_admin_ping(tmp_path, monkeypatch):
    # viewer 调用 /admin/ping -> 403；admin 调用 -> 200
    cfg = {
        "jwt_secret": "rbac-secret",
        "jwt_expires_seconds": 1200,
        "groups_map": {
            "viewer": ["wf:view"],
            "admin": ["admin"]
        },
        "users": [
            {"username": "viewer", "password": "viewer", "groups": ["viewer"]}
        ],
        "codes": [
            {"code": "ADMIN-CODE", "expires_at": "2099-12-31T23:59:59Z", "groups": ["admin"]}
        ],
    }
    client = make_client(tmp_path, monkeypatch, cfg)

    # viewer login
    rv = client.post("/api/v1/auth/login", json={"username": "viewer", "password": "viewer"})
    assert rv.status_code == 200, rv.text
    viewer_token = rv.json()["access_token"]

    # call admin ping with viewer token -> 403
    r_forbidden = client.get("/api/v1/auth/admin/ping", headers={"Authorization": f"Bearer {viewer_token}"})
    assert r_forbidden.status_code == 403

    # admin code login
    ra = client.post("/api/v1/auth/code", json={"code": "ADMIN-CODE"})
    assert ra.status_code == 200, ra.text
    admin_token = ra.json()["access_token"]

    # call admin ping with admin token -> 200
    r_ok = client.get("/api/v1/auth/admin/ping", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_ok.status_code == 200
    assert r_ok.json().get("ok") is True
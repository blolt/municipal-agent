"""Unit tests for service-to-service JWT authentication."""

import time

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentic_common.auth import (
    ServiceAuthDependency,
    ServiceIdentity,
    generate_service_token,
    verify_service_token,
)

SECRET = "test-secret-key"


# --- Token generation tests ---


class TestGenerateServiceToken:
    def test_generates_valid_jwt(self):
        token = generate_service_token("my-service", SECRET)
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["sub"] == "my-service"
        assert "iat" in payload
        assert "exp" in payload

    def test_default_expiry_is_5_minutes(self):
        token = generate_service_token("my-service", SECRET)
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["exp"] - payload["iat"] == 300

    def test_custom_expiry(self):
        token = generate_service_token("my-service", SECRET, expiry_seconds=60)
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["exp"] - payload["iat"] == 60


# --- Token verification tests ---


class TestVerifyServiceToken:
    def test_valid_token(self):
        token = generate_service_token("orchestrator-service", SECRET)
        identity = verify_service_token(token, SECRET)
        assert identity.service_name == "orchestrator-service"
        assert identity.issued_at > 0

    def test_allowed_services_accepted(self):
        token = generate_service_token("orchestrator-service", SECRET)
        identity = verify_service_token(
            token, SECRET, allowed_services=["orchestrator-service", "discord-service"]
        )
        assert identity.service_name == "orchestrator-service"

    def test_disallowed_service_rejected(self):
        token = generate_service_token("rogue-service", SECRET)
        with pytest.raises(ValueError, match="not in allowed list"):
            verify_service_token(
                token, SECRET, allowed_services=["orchestrator-service"]
            )

    def test_expired_token_rejected(self):
        token = generate_service_token("my-service", SECRET, expiry_seconds=-1)
        with pytest.raises(jwt.ExpiredSignatureError):
            verify_service_token(token, SECRET)

    def test_wrong_secret_rejected(self):
        token = generate_service_token("my-service", SECRET)
        with pytest.raises(jwt.InvalidSignatureError):
            verify_service_token(token, "wrong-secret")

    def test_tampered_token_rejected(self):
        token = generate_service_token("my-service", SECRET)
        # Flip a character in the signature portion
        tampered = token[:-4] + "XXXX"
        with pytest.raises(jwt.InvalidTokenError):
            verify_service_token(tampered, SECRET)

    def test_missing_sub_claim(self):
        payload = {"iat": time.time(), "exp": time.time() + 300}
        token = jwt.encode(payload, SECRET, algorithm="HS256")
        with pytest.raises(jwt.InvalidTokenError, match="missing 'sub'"):
            verify_service_token(token, SECRET)

    def test_none_allowed_services_accepts_any(self):
        token = generate_service_token("any-service", SECRET)
        identity = verify_service_token(token, SECRET, allowed_services=None)
        assert identity.service_name == "any-service"


# --- FastAPI dependency tests ---


class TestServiceAuthDependency:
    @pytest.fixture
    def app(self):
        """Create a test FastAPI app with an auth-protected endpoint."""
        app = FastAPI()
        auth = ServiceAuthDependency(
            secret=SECRET, allowed_services=["orchestrator-service"]
        )

        @app.get("/protected")
        async def protected(caller: ServiceIdentity = pytest.importorskip("fastapi").Depends(auth)):
            return {"caller": caller.service_name}

        @app.get("/public")
        async def public():
            return {"status": "ok"}

        return app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_valid_token_grants_access(self, client):
        token = generate_service_token("orchestrator-service", SECRET)
        response = client.get(
            "/protected", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["caller"] == "orchestrator-service"

    def test_missing_auth_header_returns_401(self, client):
        response = client.get("/protected")
        assert response.status_code == 401
        assert "Missing Authorization" in response.json()["detail"]

    def test_invalid_token_returns_401(self, client):
        response = client.get(
            "/protected", headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401

    def test_expired_token_returns_401(self, client):
        token = generate_service_token("orchestrator-service", SECRET, expiry_seconds=-1)
        response = client.get(
            "/protected", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"]

    def test_wrong_service_returns_403(self, client):
        token = generate_service_token("rogue-service", SECRET)
        response = client.get(
            "/protected", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
        assert "not in allowed list" in response.json()["detail"]

    def test_malformed_auth_header_returns_401(self, client):
        response = client.get(
            "/protected", headers={"Authorization": "Basic abc123"}
        )
        assert response.status_code == 401

    def test_public_endpoint_needs_no_auth(self, client):
        response = client.get("/public")
        assert response.status_code == 200

"""Service-to-service JWT authentication for Agentic Bridge.

Provides HS256 JWT token generation and verification for securing
internal service communication within the Docker Compose network.
"""

import time
from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status


# Default token lifetime: 5 minutes (short-lived, generated per-request)
DEFAULT_TOKEN_EXPIRY_SECONDS = 300


@dataclass
class ServiceIdentity:
    """Verified identity of a calling service."""

    service_name: str
    issued_at: float


def generate_service_token(
    service_name: str,
    secret: str,
    expiry_seconds: int = DEFAULT_TOKEN_EXPIRY_SECONDS,
) -> str:
    """Generate an HS256 JWT service token.

    Args:
        service_name: Name of the calling service (e.g., "orchestrator-service")
        secret: Shared secret for signing
        expiry_seconds: Token lifetime in seconds (default: 300)

    Returns:
        Encoded JWT string
    """
    now = time.time()
    payload = {
        "sub": service_name,
        "iat": now,
        "exp": now + expiry_seconds,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_service_token(
    token: str,
    secret: str,
    allowed_services: Optional[list[str]] = None,
) -> ServiceIdentity:
    """Verify an HS256 JWT service token.

    Args:
        token: The JWT string to verify
        secret: Shared secret for verification
        allowed_services: If provided, only accept tokens from these service names.
                         If None, accept any valid token.

    Returns:
        ServiceIdentity with the verified caller info

    Raises:
        jwt.ExpiredSignatureError: Token has expired
        jwt.InvalidTokenError: Token is invalid
        ValueError: Service not in allowed list
    """
    payload = jwt.decode(token, secret, algorithms=["HS256"])

    service_name = payload.get("sub")
    if not service_name:
        raise jwt.InvalidTokenError("Token missing 'sub' claim")

    if allowed_services and service_name not in allowed_services:
        raise ValueError(
            f"Service '{service_name}' not in allowed list: {allowed_services}"
        )

    return ServiceIdentity(
        service_name=service_name,
        issued_at=payload.get("iat", 0),
    )


def _extract_bearer_token(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


class ServiceAuthDependency:
    """FastAPI dependency for service-to-service authentication.

    Usage:
        require_auth = ServiceAuthDependency(secret="...", allowed_services=["orchestrator-service"])
        @app.post("/events", dependencies=[Depends(require_auth)])
        async def create_event(...): ...

    Or to access the identity:
        @app.post("/events")
        async def create_event(caller: ServiceIdentity = Depends(require_auth)): ...
    """

    def __init__(
        self,
        secret: str,
        allowed_services: Optional[list[str]] = None,
    ):
        self.secret = secret
        self.allowed_services = allowed_services

    async def __call__(self, request: Request) -> ServiceIdentity:
        token = _extract_bearer_token(request)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Authorization header with Bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            return verify_service_token(
                token, self.secret, self.allowed_services
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e),
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            )

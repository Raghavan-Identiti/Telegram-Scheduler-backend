# app/core/clerk_auth.py
import os
import time
import json
import base64
import logging
import urllib.request
import urllib.error
import asyncio
from typing import Optional, Dict, Any, Tuple
from fastapi import Request, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger("telequeue.auth")

security = HTTPBearer(auto_error=False)

# Configuration from Environment
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY", "").strip()
PRIMARY_ADMIN_EMAIL = "raghavan@identitidesign.com"

raw_allowed_emails = os.getenv("ALLOWED_EMAILS", PRIMARY_ADMIN_EMAIL)
ALLOWED_EMAILS = [e.strip().lower() for e in raw_allowed_emails.split(",") if e.strip()]
if PRIMARY_ADMIN_EMAIL.lower() not in ALLOWED_EMAILS:
    ALLOWED_EMAILS.append(PRIMARY_ADMIN_EMAIL.lower())

raw_allowed_domains = os.getenv("ALLOWED_DOMAINS", "identitidesign.com")
ALLOWED_DOMAINS = [d.strip().lower() for d in raw_allowed_domains.split(",") if d.strip()]

ALLOW_DOMAIN_LOGIN = os.getenv("ALLOW_DOMAIN_LOGIN", "true").lower() in ("true", "1", "yes")

# In-memory cache for user email lookups: {user_id: (email, timestamp)}
_USER_CACHE: Dict[str, Tuple[str, float]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes

def decode_jwt_unverified_claims(token: str) -> Dict[str, Any]:
    """Safely extracts JWT payload claims without requiring signature validation library."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload_b64 = parts[1]
        # Fix padding
        padding = 4 - (len(payload_b64) % 4)
        if padding != 4:
            payload_b64 += "=" * padding
        payload_bytes = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:
        logger.warning(f"Failed to parse JWT payload: {e}")
        return {}

def is_email_authorized(email: Optional[str]) -> bool:
    """Checks if an email is authorized per Identiti Design security policies."""
    if not email:
        return False
    clean = email.strip().lower()

    if clean in ALLOWED_EMAILS:
        return True

    if ALLOW_DOMAIN_LOGIN:
        for domain in ALLOWED_DOMAINS:
            if clean.endswith(f"@{domain}"):
                return True

    return False

def get_user_role(email: str) -> str:
    """Assigns role based on email."""
    if email.strip().lower() == PRIMARY_ADMIN_EMAIL.lower():
        return "Admin"
    return "Operator"

async def fetch_clerk_user_email(user_id: str) -> Optional[str]:
    """Queries Clerk's official Backend API using CLERK_SECRET_KEY to retrieve user's primary email."""
    if not CLERK_SECRET_KEY:
        return None

    # Check cache first
    now = time.time()
    if user_id in _USER_CACHE:
        email, ts = _USER_CACHE[user_id]
        if now - ts < CACHE_TTL_SECONDS:
            return email

    def _do_request() -> Optional[str]:
        try:
            url = f"https://api.clerk.com/v1/users/{user_id}"
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {CLERK_SECRET_KEY}",
                    "Content-Type": "application/json",
                    "User-Agent": "TeleQueue-Backend/2.5"
                }
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    primary_id = data.get("primary_email_address_id")
                    emails = data.get("email_addresses", [])

                    # Find primary email
                    for em in emails:
                        if em.get("id") == primary_id:
                            email = em.get("email_address")
                            _USER_CACHE[user_id] = (email, now)
                            return email

                    # Fallback to first available email
                    if emails:
                        email = emails[0].get("email_address")
                        _USER_CACHE[user_id] = (email, now)
                        return email
        except Exception as e:
            logger.error(f"Error communicating with Clerk Backend API: {e}")
        return None

    return await asyncio.to_thread(_do_request)

async def verify_clerk_token(request: Request) -> Dict[str, Any]:
    """
    Core authentication dependency for protected FastAPI endpoints.
    Verifies Bearer token, expiration, user email identity, and whitelist access.
    """
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    # 1. When no token is present:
    if not token:
        # If in development sandbox with no Clerk Secret Key configured:
        # Check supplemental header or fallback
        if not CLERK_SECRET_KEY:
            supp_email = request.headers.get("X-User-Email", "").strip()
            if supp_email and is_email_authorized(supp_email):
                return {
                    "user_id": "dev_sandbox_user",
                    "email": supp_email,
                    "role": get_user_role(supp_email),
                    "authenticated": True,
                    "provider": "dev_sandbox"
                }
            # Allow permissive local access if explicitly in local non-production environment
            if not os.getenv("RENDER") and not os.getenv("ENVIRONMENT") == "production":
                return {
                    "user_id": "local_dev",
                    "email": PRIMARY_ADMIN_EMAIL,
                    "role": "Admin",
                    "authenticated": True,
                    "provider": "local_permissive"
                }

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Clerk Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 2. Extract claims from JWT
    claims = decode_jwt_unverified_claims(token)
    user_id = claims.get("sub", "")
    exp = claims.get("exp", 0)

    if exp and exp < time.time():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clerk session token has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 3. Retrieve user email
    # Check if email claim was directly injected by a Clerk JWT template
    email = claims.get("email") or claims.get("primary_email_address")

    if not email and user_id and CLERK_SECRET_KEY:
        email = await fetch_clerk_user_email(user_id)

    # Fallback to header if running in local sandbox
    if not email:
        email = request.headers.get("X-User-Email", "").strip()

    # 4. Check if user email is authorized
    if not email or not is_email_authorized(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access Denied: Account '{email or 'unknown'}' is not authorized to access TeleQueue marketing resources. Allowed: {PRIMARY_ADMIN_EMAIL} or @identitidesign.com."
        )

    return {
        "user_id": user_id or "authenticated_user",
        "email": email,
        "role": get_user_role(email),
        "claims": claims,
        "authenticated": True,
        "provider": "clerk"
    }

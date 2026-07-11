"""
JWT authentication for the Aegis FastAPI backend.

Login validates users from AEGIS_USERS (or AEGIS_USERNAME / AEGIS_PASSWORD).
The JWT payload carries user_id, user_role, and employee_id so every protected
endpoint can enforce RBAC without an extra DB round-trip.

AEGIS_USERS entry format:  username:role:password[:employee_id]
    employee_id is the HR-database identity (employees.employee_id) used for
    row-level security. Login usernames and DB employee ids are different
    namespaces — without this mapping, "employees see their own records" can
    never match a row.

Roles come from RBAC_ROLES in config.py:
    admin    — full access + audit log
    manager  — department-level access
    employee — personal data only
"""
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import bcrypt as _bcrypt
import jwt  # PyJWT
from jwt import InvalidTokenError as JWTError
from pydantic import BaseModel

from aegis.config import RBAC_ROLES

logger = logging.getLogger(__name__)

_DEFAULT_SECRET = "CHANGE_ME_IN_PRODUCTION_USE_RANDOM_32_BYTES"
SECRET_KEY   = os.getenv("AEGIS_JWT_SECRET", _DEFAULT_SECRET)
if SECRET_KEY == _DEFAULT_SECRET:
    if os.getenv("AEGIS_ENV", "").lower() in {"prod", "production"}:
        raise RuntimeError("AEGIS_JWT_SECRET must be set in production")
    logger.warning("Using development JWT secret; set AEGIS_JWT_SECRET before deployment")
ALGORITHM    = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("AEGIS_JWT_EXPIRE_MINUTES", "480"))  # 8 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _check_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    user_role: str
    expires_in: int


class UserInfo(BaseModel):
    user_id: str
    user_role: str
    employee_id: str = ""  # HR-database identity for row-level security ("" = unmapped)


def _load_users() -> dict[str, dict]:
    """
    Returns a dict of username → {hashed_password, user_id, user_role, employee_id}.
    In production replace with a real user store.
    Currently reads comma-separated entries from env:
        AEGIS_USERS=alice:admin:secret,bob:employee:pass123:EMP0042
    (4th field = optional HR employee_id for row-level security.)
    Falls back to AEGIS_USERNAME / AEGIS_PASSWORD (single user, role=admin).
    """
    users: dict[str, dict] = {}

    # Multi-user format: AEGIS_USERS=username:role:password[:employee_id],...
    raw = os.getenv("AEGIS_USERS", "")
    if raw:
        for entry in raw.split(","):
            parts = entry.strip().split(":")
            if len(parts) in (3, 4):
                username, role, password = parts[0], parts[1], parts[2]
                employee_id = parts[3] if len(parts) == 4 else ""
                if role not in RBAC_ROLES:
                    logger.warning(f"Unknown role '{role}' for user '{username}' — skipping")
                    continue
                users[username] = {
                    "hashed_password": _hash_password(password),
                    "user_id": username,
                    "user_role": role,
                    "employee_id": employee_id,
                }
            elif entry.strip():
                logger.warning(
                    "Malformed AEGIS_USERS entry (expected user:role:password[:employee_id]) — skipping"
                )

    # Fallback single-user from original AEGIS_USERNAME / AEGIS_PASSWORD
    username = os.getenv("AEGIS_USERNAME", "admin")
    password = os.getenv("AEGIS_PASSWORD", "")
    role     = os.getenv("AEGIS_DEFAULT_ROLE", "admin")
    if username and password and username not in users:
        users[username] = {
            "hashed_password": _hash_password(password),
            "user_id": username,
            "user_role": role if role in RBAC_ROLES else "employee",
            "employee_id": os.getenv("AEGIS_EMPLOYEE_ID", ""),
        }

    return users


_USERS = _load_users()


def _create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _verify_password(plain: str, hashed: str) -> bool:
    return _check_password(plain, hashed)


def _authenticate_user(username: str, password: str) -> Optional[dict]:
    user = _USERS.get(username)
    if not user:
        return None
    if not _verify_password(password, user["hashed_password"]):
        return None
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInfo:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        user_role: str = payload.get("role")
        if user_id is None or user_role is None:
            raise credentials_exception
    except JWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        raise credentials_exception
    return UserInfo(
        user_id=user_id,
        user_role=user_role,
        employee_id=payload.get("emp", "") or "",
    )


async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    user = _authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = _create_access_token(
        data={
            "sub": user["user_id"],
            "role": user["user_role"],
            "emp": user.get("employee_id", ""),
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    logger.info(f"Login: user='{user['user_id']}' role='{user['user_role']}'")
    return TokenResponse(
        access_token=token,
        user_id=user["user_id"],
        user_role=user["user_role"],
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

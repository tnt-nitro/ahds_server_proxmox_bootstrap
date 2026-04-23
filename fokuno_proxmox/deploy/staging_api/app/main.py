"""Staging-API mit Migrationen, Auth-Basis und Kalender-Endpunkten."""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time
from typing import Any

import psycopg
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from psycopg import Error as PsycopgError
from psycopg.rows import dict_row

app = FastAPI(title="AhDs Staging API", version="0.3.0")
_API_MAJOR = "v1"
_API_RELEASE = app.version
_API_COMPAT_POLICY = (
    "Innerhalb einer Major-Version keine Breaking Changes ohne neuen Major-Pfad."
)
_CLIENT_MAJOR_HEADER = "x-client-api-major"
_DEPRECATED_PATHS: dict[str, dict[str, str]] = {
    "/v1/admin/logs": {
        "sunset": "Wed, 31 Dec 2026 23:59:59 GMT",
        "successor": "/v1/admin/audit-logs",
        "note": "Bitte auf /v1/admin/audit-logs wechseln.",
    }
}

_MIGRATIONEN_ORDNER = Path(__file__).resolve().parent / "migrations"
_ACCESS_TTL_SEKUNDEN = 60 * 60 * 8
_REFRESH_TTL_SEKUNDEN = 60 * 60 * 24 * 14
_LOGIN_MAX_FEHLVERSUCHE = int(os.environ.get("LOGIN_MAX_FEHLVERSUCHE", "5"))
_LOGIN_SPERRE_SEKUNDEN = int(os.environ.get("LOGIN_SPERRE_SEKUNDEN", "900"))
_RESET_TOKEN_TTL_SEKUNDEN = int(os.environ.get("RESET_TOKEN_TTL_SEKUNDEN", "1800"))


def _app_env() -> str:
    return (os.environ.get("APP_ENV") or "staging").strip().lower()


def _token_secret() -> bytes:
    # Im Staging/Prod per .env setzen.
    s = os.environ.get("API_TOKEN_SECRET", "").strip()
    if not s:
        s = "ahds-dev-insecure-secret"
    return s.encode("utf-8")


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _admin_email() -> str:
    return (os.environ.get("ADMIN_EMAIL") or "").strip().lower()


def _conn() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("PGHOST", "").strip(),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ.get("PGDATABASE", "postgres"),
        user=os.environ.get("PGUSER", ""),
        password=os.environ.get("PGPASSWORD", ""),
        connect_timeout=5,
        autocommit=True,
    )


def _migrationen_ausfuehren() -> None:
    if not _MIGRATIONEN_ORDNER.exists():
        return
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  name TEXT PRIMARY KEY,
                  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            for pfad in sorted(_MIGRATIONEN_ORDNER.glob("*.sql")):
                cur.execute(
                    "SELECT 1 FROM schema_migrations WHERE name = %s",
                    (pfad.name,),
                )
                if cur.fetchone() is not None:
                    continue
                sql = pfad.read_text(encoding="utf-8")
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations(name) VALUES (%s)",
                    (pfad.name,),
                )


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * ((4 - (len(data) % 4)) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _sign(text: str) -> str:
    sig = hmac.new(_token_secret(), text.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(sig)


def _password_hash(password: str, salt_hex: str) -> str:
    roh = (salt_hex + "|" + password).encode("utf-8")
    return hashlib.sha256(roh).hexdigest()


def _reset_token_hash(token: str) -> str:
    roh = (_token_secret().decode("utf-8") + "|" + token).encode("utf-8")
    return hashlib.sha256(roh).hexdigest()


def _token_erzeugen(
    *,
    user_id: int,
    email: str,
    role: str,
    token_version: int,
    token_typ: str,
    ttl_sekunden: int,
) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "tv": token_version,
        "typ": token_typ,
        "exp": int(time.time()) + ttl_sekunden,
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(body)}"


def _token_lesen(token: str) -> dict[str, Any]:
    teile = token.split(".")
    if len(teile) != 2:
        raise HTTPException(status_code=401, detail="ungueltiger Token")
    body, sig = teile
    if not hmac.compare_digest(sig, _sign(body)):
        raise HTTPException(status_code=401, detail="ungueltiger Token")
    try:
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="ungueltiger Token") from exc
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=401, detail="Token abgelaufen")
    return payload


def _bearer_aus_header(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization fehlt")
    teile = authorization.split(" ", 1)
    if len(teile) != 2 or teile[0].lower() != "bearer" or not teile[1].strip():
        raise HTTPException(status_code=401, detail="Bearer Token fehlt")
    return teile[1].strip()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: str


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=190)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=190)
    password: str = Field(min_length=1, max_length=128)


class AuthOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class ApiVersionOut(BaseModel):
    api_major: str
    api_release: str
    app_env: str
    compat_policy: str


class DeprecationInfoOut(BaseModel):
    path: str
    sunset: str
    successor: str
    note: str


class PasswordResetRequestIn(BaseModel):
    email: str = Field(min_length=3, max_length=190)


class PasswordResetRequestOut(BaseModel):
    status: str
    detail: str
    reset_token_preview: str | None = None


class PasswordResetConfirmIn(BaseModel):
    email: str = Field(min_length=3, max_length=190)
    reset_token: str = Field(min_length=8, max_length=400)
    new_password: str = Field(min_length=8, max_length=128)


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event: str
    ok: bool
    user_id: int | None = None
    email: str | None = None
    detail: str = ""
    created_at: dt.datetime


class EventCreate(BaseModel):
    titel: str = Field(min_length=1, max_length=200)
    starts_at: dt.datetime
    ends_at: dt.datetime
    notiz: str = Field(default="", max_length=2000)


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    titel: str
    starts_at: dt.datetime
    ends_at: dt.datetime
    notiz: str


def _auth_row_aus_header(
    authorization: str | None,
    *,
    erwarteter_typ: str,
) -> dict[str, Any]:
    token = _bearer_aus_header(authorization)
    payload = _token_lesen(token)
    token_typ = str(payload.get("typ", ""))
    if token_typ != erwarteter_typ:
        raise HTTPException(status_code=401, detail="falscher Token-Typ")
    user_id = int(payload.get("sub", 0))
    email = str(payload.get("email", "")).strip().lower()
    token_version = int(payload.get("tv", -1))
    with _conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, name, email, role, token_version
                FROM users
                WHERE id = %s AND lower(email) = %s
                LIMIT 1
                """,
                (user_id, email),
            )
            row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="Token-Benutzer unbekannt")
    row_tv = int(row.get("token_version") or 0)
    if token_version != row_tv:
        raise HTTPException(status_code=401, detail="Token nicht mehr gueltig")
    return row


def _aktueller_user_aus_header(authorization: str | None) -> UserOut:
    row = _auth_row_aus_header(authorization, erwarteter_typ="access")
    return UserOut.model_validate(row)


def _admin_user_aus_header(authorization: str | None) -> UserOut:
    user = _aktueller_user_aus_header(authorization)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin erforderlich")
    return user


def _audit_log(
    *,
    event: str,
    ok: bool,
    user_id: int | None = None,
    email: str | None = None,
    detail: str = "",
) -> None:
    """Best-Effort Audit-Log; darf Business-Endpunkte nicht blockieren."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_log(event, ok, user_id, email, detail)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (event, ok, user_id, email, detail),
                )
    except PsycopgError:
        return


@app.on_event("startup")
def startup_migrationen() -> None:
    """Stellt sicher, dass Basistabellen vor dem ersten Request existieren."""
    _migrationen_ausfuehren()


@app.middleware("http")
async def api_versions_header(request: Request, call_next):  # type: ignore[no-untyped-def]
    if request.url.path.startswith("/v1") and request.url.path != "/v1/meta/version":
        major = (request.headers.get(_CLIENT_MAJOR_HEADER) or "").strip().lower()
        if major != _API_MAJOR:
            return JSONResponse(
                status_code=426,
                content={
                    "detail": "Client-API-Version nicht kompatibel",
                    "expected_major": _API_MAJOR,
                    "received_major": major or None,
                    "required_header": _CLIENT_MAJOR_HEADER,
                },
            )
    response = await call_next(request)
    response.headers["X-API-Major"] = _API_MAJOR
    response.headers["X-API-Release"] = _API_RELEASE
    dep = _DEPRECATED_PATHS.get(request.url.path)
    if dep is not None:
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = dep["sunset"]
        successor_url = str(request.url.replace(path=dep["successor"]))
        successor_link = f'<{successor_url}>; rel="successor-version"'
        link_alt = response.headers.get("Link")
        response.headers["Link"] = (
            f"{link_alt}, {successor_link}" if link_alt else successor_link
        )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    """Prozess lebt (Loadbalancer / Docker HEALTHCHECK)."""
    return {"status": "ok", "app_env": _app_env()}


@app.get("/ready")
def ready(response: Response) -> dict[str, Any]:
    """Datenbank erreichbar; HTTP 503 bei Fehler."""
    if not os.environ.get("PGHOST", "").strip():
        response.status_code = 503
        return {"db": "not_configured", "detail": "PGHOST fehlt"}

    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except PsycopgError as exc:
        response.status_code = 503
        return {"db": "error", "detail": str(exc)}

    return {"db": "ok", "app_env": _app_env()}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "ahds-staging-api", "app_env": _app_env()}


@app.get("/v1/meta/version", summary="API-Version und Kompatibilitaet")
def api_version() -> ApiVersionOut:
    return ApiVersionOut(
        api_major=_API_MAJOR,
        api_release=_API_RELEASE,
        app_env=_app_env(),
        compat_policy=_API_COMPAT_POLICY,
    )


@app.get("/v1/meta/deprecations", summary="Liste geplanter Abschaltungen")
def api_deprecations() -> list[DeprecationInfoOut]:
    eintraege: list[DeprecationInfoOut] = []
    for path, info in sorted(_DEPRECATED_PATHS.items()):
        eintraege.append(
            DeprecationInfoOut(
                path=path,
                sunset=info["sunset"],
                successor=info["successor"],
                note=info["note"],
            )
        )
    return eintraege


@app.post("/v1/auth/register", status_code=201)
def register(payload: RegisterIn) -> AuthOut:
    email = payload.email.strip().lower()
    role = "admin" if _admin_email() and email == _admin_email() else "user"
    salt_hex = secrets.token_hex(16)
    pw_hash = _password_hash(payload.password, salt_hex)
    with _conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id FROM users WHERE lower(email) = %s", (email,))
            if cur.fetchone() is not None:
                _audit_log(
                    event="auth.register",
                    ok=False,
                    email=email,
                    detail="email_bereits_vergeben",
                )
                raise HTTPException(status_code=409, detail="E-Mail bereits vergeben")
            cur.execute(
                """
                INSERT INTO users(name, email, role, password_salt, password_hash)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, name, email, role, token_version
                """,
                (payload.name.strip(), email, role, salt_hex, pw_hash),
            )
            row = cur.fetchone()
    assert row is not None
    user = UserOut.model_validate(row)
    token_version = int(row.get("token_version") or 0)
    access_token = _token_erzeugen(
        user_id=user.id,
        email=user.email,
        role=user.role,
        token_version=token_version,
        token_typ="access",
        ttl_sekunden=_ACCESS_TTL_SEKUNDEN,
    )
    refresh_token = _token_erzeugen(
        user_id=user.id,
        email=user.email,
        role=user.role,
        token_version=token_version,
        token_typ="refresh",
        ttl_sekunden=_REFRESH_TTL_SEKUNDEN,
    )
    _audit_log(
        event="auth.register",
        ok=True,
        user_id=user.id,
        email=user.email,
        detail=f"role={user.role}",
    )
    return AuthOut(access_token=access_token, refresh_token=refresh_token, user=user)


@app.post("/v1/auth/login")
def login(payload: LoginIn) -> AuthOut:
    email = payload.email.strip().lower()
    jetzt = _utc_now()
    with _conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                  id,
                  name,
                  email,
                  role,
                  password_salt,
                  password_hash,
                  token_version,
                  failed_login_count,
                  locked_until
                FROM users
                WHERE lower(email) = %s
                LIMIT 1
                """,
                (email,),
            )
            row = cur.fetchone()
    if row is None:
        _audit_log(event="auth.login", ok=False, email=email, detail="unbekannte_email")
        raise HTTPException(status_code=401, detail="Login fehlgeschlagen")
    locked_until = row.get("locked_until")
    if isinstance(locked_until, dt.datetime):
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=dt.timezone.utc)
        if locked_until > jetzt:
            _audit_log(
                event="auth.login",
                ok=False,
                user_id=int(row["id"]),
                email=email,
                detail="temporarily_locked",
            )
            raise HTTPException(
                status_code=429,
                detail="Zu viele Fehlversuche, bitte spaeter erneut versuchen",
            )
    salt = str(row.get("password_salt") or "")
    pw_hash = str(row.get("password_hash") or "")
    if not salt or not pw_hash:
        _audit_log(
            event="auth.login",
            ok=False,
            user_id=int(row["id"]),
            email=email,
            detail="keine_passworddaten",
        )
        raise HTTPException(status_code=401, detail="Login fehlgeschlagen")
    if not hmac.compare_digest(_password_hash(payload.password, salt), pw_hash):
        failed_count = int(row.get("failed_login_count") or 0) + 1
        with _conn() as conn:
            with conn.cursor() as cur:
                if failed_count >= _LOGIN_MAX_FEHLVERSUCHE:
                    bis = jetzt + dt.timedelta(seconds=_LOGIN_SPERRE_SEKUNDEN)
                    cur.execute(
                        """
                        UPDATE users
                        SET failed_login_count = 0,
                            locked_until = %s
                        WHERE id = %s
                        """,
                        (bis, int(row["id"])),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE users
                        SET failed_login_count = %s
                        WHERE id = %s
                        """,
                        (failed_count, int(row["id"])),
                    )
        _audit_log(
            event="auth.login",
            ok=False,
            user_id=int(row["id"]),
            email=email,
            detail="falsches_passwort",
        )
        raise HTTPException(status_code=401, detail="Login fehlgeschlagen")
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET failed_login_count = 0,
                    locked_until = NULL
                WHERE id = %s
                """,
                (int(row["id"]),),
            )
    user = UserOut(
        id=int(row["id"]),
        name=str(row["name"]),
        email=str(row["email"]),
        role=str(row.get("role") or "user"),
    )
    token_version = int(row.get("token_version") or 0)
    access_token = _token_erzeugen(
        user_id=user.id,
        email=user.email,
        role=user.role,
        token_version=token_version,
        token_typ="access",
        ttl_sekunden=_ACCESS_TTL_SEKUNDEN,
    )
    refresh_token = _token_erzeugen(
        user_id=user.id,
        email=user.email,
        role=user.role,
        token_version=token_version,
        token_typ="refresh",
        ttl_sekunden=_REFRESH_TTL_SEKUNDEN,
    )
    _audit_log(
        event="auth.login",
        ok=True,
        user_id=user.id,
        email=user.email,
        detail=f"role={user.role}",
    )
    return AuthOut(access_token=access_token, refresh_token=refresh_token, user=user)


@app.post("/v1/auth/password-reset/request")
def password_reset_request(payload: PasswordResetRequestIn) -> PasswordResetRequestOut:
    email = payload.email.strip().lower()
    reset_token = secrets.token_urlsafe(24)
    reset_hash = _reset_token_hash(reset_token)
    expires_at = _utc_now() + dt.timedelta(seconds=_RESET_TOKEN_TTL_SEKUNDEN)
    with _conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id FROM users WHERE lower(email) = %s", (email,))
            row = cur.fetchone()
            if row is not None:
                cur.execute(
                    """
                    UPDATE users
                    SET reset_token_hash = %s,
                        reset_token_expires_at = %s
                    WHERE id = %s
                    """,
                    (reset_hash, expires_at, int(row["id"])),
                )
                _audit_log(
                    event="auth.password_reset.request",
                    ok=True,
                    user_id=int(row["id"]),
                    email=email,
                    detail="token_erstellt",
                )
            else:
                _audit_log(
                    event="auth.password_reset.request",
                    ok=True,
                    email=email,
                    detail="email_nicht_gefunden_neutral",
                )
    # Absichtlich keine Information, ob E-Mail existiert.
    preview = reset_token if _app_env() != "prod" else None
    return PasswordResetRequestOut(
        status="ok",
        detail="Falls der Account existiert, wurde ein Reset gestartet.",
        reset_token_preview=preview,
    )


@app.post("/v1/auth/password-reset/confirm")
def password_reset_confirm(payload: PasswordResetConfirmIn) -> dict[str, str]:
    email = payload.email.strip().lower()
    token_hash = _reset_token_hash(payload.reset_token.strip())
    jetzt = _utc_now()
    with _conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, reset_token_hash, reset_token_expires_at
                FROM users
                WHERE lower(email) = %s
                LIMIT 1
                """,
                (email,),
            )
            row = cur.fetchone()
            if row is None:
                _audit_log(
                    event="auth.password_reset.confirm",
                    ok=False,
                    email=email,
                    detail="user_unbekannt",
                )
                raise HTTPException(status_code=400, detail="Reset ungueltig")
            stored_hash = str(row.get("reset_token_hash") or "")
            expires_at = row.get("reset_token_expires_at")
            if not stored_hash or expires_at is None:
                _audit_log(
                    event="auth.password_reset.confirm",
                    ok=False,
                    user_id=int(row["id"]),
                    email=email,
                    detail="kein_reset_hinterlegt",
                )
                raise HTTPException(status_code=400, detail="Reset ungueltig")
            if isinstance(expires_at, dt.datetime):
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=dt.timezone.utc)
                if expires_at <= jetzt:
                    _audit_log(
                        event="auth.password_reset.confirm",
                        ok=False,
                        user_id=int(row["id"]),
                        email=email,
                        detail="reset_abgelaufen",
                    )
                    raise HTTPException(status_code=400, detail="Reset abgelaufen")
            if not hmac.compare_digest(stored_hash, token_hash):
                _audit_log(
                    event="auth.password_reset.confirm",
                    ok=False,
                    user_id=int(row["id"]),
                    email=email,
                    detail="token_mismatch",
                )
                raise HTTPException(status_code=400, detail="Reset ungueltig")
            salt_hex = secrets.token_hex(16)
            pw_hash = _password_hash(payload.new_password, salt_hex)
            cur.execute(
                """
                UPDATE users
                SET password_salt = %s,
                    password_hash = %s,
                    token_version = token_version + 1,
                    failed_login_count = 0,
                    locked_until = NULL,
                    reset_token_hash = NULL,
                    reset_token_expires_at = NULL
                WHERE id = %s
                """,
                (salt_hex, pw_hash, int(row["id"])),
            )
            _audit_log(
                event="auth.password_reset.confirm",
                ok=True,
                user_id=int(row["id"]),
                email=email,
                detail="passwort_aktualisiert",
            )
    return {"status": "ok", "detail": "Passwort aktualisiert"}


@app.post("/v1/auth/refresh")
def refresh(authorization: str | None = Header(default=None)) -> AuthOut:
    row = _auth_row_aus_header(authorization, erwarteter_typ="refresh")
    user = UserOut.model_validate(row)
    token_version = int(row.get("token_version") or 0)
    access_token = _token_erzeugen(
        user_id=user.id,
        email=user.email,
        role=user.role,
        token_version=token_version,
        token_typ="access",
        ttl_sekunden=_ACCESS_TTL_SEKUNDEN,
    )
    refresh_token = _token_erzeugen(
        user_id=user.id,
        email=user.email,
        role=user.role,
        token_version=token_version,
        token_typ="refresh",
        ttl_sekunden=_REFRESH_TTL_SEKUNDEN,
    )
    _audit_log(
        event="auth.refresh",
        ok=True,
        user_id=user.id,
        email=user.email,
        detail="token_erneuert",
    )
    return AuthOut(access_token=access_token, refresh_token=refresh_token, user=user)


@app.post("/v1/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict[str, str]:
    row = _auth_row_aus_header(authorization, erwarteter_typ="access")
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET token_version = token_version + 1 WHERE id = %s",
                (int(row["id"]),),
            )
    _audit_log(
        event="auth.logout",
        ok=True,
        user_id=int(row["id"]),
        email=str(row.get("email") or ""),
        detail="token_version_erhoeht",
    )
    return {"status": "ok", "detail": "abgemeldet"}


@app.get("/v1/users/me")
def me(authorization: str | None = Header(default=None)) -> UserOut:
    return _aktueller_user_aus_header(authorization)


@app.get("/v1/admin/users")
def admin_users_liste(authorization: str | None = Header(default=None)) -> list[UserOut]:
    admin = _admin_user_aus_header(authorization)
    with _conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, name, email, role
                FROM users
                ORDER BY id ASC
                LIMIT 500
                """
            )
            rows = cur.fetchall()
    _audit_log(
        event="admin.users.list",
        ok=True,
        user_id=admin.id,
        email=admin.email,
        detail=f"count={len(rows)}",
    )
    return [UserOut.model_validate(row) for row in rows]


@app.get(
    "/v1/admin/audit-logs",
    summary="Admin: Audit-Logs mit Filtern und Pagination",
    responses={
        200: {
            "description": "Gefilterte Audit-Eintraege",
            "headers": {
                "X-Total-Count": {
                    "description": "Gesamtanzahl zur aktuellen Filtermenge (ohne limit/offset).",
                    "schema": {"type": "integer"},
                },
                "Link": {
                    "description": 'Pagination-Links mit rel="next"/rel="prev" (wenn vorhanden).',
                    "schema": {"type": "string"},
                },
            },
        }
    },
)
def admin_audit_logs(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    limit: int = 100,
    offset: int = 0,
    event: str | None = None,
    ok: bool | None = None,
    since: dt.datetime | None = None,
    until: dt.datetime | None = None,
) -> list[AuditOut]:
    """Liefert Audit-Logs mit Filtern; setzt X-Total-Count und optional Link."""
    admin = _admin_user_aus_header(authorization)
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, min(offset, 50000))
    where_parts: list[str] = []
    params: list[object] = []
    if event is not None and event.strip():
        where_parts.append("event = %s")
        params.append(event.strip())
    if ok is not None:
        where_parts.append("ok = %s")
        params.append(ok)
    if since is not None:
        where_parts.append("created_at >= %s")
        params.append(since)
    if until is not None:
        where_parts.append("created_at <= %s")
        params.append(until)
    where_sql = ""
    if where_parts:
        where_sql = "WHERE " + " AND ".join(where_parts)
    total_count = 0
    with _conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) AS total_count
                FROM audit_log
                {where_sql}
                """,
                tuple(params),
            )
            row_count = cur.fetchone()
            if row_count is not None:
                total_count = int(row_count.get("total_count") or 0)
            cur.execute(
                f"""
                SELECT id, event, ok, user_id, email, detail, created_at
                FROM audit_log
                {where_sql}
                ORDER BY id DESC
                LIMIT %s
                OFFSET %s
                """,
                (*params, safe_limit, safe_offset),
            )
            rows = cur.fetchall()
    response.headers["X-Total-Count"] = str(total_count)
    query_basis: dict[str, str] = {}
    if event is not None and event.strip():
        query_basis["event"] = event.strip()
    if ok is not None:
        query_basis["ok"] = "true" if ok else "false"
    if since is not None:
        query_basis["since"] = since.isoformat()
    if until is not None:
        query_basis["until"] = until.isoformat()
    links: list[str] = []
    if safe_offset > 0:
        prev_offset = max(0, safe_offset - safe_limit)
        prev_url = request.url.include_query_params(
            limit=safe_limit,
            offset=prev_offset,
            **query_basis,
        )
        links.append(f'<{prev_url}>; rel="prev"')
    if safe_offset + safe_limit < total_count:
        next_offset = safe_offset + safe_limit
        next_url = request.url.include_query_params(
            limit=safe_limit,
            offset=next_offset,
            **query_basis,
        )
        links.append(f'<{next_url}>; rel="next"')
    if links:
        response.headers["Link"] = ", ".join(links)
    _audit_log(
        event="admin.audit_logs.list",
        ok=True,
        user_id=admin.id,
        email=admin.email,
        detail=(
            f"limit={safe_limit},offset={safe_offset},event={event or ''},"
            f"ok={ok},total={total_count}"
        ),
    )
    return [AuditOut.model_validate(row) for row in rows]


@app.get(
    "/v1/admin/logs",
    summary="Veraltet: Audit-Logs (Alias)",
    deprecated=True,
)
def admin_logs_alias(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    limit: int = 100,
    offset: int = 0,
    event: str | None = None,
    ok: bool | None = None,
    since: dt.datetime | None = None,
    until: dt.datetime | None = None,
) -> list[AuditOut]:
    """Altpfad: bitte /v1/admin/audit-logs verwenden."""
    return admin_audit_logs(
        request=request,
        response=response,
        authorization=authorization,
        limit=limit,
        offset=offset,
        event=event,
        ok=ok,
        since=since,
        until=until,
    )


@app.get("/v1/events")
def events_liste(authorization: str | None = Header(default=None)) -> list[EventOut]:
    user = _aktueller_user_aus_header(authorization)
    with _conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, user_id, titel, starts_at, ends_at, notiz
                FROM events
                WHERE user_id = %s
                ORDER BY starts_at ASC, id ASC
                LIMIT 400
                """,
                (user.id,),
            )
            rows = cur.fetchall()
    return [EventOut.model_validate(row) for row in rows]


@app.post("/v1/events", status_code=201)
def event_anlegen(
    payload: EventCreate,
    authorization: str | None = Header(default=None),
) -> EventOut:
    user = _aktueller_user_aus_header(authorization)
    with _conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO events(user_id, titel, starts_at, ends_at, notiz)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, user_id, titel, starts_at, ends_at, notiz
                """,
                (
                    user.id,
                    payload.titel.strip(),
                    payload.starts_at,
                    payload.ends_at,
                    payload.notiz.strip(),
                ),
            )
            row = cur.fetchone()
    assert row is not None
    _audit_log(
        event="events.create",
        ok=True,
        user_id=user.id,
        email=user.email,
        detail=f"event_id={int(row['id'])}",
    )
    return EventOut.model_validate(row)

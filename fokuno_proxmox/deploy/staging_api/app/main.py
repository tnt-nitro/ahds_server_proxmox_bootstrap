"""Staging-API mit Migrationen, Auth-Basis und Kalender-Endpunkten."""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import html
import json
import os
from pathlib import Path
import secrets
import time
from typing import Any

import psycopg
from fastapi import FastAPI, Form, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from psycopg import Error as PsycopgError
from psycopg.rows import dict_row

app = FastAPI(title="AhDs Staging API", version="0.3.2")
_API_MAJOR = "v1"
_API_RELEASE = app.version
_API_COMPAT_POLICY = (
    "Innerhalb einer Major-Version keine Breaking Changes ohne neuen Major-Pfad."
)
_CLIENT_MAJOR_HEADER = "x-client-api-major"
_SERVER_UI_VERSION = "ui-0.1.0"
_ADMIN_PANEL_USER = "Admin"
_ADMIN_PANEL_PASSWORD = "x"
_RUNTIME_ENV_PATH = Path(os.environ.get("AHDS_RUNTIME_ENV_FILE", "/opt/ahds-native/.env"))
_SERVER_PROJECT_START = dt.date(2026, 4, 4)
_SERVER_STATUS_PATH = Path(
    os.environ.get("AHDS_SERVER_STATUS_FILE", "/opt/ahds-native/data/server_status.json")
)
_UPDATE_STATUS_PATH = Path(
    os.environ.get("AHDS_UPDATE_STATUS_FILE", "/opt/ahds-native/data/update_status.json")
)
_UPDATE_REQUEST_PATH = Path(
    os.environ.get("AHDS_UPDATE_REQUEST_FILE", "/opt/ahds-native/data/update_request.json")
)
_SERVER_STARTED_AT = dt.datetime.now(dt.timezone.utc)
_SERVER_COUNTER: dict[str, int] = {"major": 0, "minor": 0, "patch": 0, "total": 0}
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


def _admin_panel_auth_pruefen(authorization: str | None) -> None:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Login erforderlich",
            headers={"WWW-Authenticate": 'Basic realm="AhDs Admin"'},
        )
    teile = authorization.split(" ", 1)
    if len(teile) != 2 or teile[0].lower() != "basic":
        raise HTTPException(
            status_code=401,
            detail="Basic Auth erforderlich",
            headers={"WWW-Authenticate": 'Basic realm="AhDs Admin"'},
        )
    try:
        dec = base64.b64decode(teile[1]).decode("utf-8")
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail="Ungültige Authentifizierung",
            headers={"WWW-Authenticate": 'Basic realm="AhDs Admin"'},
        ) from exc
    if ":" not in dec:
        raise HTTPException(
            status_code=401,
            detail="Ungültige Authentifizierung",
            headers={"WWW-Authenticate": 'Basic realm="AhDs Admin"'},
        )
    user, pw = dec.split(":", 1)
    if user != _ADMIN_PANEL_USER or pw != _ADMIN_PANEL_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Benutzer oder Passwort falsch",
            headers={"WWW-Authenticate": 'Basic realm="AhDs Admin"'},
        )


def _runtime_env_laden() -> dict[str, str]:
    daten: dict[str, str] = {}
    if not _RUNTIME_ENV_PATH.exists():
        return daten
    for zeile in _RUNTIME_ENV_PATH.read_text(encoding="utf-8").splitlines():
        roh = zeile.strip()
        if not roh or roh.startswith("#") or "=" not in roh:
            continue
        k, v = roh.split("=", 1)
        daten[k.strip()] = v.strip()
    return daten


def _runtime_env_schreiben(daten: dict[str, str]) -> None:
    keys = [
        "APP_ENV",
        "STAGING_DOMAIN",
        "TLS_EMAIL",
        "API_TOKEN_SECRET",
        "ADMIN_EMAIL",
        "LOGIN_MAX_FEHLVERSUCHE",
        "LOGIN_SPERRE_SEKUNDEN",
        "RESET_TOKEN_TTL_SEKUNDEN",
        "PGHOST",
        "PGPORT",
        "PGUSER",
        "PGPASSWORD",
        "PGDATABASE",
        "DUCKDNS_TOKEN",
    ]
    ausgabe: list[str] = []
    for key in keys:
        if key in daten:
            ausgabe.append(f"{key}={daten[key]}")
    _RUNTIME_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    _RUNTIME_ENV_PATH.write_text("\n".join(ausgabe) + "\n", encoding="utf-8")


def _semver_aufloesen(version: str) -> tuple[int, int, int]:
    teile = version.split(".")
    if len(teile) != 3:
        return (0, 0, 0)
    try:
        return (int(teile[0]), int(teile[1]), int(teile[2]))
    except ValueError:
        return (0, 0, 0)


def _server_status_laden() -> dict[str, dict[str, int]]:
    if not _SERVER_STATUS_PATH.exists():
        return {"by_version": {}}
    try:
        daten = json.loads(_SERVER_STATUS_PATH.read_text(encoding="utf-8"))
        if isinstance(daten, dict):
            by_version = daten.get("by_version", {})
            if isinstance(by_version, dict):
                return {"by_version": {str(k): int(v) for k, v in by_version.items()}}
    except Exception:
        pass
    return {"by_version": {}}


def _server_status_schreiben(daten: dict[str, dict[str, int]]) -> None:
    _SERVER_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SERVER_STATUS_PATH.write_text(
        json.dumps(daten, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def _server_counter_aktualisieren() -> None:
    daten = _server_status_laden()
    by_version = daten.get("by_version", {})
    version_count = int(by_version.get(_API_RELEASE, 0)) + 1
    by_version[_API_RELEASE] = version_count
    daten["by_version"] = by_version
    _server_status_schreiben(daten)

    major, minor, _patch = _semver_aufloesen(_API_RELEASE)
    major_count = 0
    minor_count = 0
    total_count = 0
    for version_key, count in by_version.items():
        count_int = int(count)
        total_count += count_int
        v_major, v_minor, _ = _semver_aufloesen(str(version_key))
        if v_major == major:
            major_count += count_int
        if v_major == major and v_minor == minor:
            minor_count += count_int

    _SERVER_COUNTER["major"] = major_count
    _SERVER_COUNTER["minor"] = minor_count
    _SERVER_COUNTER["patch"] = version_count
    _SERVER_COUNTER["total"] = total_count


def _update_status_laden() -> dict[str, Any]:
    if not _UPDATE_STATUS_PATH.exists():
        return {
            "status": "unknown",
            "detail": "Noch kein Updater-Lauf protokolliert.",
        }
    try:
        daten = json.loads(_UPDATE_STATUS_PATH.read_text(encoding="utf-8"))
        if isinstance(daten, dict):
            return daten
    except Exception:
        pass
    return {"status": "error", "detail": "Update-Statusdatei ist ungültig."}


def _update_request_schreiben() -> None:
    _UPDATE_REQUEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "requested_at": _utc_now().isoformat(),
        "source": "browser",
        "note": "Update manuell angefordert",
    }
    _UPDATE_REQUEST_PATH.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def _admin_form_html(
    *,
    env_daten: dict[str, str],
    meldung: str = "",
    fehler: str = "",
) -> str:
    def esc(key: str, fallback: str = "") -> str:
        return html.escape(env_daten.get(key, fallback), quote=True)

    meldung_html = (
        f'<div class="ok">{html.escape(meldung)}</div>' if meldung else ""
    )
    fehler_html = (
        f'<div class="err">{html.escape(fehler)}</div>' if fehler else ""
    )
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AhDs Admin</title>
  <style>
    body {{ font-family: "Segoe UI", system-ui, sans-serif; background: #f6f0e6; color: #2f2b24; margin: 0; }}
    .wrap {{ max-width: 760px; margin: 24px auto; padding: 0 16px; }}
    .card {{ background: #fffef8; border: 1px solid #e7dcc7; border-radius: 12px; padding: 16px; }}
    h1 {{ margin: 0 0 8px; font-size: 1.25rem; }}
    p {{ margin: 4px 0 12px; color: #6f6b64; }}
    label {{ display: block; margin: 10px 0 4px; font-weight: 600; }}
    input {{ width: 100%; box-sizing: border-box; padding: 8px; border: 1px solid #d9ccb5; border-radius: 8px; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .ok {{ margin: 10px 0; padding: 10px; border-radius: 8px; background: #edf8ef; border: 1px solid #9bcaac; color: #1d6a36; }}
    .err {{ margin: 10px 0; padding: 10px; border-radius: 8px; background: #fff1f1; border: 1px solid #e2abab; color: #8b2323; }}
    button {{ margin-top: 14px; background: #9f8a60; color: #fff; border: 0; border-radius: 8px; padding: 9px 14px; cursor: pointer; }}
    .hint {{ margin-top: 12px; color: #6f6b64; font-size: 0.92rem; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>AhDs Admin – Serverwerte</h1>
      <p>Hier kannst du die Installationswerte zentral pflegen. Login aktuell: Admin / x (später absichern).</p>
      {meldung_html}
      {fehler_html}
      <form method="post" action="/admin/save">
        <div class="row">
          <div>
            <label>STAGING_DOMAIN</label>
            <input name="staging_domain" value="{esc("STAGING_DOMAIN")}" />
          </div>
          <div>
            <label>TLS_EMAIL</label>
            <input name="tls_email" value="{esc("TLS_EMAIL")}" />
          </div>
        </div>
        <div class="row">
          <div>
            <label>ADMIN_EMAIL</label>
            <input name="admin_email" value="{esc("ADMIN_EMAIL")}" />
          </div>
          <div>
            <label>DUCKDNS_TOKEN (optional)</label>
            <input name="duckdns_token" value="{esc("DUCKDNS_TOKEN")}" />
          </div>
        </div>
        <label>POSTGRES_PASSWORD (leer = unverändert)</label>
        <input type="password" name="postgres_password" value="" />
        <label>API_TOKEN_SECRET (leer = unverändert)</label>
        <input type="password" name="api_token_secret" value="" />
        <div class="row">
          <div>
            <label>LOGIN_MAX_FEHLVERSUCHE</label>
            <input name="login_max" value="{esc("LOGIN_MAX_FEHLVERSUCHE", "5")}" />
          </div>
          <div>
            <label>LOGIN_SPERRE_SEKUNDEN</label>
            <input name="login_lock" value="{esc("LOGIN_SPERRE_SEKUNDEN", "900")}" />
          </div>
        </div>
        <label>RESET_TOKEN_TTL_SEKUNDEN</label>
        <input name="reset_ttl" value="{esc("RESET_TOKEN_TTL_SEKUNDEN", "1800")}" />
        <button type="submit">Werte speichern</button>
      </form>
      <div class="hint">
        Hinweis: Änderungen an Secrets/DB-Parametern werden erst nach Service-Neustart wirksam
        (<code>systemctl restart ahds-staging-api</code>).
      </div>
    </div>
  </div>
</body>
</html>"""


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
    _server_counter_aktualisieren()


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
def root() -> HTMLResponse:
    env = _app_env()
    env_titel = {
        "dev": "AhDs Development Server",
        "staging": "AhDs Staging Server",
        "prod": "AhDs Production Server",
    }.get(env, "Server")
    env_build = {
        "dev": "Development Build",
        "staging": "Staging Build",
        "prod": "Production Build",
    }.get(env, "Unknown Build")
    major, minor, patch = _semver_aufloesen(_API_RELEASE)
    invocation = _utc_now().strftime("%Y-%m-%d %H:%M:%S")
    started = _SERVER_STARTED_AT.strftime("%Y-%m-%d %H:%M:%S")
    dev_days = (dt.date.today() - _SERVER_PROJECT_START).days
    title_line = (
        f"Working Title AhDs Staging Server | {env_build} | "
        f"v{_API_RELEASE} | User: Gast | Opened: {invocation}"
    )
    page_html = f"""<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{html.escape(title_line)}</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f5f0e6;
        --card: #fffef8;
        --text: #35312b;
        --muted: #6f6b64;
        --accent: #9f8a60;
        --danger: #b93f3f;
      }}
      body {{
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: "Segoe UI", system-ui, sans-serif;
      }}
      .wrap {{
        max-width: 980px;
        margin: 28px auto;
        padding: 0 16px;
      }}
      .card {{
        background: var(--card);
        border: 1px solid #e5dccb;
        border-radius: 14px;
        padding: 18px 18px 16px;
        box-shadow: 0 4px 14px rgba(25, 18, 8, 0.05);
      }}
      h1 {{
        margin: 0 0 8px;
        font-size: 1.35rem;
      }}
      .muted {{ color: var(--muted); }}
      .titlebar {{
        font-size: 0.9rem;
        color: #5c584f;
        margin-bottom: 10px;
      }}
      .pill {{
        display: inline-block;
        margin: 8px 8px 8px 0;
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 0.8rem;
        border: 1px solid #d8ccb8;
      }}
      .ok {{ color: #1f6b37; border-color: #9ed0ae; background: #edf8f0; }}
      .warn {{ color: var(--danger); border-color: #e4aaaa; background: #fff2f2; }}
      .grid {{
        margin-top: 14px;
        display: grid;
        gap: 10px;
        grid-template-columns: 1.2fr 1fr;
      }}
      .box {{
        border: 1px solid #eadfce;
        border-radius: 10px;
        padding: 10px 11px;
        background: #fff;
      }}
      .box h2 {{
        font-size: 0.96rem;
        margin: 0 0 8px;
      }}
      .loginbox input {{
        width: 100%;
        box-sizing: border-box;
        padding: 8px;
        border: 1px solid #d9ccb5;
        border-radius: 8px;
        margin: 4px 0 10px;
        background: #fff;
      }}
      .btn {{
        display: inline-block;
        border: 0;
        border-radius: 8px;
        background: #9f8a60;
        color: #fff;
        padding: 8px 12px;
        cursor: pointer;
      }}
      .btn.secondary {{
        background: #6f6b64;
        margin-left: 8px;
      }}
      .btn.update {{
        background: #3f6e9d;
      }}
      .smalllink {{
        margin: 6px 0 12px;
        font-size: 0.92rem;
      }}
      a {{ color: var(--accent); text-decoration: none; }}
      a:hover {{ text-decoration: underline; }}
      code {{
        font-family: Consolas, "Courier New", monospace;
        background: #f9f5ee;
        border-radius: 6px;
        padding: 2px 5px;
      }}
      ul {{
        margin: 0;
        padding-left: 18px;
      }}
      li {{ margin: 4px 0; }}
      .status-list {{
        white-space: pre-line;
        line-height: 1.45;
      }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        <div class="titlebar">{html.escape(title_line)}</div>
        <h1>Bei AhDs Staging Server anmelden</h1>
        <div>
          <span class="pill ok">Server erreichbar</span>
          <span class="pill">APP_ENV: {env}</span>
          <span class="pill">API: {_API_MAJOR} / {_API_RELEASE}</span>
          <span class="pill">UI-Version: {_SERVER_UI_VERSION}</span>
          <button class="btn secondary" type="button" onclick="window.location.reload();">Aktualisieren</button>
          <button class="btn update" type="button" id="btn-update-check">Update prüfen</button>
          <button class="btn update" type="button" id="btn-update-install">Update installieren</button>
        </div>
        <div id="update-result" class="smalllink"></div>

        <div class="grid">
          <section class="box loginbox">
            <h2>Login</h2>
            <form id="login-form">
              <label>Benutzer:</label>
              <input id="login-email" name="email" type="text" placeholder="E-Mail / Benutzer" />
              <label>Passwort:</label>
              <input id="login-password" name="password" type="password" placeholder="Passwort" />
              <div class="smalllink"><a href="#" onclick="alert('Passwort vergessen ist noch nicht aktiv.'); return false;">Passwort vergessen</a> (soll noch nicht funktionieren)</div>
              <button class="btn" type="submit">Anmelden</button>
            </form>
            <div id="login-result" class="smalllink"></div>
            <div class="smalllink" style="margin-top:10px;">
              API-Doku: <a href="/docs">/docs</a>
            </div>
          </section>
          <section class="box">
            <h2>Statusliste (AhDs)</h2>
            <div class="status-list">Working Title: AhDs
Current version: v{_API_RELEASE}
Version created: {started}
Invocation date: {invocation}
Project start date: {_SERVER_PROJECT_START.isoformat()}
Development time in days: {dev_days}
Laufzeit-Umgebung: {env}

Resolved version (Semantic Versioning):
MAJOR: {major}
MINOR: {minor}
PATCH: {patch}

Counter (start invocations):
Major: {_SERVER_COUNTER["major"]}
Minor: {_SERVER_COUNTER["minor"]}
Patch: {_SERVER_COUNTER["patch"]}
Total: {_SERVER_COUNTER["total"]}</div>
            <div class="smalllink" style="margin-top:10px;">
              Schnellcheck: <a href="/health">/health</a> | <a href="/ready">/ready</a> | <a href="/v1/meta/version">/v1/meta/version</a>
            </div>
          </section>
        </div>
      </div>
    </div>
    <script>
      const form = document.getElementById("login-form");
      const result = document.getElementById("login-result");
      form?.addEventListener("submit", async (ev) => {{
        ev.preventDefault();
        const email = document.getElementById("login-email")?.value || "";
        const password = document.getElementById("login-password")?.value || "";
        result.textContent = "Anmeldung wird geprüft...";
        try {{
          const res = await fetch("/v1/auth/login", {{
            method: "POST",
            headers: {{
              "content-type": "application/json",
              "x-client-api-major": "{_API_MAJOR}"
            }},
            body: JSON.stringify({{ email, password }})
          }});
          const data = await res.json();
          if (!res.ok) {{
            result.textContent = "Login fehlgeschlagen: " + (data.detail || res.status);
            return;
          }}
          result.textContent = "Login erfolgreich. Token wurde erstellt.";
        }} catch (e) {{
          result.textContent = "Login fehlgeschlagen: " + String(e);
        }}
      }});

      const updateResult = document.getElementById("update-result");
      const btnCheck = document.getElementById("btn-update-check");
      const btnInstall = document.getElementById("btn-update-install");

      btnCheck?.addEventListener("click", async () => {{
        updateResult.textContent = "Prüfe Update-Status ...";
        try {{
          const res = await fetch("/update/status");
          const data = await res.json();
          updateResult.textContent =
            "Update-Status: " + (data.status || "unknown") +
            " | Letzte Prüfung: " + (data.checked_at || "-") +
            " | Detail: " + (data.detail || "-");
        }} catch (e) {{
          updateResult.textContent = "Update-Prüfung fehlgeschlagen: " + String(e);
        }}
      }});

      btnInstall?.addEventListener("click", async () => {{
        updateResult.textContent = "Update-Anforderung wird gespeichert ...";
        try {{
          const res = await fetch("/update/request", {{ method: "POST" }});
          const data = await res.json();
          if (!res.ok) {{
            updateResult.textContent = "Update-Anforderung fehlgeschlagen: " + (data.detail || res.status);
            return;
          }}
          updateResult.textContent = data.detail || "Update angefordert.";
        }} catch (e) {{
          updateResult.textContent = "Update-Anforderung fehlgeschlagen: " + String(e);
        }}
      }});
    </script>
  </body>
</html>
"""
    return HTMLResponse(content=page_html)


@app.get("/admin")
def admin_panel(authorization: str | None = Header(default=None)) -> HTMLResponse:
    _admin_panel_auth_pruefen(authorization)
    env_daten = _runtime_env_laden()
    return HTMLResponse(content=_admin_form_html(env_daten=env_daten))


@app.post("/admin/save")
def admin_panel_save(
    authorization: str | None = Header(default=None),
    staging_domain: str = Form(default=""),
    tls_email: str = Form(default=""),
    admin_email: str = Form(default=""),
    duckdns_token: str = Form(default=""),
    postgres_password: str = Form(default=""),
    api_token_secret: str = Form(default=""),
    login_max: str = Form(default="5"),
    login_lock: str = Form(default="900"),
    reset_ttl: str = Form(default="1800"),
) -> HTMLResponse:
    _admin_panel_auth_pruefen(authorization)
    env_daten = _runtime_env_laden()
    try:
        if not staging_domain.strip():
            raise ValueError("STAGING_DOMAIN darf nicht leer sein.")
        if not tls_email.strip():
            raise ValueError("TLS_EMAIL darf nicht leer sein.")
        if not admin_email.strip():
            raise ValueError("ADMIN_EMAIL darf nicht leer sein.")
        env_daten["STAGING_DOMAIN"] = staging_domain.strip()
        env_daten["TLS_EMAIL"] = tls_email.strip()
        env_daten["ADMIN_EMAIL"] = admin_email.strip().lower()
        env_daten["DUCKDNS_TOKEN"] = duckdns_token.strip()
        env_daten["LOGIN_MAX_FEHLVERSUCHE"] = str(int(login_max))
        env_daten["LOGIN_SPERRE_SEKUNDEN"] = str(int(login_lock))
        env_daten["RESET_TOKEN_TTL_SEKUNDEN"] = str(int(reset_ttl))
        if postgres_password.strip():
            env_daten["PGPASSWORD"] = postgres_password.strip()
        if api_token_secret.strip():
            env_daten["API_TOKEN_SECRET"] = api_token_secret.strip()
        if "APP_ENV" not in env_daten:
            env_daten["APP_ENV"] = _app_env()
        if "PGHOST" not in env_daten:
            env_daten["PGHOST"] = os.environ.get("PGHOST", "127.0.0.1")
        if "PGPORT" not in env_daten:
            env_daten["PGPORT"] = os.environ.get("PGPORT", "5432")
        if "PGUSER" not in env_daten:
            env_daten["PGUSER"] = os.environ.get("PGUSER", "ahds")
        if "PGDATABASE" not in env_daten:
            env_daten["PGDATABASE"] = os.environ.get("PGDATABASE", "ahds_staging")
        _runtime_env_schreiben(env_daten)
    except Exception as exc:
        return HTMLResponse(
            content=_admin_form_html(
                env_daten=env_daten,
                fehler=f"Speichern fehlgeschlagen: {exc}",
            ),
            status_code=400,
        )

    return HTMLResponse(
        content=_admin_form_html(
            env_daten=env_daten,
            meldung="Gespeichert. Für volle Wirkung bei Secrets/DB: Service neu starten.",
        )
    )


@app.get("/update/status")
def update_status() -> dict[str, Any]:
    return _update_status_laden()


@app.post("/update/request")
def update_request() -> dict[str, str]:
    _update_request_schreiben()
    return {
        "status": "ok",
        "detail": (
            "Update wurde angefordert. Auf dem Proxmox-Host startet der Watcher-Timer "
            "(ahds-native-update-on-request, siehe README) in der Regel innerhalb von etwa einer Minute "
            "das Einspielen; ohne diesen Timer bitte auf dem Host manuell native_update_ct.sh ausführen."
        ),
    }


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

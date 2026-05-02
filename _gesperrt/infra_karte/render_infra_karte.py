#!/usr/bin/env python3
"""
Liest `_gesperrt/infra_karte/daten.json` und erzeugt:
- `infra_karte.html`
- `push_hilfe.html` (Text aus `push_hilfe_inhalt.txt`)
- `wireguard_setup.html` (Text aus `wireguard_setup_inhalt.txt`)

Vorgehen: `daten.template.json` nach `daten.json` kopieren und befüllen.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
DATEI_DATEN = DIR / "daten.json"
AUSGABE = DIR / "infra_karte.html"
DATEI_PUSH_INHALT = DIR / "push_hilfe_inhalt.txt"
AUSGABE_PUSH = DIR / "push_hilfe.html"
DATEI_SSH_INHALT = DIR / "ssh_setup_inhalt.txt"
AUSGABE_SSH = DIR / "ssh_setup.html"
DATEI_NPM_INHALT = DIR / "npm_setup_inhalt.txt"
AUSGABE_NPM = DIR / "npm_setup.html"
DATEI_TELEGRAM_INHALT = DIR / "telegram_setup_inhalt.txt"
AUSGABE_TELEGRAM = DIR / "telegram_setup.html"
AUSGABE_TLS_WEGE = DIR / "tls_wege.html"
DATEI_WG_INHALT = DIR / "wireguard_setup_inhalt.txt"
AUSGABE_WG = DIR / "wireguard_setup.html"

SHARED_CSS = """
    body { font-family: system-ui, sans-serif; margin: 0; background: #f4f4f2; color: #1a1a18; }
    .wrap { max-width: 52rem; margin: 0 auto; padding: 1.25rem; }
    h1 { font-size: 1.35rem; }
    .card { background: #fff; border-radius: 10px; padding: 1rem 1.1rem; margin-bottom: 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,.08); }
    .warn { background: #fff8e6; padding: .6rem .75rem; border-radius: 6px; }
    .muted { color: #555; font-size: .92rem; }
    table { width: 100%; border-collapse: collapse; font-size: .9rem; }
    th, td { border: 1px solid #ddd; padding: .35rem .5rem; text-align: left; }
    th { background: #eee; }
    .ct { border: 1px dashed #bbb; padding: .75rem; margin: .5rem 0; border-radius: 8px; }
    dl { display: grid; grid-template-columns: 8rem 1fr; gap: .25rem .5rem; margin: .5rem 0; }
    dt { font-weight: 600; }
    pre, .hilfe-pre { overflow: auto; background: #f0f0ed; padding: .75rem; border-radius: 6px; font-size: .85rem;
            white-space: pre-wrap; font-family: ui-monospace, Consolas, monospace; }
    code { font-size: 0.9em; }
    a { color: #0b5cad; }
"""


def _attr(s: str) -> str:
    return html.escape(s, quote=True)


def _mermaid_fluss(d: dict) -> str:
    """Einfaches Übersichtsdiagramm: Workstation → Fritz → Internet → GitHub; Server pull."""
    git = d.get("datenfluss_git") or {}
    status = str(git.get("status") or "?").replace("\n", " ").replace("\r", "")[:80]
    lines = [
        "flowchart LR",
        "  subgraph lan[\"Heimnetz\"]",
        "    WS[\"Workstation\\n(Cursor / Dev)\"]",
        "    FB[\"FritzBox\"]",
        "    HM[\"Homeserver / Proxmox\"]",
        "    NPM[\"Nginx Proxy Manager\\n(native, nicht CT)\"]",
        "  end",
        "  subgraph wan[\"Internet\"]",
        "    GH[\"GitHub\"]",
        "  end",
        "  subgraph boot[\"Öffentlicher Bootstrap\"]",
        "    RAW[\"raw.githubusercontent.com\\ninstall-ahds-ct.sh\"]",
        "  end",
        "  WS -->|git push| FB",
        "  FB --> GH",
        "  GH -.->|curl als root| RAW",
        "  RAW -->|klont privat| HM",
        "  GH -->|git pull / deploy| HM",
        "  WS -.->|optional: LAN-Admin| HM",
        "  NPM -.->|Reverse Proxy| HM",
        f"  %% Datenfluss-Status (manuell): {status}",
    ]
    return "\n".join(lines)


def _section(title: str, body_html: str) -> str:
    return f'<section class="card"><h2>{html.escape(title)}</h2>{body_html}</section>'


def _render_zugangsdaten_section(d: dict) -> str:
    """Zeigt nur Namen / Status — Klartext-Token niemals im HTML."""
    zu = d.get("zugangsdaten") or {}
    fname = str(zu.get("speicher_datei") or "geheimnisse.json").strip()
    vorlage = str(zu.get("vorlage_datei") or "geheimnisse.template.json").strip()
    pyhilfe = str(zu.get("hilfe_skript") or "geheimnisse_eintragen.py").strip()
    pfad = DIR / fname

    kopf = (
        f"<p>{html.escape(str(zu.get('hinweis_karte','')))}</p>"
        f"<p class=\"muted\">{html.escape(str(zu.get('wo_verwendet_github_pat_kurz','')))}</p>"
        "<p><strong>Speicherung:</strong> "
        f"<code>{html.escape(fname)}</code> (gleicher Ordner wie diese Karte). "
        "Anlegen: <code>"
        + html.escape(vorlage)
        + "</code> kopieren oder <code>"
        + html.escape(pyhilfe)
        + "</code> nutzen.</p>"
        '<p class="warn">Aus Sicherheitsgründen steht der Token hier nicht '
        "und auch nicht in daten.json — nur in <code>"
        + html.escape(fname)
        + "</code>.</p>"
    )

    if not pfad.is_file():
        return _section(
            "Zugangsdaten (Bezeichnung + Token, nur lokal)",
            kopf + "<p>Noch keine Datei — Vorlage kopieren oder Hilfeskript ausführen.</p>",
        )

    try:
        gj = json.loads(pfad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return _section(
            "Zugangsdaten (Bezeichnung + Token, nur lokal)",
            kopf + f"<p class=\"warn\">Konnte nicht lesen: {html.escape(str(exc))}</p>",
        )

    wo_extra = gj.get("_wo_braucht_man_den_token") if isinstance(gj, dict) else ""
    eintraege = gj.get("eintraege") if isinstance(gj, dict) else None
    if not isinstance(eintraege, list):
        eintraege = []

    zusatz = ""
    if wo_extra:
        zusatz += f"<p class=\"muted\">{html.escape(str(wo_extra))}</p>"

    rows = []
    for ein in eintraege:
        if not isinstance(ein, dict):
            continue
        bez = html.escape(str(ein.get("bezeichnung") or "(ohne Name)"))
        tok = str(ein.get("token") or "")
        wo = html.escape(str(ein.get("wo_verwendet") or "—"))
        if tok.strip():
            status_tok = "Token hinterlegt (" + str(len(tok)) + " Zeichen)"
        else:
            status_tok = "Token-Feld leer"
        rows.append(
            "<tr>"
            f"<td>{bez}</td>"
            f"<td>{html.escape(status_tok)}</td>"
            f"<td>{wo}</td>"
            "</tr>"
        )

    tab = (
        "<table><thead><tr>"
        "<th>Bezeichnung</th><th>Token</th><th>Verwendung</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )

    if not rows:
        tab = "<p class=\"muted\">Noch keine Einträge in <code>eintraege</code>.</p>"

    return _section("Zugangsdaten (Bezeichnung + Token, nur lokal)", kopf + zusatz + tab)


def _render_push_html(
    inhalt_roh: str,
    titel: str,
    *,
    linkify_urls: list[str] | None = None,
    source_filename: str = "push_hilfe_inhalt.txt",
) -> str:
    nav = '<p><a href="infra_karte.html">← Zurück zur Infra-Karte</a></p>'
    meta = (
        f'<p class="muted">Quelle zum Bearbeiten: <code>{html.escape(source_filename)}</code> '
        "(gleicher Ordner). Danach <code>render_infra_karte.bat</code> ausführen.</p>"
    )
    esc = html.escape(inhalt_roh)
    if linkify_urls:
        # Zwei-Phasen-Ersatz mit Platzhaltern:
        # 1) URLs im escaped Text markieren
        # 2) Platzhalter in Link-HTML verwandeln
        # So vermeiden wir verschachtelte Ersetzungen.
        url_items = [str(x).strip() for x in linkify_urls if str(x).strip()]
        url_items = sorted(url_items, key=len, reverse=True)
        placeholders: list[tuple[str, str]] = []
        for idx, u in enumerate(url_items):
            token = f"__URL_PLACEHOLDER_{idx}__"
            esc = esc.replace(u, token)
            placeholders.append((token, u))
        for token, u in placeholders:
            esc = esc.replace(
                token,
                f'<a href="{html.escape(u, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(u)}</a>',
            )
    body = f'<pre class="hilfe-pre">{esc}</pre>'
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(titel)}</title>
  <style>{SHARED_CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>{html.escape(titel)}</h1>
  {nav}
  {meta}
  <section class="card">
    {body}
  </section>
</div>
</body>
</html>"""


def _render_telegram_setup_html(source_filename: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Telegram am Handy: Healthcheck-Fehlermeldungen einrichten</title>
  <style>
    {SHARED_CSS}
    .ok {{ background: #eaf8ef; padding: .6rem .75rem; border-radius: 6px; }}
    .step {{ background: #eef5ff; padding: .6rem .75rem; border-radius: 6px; }}
  </style>
</head>
<body>
<div class="wrap">
  <h1>Telegram am Handy: Healthcheck-Fehlermeldungen einrichten</h1>
  <p><a href="infra_karte.html">← Zurück zur Infra-Karte</a></p>
  <p class="muted">Quelle zum Bearbeiten: <code>{html.escape(source_filename)}</code> (gleicher Ordner). Danach <code>render_infra_karte.bat</code> ausführen.</p>

  <section class="card">
    <h2>Ziel</h2>
    <p>Wenn der Healthcheck auf dem Proxmox-Host einen Fehler erkennt, soll sofort eine Nachricht auf dem Handy ankommen.</p>
    <p class="warn"><strong>Wichtig:</strong> Bot-Token ist ein Geheimnis. Nur lokal speichern, niemals in öffentliche Repositories committen.</p>
  </section>

  <section class="card">
    <h2>Schritt 1: Bot in Telegram erstellen</h2>
    <ol>
      <li>Telegram öffnen und <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer">BotFather</a> starten.</li>
      <li><code>/newbot</code> ausführen und Bot erstellen.</li>
      <li>Den Bot-Token kopieren (Format ähnlich <code>123456789:AA...</code>).</li>
    </ol>
    <p class="step"><strong>Im Programm jetzt eintragen:</strong> <code>geheimnisse_eintragen.py</code> öffnen → Bereich <strong>Telegram Healthcheck (API-Links)</strong> → Feld <strong>Bot-Token</strong>.</p>
  </section>

  <section class="card">
    <h2>Schritt 2: Bot-Token prüfen</h2>
    <p>Im Programm auf <strong>getMe-URL kopieren</strong> klicken, URL im Browser öffnen.</p>
    <p class="ok"><strong>Erwartung:</strong> JSON mit <code>"ok": true</code> und Bot-Infos.</p>
  </section>

  <section class="card">
    <h2>Schritt 3: Chat-ID ermitteln</h2>
    <ol>
      <li>Im Telegram-Chat mit deinem Bot einmal auf <strong>Start</strong> klicken oder eine Nachricht senden.</li>
      <li>Im Programm auf <strong>getUpdates (curl) kopieren</strong> klicken und den Befehl in der Proxmox-Shell ausführen.</li>
      <li>In der Antwort unter <code>chat</code> → <code>id</code> die Chat-ID übernehmen.</li>
    </ol>
    <p class="step"><strong>Im Programm jetzt eintragen:</strong> Feld <strong>Chat-ID</strong>, danach <strong>Telegram-Daten speichern</strong>.</p>
    <p class="ok"><strong>Erwartung:</strong> In <code>result</code> steht mindestens ein Eintrag (nicht mehr leer).</p>
  </section>

  <section class="card">
    <h2>Schritt 4: Testnachricht ans Handy</h2>
    <p>Im Programm auf <strong>sendMessage Test-URL kopieren</strong> klicken und die URL im Browser öffnen.</p>
    <p class="ok"><strong>Erwartung:</strong> Auf dem Handy kommt eine Nachricht (z. B. „Test“) an.</p>
  </section>

  <section class="card">
    <h2>Schritt 5: Werte für den Server übernehmen</h2>
    <p>Im Programm auf <strong>Zwei Zeilen für /etc/default kopieren</strong> klicken und in <code>/etc/default/ahds-healthcheck</code> einfügen.</p>
    <pre>HEALTHCHECK_TELEGRAM_BOT_TOKEN=&lt;DEIN_BOT_TOKEN&gt;
HEALTHCHECK_TELEGRAM_CHAT_ID=&lt;DEINE_CHAT_ID&gt;</pre>
    <p>Danach testen:</p>
    <pre>systemctl start ahds-healthcheck.service
systemctl status ahds-healthcheck.service --no-pager</pre>
  </section>

  <section class="card">
    <h2>Optional: Löschen im Programm</h2>
    <p>Falls du neu starten willst: im Bereich Telegram auf <strong>Telegram-Daten löschen</strong> klicken.</p>
    <p class="warn">Es erscheint ein Nachfragefenster: <strong>„Telegram-Daten wirklich löschen?“</strong> mit <strong>Ja/Nein</strong>.</p>
  </section>
</div>
</body>
</html>"""


def _render_html(d: dict) -> str:
    meta = d.get("meta") or {}
    titel = meta.get("titel") or "Infra-Karte"
    stand = meta.get("stand_datum") or ""
    ba = d.get("bootstrap_agenten") or {}
    push_html_name = str(ba.get("push_hilfe_html_seite") or "push_hilfe.html").strip() or "push_hilfe.html"
    push_link = f'<p><strong>Git push / Bootstrap veröffentlichen:</strong> '
    push_link += f'<a href="{_attr(push_html_name)}">eigene Hilfeseite öffnen</a>'
    push_link += (
        f' <span class="muted">(Quelltext: <code>{html.escape(str(ba.get("push_hilfe_inhalt_datei", "push_hilfe_inhalt.txt")))}</code>)</span></p>'
    )

    parts: list[str] = []
    if stand:
        parts.append(f"<p><strong>Stand:</strong> {html.escape(str(stand))}</p>")

    parts.append(_render_zugangsdaten_section(d))

    dg = d.get("datenfluss_git") or {}
    schritte = dg.get("schritte") or []
    schritte_html = (
        "<ol>" + "".join(f"<li>{html.escape(str(s))}</li>" for s in schritte) + "</ol>"
        if schritte
        else ""
    )
    parts.append(
        _section(
            "Datenfluss zu GitHub",
            f"<p>{html.escape(str(dg.get('beschreibung','')))}</p>"
            f"{schritte_html}"
            f"<p><em>Status (manuell):</em> {html.escape(str(dg.get('status','')))}</p>",
        )
    )

    gh = d.get("github") or {}
    repos = gh.get("repos") or []
    repo_rows = []
    for r in repos:
        name = html.escape(str(r.get("name", "")))
        sicht = html.escape(str(r.get("sichtbarkeit", "")))
        zweck = html.escape(str(r.get("zweck", "")))
        web = str(r.get("repo_web_url") or "").strip()
        raw_u = str(r.get("raw_install_script_url") or "").strip()
        links = []
        if web:
            links.append(
                f'<a href="{_attr(web)}" target="_blank" rel="noopener noreferrer">Repo</a>'
            )
        if raw_u:
            links.append(
                f'<a href="{_attr(raw_u)}" target="_blank" rel="noopener noreferrer">'
                f"Raw install-ahds-ct.sh</a>"
            )
        link_cell = " · ".join(links) if links else "—"
        repo_rows.append(
            f"<tr><td>{name}</td><td>{sicht}</td><td>{zweck}</td><td>{link_cell}</td></tr>"
        )
    parts.append(
        _section(
            "GitHub-Repositories",
            f"<p>{html.escape(str(gh.get('hinweis_minimal_oeffentlich','')))}</p>"
            "<table><thead><tr><th>Repo</th><th>Sichtbarkeit</th><th>Zweck</th><th>Links</th></tr></thead><tbody>"
            + "".join(repo_rows)
            + "</tbody></table>",
        )
    )

    bo = d.get("bootstrap_oeffentlich") or {}
    one_liner = str(bo.get("one_liner_auf_proxmox_als_root") or "")
    parts.append(
        _section(
            "Öffentliches Bootstrap (ahds_server_proxmox_bootstrap)",
            f"<p class=\"warn\">{html.escape(str(bo.get('hinweis_readme_github','')))}</p>"
            f"<p><strong>Lokaler Ordner im Monorepo:</strong> "
            f"<code>{html.escape(str(bo.get('lokaler_ordner_im_monorepo','')))}</code></p>"
            f"<p><strong>Remote-Name:</strong> {html.escape(str(bo.get('repo_name_remote','')))}</p>"
            "<h3>One-Liner auf Proxmox (root)</h3>"
            f"<pre>{html.escape(one_liner)}</pre>",
        )
    )

    bp = d.get("bootstrap_privat") or {}
    parts.append(
        _section(
            "Privates Monorepo (nach Bootstrap auf dem Server)",
            f"<p><strong>Klon-Ziel:</strong> <code>{html.escape(str(bp.get('clone_ziel_pfad','')))}</code></p>"
            f"<p><strong>SSH-URL:</strong> <code>{html.escape(str(bp.get('privat_repo_ssh','')))}</code></p>"
            f"{('<p><strong>Bootstrap-Prompt (Default):</strong> Owner <code>' + html.escape(str(bp.get('runtime_prompt_git_owner_default',''))) + '</code>, Repo <code>' + html.escape(str(bp.get('runtime_prompt_private_repo_default',''))) + '</code></p>') if (bp.get('runtime_prompt_git_owner_default') or bp.get('runtime_prompt_private_repo_default')) else ''}"
            f"{('<p class=\"muted\">' + html.escape(str(bp.get('runtime_prompt_account_switch_hinweis',''))) + '</p>') if bp.get('runtime_prompt_account_switch_hinweis') else ''}"
            f"<p><strong>Installer (relativ):</strong> "
            f"<code>{html.escape(str(bp.get('installer_script_relativ','')))}</code></p>"
            f"<p>{html.escape(str(bp.get('deploy_key_hinweis','')))}</p>"
            f"<p><em>SSH vom Proxmox zum privaten Repo:</em> "
            f"{html.escape(str(bp.get('status_ssh_vom_proxmox','')))}</p>",
        )
    )

    rolle = ba.get("rolle") or []
    rolle_html = "<ul>" + "".join(f"<li>{html.escape(str(x))}</li>" for x in rolle) + "</ul>"
    da = ba.get("dateien_anpassen") or []
    rows_da = "".join(
        "<tr>"
        f"<td>{html.escape(str(x.get('datei','')))}</td>"
        f"<td>{html.escape(str(x.get('feld','')))}</td>"
        "</tr>"
        for x in da
    )
    nie = ba.get("nie") or []
    nie_html = "<ul>" + "".join(f"<li>{html.escape(str(x))}</li>" for x in nie) + "</ul>"
    parts.append(
        _section(
            "Cursor-Agenten: Bootstrap",
            "<h3>Rolle</h3>"
            f"{rolle_html}"
            "<h3>Dateien bei Änderungen</h3>"
            "<table><thead><tr><th>Datei</th><th>Felder / Inhalt</th></tr></thead>"
            f"<tbody>{rows_da}</tbody></table>"
            "<h3>Nicht öffentlich machen</h3>"
            f"{nie_html}"
            f"{push_link}"
            '<p class="muted">SSH-Setup (Deploy Key) als Unterseite: <a href="ssh_setup.html">ssh_setup.html</a></p>'
            f"<p class=\"muted\">{html.escape(str(ba.get('hinweis_agent_kann_nicht_automatisch_pushen','')))}</p>",
        )
    )

    bw = d.get("wege_zum_server") or {}
    pa = bw.get("pfad_a_lan_direkt") or {}
    pb = bw.get("pfad_b_ueber_internet") or {}
    parts.append(
        _section(
            "Zwei Wege zur Kommunikation (Workstation ↔ Server)",
            "<p>Zwei Karten auf dem Chart sind möglich – oder <strong>eine</strong> Workstation-Karte mit "
            "<strong>zwei beschrifteten Kanten</strong> (Pfad A / Pfad B).</p>"
            f"<h3>{html.escape(str(pa.get('kurzlabel','A')))}</h3>"
            f"<p>{html.escape(str(pa.get('beschreibung','')))}</p>"
            f"<p><em>Status:</em> {html.escape(str(pa.get('status','')))}</p>"
            "<ul>"
            + "".join(f"<li>{html.escape(str(u))}</li>" for u in (pa.get("beispiel_urls") or []))
            + "</ul>"
            f"<h3>{html.escape(str(pb.get('kurzlabel','B')))}</h3>"
            f"<p>{html.escape(str(pb.get('beschreibung','')))}</p>"
            f"<p><em>Status:</em> {html.escape(str(pb.get('status','')))}</p>"
            "<ul>"
            + "".join(f"<li>{html.escape(str(u))}</li>" for u in (pb.get("beispiel_urls") or []))
            + "</ul>",
        )
    )

    npm = d.get("nginx_proxy_manager") or {}
    npm_hinweis = npm.get("wichtig") or ""
    npm_html_name = str(npm.get("npm_setup_html_seite") or "npm_setup.html").strip() or "npm_setup.html"
    npm_inhalt_name = str(npm.get("npm_setup_inhalt_datei") or "npm_setup_inhalt.txt").strip() or "npm_setup_inhalt.txt"
    telegram_html_name = str(npm.get("telegram_setup_html_seite") or "telegram_setup.html").strip() or "telegram_setup.html"
    telegram_inhalt_name = str(npm.get("telegram_setup_inhalt_datei") or "telegram_setup_inhalt.txt").strip() or "telegram_setup_inhalt.txt"
    tls_wege_name = "tls_wege.html"
    parts.append(
        _section(
            "Nginx Proxy Manager",
            f"<p class=\"warn\">{html.escape(str(npm_hinweis))}</p>"
            f"<p><strong>Installation:</strong> {html.escape(str(npm.get('installation','')))}</p>"
            f"<p><strong>NPM-Setup Schritt-für-Schritt:</strong> "
            f"<a href=\"{_attr(npm_html_name)}\">{html.escape(npm_html_name)}</a> "
            f"<span class=\"muted\">(Quelle: <code>{html.escape(npm_inhalt_name)}</code>)</span></p>"
            f"<p><strong>Bild-Erklärung (Technikweg):</strong> "
            f"<a href=\"{_attr(tls_wege_name)}\">{html.escape(tls_wege_name)}</a> "
            "<span class=\"muted\">(mit Diagramm für TLS im NPM vs. TLS im Container)</span></p>"
            f"<p><strong>Healthcheck-Alarm auf Handy (Telegram):</strong> "
            f"<a href=\"{_attr(telegram_html_name)}\">{html.escape(telegram_html_name)}</a> "
            f"<span class=\"muted\">(Quelle: <code>{html.escape(telegram_inhalt_name)}</code>)</span></p>",
        )
    )

    api_web = d.get("staging_api_web") or {}
    if api_web:
        url_full = str(api_web.get("admin_login_url_vollstaendig") or "").strip()
        basis = str(api_web.get("oeffentliche_basis_url") or "").strip().rstrip("/")
        alias = str(api_web.get("standard_alias_pfad") or "/k9Qm4pZ7tL2v").strip()
        if not alias.startswith("/"):
            alias = "/" + alias
        if not url_full and basis:
            url_full = f"{basis}{alias}/"
        sw_body = f"<p>{html.escape(str(api_web.get('beschreibung', '')))}</p>"
        if url_full:
            sw_body += (
                '<p class="warn" style="padding:.85rem 1rem;border-radius:10px;line-height:1.5;">'
                "<strong>Web-Admin (ein Klick):</strong><br/>"
                f'<a href="{_attr(url_full)}" target="_blank" rel="noopener noreferrer" '
                f'style="font-size:1.08rem;font-weight:600;word-break:break-all;">'
                f"{html.escape(url_full)}</a>"
                "</p>"
            )
        wg_meta = d.get("wireguard") or {}
        wg_html_n = str(
            wg_meta.get("anleitung_html_seite") or "wireguard_setup.html"
        ).strip() or "wireguard_setup.html"
        wg_inhalt_n = str(
            wg_meta.get("anleitung_inhalt_datei") or "wireguard_setup_inhalt.txt"
        ).strip() or "wireguard_setup_inhalt.txt"
        sw_body += (
            "<p><strong>VPN &amp; Admin absichern (Schritt-für-Schritt):</strong> "
            f'<a href="{_attr(wg_html_n)}" target="_blank" rel="noopener noreferrer">'
            f"{html.escape(wg_html_n)}</a> "
            f'<span class="muted">(Quelle: <code>{html.escape(wg_inhalt_n)}</code>)</span></p>'
        )
        sw_body += (
            "<p><strong>Alias:</strong> "
            f"<code>{html.escape(alias)}</code> · "
            f"<span class=\"muted\">{html.escape(str(api_web.get('hinweis_umgebungsvariablen', '')))}</span></p>"
            f"<p><em>Status:</em> {html.escape(str(api_web.get('status', '')))}</p>"
        )
        parts.append(_section("Staging API · Web-Admin (verborgener Pfad)", sw_body))

    sgu = d.get("server_git_auto_update") or {}
    if sgu:
        zeilen: list[tuple[str, str]] = [
            ("systemd_timer", "systemd-Timer"),
            ("systemd_service", "systemd-Service"),
            ("skript", "Skript"),
            ("ablauf", "Ablauf"),
            ("konfig_datei_optional", "Konfiguration (optional)"),
            ("intervall", "Intervall"),
            ("execstart_hinweis", "ExecStart"),
        ]
        sgu_body = f"<p>{html.escape(str(sgu.get('beschreibung', '')))}</p><dl>"
        for key, label in zeilen:
            if sgu.get(key):
                sgu_body += (
                    f"<dt>{html.escape(label)}</dt>"
                    f"<dd>{html.escape(str(sgu[key]))}</dd>"
                )
        sgu_body += (
            "</dl>"
            f"<p><em>Status:</em> {html.escape(str(sgu.get('status', '')))}</p>"
        )
        parts.append(_section("Proxmox-Host · GitHub-Abgleich & CT-Deploy", sgu_body))

    wg = d.get("wireguard") or {}
    if wg:
        wg_html_name = str(
            wg.get("anleitung_html_seite") or "wireguard_setup.html"
        ).strip() or "wireguard_setup.html"
        wg_inhalt_name = str(
            wg.get("anleitung_inhalt_datei") or "wireguard_setup_inhalt.txt"
        ).strip() or "wireguard_setup_inhalt.txt"
        wg_zeilen: list[tuple[str, str]] = [
            ("ziel", "Ziel"),
            ("erfahrung", "Stand / Erfahrung"),
            ("wo_einrichten", "Einrichtung (wo)"),
            ("nginx_npm_hinweis", "Nginx / NPM"),
            ("naechster_schritt", "Nächster Schritt"),
        ]
        wg_body = (
            f"<p>{html.escape(str(wg.get('beschreibung', '')))}</p>"
            "<p><strong>Ausführliche Anleitung:</strong> "
            f'<a href="{_attr(wg_html_name)}" target="_blank" rel="noopener noreferrer">'
            f"{html.escape(wg_html_name)}</a> "
            f'<span class="muted">(Quelle: <code>{html.escape(wg_inhalt_name)}</code>)</span></p><dl>'
        )
        for key, label in wg_zeilen:
            if wg.get(key):
                wg_body += (
                    f"<dt>{html.escape(label)}</dt>"
                    f"<dd>{html.escape(str(wg[key]))}</dd>"
                )
        wg_body += (
            "</dl>"
            f"<p><em>Status:</em> {html.escape(str(wg.get('status', '')))}</p>"
        )
        parts.append(_section("WireGuard (VPN) · Admin-Zugang absichern", wg_body))

    fz = d.get("fritzbox") or {}
    pf = fz.get("portfreigaben") or []
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(x.get('dienst','')))}</td>"
        f"<td>{html.escape(str(x.get('extern','')))}</td>"
        f"<td>{html.escape(str(x.get('intern_host','')))}</td>"
        f"<td>{html.escape(str(x.get('status','')))}</td>"
        "</tr>"
        for x in pf
    )
    parts.append(
        _section(
            "FritzBox (stabile Fakten für Agenten)",
            f"<p><strong>Modell:</strong> {html.escape(str(fz.get('modell','')))} &nbsp; "
            f"<strong>DynDNS:</strong> {html.escape(str(fz.get('dyn_dns_name','')))}</p>"
            "<table><thead><tr><th>Dienst</th><th>Extern</th><th>Ziel</th><th>Status</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
            f"<p>{html.escape(str(fz.get('festgelegte_fakten_fuer_support','')))}</p>",
        )
    )

    px = d.get("proxmox") or {}
    cts = px.get("container_und_vm") or []
    ct_blocks = []
    for c in cts:
        if not any(c.values()):
            continue
        ct_blocks.append(
            "<div class=\"ct\">"
            f"<h4>{html.escape(str(c.get('name') or 'CT/VM'))}</h4>"
            "<dl>"
            f"<dt>CTID</dt><dd>{html.escape(str(c.get('ctid','')))}</dd>"
            f"<dt>IPv4</dt><dd>{html.escape(str(c.get('ipv4','')))}</dd>"
            f"<dt>Dienste</dt><dd>{html.escape(str(c.get('dienste','')))}</dd>"
            f"<dt>Admin</dt><dd>{html.escape(str(c.get('admin_zugang','')))}</dd>"
            f"<dt>User</dt><dd>{html.escape(str(c.get('user_zugang','')))}</dd>"
            f"<dt>Status</dt><dd>{html.escape(str(c.get('status','')))}</dd>"
            "</dl>"
            f"<p class=\"muted\">{html.escape(str(c.get('notizen','')))}</p>"
            "</div>"
        )
    parts.append(
        _section(
            "Proxmox: Container / VM",
            "".join(ct_blocks) if ct_blocks else "<p class=\"muted\">Noch keine CT-Angaben.</p>",
        )
    )

    mm = _mermaid_fluss(d)
    mermaid_block = f"<pre class=\"mermaid\">\n{mm}\n</pre>"

    checklist = d.get("checkliste_fuer_agenten") or []
    cl_html = "<ul>" + "".join(f"<li>{html.escape(str(x))}</li>" for x in checklist) + "</ul>"

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(titel)}</title>
  <style>{SHARED_CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>{html.escape(titel)}</h1>
  {''.join(parts)}
  <section class="card">
    <h2>Diagramm (Überblick Datenfluss)</h2>
    <p class="muted">Grober Ablauf; Details stehen in den Abschnitten oben.</p>
    {mermaid_block}
  </section>
  <section class="card">
    <h2>Checkliste für Agenten</h2>
    {cl_html}
  </section>
</div>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
  mermaid.initialize({{ startOnLoad: true, theme: "neutral" }});
</script>
</body>
</html>"""


def main() -> int:
    if not DATEI_DATEN.is_file():
        print(
            "Fehlt: daten.json — bitte daten.template.json nach daten.json kopieren und anpassen.",
            file=sys.stderr,
        )
        return 1
    data = json.loads(DATEI_DATEN.read_text(encoding="utf-8"))
    AUSGABE.write_text(_render_html(data), encoding="utf-8")
    print(f"Geschrieben: {AUSGABE}")

    ba = data.get("bootstrap_agenten") or {}
    titel_push = str(ba.get("push_hilfe_seiten_titel") or "Git push — Bootstrap öffentlich aktualisieren")
    if DATEI_PUSH_INHALT.is_file():
        roh = DATEI_PUSH_INHALT.read_text(encoding="utf-8")
        AUSGABE_PUSH.write_text(
            _render_push_html(roh, titel_push, source_filename=DATEI_PUSH_INHALT.name),
            encoding="utf-8",
        )
        print(f"Geschrieben: {AUSGABE_PUSH}")
    else:
        print(f"Hinweis: {DATEI_PUSH_INHALT.name} fehlt — {AUSGABE_PUSH.name} nicht erzeugt.", file=sys.stderr)

    # SSH Setup Unterseite fuer Proxmox → GitHub Deploy Keys.
    titel_ssh = "Proxmox: SSH-Deploy Key fuer GitHub (read-only)"
    if DATEI_SSH_INHALT.is_file():
        roh_ssh = DATEI_SSH_INHALT.read_text(encoding="utf-8")
        AUSGABE_SSH.write_text(
            _render_push_html(
                roh_ssh,
                titel_ssh,
                linkify_urls=[
                    "https://github.com/tnt-nitro/ahds_server_proxmox",
                    "https://github.com/tnt-nitro/ahds_server_proxmox/settings/keys",
                ],
                source_filename=DATEI_SSH_INHALT.name,
            ),
            encoding="utf-8",
        )
        print(f"Geschrieben: {AUSGABE_SSH}")
    else:
        print(f"Hinweis: {DATEI_SSH_INHALT.name} fehlt — {AUSGABE_SSH.name} nicht erzeugt.", file=sys.stderr)

    # NPM Setup Unterseite fuer Router -> NPM -> Zielservice.
    titel_npm = "NPM Setup: Domain, Proxy Host, SSL und Tests"
    if DATEI_NPM_INHALT.is_file():
        roh_npm = DATEI_NPM_INHALT.read_text(encoding="utf-8")
        AUSGABE_NPM.write_text(
            _render_push_html(
                roh_npm,
                titel_npm,
                linkify_urls=[
                    "http://192.168.178.113/health",
                    "http://ahdsserver.duckdns.org/health",
                    "https://ahdsserver.duckdns.org/health",
                    "https://ahdsserver.duckdns.org/k9Qm4pZ7tL2v/",
                    "https://certbot.eff.org/",
                    "https://letsencrypt.org/",
                    "https://de.wikipedia.org/wiki/Certbot",
                    "https://de.wikipedia.org/wiki/Let%E2%80%99s_Encrypt",
                ],
                source_filename=DATEI_NPM_INHALT.name,
            ),
            encoding="utf-8",
        )
        print(f"Geschrieben: {AUSGABE_NPM}")
    else:
        print(f"Hinweis: {DATEI_NPM_INHALT.name} fehlt — {AUSGABE_NPM.name} nicht erzeugt.", file=sys.stderr)

    # WireGuard: VPN + Admin absichern (lokale Anleitungsseite).
    wg_data = data.get("wireguard") or {}
    titel_wg = str(
        wg_data.get("anleitung_seiten_titel")
        or "WireGuard: VPN ins Heimnetz und Admin vorbereiten"
    ).strip() or "WireGuard: VPN ins Heimnetz und Admin vorbereiten"
    if DATEI_WG_INHALT.is_file():
        roh_wg = DATEI_WG_INHALT.read_text(encoding="utf-8")
        AUSGABE_WG.write_text(
            _render_push_html(
                roh_wg,
                titel_wg,
                linkify_urls=[
                    "https://www.wireguard.com/",
                    "https://www.wireguard.com/quickstart/",
                    "https://www.wireguard.com/install/",
                    "https://ahdsserver.duckdns.org/k9Qm4pZ7tL2v/",
                    "http://192.168.178.113/health",
                    "https://ahdsserver.duckdns.org/health",
                ],
                source_filename=DATEI_WG_INHALT.name,
            ),
            encoding="utf-8",
        )
        print(f"Geschrieben: {AUSGABE_WG}")
    else:
        print(f"Hinweis: {DATEI_WG_INHALT.name} fehlt — {AUSGABE_WG.name} nicht erzeugt.", file=sys.stderr)

    # Telegram Setup Unterseite fuer Healthcheck-Fehlermeldungen aufs Handy.
    if DATEI_TELEGRAM_INHALT.is_file():
        AUSGABE_TELEGRAM.write_text(
            _render_telegram_setup_html(DATEI_TELEGRAM_INHALT.name),
            encoding="utf-8",
        )
        print(f"Geschrieben: {AUSGABE_TELEGRAM}")
    else:
        print(f"Hinweis: {DATEI_TELEGRAM_INHALT.name} fehlt — {AUSGABE_TELEGRAM.name} nicht erzeugt.", file=sys.stderr)

    # Technische Bild-Erklaerung als eigene Seite (Diagramm + kurze Klartexte).
    domain = "ahdsserver.duckdns.org"
    try:
        npm = data.get("nginx_proxy_manager") or {}
        hosts = npm.get("proxy_hosts_kurz") or []
        if isinstance(hosts, list) and hosts:
            d0 = str((hosts[0] or {}).get("domain") or "").strip()
            if d0:
                domain = d0
    except Exception:
        pass
    mermaid = f"""
flowchart TD
  U["Internet Nutzer"] --> R["FritzBox Router"]
  R --> N["Nginx Proxy Manager (NPM) CT101"]
  N --> A["API Container (CT113)"]
  A --> S["AhDs API Dienst"]

  N -->|TLS Zertifikat im NPM| X["HTTPS fuer {domain}"]
  R -. Alternative .-> Y["Port 80/443 direkt auf CT113"]
  Y --> Z["Certbot im API Container"]
"""
    tls_html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>TLS-Wege erklärt (NPM vs. Container)</title>
  <style>{SHARED_CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>TLS-Wege erklärt (NPM vs. Container)</h1>
  <p><a href="infra_karte.html">← Zurück zur Infra-Karte</a></p>

  <section class="card">
    <h2>Bild: Datenweg und TLS-Ort</h2>
    <p class="muted">So läuft es in deinem Standardaufbau: Router → Nginx Proxy Manager → API-Container.</p>
    <pre class="mermaid">{mermaid}</pre>
  </section>

  <section class="card">
    <h2>Kurz erklärt ohne Fachchinesisch</h2>
    <ul>
      <li><strong>Certbot:</strong> Werkzeug, das automatisch kostenlose Zertifikate für Transportverschlüsselung (TLS) von Let's Encrypt holt.</li>
      <li><strong>Wenn Nginx Proxy Manager (NPM) vorgeschaltet ist:</strong> Zertifikat im NPM verwalten (empfohlen in deinem Setup).</li>
      <li><strong>Wenn Certbot im API-Container läuft:</strong> Router-Port 80/443 muss direkt auf den API-Container zeigen (nicht auf NPM).</li>
      <li><strong>Darum gab es den Fehler:</strong> Der Installationslauf wollte Certbot im Container, während dein Router auf NPM zeigte.</li>
    </ul>
  </section>

  <section class="card">
    <h2>Merksatz</h2>
    <p class="warn">TLS immer dort einrichten, wo der externe HTTPS-Verkehr zuerst ankommt.</p>
    <p>Bei dir: Das ist der <strong>Nginx Proxy Manager (NPM)</strong>.</p>
  </section>
</div>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
  mermaid.initialize({{ startOnLoad: true, theme: "neutral" }});
</script>
</body>
</html>"""
    AUSGABE_TLS_WEGE.write_text(tls_html, encoding="utf-8")
    print(f"Geschrieben: {AUSGABE_TLS_WEGE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
GUI zum Verwalten von geheimnisse.json.

Funktionen:
- Einträge lesen und anzeigen
- neue Einträge speichern
- Werte per Klick in die Zwischenablage kopieren
"""
from __future__ import annotations

import json
import re
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.parse import urlencode

DIR = Path(__file__).resolve().parent
DATEI = DIR / "geheimnisse.json"


def _normalize_geheimnisse(data: dict) -> None:
    """Sorgt für konsistente Schlüssel ohne bestehende Einträge zu überschreiben."""
    eintraege = data.get("eintraege")
    if not isinstance(eintraege, list):
        data["eintraege"] = []
    tg = data.get("telegram_healthcheck")
    if not isinstance(tg, dict):
        data["telegram_healthcheck"] = {"bot_token": "", "chat_id": ""}
    else:
        tg.setdefault("bot_token", "")
        tg.setdefault("chat_id", "")


def _telegram_api_basis_url(bot_token: str) -> str:
    t = bot_token.strip()
    if not t:
        return ""
    return f"https://api.telegram.org/bot{t}"


def _json_laden() -> dict:
    raw = DATEI.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("geheimnisse.json hat kein gültiges JSON-Objekt.")
    _normalize_geheimnisse(data)
    return data


def _json_speichern(data: dict) -> None:
    DATEI.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class GeheimnisseApp:
    def __init__(self, root: tk.Tk, data: dict) -> None:
        self.root = root
        self.data = data
        self.eintraege: list[dict] = data.get("eintraege", [])
        self.tokens_maskiert = False

        self.root.title("AhDs Geheimnisse – Verwalten")
        self.root.geometry("980x760")

        self._build_ui()
        self._refresh_table()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        top_frame.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value=f"Datei: {DATEI}")
        ttk.Label(top_frame, textvariable=self.status_var).grid(
            row=0, column=0, sticky="w"
        )

        btn_frame = ttk.Frame(top_frame)
        btn_frame.grid(row=0, column=1, sticky="e")
        self.toggle_tokens_btn = ttk.Button(
            btn_frame, text="Token ausblenden", command=self.toggle_token_visibility
        )
        self.toggle_tokens_btn.grid(row=0, column=0, padx=(0, 6))
        ttk.Button(btn_frame, text="Neu laden", command=self.reload_file).grid(
            row=0, column=1, padx=(0, 6)
        )
        ttk.Button(btn_frame, text="Auswahl löschen", command=self.delete_selected).grid(
            row=0, column=2
        )

        masks_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        masks_frame.grid(row=1, column=0, sticky="ew")
        masks_frame.columnconfigure(0, weight=1)
        masks_frame.columnconfigure(1, weight=1)
        masks_frame.columnconfigure(2, weight=1)

        form = ttk.LabelFrame(masks_frame, text="Neuer Eintrag", padding=10)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Bezeichnung").grid(row=0, column=0, sticky="w")
        self.bez_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.bez_var).grid(
            row=0, column=1, sticky="ew", padx=(8, 0), pady=(0, 8)
        )

        ttk.Label(form, text="Token").grid(row=1, column=0, sticky="w")
        self.tok_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.tok_var, show="*").grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(0, 8)
        )

        ttk.Label(form, text="Wo verwendet").grid(row=2, column=0, sticky="w")
        self.verw_var = tk.StringVar(value="siehe Infra-Karte")
        ttk.Entry(form, textvariable=self.verw_var).grid(
            row=2, column=1, sticky="ew", padx=(8, 0), pady=(0, 8)
        )

        ttk.Button(form, text="Eintrag speichern", command=self.add_entry).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0)
        )

        copy_box = ttk.LabelFrame(
            masks_frame, text="Ausgewählten Eintrag kopieren / laden", padding=10
        )
        copy_box.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        copy_box.columnconfigure(0, weight=1)

        self.selected_label = tk.StringVar(value="Keine Auswahl")
        ttk.Label(copy_box, textvariable=self.selected_label).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        ttk.Button(
            copy_box, text="Bezeichnung kopieren", command=self.copy_bezeichnung
        ).grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(copy_box, text="Token kopieren", command=self.copy_token).grid(
            row=2, column=0, sticky="ew", pady=(0, 6)
        )
        ttk.Button(
            copy_box, text="Wo verwendet kopieren", command=self.copy_verwendung
        ).grid(row=3, column=0, sticky="ew")
        ttk.Button(
            copy_box, text="Auswahl in Eingabefelder laden", command=self.load_selected_into_inputs
        ).grid(row=4, column=0, sticky="ew", pady=(8, 0))

        tg_frame = ttk.LabelFrame(
            masks_frame, text="Telegram Healthcheck (API-Links)", padding=10
        )
        tg_frame.grid(row=0, column=2, sticky="ew", padx=(10, 0))
        tg_frame.columnconfigure(1, weight=1)

        ttk.Label(tg_frame, text="Bot-Token").grid(row=0, column=0, sticky="w")
        self.tg_tok_var = tk.StringVar()
        ttk.Entry(tg_frame, textvariable=self.tg_tok_var).grid(
            row=0, column=1, sticky="ew", padx=(8, 0), pady=(0, 6)
        )

        ttk.Label(tg_frame, text="Chat-ID").grid(row=1, column=0, sticky="w")
        self.tg_cid_var = tk.StringVar()
        ttk.Entry(tg_frame, textvariable=self.tg_cid_var).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(0, 6)
        )

        ttk.Button(
            tg_frame, text="Telegram-Daten speichern", command=self.save_telegram_block
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Button(
            tg_frame, text="Telegram-Daten löschen", command=self.delete_telegram_block
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        ttk.Separator(tg_frame, orient="horizontal").grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(0, 8)
        )

        ttk.Label(
            tg_frame,
            text="Fertige URLs / Zeilen (Token + Chat-ID oben eintragen, nicht von Hand in URLs setzen):",
            wraplength=400,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 6))

        btn_tg = ttk.Frame(tg_frame)
        btn_tg.grid(row=6, column=0, columnspan=2, sticky="ew")
        btn_tg.columnconfigure(0, weight=1)
        ttk.Button(btn_tg, text="getMe-URL kopieren", command=self.copy_tg_get_me).grid(
            row=0, column=0, sticky="ew", pady=(0, 4)
        )
        ttk.Button(
            btn_tg, text="getUpdates (curl) kopieren", command=self.copy_tg_curl_updates
        ).grid(row=1, column=0, sticky="ew", pady=(0, 4))
        ttk.Button(
            btn_tg, text="sendMessage Test-URL kopieren", command=self.copy_tg_send_test
        ).grid(row=2, column=0, sticky="ew", pady=(0, 4))
        ttk.Button(
            btn_tg,
            text="Zwei Zeilen für /etc/default kopieren",
            command=self.copy_tg_env_lines,
        ).grid(row=3, column=0, sticky="ew")

        table_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("bezeichnung", "token", "wo_verwendet")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.tree.heading("bezeichnung", text="Bezeichnung")
        self.tree.heading("token", text="Token")
        self.tree.heading("wo_verwendet", text="Wo verwendet")
        self.tree.column("bezeichnung", width=260, anchor="w")
        self.tree.column("token", width=760, anchor="w")
        self.tree.column("wo_verwendet", width=460, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

    def save_telegram_block(self) -> None:
        bot_token = self.tg_tok_var.get().strip()
        chat_id = self.tg_cid_var.get().strip()
        self.data.setdefault("telegram_healthcheck", {})
        self.data["telegram_healthcheck"]["bot_token"] = bot_token
        self.data["telegram_healthcheck"]["chat_id"] = chat_id
        self._upsert_telegram_entry(bot_token, chat_id)
        _normalize_geheimnisse(self.data)
        self._save()
        self._refresh_table()
        self.status_var.set(
            f"Telegram Healthcheck gespeichert in {DATEI.name}"
        )

    def delete_telegram_block(self) -> None:
        ok = messagebox.askyesno(
            "Telegram-Daten löschen",
            "Telegram-Daten wirklich löschen?\n\nBot-Token und Chat-ID werden geleert.",
        )
        if not ok:
            return
        self.tg_tok_var.set("")
        self.tg_cid_var.set("")
        self.data.setdefault("telegram_healthcheck", {})
        self.data["telegram_healthcheck"]["bot_token"] = ""
        self.data["telegram_healthcheck"]["chat_id"] = ""
        self._remove_telegram_entry()
        _normalize_geheimnisse(self.data)
        self._save()
        self._refresh_table()
        self.status_var.set("Telegram-Daten gelöscht")

    def _upsert_telegram_entry(self, bot_token: str, chat_id: str) -> None:
        idx = None
        for i, eintrag in enumerate(self.eintraege):
            if str(eintrag.get("bezeichnung", "")).strip() == "Telegram BOT Token":
                idx = i
                break
        verwendung = "Healthcheck Telegram: Bot Token"
        if chat_id:
            verwendung += f" (Chat-ID: {chat_id})"
        payload = {
            "bezeichnung": "Telegram BOT Token",
            "token": bot_token,
            "wo_verwendet": verwendung,
        }
        if idx is None:
            self.eintraege.append(payload)
        else:
            self.eintraege[idx] = payload

    def _remove_telegram_entry(self) -> None:
        self.eintraege = [
            x
            for x in self.eintraege
            if str(x.get("bezeichnung", "")).strip() != "Telegram BOT Token"
        ]

    def _telegram_token(self) -> str:
        t = self.tg_tok_var.get().strip()
        if t:
            return t
        eintrag = self._selected_entry()
        if not eintrag:
            return ""
        bez = str(eintrag.get("bezeichnung", "")).strip()
        if bez != "Telegram BOT Token":
            return ""
        tok = str(eintrag.get("token", "")).strip()
        if tok:
            self.tg_tok_var.set(tok)
        return tok

    def _telegram_chat_id(self) -> str:
        c = self.tg_cid_var.get().strip()
        if c:
            return c
        eintrag = self._selected_entry()
        if not eintrag:
            return ""
        bez = str(eintrag.get("bezeichnung", "")).strip()
        if bez != "Telegram BOT Token":
            return ""
        verw = str(eintrag.get("wo_verwendet", "")).strip()
        match = re.search(r"Chat-ID:\s*([^\)]+)", verw)
        if match:
            c = match.group(1).strip()
            self.tg_cid_var.set(c)
        return c

    def copy_tg_get_me(self) -> None:
        t = self._telegram_token()
        if not t:
            messagebox.showinfo("Hinweis", "Bitte Bot-Token eintragen (und speichern ist optional).")
            return
        url = _telegram_api_basis_url(t) + "/getMe"
        self._copy_text(url, "getMe-URL")

    def copy_tg_curl_updates(self) -> None:
        t = self._telegram_token()
        if not t:
            messagebox.showinfo("Hinweis", "Bitte Bot-Token eintragen.")
            return
        url = _telegram_api_basis_url(t) + "/getUpdates"
        zeile = "curl -s " + json.dumps(url)
        self._copy_text(zeile, "curl getUpdates")

    def copy_tg_send_test(self) -> None:
        t = self._telegram_token()
        c = self._telegram_chat_id()
        if not t or not c:
            messagebox.showinfo(
                "Hinweis", "Bitte Bot-Token und Chat-ID eintragen."
            )
            return
        q = urlencode({"chat_id": c, "text": "Test"})
        url = _telegram_api_basis_url(t) + "/sendMessage?" + q
        self._copy_text(url, "sendMessage-URL")

    def copy_tg_env_lines(self) -> None:
        t = self._telegram_token()
        c = self._telegram_chat_id()
        if not t or not c:
            messagebox.showinfo(
                "Hinweis", "Bitte Bot-Token und Chat-ID eintragen."
            )
            return
        block = (
            f"HEALTHCHECK_TELEGRAM_BOT_TOKEN={t}\n"
            f"HEALTHCHECK_TELEGRAM_CHAT_ID={c}"
        )
        self._copy_text(block, "Umgebungszeilen")

    def _refresh_table(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for i, eintrag in enumerate(self.eintraege):
            bez = str(eintrag.get("bezeichnung", ""))
            tok = str(eintrag.get("token", ""))
            verw = str(eintrag.get("wo_verwendet", ""))
            self.tree.insert(
                "", "end", iid=str(i), values=(bez, self._token_table_text(tok), verw)
            )
        self.selected_label.set("Keine Auswahl")

    def _token_table_text(self, token: str) -> str:
        if not self.tokens_maskiert:
            return token
        if not token:
            return ""
        return "*" * len(token)

    def toggle_token_visibility(self) -> None:
        self.tokens_maskiert = not self.tokens_maskiert
        if self.tokens_maskiert:
            self.toggle_tokens_btn.configure(text="Token anzeigen")
            self.status_var.set("Tokens in Tabelle sind maskiert")
        else:
            self.toggle_tokens_btn.configure(text="Token ausblenden")
            self.status_var.set("Tokens in Tabelle sind sichtbar")
        self._refresh_table()

    def _save(self) -> None:
        self.data["eintraege"] = self.eintraege
        _normalize_geheimnisse(self.data)
        _json_speichern(self.data)
        self.status_var.set(f"Gespeichert: {DATEI} ({len(self.eintraege)} Einträge)")

    def _selected_index(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _selected_entry(self) -> dict | None:
        idx = self._selected_index()
        if idx is None or idx < 0 or idx >= len(self.eintraege):
            return None
        return self.eintraege[idx]

    def on_select(self, _event=None) -> None:
        eintrag = self._selected_entry()
        if not eintrag:
            self.selected_label.set("Keine Auswahl")
            return
        self.selected_label.set(str(eintrag.get("bezeichnung", "(ohne Bezeichnung)")))

    def add_entry(self) -> None:
        bez = self.bez_var.get().strip()
        tok = self.tok_var.get().strip()
        verw = self.verw_var.get().strip() or "siehe Infra-Karte"
        if not bez:
            messagebox.showerror("Fehler", "Bezeichnung darf nicht leer sein.")
            return
        if not tok:
            messagebox.showerror("Fehler", "Token darf nicht leer sein.")
            return

        self.eintraege.append(
            {"bezeichnung": bez, "token": tok, "wo_verwendet": verw}
        )
        self._save()
        self._refresh_table()

        self.bez_var.set("")
        self.tok_var.set("")
        self.verw_var.set("siehe Infra-Karte")

    def delete_selected(self) -> None:
        idx = self._selected_index()
        if idx is None:
            messagebox.showinfo("Hinweis", "Bitte zuerst einen Eintrag auswählen.")
            return
        eintrag = self.eintraege[idx]
        bez = str(eintrag.get("bezeichnung", "(ohne Bezeichnung)"))
        ok = messagebox.askyesno(
            "Eintrag löschen", f"Eintrag wirklich löschen?\n\n{bez}"
        )
        if not ok:
            return
        del self.eintraege[idx]
        self._save()
        self._refresh_table()

    def _copy_text(self, text: str, label: str) -> None:
        if not text:
            messagebox.showinfo("Hinweis", f"{label} ist leer.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set(f"In Zwischenablage kopiert: {label}")

    def copy_bezeichnung(self) -> None:
        eintrag = self._selected_entry()
        if not eintrag:
            messagebox.showinfo("Hinweis", "Bitte zuerst einen Eintrag auswählen.")
            return
        self._copy_text(str(eintrag.get("bezeichnung", "")), "Bezeichnung")

    def copy_token(self) -> None:
        eintrag = self._selected_entry()
        if not eintrag:
            messagebox.showinfo("Hinweis", "Bitte zuerst einen Eintrag auswählen.")
            return
        self._copy_text(str(eintrag.get("token", "")), "Token")

    def copy_verwendung(self) -> None:
        eintrag = self._selected_entry()
        if not eintrag:
            messagebox.showinfo("Hinweis", "Bitte zuerst einen Eintrag auswählen.")
            return
        self._copy_text(str(eintrag.get("wo_verwendet", "")), "Wo verwendet")

    def load_selected_into_inputs(self) -> None:
        eintrag = self._selected_entry()
        if not eintrag:
            messagebox.showinfo("Hinweis", "Bitte zuerst einen Eintrag auswählen.")
            return
        bez = str(eintrag.get("bezeichnung", ""))
        tok = str(eintrag.get("token", ""))
        verw = str(eintrag.get("wo_verwendet", ""))
        self.bez_var.set(bez)
        self.tok_var.set(tok)
        self.verw_var.set(verw)
        if bez == "Telegram BOT Token":
            self.tg_tok_var.set(tok)
            match = re.search(r"Chat-ID:\s*([^\)]+)", verw)
            self.tg_cid_var.set(match.group(1).strip() if match else "")
        self.status_var.set("Auswahl in Eingabefelder geladen")

    def reload_file(self) -> None:
        try:
            data = _json_laden()
        except Exception as exc:
            messagebox.showerror("Fehler", f"Neu laden fehlgeschlagen:\n{exc}")
            return
        self.data = data
        self.eintraege = data.get("eintraege", [])
        self.tg_tok_var.set("")
        self.tg_cid_var.set("")
        self._refresh_table()
        self.status_var.set(f"Neu geladen: {DATEI} ({len(self.eintraege)} Einträge)")


def main() -> int:
    if not DATEI.is_file():
        messagebox.showerror(
            "Fehlt: geheimnisse.json",
            "Bitte zuerst geheimnisse.template.json nach geheimnisse.json kopieren.",
        )
        return 1
    try:
        data = _json_laden()
    except Exception as exc:
        messagebox.showerror("JSON-Fehler", f"Konnte geheimnisse.json nicht laden:\n{exc}")
        return 1

    root = tk.Tk()
    GeheimnisseApp(root, data)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

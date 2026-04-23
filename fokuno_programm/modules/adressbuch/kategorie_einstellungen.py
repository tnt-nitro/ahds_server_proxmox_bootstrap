"""Dialog: Kontakt-Kategorien (Stufe 1–3) bearbeiten."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox

from locales import get_string

from .kategorie_konfig import (
    KategorieSchema,
    Stufe1Eintrag,
    Stufe2Eintrag,
    Stufe3Eintrag,
    _bau_default_schema,
    _datei_pfad,
    kategorie_schema_leeren,
    kategorien_laden,
    kategorien_speichern,
    slug_ist_gueltig,
)


def _schema_nach_mutable(schema: KategorieSchema) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for o in schema.stufe1:
        u_list: list[dict[str, object]] = []
        for u in o.stufe2:
            z_list = [{"id": z.id, "label": z.label} for z in u.stufe3]
            u_list.append({"id": u.id, "label": u.label, "stufe3": z_list})
        out.append({"id": o.id, "label": o.label, "stufe2": u_list})
    return out


def _mutable_nach_schema(data: list[dict[str, object]]) -> KategorieSchema | None:
    s1: list[Stufe1Eintrag] = []
    for o in data:
        if not isinstance(o, dict):
            continue
        oid = str(o.get("id", "")).strip()
        olab = str(o.get("label", "")).strip() or oid
        if not slug_ist_gueltig(oid):
            return None
        s2_raw = o.get("stufe2", [])
        if not isinstance(s2_raw, list):
            return None
        s2_list: list[Stufe2Eintrag] = []
        for u in s2_raw:
            if not isinstance(u, dict):
                return None
            uid = str(u.get("id", "")).strip()
            ulab = str(u.get("label", "")).strip() or uid
            if not slug_ist_gueltig(uid):
                return None
            z_raw = u.get("stufe3", [])
            if not isinstance(z_raw, list):
                return None
            z_list: list[Stufe3Eintrag] = []
            for z in z_raw:
                if not isinstance(z, dict):
                    return None
                zid = str(z.get("id", "")).strip()
                zlab = str(z.get("label", "")).strip() or zid
                if not slug_ist_gueltig(zid):
                    return None
                z_list.append(Stufe3Eintrag(id=zid, label=zlab))
            s2_list.append(
                Stufe2Eintrag(id=uid, label=ulab, stufe3=tuple(z_list))
            )
        s1.append(Stufe1Eintrag(id=oid, label=olab, stufe2=tuple(s2_list)))
    if not s1:
        return None
    return KategorieSchema(version=1, stufe1=tuple(s1))


def kategorie_einstellungen_oeffnen(
    parent: tk.Misc,
    locale: str,
    on_gespeichert: Callable[[], None] | None = None,
) -> None:
    schema = kategorien_laden()
    data: list[dict[str, object]] = _schema_nach_mutable(schema)

    win = tk.Toplevel(parent.winfo_toplevel())
    win.title(get_string("app.kontakte.kat_einst_titel", locale))
    win.configure(bg="#F5F5F5")
    win.minsize(520, 420)
    win.geometry("640x480")

    kf_bg = "#F5F5F5"
    frm = tk.Frame(win, bg=kf_bg, padx=12, pady=10)
    frm.pack(fill=tk.BOTH, expand=True)

    tk.Label(
        frm,
        text=get_string("app.kontakte.kat_einst_hinweis", locale),
        bg=kf_bg,
        fg="#333333",
        font=("Segoe UI", 9),
        wraplength=600,
        justify=tk.LEFT,
    ).pack(fill=tk.X, pady=(0, 8))

    pan = tk.Frame(frm, bg=kf_bg)
    pan.pack(fill=tk.BOTH, expand=True)

    # —— Stufe 1
    col1 = tk.LabelFrame(
        pan,
        text=get_string("app.kontakte.kat_einst_stufe1", locale),
        bg=kf_bg,
        font=("Segoe UI", 9, "bold"),
    )
    col1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
    lb1 = tk.Listbox(col1, height=12, font=("Segoe UI", 9), exportselection=False)
    lb1.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
    bf1 = tk.Frame(col1, bg=kf_bg)
    bf1.pack(fill=tk.X, padx=6, pady=(0, 6))

    # —— Stufe 2
    col2 = tk.LabelFrame(
        pan,
        text=get_string("app.kontakte.kat_einst_stufe2", locale),
        bg=kf_bg,
        font=("Segoe UI", 9, "bold"),
    )
    col2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
    lb2 = tk.Listbox(col2, height=12, font=("Segoe UI", 9), exportselection=False)
    lb2.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
    bf2 = tk.Frame(col2, bg=kf_bg)
    bf2.pack(fill=tk.X, padx=6, pady=(0, 6))

    # —— Stufe 3
    col3 = tk.LabelFrame(
        pan,
        text=get_string("app.kontakte.kat_einst_stufe3", locale),
        bg=kf_bg,
        font=("Segoe UI", 9, "bold"),
    )
    col3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
    lb3 = tk.Listbox(col3, height=12, font=("Segoe UI", 9), exportselection=False)
    lb3.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
    bf3 = tk.Frame(col3, bg=kf_bg)
    bf3.pack(fill=tk.X, padx=6, pady=(0, 6))

    edit = tk.Frame(frm, bg=kf_bg)
    edit.pack(fill=tk.X, pady=(8, 0))

    tk.Label(
        edit,
        text=get_string("app.kontakte.kat_einst_feld_id", locale),
        bg=kf_bg,
        anchor=tk.W,
    ).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
    id_var = tk.StringVar()
    id_entry = tk.Entry(edit, textvariable=id_var, width=24, font=("Segoe UI", 9))
    id_entry.grid(row=0, column=1, sticky=tk.W)

    tk.Label(
        edit,
        text=get_string("app.kontakte.kat_einst_feld_label", locale),
        bg=kf_bg,
        anchor=tk.W,
    ).grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=(4, 0))
    lab_var = tk.StringVar()
    tk.Entry(edit, textvariable=lab_var, width=40, font=("Segoe UI", 9)).grid(
        row=1, column=1, sticky=tk.EW, pady=(4, 0)
    )
    edit.grid_columnconfigure(1, weight=1)

    modus: list[str] = ["ober"]  # ober | unter | stufe3

    def _idx_ober() -> int:
        t = lb1.curselection()
        return int(t[0]) if t else -1

    def _idx_unter() -> int:
        t = lb2.curselection()
        return int(t[0]) if t else -1

    def _refresh_lb1() -> None:
        sel = _idx_ober()
        lb1.delete(0, tk.END)
        for o in data:
            lb1.insert(tk.END, f'{o["id"]} — {o["label"]}')
        if 0 <= sel < len(data):
            lb1.selection_set(sel)
            lb1.see(sel)

    def _refresh_lb2() -> None:
        lb2.delete(0, tk.END)
        io = _idx_ober()
        if io < 0 or io >= len(data):
            return
        o = data[io]
        st2 = o.get("stufe2", [])
        if not isinstance(st2, list):
            return
        sel = _idx_unter()
        for i, u in enumerate(st2):
            if isinstance(u, dict):
                lb2.insert(tk.END, f'{u.get("id","")} — {u.get("label","")}')
        if st2 and 0 <= sel < len(st2):
            lb2.selection_set(sel)
            lb2.see(sel)

    def _refresh_lb3() -> None:
        lb3.delete(0, tk.END)
        io, iu = _idx_ober(), _idx_unter()
        if io < 0 or iu < 0:
            return
        o = data[io]
        st2 = o.get("stufe2", [])
        if not isinstance(st2, list) or iu >= len(st2):
            return
        u = st2[iu]
        if not isinstance(u, dict):
            return
        zr = u.get("stufe3", [])
        if not isinstance(zr, list):
            return
        t = lb3.curselection()
        sel = int(t[0]) if t else -1
        for z in zr:
            if isinstance(z, dict):
                lb3.insert(tk.END, f'{z.get("id","")} — {z.get("label","")}')
        if zr and 0 <= sel < len(zr):
            lb3.selection_set(sel)
            lb3.see(sel)

    def _apply_edit_to_data() -> None:
        oid, lid = id_var.get().strip(), lab_var.get().strip()
        io, iu = _idx_ober(), _idx_unter()
        iz = int(lb3.curselection()[0]) if lb3.curselection() else -1
        if modus[0] == "ober" and 0 <= io < len(data):
            if slug_ist_gueltig(oid):
                data[io]["id"] = oid
            data[io]["label"] = lid or str(data[io].get("id", ""))
        elif modus[0] == "unter" and io >= 0 and iu >= 0:
            o = data[io]
            st2 = o.get("stufe2", [])
            if isinstance(st2, list) and iu < len(st2) and isinstance(st2[iu], dict):
                if slug_ist_gueltig(oid):
                    st2[iu]["id"] = oid
                st2[iu]["label"] = lid or str(st2[iu].get("id", ""))
        elif modus[0] == "stufe3" and io >= 0 and iu >= 0 and iz >= 0:
            o = data[io]
            st2 = o.get("stufe2", [])
            if not isinstance(st2, list) or iu >= len(st2):
                return
            u = st2[iu]
            if not isinstance(u, dict):
                return
            zr = u.get("stufe3", [])
            if isinstance(zr, list) and iz < len(zr) and isinstance(zr[iz], dict):
                if slug_ist_gueltig(oid):
                    zr[iz]["id"] = oid
                zr[iz]["label"] = lid or str(zr[iz].get("id", ""))

    def _load_selection_to_edit() -> None:
        io, iu = _idx_ober(), _idx_unter()
        iz = int(lb3.curselection()[0]) if lb3.curselection() else -1
        if modus[0] == "ober" and 0 <= io < len(data):
            o = data[io]
            id_var.set(str(o.get("id", "")))
            lab_var.set(str(o.get("label", "")))
            id_entry.configure(state=tk.NORMAL)
        elif modus[0] == "unter" and io >= 0 and iu >= 0:
            o = data[io]
            st2 = o.get("stufe2", [])
            if isinstance(st2, list) and iu < len(st2) and isinstance(st2[iu], dict):
                u = st2[iu]
                id_var.set(str(u.get("id", "")))
                lab_var.set(str(u.get("label", "")))
                id_entry.configure(state=tk.NORMAL)
        elif modus[0] == "stufe3" and io >= 0 and iu >= 0 and iz >= 0:
            o = data[io]
            st2 = o.get("stufe2", [])
            if not isinstance(st2, list) or iu >= len(st2):
                return
            u = st2[iu]
            if not isinstance(u, dict):
                return
            zr = u.get("stufe3", [])
            if isinstance(zr, list) and iz < len(zr) and isinstance(zr[iz], dict):
                z = zr[iz]
                id_var.set(str(z.get("id", "")))
                lab_var.set(str(z.get("label", "")))
                id_entry.configure(state=tk.NORMAL)

    def _ober_waehlen(_e: tk.Event | None = None) -> None:
        modus[0] = "ober"
        id_entry.configure(state=tk.NORMAL)
        _refresh_lb2()
        _refresh_lb3()
        _load_selection_to_edit()

    def _unter_waehlen(_e: tk.Event | None = None) -> None:
        modus[0] = "unter"
        id_entry.configure(state=tk.NORMAL)
        _refresh_lb3()
        _load_selection_to_edit()

    def _stufe3_waehlen(_e: tk.Event | None = None) -> None:
        modus[0] = "stufe3"
        _load_selection_to_edit()

    def _ober_neu() -> None:
        data.append({"id": "neu_bereich", "label": "Neu", "stufe2": []})
        _refresh_lb1()
        lb1.selection_set(len(data) - 1)
        _ober_waehlen()

    def _ober_loeschen() -> None:
        io = _idx_ober()
        if io < 0 or len(data) <= 1:
            messagebox.showwarning(
                get_string("app.kontakte.kat_einst_warn_titel", locale),
                get_string("app.kontakte.kat_einst_warn_min_ober", locale),
                parent=win,
            )
            return
        del data[io]
        _refresh_lb1()
        _refresh_lb2()
        _refresh_lb3()

    def _unter_neu() -> None:
        io = _idx_ober()
        if io < 0:
            return
        o = data[io]
        st2 = o.setdefault("stufe2", [])
        if not isinstance(st2, list):
            o["stufe2"] = []
            st2 = o["stufe2"]
        st2.append({"id": "neu_unter", "label": "Neu", "stufe3": []})
        _refresh_lb2()
        lb2.selection_set(len(st2) - 1)
        _unter_waehlen()

    def _unter_loeschen() -> None:
        io, iu = _idx_ober(), _idx_unter()
        if io < 0 or iu < 0:
            return
        st2 = data[io].get("stufe2", [])
        if isinstance(st2, list) and iu < len(st2):
            del st2[iu]
        _refresh_lb2()
        _refresh_lb3()

    def _s3_neu() -> None:
        io, iu = _idx_ober(), _idx_unter()
        if io < 0 or iu < 0:
            return
        st2 = data[io].get("stufe2", [])
        if not isinstance(st2, list) or iu >= len(st2):
            return
        u = st2[iu]
        if not isinstance(u, dict):
            return
        zr = u.setdefault("stufe3", [])
        if not isinstance(zr, list):
            u["stufe3"] = []
            zr = u["stufe3"]
        zr.append({"id": "neu_detail", "label": "Neu"})
        _refresh_lb3()
        lb3.selection_set(len(zr) - 1)
        _stufe3_waehlen()

    def _s3_loeschen() -> None:
        io, iu = _idx_ober(), _idx_unter()
        iz = int(lb3.curselection()[0]) if lb3.curselection() else -1
        if io < 0 or iu < 0 or iz < 0:
            return
        st2 = data[io].get("stufe2", [])
        if not isinstance(st2, list) or iu >= len(st2):
            return
        u = st2[iu]
        if not isinstance(u, dict):
            return
        zr = u.get("stufe3", [])
        if isinstance(zr, list) and iz < len(zr):
            del zr[iz]
        _refresh_lb3()

    def _apply_id_label() -> None:
        _apply_edit_to_data()
        _refresh_lb1()
        _refresh_lb2()
        _refresh_lb3()

    tk.Button(
        bf1,
        text=get_string("app.kontakte.kat_einst_neu", locale),
        command=_ober_neu,
        font=("Segoe UI", 9),
    ).pack(side=tk.LEFT, padx=(0, 4))
    tk.Button(
        bf1,
        text=get_string("app.kontakte.kat_einst_loeschen", locale),
        command=_ober_loeschen,
        font=("Segoe UI", 9),
    ).pack(side=tk.LEFT)
    tk.Button(
        bf2,
        text=get_string("app.kontakte.kat_einst_neu", locale),
        command=_unter_neu,
        font=("Segoe UI", 9),
    ).pack(side=tk.LEFT, padx=(0, 4))
    tk.Button(
        bf2,
        text=get_string("app.kontakte.kat_einst_loeschen", locale),
        command=_unter_loeschen,
        font=("Segoe UI", 9),
    ).pack(side=tk.LEFT)
    tk.Button(
        bf3,
        text=get_string("app.kontakte.kat_einst_neu", locale),
        command=_s3_neu,
        font=("Segoe UI", 9),
    ).pack(side=tk.LEFT, padx=(0, 4))
    tk.Button(
        bf3,
        text=get_string("app.kontakte.kat_einst_loeschen", locale),
        command=_s3_loeschen,
        font=("Segoe UI", 9),
    ).pack(side=tk.LEFT)

    tk.Button(
        edit,
        text=get_string("app.kontakte.kat_einst_uebernehmen", locale),
        command=_apply_id_label,
        font=("Segoe UI", 9),
    ).grid(row=2, column=1, sticky=tk.W, pady=(6, 0))

    lb1.bind("<<ListboxSelect>>", _ober_waehlen)
    lb2.bind("<<ListboxSelect>>", _unter_waehlen)
    lb3.bind("<<ListboxSelect>>", _stufe3_waehlen)

    btn_zeile = tk.Frame(frm, bg=kf_bg)
    btn_zeile.pack(fill=tk.X, pady=(12, 0))

    def _speichern() -> None:
        _apply_edit_to_data()
        neu = _mutable_nach_schema(data)
        if neu is None:
            messagebox.showerror(
                get_string("app.kontakte.fehler_titel", locale),
                get_string("app.kontakte.kat_einst_fehler_schema", locale),
                parent=win,
            )
            return
        kategorien_speichern(neu)
        if on_gespeichert is not None:
            on_gespeichert()
        messagebox.showinfo(
            get_string("app.kontakte.kat_einst_gespeichert_titel", locale),
            get_string("app.kontakte.kat_einst_gespeichert_text", locale),
            parent=win,
        )
        win.destroy()

    def _zuruecksetzen() -> None:
        if not messagebox.askyesno(
            get_string("app.kontakte.kat_einst_reset_titel", locale),
            get_string("app.kontakte.kat_einst_reset_frage", locale),
            parent=win,
        ):
            return
        pf = _datei_pfad()
        try:
            pf.unlink(missing_ok=True)
        except OSError:
            pass
        kategorie_schema_leeren()
        nonlocal data
        data = _schema_nach_mutable(_bau_default_schema())
        _refresh_lb1()
        _refresh_lb2()
        _refresh_lb3()
        if on_gespeichert is not None:
            on_gespeichert()
        messagebox.showinfo(
            get_string("app.kontakte.kat_einst_reset_fertig_titel", locale),
            get_string("app.kontakte.kat_einst_reset_fertig_text", locale),
            parent=win,
        )

    tk.Button(
        btn_zeile,
        text=get_string("app.kontakte.kat_einst_speichern", locale),
        command=_speichern,
        font=("Segoe UI", 10),
        bg="#1565C0",
        fg="#FFFFFF",
    ).pack(side=tk.RIGHT, padx=(6, 0))
    tk.Button(
        btn_zeile,
        text=get_string("app.kontakte.kat_einst_abbrechen", locale),
        command=win.destroy,
        font=("Segoe UI", 10),
    ).pack(side=tk.RIGHT)
    tk.Button(
        btn_zeile,
        text=get_string("app.kontakte.kat_einst_reset", locale),
        command=_zuruecksetzen,
        font=("Segoe UI", 9),
    ).pack(side=tk.LEFT)

    _refresh_lb1()
    if data:
        lb1.selection_set(0)
        _ober_waehlen()

    win.transient(parent.winfo_toplevel())
    win.grab_set()

#!/usr/bin/env python3
"""La lecture rédigée du briefing — et le contrôle qui l'autorise — 01/10/2026.

⚠️ POURQUOI CE MODULE
Abd Moutalib a comparé notre briefing à celui de GPT : GPT « est fort en
lecture d'analyste mais fait des erreurs côté chiffres ». Mesuré sur la
séance du 30/09 : RDS annoncé +3,45 % à 173,90 (c'était le plus haut ; la
clôture valait 171,00, +1,73 %), TGCC en hausse quand il a clôturé en baisse,
des probabilités « 45 / 30 / 25 % » sans aucun calibrage.

La réponse est de SÉPARER LES RÔLES : les chiffres viennent du moteur, la
plume peut venir d'un modèle (une routine Claude, sans API, décidée le
01/10). Et entre les deux, ce contrôle : **chaque nombre écrit doit exister
dans les faits du briefing**, aux arrondis près. Un seul nombre étranger, et
le texte est refusé ; la version sèche, générée ici sans modèle, reste en
place.

    python pipeline/redaction.py --controler texte.md
    python pipeline/redaction.py --appliquer texte.md --auteur claude
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

# Un nombre écrit à la française : milliers séparés par une espace (normale,
# insécable ou fine), décimales par une virgule. « 17 733,06 », « 1,73 »,
# « 2026 ». Le point décimal est accepté aussi : un texte peut en contenir.
_NOMBRE = re.compile(r"(?<![\w,.])\d{1,3}(?:[   ]\d{3})+(?:[,.]\d+)?(?![\w])"
                     r"|(?<![\w,.])\d+(?:[,.]\d+)?(?![\w])")
# Les dates s'écrivent « 30/09 » ou « 30/09/2026 » : leurs morceaux ne sont
# pas des mesures, on les retire avant de chercher les nombres.
_DATE = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b\d{4}-\d{2}-\d{2}\b")
_HEURE = re.compile(r"\b\d{1,2}h\d{0,2}\b|\b\d{1,2}:\d{2}(?::\d{2})?\b")
ECHELLES = (1, 1e-3, 1e-6)


def nombres(texte: str) -> list[tuple[str, float, int]]:
    """Les nombres d'un texte : (tel qu'écrit, valeur, décimales). Pure."""
    t = _HEURE.sub(" ", _DATE.sub(" ", texte or ""))
    out = []
    for m in _NOMBRE.finditer(t):
        brut = m.group(0)
        net = re.sub(r"[   ]", "", brut).replace(",", ".")
        try:
            v = float(net)
        except ValueError:
            continue
        d = len(net.split(".")[1]) if "." in net else 0
        out.append((brut, v, d))
    return out


def _valeurs(x, out: list):
    """Toutes les valeurs numériques des faits, y compris celles écrites dans
    les phrases (`constats`), dont le texte rédigé est la reformulation."""
    if isinstance(x, bool) or x is None:
        return
    if isinstance(x, (int, float)):
        out.append(abs(float(x)))
    elif isinstance(x, str):
        out.extend(abs(v) for _, v, _ in nombres(x))
    elif isinstance(x, dict):
        for k, v in x.items():
            if k != "redaction":          # le texte ne se justifie pas par lui-même
                _valeurs(v, out)
    elif isinstance(x, list):
        for v in x:
            _valeurs(v, out)


def autorises(faits: dict) -> list[float]:
    out: list[float] = []
    _valeurs(faits, out)
    return out


def _correspond(v: float, d: int, faits: list[float]) -> bool:
    v = abs(v)
    for f in faits:
        for e in ECHELLES:
            if abs(round(f * e, d) - v) < 1e-9:
                return True
    return False


def controler(texte: str, faits: dict) -> dict:
    """Chaque nombre du texte existe-t-il dans les faits ? Pure.

    ⚠️ PAS DE TOLÉRANCE EN POURCENTAGE : un nombre est accepté s'il est
    l'ARRONDI d'une valeur des faits au nombre de décimales écrit (17 733,06
    ou 17 733 pour 17733.0593 ; 19,7 pour 19.747 MDH ; 2,8 pour 2 806 816 DH
    en millions). « 173,90 » pour RDS passe seulement si 173,90 est un fait —
    et c'en est un : c'est le PLUS HAUT. D'où la règle de rédaction : chaque
    nombre est nommé par ce qu'il est (voir la compétence `rediger-briefing`).
    """
    ok_faits = autorises(faits)
    refuses = [brut for brut, v, d in nombres(texte) if not _correspond(v, d, ok_faits)]
    return {"ok": not refuses, "refuses": refuses,
            "n_nombres": len(nombres(texte))}


# ⚠️ LISIBILITÉ — 02/10/2026. Abd Moutalib : « trop de répétition, trop de
# chiffres en texte, pas confortable à la vue ». Mesuré sur la lecture du
# 01/10 : 40 nombres, plusieurs écrits deux fois, et tous déjà affichés par
# l'en-tête et le tableau. Un texte rédigé est désormais refusé au-delà de
# MAX_NOMBRES, ou s'il écrit deux fois le même nombre. Les chiffres vivent
# dans l'en-tête, le tableau et le détail ; le texte dit ce qu'ils montrent.
MAX_NOMBRES = 12


def lisibilite(texte: str, max_nombres: int = MAX_NOMBRES) -> dict:
    """Le texte reste-t-il lisible ? Pure. Un nombre répété est compté sur sa
    valeur (« 17 579,17 » et « 17579,17 » sont le même)."""
    vals = [(brut, round(v, d)) for brut, v, d in nombres(texte)]
    vus, repetes = set(), []
    for brut, v in vals:
        if v in vus and brut not in repetes:
            repetes.append(brut)
        vus.add(v)
    ok = len(vals) <= max_nombres and not repetes
    return {"ok": ok, "n_nombres": len(vals), "max": max_nombres, "repetes": repetes}


# ── La version sèche : rédigée sans modèle, à partir des seuls faits ─────────

def _fr(x, d=2):
    s = f"{abs(x):,.{d}f}".replace(",", " ").replace(".", ",")
    return ("−" if x < 0 else "") + s


def _signe(x, d=2):
    return ("+" if x > 0 else "") + _fr(x, d)


def redaction_seche(b: dict) -> str:
    """Une lecture courte, construite sans modèle à partir des faits. Pure.

    ⚠️ PRESQUE SANS CHIFFRES — 02/10/2026. La première version recopiait les
    constats bout à bout : 42 nombres en un bloc, que l'en-tête du terminal et
    le tableau « À surveiller » affichent déjà. Abd Moutalib : « trop de
    répétition, trop de chiffres en texte ». Les chiffres restent à leur
    place (en-tête, tableau, détail) ; ce texte dit ce qu'ils montrent, en
    mots, et renvoie au tableau.
    """
    paras = []
    acc = b.get("accord") or {}
    t = b.get("trajectoire") or {}
    phr = []
    r = acc.get("ratio")
    if isinstance(r, (int, float)):
        phr.append("La grande majorité des valeurs a reculé." if r <= -0.4 else
                   "La grande majorité des valeurs a progressé." if r >= 0.4 else
                   "Hausses et baisses se sont à peu près équilibrées.")
    c, bas, haut = t.get("cloture"), t.get("plus_bas"), t.get("plus_haut")
    ouv, veille = t.get("ouverture"), t.get("veille")
    if all(isinstance(x, (int, float)) for x in (c, bas, haut)) and haut > bas:
        pos = (c - bas) / (haut - bas)
        traj = ("L'indice termine au plus bas de la séance" if pos <= 0.05 else
                "L'indice termine au plus haut de la séance" if pos >= 0.95 else
                "L'indice termine dans le bas de sa fourchette du jour" if pos < 0.34 else
                "L'indice termine dans le haut de sa fourchette du jour" if pos > 0.66 else
                "L'indice termine au milieu de sa fourchette du jour")
        if isinstance(ouv, (int, float)) and isinstance(veille, (int, float)):
            if ouv > veille and c <= veille:
                traj += ", après avoir effacé son gain d'ouverture"
            elif ouv < veille and c >= veille:
                traj += ", après avoir effacé sa baisse d'ouverture"
        phr.append(traj + ".")
    sect = [x for x in (b.get("secteurs") or []) if isinstance(x.get("variation_pct"), (int, float))]
    if sect:
        n_b = sum(1 for x in sect if x["variation_pct"] < 0)
        n_h = sum(1 for x in sect if x["variation_pct"] > 0)
        phr.append(f"Côté secteurs, {n_b} indices reculent et {n_h} progressent sur {len(sect)}.")
    if phr:
        paras.append("L'essentiel. " + " ".join(phr))

    a = b.get("a_surveiller") or {}
    lignes = []
    for z in a.get("a_publie") or []:
        ch = z.get("chiffres") or {}
        r26, r25 = ch.get("rnpg_s1_2026"), ch.get("rnpg_s1_2025")
        res = ""
        if isinstance(r26, (int, float)) and isinstance(r25, (int, float)):
            res = (" : résultat semestriel en hausse" if r26 > r25 else
                   " : résultat semestriel en baisse" if r26 < r25 else
                   " : résultat semestriel stable")
        chg = z.get("chg")
        reac = ("le titre n'a pas coté" if chg is None else
                "le titre termine en hausse" if chg > 0 else
                "le titre termine en baisse" if chg < 0 else "le titre termine inchangé")
        lignes.append(f"{z['symbol']} a publié ses comptes{res}, et {reac}.")
    if lignes:
        paras.append("Publications. " + " ".join(lignes))
    bouge = [z["symbol"] for z in a.get("a_bouge") or [] if z.get("chg") is not None]
    if bouge:
        paras.append("Critères remplis. " + ", ".join(bouge)
                     + " remplissent au moins un critère mesuré — volume inhabituel, "
                       "extrême de douze mois ou variation parmi les plus fortes. "
                       "Le détail est dans le tableau ci-dessous.")
    return "\n\n".join(paras)


def rediger(b: dict, ancien: dict | None = None) -> dict:
    """Pose `b["redaction"]`. Garde une rédaction de modèle de la même séance
    si elle passe ENCORE le contrôle contre les faits du jour ; sinon, la
    version sèche. Pure."""
    r = (ancien or {}).get("redaction") or {}
    if (r.get("auteur") not in (None, "seche")
            and (ancien or {}).get("seance") == b.get("seance")
            and (ancien or {}).get("moment") == b.get("moment")
            and controler(r.get("texte") or "", b)["ok"]):
        b["redaction"] = r
        return b
    texte = redaction_seche(b)
    b["redaction"] = {"texte": texte, "auteur": "seche",
                      "controle": controler(texte, b)}
    return b


def appliquer(texte: str, auteur: str, racine=None) -> dict:
    """Pose un texte rédigé sur la lecture de clôture publiée, s'il passe."""
    r = Path(racine) if racine else RACINE
    p = r / "briefing_cloture.json"
    b = json.loads(p.read_text(encoding="utf-8"))
    c = controler(texte, b)
    c["lisibilite"] = lisibilite(texte)
    if not c["lisibilite"]["ok"]:
        c["ok"] = False
    if not c["ok"]:
        return c
    b["redaction"] = {"texte": texte.strip(), "auteur": auteur, "controle": c}
    p.write_text(json.dumps(b, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    from pipeline.briefing import archiver
    s = str(b.get("seance") or "")[:10]
    a = r / "briefings" / f"{s}.json"
    if a.exists():
        doc = json.loads(a.read_text(encoding="utf-8"))
        # ⚠️ L'archive est figée : une rédaction peut y REMPLACER la version
        # sèche (c'est un ajout), jamais une autre rédaction déjà archivée.
        deja = ((doc.get("cloture") or {}).get("redaction") or {}).get("auteur")
        if doc.get("cloture") and deja in (None, "seche"):
            doc["cloture"]["redaction"] = b["redaction"]
            a.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")),
                         encoding="utf-8")
    else:
        archiver(b, s, r)
    return c


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--controler")
    ap.add_argument("--appliquer")
    ap.add_argument("--auteur", default="claude")
    a = ap.parse_args()
    chemin = a.appliquer or a.controler
    if not chemin:
        ap.error("--controler ou --appliquer")
    texte = Path(chemin).read_text(encoding="utf-8")
    if a.appliquer:
        c = appliquer(texte, a.auteur)
    else:
        b = json.loads((RACINE / "briefing_cloture.json").read_text(encoding="utf-8"))
        c = controler(texte, b)
        c["lisibilite"] = lisibilite(texte)
        c["ok"] = c["ok"] and c["lisibilite"]["ok"]
    print(json.dumps(c, ensure_ascii=False, indent=1))
    return 0 if c["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

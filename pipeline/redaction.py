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


# ── La version sèche : rédigée sans modèle, à partir des seuls faits ─────────

def _fr(x, d=2):
    s = f"{abs(x):,.{d}f}".replace(",", " ").replace(".", ",")
    return ("−" if x < 0 else "") + s


def _signe(x, d=2):
    return ("+" if x > 0 else "") + _fr(x, d)


def redaction_seche(b: dict) -> str:
    """Une lecture en paragraphes, construite phrase par phrase. Pure.

    Moins littéraire qu'un analyste, mais exacte par construction : elle ne
    reprend que des constats déjà mesurés et les chiffres lus dans les dépôts.
    """
    paras = []
    tete = [c for c in (b.get("constats") or [])[:2]]
    if tete:
        paras.append("L'essentiel. " + " ".join(tete))
    a = b.get("a_surveiller") or {}
    lignes = []
    for z in a.get("a_publie") or []:
        ch = z.get("chiffres") or {}
        morceaux = [f"{z['symbol']} a déposé ses résultats semestriels"]
        if ch.get("ca_s1_2026") is not None and ch.get("var_ca_pct") is not None:
            morceaux.append(f"chiffre d'affaires {_fr(ch['ca_s1_2026'], 1)} MDH "
                            f"({_signe(ch['var_ca_pct'], 1)} %)")
        if ch.get("rnpg_s1_2026") is not None and ch.get("rnpg_s1_2025") is not None:
            morceaux.append(f"résultat part du groupe {_fr(ch['rnpg_s1_2026'], 1)} MDH "
                            f"contre {_fr(ch['rnpg_s1_2025'], 1)}")
        if z.get("chg") is not None:
            r = f"le cours a terminé à {_signe(z['chg'], 2)} %"
            if z.get("volume_rapport") is not None:
                r += f", volume {_fr(z['volume_rapport'], 1)} fois sa médiane de 20 séances"
            morceaux.append(r)
        else:
            morceaux.append("le titre n'a pas coté")
        lignes.append(" ; ".join(morceaux) + ".")
    for z in a.get("a_bouge") or []:
        if z.get("chg") is None:
            continue
        lignes.append(f"{z['symbol']} ({_signe(z['chg'], 2)} %) : "
                      + ", ".join(c["texte"] for c in z["criteres"]) + ".")
    if lignes:
        paras.append("Valeurs à retenir. " + " ".join(lignes))
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
    print(json.dumps(c, ensure_ascii=False, indent=1))
    return 0 if c["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

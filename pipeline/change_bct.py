#!/usr/bin/env python3
"""Taux officiel dirham marocain → dinar tunisien, publié par la Banque Centrale de Tunisie.

⚠️ RÈGLE g — 20/10/2026 — IAS 21 (verificateur-finance, tranché par Abd Moutalib).
Ennakl Automobiles (ENK) cote à Casablanca en MAD mais publie ses comptes en
DINARS TUNISIENS. Aucun ratio ne mêle les deux monnaies : la CAPITALISATION est
convertie en TND au taux officiel DATÉ DU JOUR DU COURS (IAS 21.21 : cours du
jour de la transaction), le taux, sa date et sa source étant stockés à côté.
Pas de taux de ce jour : pas de conversion — jamais le taux de la veille en
silence. Et l'on n'additionne jamais du SCE (exercice 2025, système comptable
tunisien) et de l'IFRS (S1 2026) pour faire un douze mois.

SOURCE ÉTABLIE le 20/10/2026 : la BCT publie chaque jour, sous le titre « Cours
Moyens des Devises Cotées en dinar tunisien sur le Marché des Changes
interbancaire », la ligne « DIRHAM MAROCAIN MAD 10 x,xxxx » (TND pour 10 MAD),
avec ses archives (`cours_archiv.jsp`, date au format AAAA-MM-JJ). Bank
Al-Maghrib ne publie pas de cours du dinar tunisien dans ses cours de référence.

    python pipeline/change_bct.py 2026-10-16 2026-10-19   # relève et range les taux

Le relevé n'est rangé que si la page porte EXACTEMENT la journée demandée : la
BCT renvoie la dernière journée publiée quand on lui en demande une autre.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
TAUX = RACINE / "datasets" / "change_mad_tnd.json"
URL_ARCHIVE = "https://www.bct.gov.tn/bct/siteprod/cours_archiv.jsp"
SOURCE = ("Banque Centrale de Tunisie — Cours moyens des devises cotées en dinar tunisien sur le marché des "
          "changes interbancaire, ligne « DIRHAM MAROCAIN MAD 10 » (TND pour 10 MAD)")


def lire_taux() -> dict:
    return (json.loads(TAUX.read_text(encoding="utf-8")).get("taux") or {}) if TAUX.exists() else {}


def analyser(html: str) -> dict | None:
    """(journée publiée, TND pour 1 MAD) depuis la page de la BCT. Pure."""
    t = re.sub(r"(&nbsp;|\s)+", " ", re.sub(r"<[^>]+>", " ", html))
    j = re.search(r"Journ\S* du (\d{2})/(\d{2})/(\d{4})", t)
    m = re.search(r"DIRHAM MAROCAIN MAD (\d+) (\d+,\d+)", t)
    if not j or not m:
        return None
    unite, cours = int(m.group(1)), float(m.group(2).replace(",", "."))
    return {"date": f"{j.group(3)}-{j.group(2)}-{j.group(1)}", "tnd_par_mad": round(cours / unite, 6),
            "citation": m.group(0)}


def relever(date_iso: str) -> dict | None:
    req = urllib.request.Request(URL_ARCHIVE, data=urllib.parse.urlencode({"input": date_iso, "langue": ""}).encode(),
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        brut = r.read()
    a = analyser(brut.decode("latin-1"))
    if not a or a["date"] != date_iso:
        return None
    return {**a, "source": SOURCE, "url": URL_ARCHIVE + f" (POST input={date_iso})",
            "sha256": hashlib.sha256(brut).hexdigest()}


def cap_en_devise(cap_mdh, prix_asof: str | None, devise: str | None, taux: dict) -> dict | None:
    """Capitalisation convertie dans la monnaie des comptes, au taux du JOUR DU COURS. Pure.

    None si les comptes sont en MAD. Sinon {"valeur", "devise", "taux", "date_taux", "source"}, ou
    {"valeur": None, "motif"} quand le taux de ce jour n'est pas relevé."""
    if not devise or devise == "MAD":
        return None
    if devise != "TND":
        return {"valeur": None, "devise": devise, "motif": f"aucune source de change {devise}/MAD établie"}
    t = taux.get(prix_asof or "")
    if cap_mdh is None or not t:
        return {"valeur": None, "devise": "TND",
                "motif": f"taux BCT du {prix_asof or 'jour du cours'} non relevé : pas de conversion "
                         "(jamais le taux d'un autre jour)"}
    return {"valeur": round(cap_mdh * t["tnd_par_mad"], 1), "unite": "MTND", "devise": "TND",
            "taux": t["tnd_par_mad"], "date_taux": prix_asof, "source": t["source"], "citation": t.get("citation"),
            "formule": f"{cap_mdh} MMAD × {t['tnd_par_mad']} TND/MAD"}


def main(dates: list[str]) -> int:
    doc = json.loads(TAUX.read_text(encoding="utf-8")) if TAUX.exists() else {"taux": {}}
    for d in dates:
        r = relever(d)
        print(d, r and r["tnd_par_mad"], "" if r else "— journée non publiée, rien rangé")
        if r:
            doc.setdefault("taux", {})[d] = r
    TAUX.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

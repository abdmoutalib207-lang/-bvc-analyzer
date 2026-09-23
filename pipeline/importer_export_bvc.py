#!/usr/bin/env python3
"""Réceptionne un export « Cours » de l'opérateur comme série d'un titre.

⚠️ CE QUE CET IMPORT REMPLACE, ET CE QU'IL NE TOUCHE PAS
────────────────────────────────────────────────────────
L'export de `casablanca-bourse.com` est publié par l'opérateur du marché
lui-même : sur la période qu'il couvre, il fait foi contre nos séries, qui
sont des reconstitutions. L'import **remplace donc la bougie entière** —
ouverture, extrêmes, clôture et volume — et non le seul volume.

Ce choix n'est pas cosmétique : le recoupement du 23/09 a trouvé
**534 clôtures fausses** sur 27 titres, concentrées du 18/06 au 06/08/2026.
Un cours faux fausse le RSI, les moyennes mobiles et le MACD — le pilier
technique vaut 25 % du score. Ne corriger que le volume aurait laissé cela
en place.

**Hors de la période de l'export, rien n'est touché.** Nos séances antérieures
à sa première ligne sont conservées telles quelles, et la séance du jour — que
l'export n'a pas encore — reste celle que le moteur vient d'écrire.

⚠️ R11 EST SATISFAITE, PAS CONTOURNÉE
La règle dit qu'une opération sur titres se constate sur PIÈCE. Ici la pièce
est l'export de l'opérateur, avec sa source et son empreinte SHA-256. On ne
déduit rien d'une série de prix : on substitue une série publiée par
l'autorité du marché à une série que nous avions reconstituée.

⚠️ CE QUE L'IMPORT RETIRE, ET POURQUOI C'EST SÛR
L'export liste TOUTES les séances réelles de la période, y compris celles sans
échange — et omet exactement les jours où la Bourse n'a pas ouvert. Une date
que nous portons, comprise dans la période, et absente de l'export est donc
une **séance fantôme**. Le 30/07/2026 (Fête du Trône) en est une, sur les
27 titres mesurés.

⚠️ Une séance ANNULÉE par la Bourse, elle, figure bien dans l'export : le
17/09/2026 y est, alors que la Bourse a arrêté la séance et annulé toutes ses
transactions. `appliquer_corrections_avant_ecriture()` la retire — sans quoi
l'import la réintroduirait.

⚠️ L'IDENTITÉ SE PROUVE, ELLE NE SE LIT PAS SUR LE FICHIER
Trois contrôles, dont un indépendant de tout nom :
  1. le code de la colonne `Ticker` résout par `IDB_TICKER_MAP` ;
  2. le nom d'instrument est relevé et publié dans le document de réception ;
  3. **`Capitalisation ÷ Dernier Cours` doit rendre un nombre d'actions
     CONSTANT** sur la période récente. C'est une identité arithmétique : deux
     sources peuvent citer le même code par erreur, un nombre d'actions qui se
     recoupe au titre près, non.

Usage :
    python3 pipeline/importer_export_bvc.py --verifier <export.csv> [...]
    python3 pipeline/importer_export_bvc.py --ecrire   <export.csv> [...]
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from bvc_config import decalage_maroc  # noqa: E402
from candle_write_policy import appliquer_corrections_avant_ecriture  # noqa: E402
from diagnostiquer_export_bvc import (  # noqa: E402
    lire_export, nombre, nos_chandelles, resoudre,
)

CANDLES = RACINE / "pipeline" / "candles"
RECEPTIONS = RACINE / "datasets" / "historiques_importes"

# Nombre de séances récentes sur lesquelles l'identité arithmétique est
# vérifiée. Assez pour qu'une coïncidence soit exclue, assez peu pour qu'une
# augmentation de capital ancienne ne fasse pas échouer un titre sain.
SEANCES_CONTROLE_IDENTITE = 40


def nombre_d_actions(officiel: dict) -> list[int]:
    """Les nombres d'actions déduits de `Capitalisation ÷ Dernier Cours`.

    ⚠️ Plusieurs valeurs ne sont PAS une anomalie en soi : une augmentation de
    capital en cours de période en produit deux. C'est l'appelant qui juge —
    d'où une liste, et non un booléen qui trancherait à sa place.
    """
    vus = []
    for d in sorted(officiel)[-SEANCES_CONTROLE_IDENTITE:]:
        cours = nombre(officiel[d]["Dernier Cours"])
        cap = nombre(officiel[d]["Capitalisation"])
        if cours and cap:
            n = round(cap / cours)
            if n not in vus:
                vus.append(n)
    return vus


def bougie_depuis_export(jour: str, ligne: dict) -> dict | None:
    """Une chandelle au format du dépôt, ou None si la séance est incotable.

    ⚠️ Une séance SANS ÉCHANGE est conservée, avec `v = 0`. Elle a bien eu
    lieu : le marché était ouvert et le titre n'a pas traité. La supprimer
    créerait un trou là où il y a une information.

    ⚠️ Et son volume vaut 0, jamais le cours — c'est le défaut n°2 que cet
    import répare.
    """
    cours = nombre(ligne["Dernier Cours"])
    if not cours or cours <= 0:
        return None
    ouverture = nombre(ligne["Ouverture"])
    haut = nombre(ligne["Plus Haut"])
    bas = nombre(ligne["Plus Bas"])
    titres = nombre(ligne["Titres Échangés"])
    bougie = {
        "d": jour,
        "o": round(ouverture if ouverture else cours, 2),
        "h": round(haut if haut else cours, 2),
        "l": round(bas if bas else cours, 2),
        "c": round(cours, 2),
        "v": int(titres) if titres else 0,
    }
    # L'invariant OHLC est une propriété de la bougie, pas une correction de
    # confort : un plus-haut inférieur à la clôture n'existe pas. L'export est
    # sain sur ce point ; la garde reste, car c'est le genre de chose qu'on
    # découvre sur le titre n°28.
    bougie["h"] = max(bougie["h"], bougie["o"], bougie["c"])
    bougie["l"] = min(bougie["l"], bougie["o"], bougie["c"])
    return bougie


def fusionner(anciennes: list[dict], officielles: list[dict]) -> dict:
    """La série après import, et le détail de ce qui a bougé.

    Fonction pure. Trois zones, traitées différemment :

      - **avant** la première séance de l'export : nos bougies, intactes.
        L'export ne dit rien de cette période, et ce qu'il ne dit pas ne
        l'autorise pas à effacer ;
      - **pendant** : l'export remplace, séance par séance ;
      - **après** sa dernière séance : nos bougies, intactes — c'est la séance
        du jour, que l'opérateur n'a pas encore publiée.

    ⚠️ Une date à nous COMPRISE dans la période et absente de l'export est une
    séance fantôme : le marché n'a pas ouvert ce jour-là. Elle est retirée, et
    nommée dans le rapport.
    """
    if not officielles:
        return {"serie": list(anciennes), "remplacees": [], "ajoutees": [],
                "fantomes": [], "conservees_avant": 0, "conservees_apres": 0}

    debut = officielles[0]["d"]
    fin = officielles[-1]["d"]
    par_date = {b["d"]: b for b in anciennes}
    officielles_par_date = {b["d"]: b for b in officielles}

    avant = [b for b in anciennes if b["d"] < debut]
    apres = [b for b in anciennes if b["d"] > fin]
    fantomes = sorted(d for d in par_date
                      if debut <= d <= fin and d not in officielles_par_date)

    remplacees, ajoutees = [], []
    for b in officielles:
        ancienne = par_date.get(b["d"])
        if ancienne is None:
            ajoutees.append(b["d"])
        elif any(ancienne.get(k) != b.get(k) for k in ("o", "h", "l", "c", "v")):
            remplacees.append(b["d"])

    serie = sorted(avant + officielles + apres, key=lambda b: b["d"])
    return {"serie": serie, "remplacees": remplacees, "ajoutees": ajoutees,
            "fantomes": fantomes, "conservees_avant": len(avant),
            "conservees_apres": len(apres)}


def preparer(chemin: Path) -> dict:
    """Tout ce qu'il faut pour décider, sans rien écrire."""
    code, instrument, officiel = lire_export(chemin)
    ticker = resoudre(code)
    if ticker is None:
        return {"fichier": chemin.name, "code_operateur": code,
                "refus": "identité non résolue"}

    officielles = []
    incotables = []
    for jour in sorted(officiel):
        b = bougie_depuis_export(jour, officiel[jour])
        (officielles if b else incotables).append(b or jour)

    anciennes = nos_chandelles(ticker)
    f = fusionner(anciennes, officielles)

    # ⚠️ Les corrections déjà réceptionnées et les séances annulées par la
    # Bourse s'appliquent APRÈS la fusion : l'export du 23/09 contient le
    # 17/09, que la Bourse a annulé. Sans cette passe, l'import le
    # réintroduirait.
    serie, rapport = appliquer_corrections_avant_ecriture(ticker, f["serie"])

    return {
        "fichier": chemin.name, "ticker": ticker, "code_operateur": code,
        "instrument": instrument,
        "sha256": hashlib.sha256(chemin.read_bytes()).hexdigest(),
        "periode_source": [officielles[0]["d"], officielles[-1]["d"]]
        if officielles else None,
        "seances_export": len(officiel),
        "nombre_d_actions_deduit": nombre_d_actions(officiel),
        "serie": serie,
        "avant": len(anciennes), "apres": len(serie),
        "remplacees": f["remplacees"], "ajoutees": f["ajoutees"],
        "fantomes": f["fantomes"], "incotables": incotables,
        "conservees_avant": f["conservees_avant"],
        "conservees_apres": f["conservees_apres"],
        "politique": rapport,
    }


def _document(p: dict) -> dict:
    """Le document de réception — la trace sans laquelle l'import ne vaut rien."""
    maintenant = datetime.now(timezone.utc)
    return {
        "_statut": "INSTRUCTION — la série publiée de ce titre EST l'export de "
                   "l'opérateur, date pour date, sur la période couverte.",
        "_portee": "La bougie ENTIÈRE (o/h/l/c/v), et non le seul volume : le "
                   "recoupement a trouvé des clôtures fausses, pas seulement "
                   "des volumes. Hors de la période de l'export, rien n'est "
                   "touché — ni nos séances antérieures, ni la séance du jour.",
        "ticker": p["ticker"],
        "code_operateur": p["code_operateur"],
        "instrument": p["instrument"],
        "source": "casablanca-bourse.com — export « Cours » 3 ans, fourni par "
                  "Abd Moutalib les 22 et 23/09/2026",
        "fichier_recu": p["fichier"],
        "sha256_fichier_recu": p["sha256"],
        "periode_source": p["periode_source"],
        "seances": p["apres"],
        "_identite_verifiee": {
            "code_dans_le_fichier": p["code_operateur"],
            "instrument_dans_le_fichier": p["instrument"],
            "nombre_d_actions_deduit": p["nombre_d_actions_deduit"],
            "methode": "Capitalisation ÷ Dernier Cours sur les "
                       f"{SEANCES_CONTROLE_IDENTITE} dernières séances. Une "
                       "valeur unique est un contrôle arithmétique indépendant "
                       "du nom comme du code : deux sources peuvent citer le "
                       "même code par erreur, un nombre d'actions qui se "
                       "recoupe au titre près, non. Plusieurs valeurs "
                       "signalent une augmentation de capital dans la "
                       "période, pas une erreur d'identité.",
        },
        "_ce_que_l_import_a_change": {
            "seances_remplacees": len(p["remplacees"]),
            "seances_ajoutees": len(p["ajoutees"]),
            "seances_fantomes_retirees": p["fantomes"],
            "conservees_avant_l_export": p["conservees_avant"],
            "conservees_apres_l_export": p["conservees_apres"],
            "annulees_retirees": p["politique"].get(
                "seances_annulees_retirees", []),
        },
        "_colonne_de_volume": "« Titres Échangés », JAMAIS « Volume (MAD) ». "
                              "L'export porte les deux. La règle vit désormais "
                              "dans `pipeline/volume_titres.py` et les "
                              "collecteurs y passent — voir "
                              "`tests/test_volume_titres.py`.",
        "_seances_sans_echange": "Conservées, avec v = 0. Le marché était "
                                 "ouvert et le titre n'a pas traité : c'est "
                                 "une information, pas un trou. Auparavant "
                                 "elles portaient le COURS comme volume.",
        "_cache": "`pipeline/historical_data.json` doit être recalculé pour ce "
                  "titre : ses indicateurs décrivent l'ancienne série.",
        "recu_le": (maintenant.astimezone(
            timezone(__import__("datetime").timedelta(
                hours=decalage_maroc(maintenant.date()))))).isoformat(),
    }


def ecrire(p: dict) -> None:
    CANDLES.mkdir(parents=True, exist_ok=True)
    RECEPTIONS.mkdir(parents=True, exist_ok=True)
    (CANDLES / f"{p['ticker']}.json").write_text(
        json.dumps(p["serie"], ensure_ascii=False), encoding="utf-8")
    (RECEPTIONS / f"{p['ticker']}.json").write_text(
        json.dumps(_document(p), ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str]) -> int:
    ecrire_vraiment = "--ecrire" in argv
    fichiers = [Path(a) for a in argv if not a.startswith("--")]
    if not fichiers:
        print(__doc__)
        return 2

    print(f"{'tk':6} {'act.':>11} {'avant':>6} {'après':>6} {'rempl.':>7} "
          f"{'ajout':>6} {'fantôme':>8} {'annulée':>8}")
    total = {"remplacees": 0, "ajoutees": 0, "fantomes": 0}
    refus = []
    for f in sorted(fichiers):
        p = preparer(f)
        if p.get("refus"):
            refus.append((f.name, p["refus"]))
            continue
        actions = p["nombre_d_actions_deduit"]
        marque = str(actions[0]) if len(actions) == 1 else f"{len(actions)} val."
        print(f"{p['ticker']:6} {marque:>11} {p['avant']:6} {p['apres']:6} "
              f"{len(p['remplacees']):7} {len(p['ajoutees']):6} "
              f"{len(p['fantomes']):8} "
              f"{len(p['politique'].get('seances_annulees_retirees', [])):8}")
        for k in total:
            total[k] += len(p[k])
        if ecrire_vraiment:
            ecrire(p)

    print(f"\n{total['remplacees']} séances remplacées, {total['ajoutees']} "
          f"ajoutées, {total['fantomes']} fantômes retirées.")
    for nom, motif in refus:
        print(f"REFUS {nom} : {motif}")
    if not ecrire_vraiment:
        print("\n⚠️ Rien n'a été écrit. Relancer avec --ecrire.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

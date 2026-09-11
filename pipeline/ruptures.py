#!/usr/bin/env python3
"""Les ruptures de cours observées dans nos séries — observation, pas verdict.

POURQUOI CE SCRIPT EXISTE
─────────────────────────
J'ai annoncé « 13 ruptures sur 9 titres » à partir d'un calcul jetable, tapé
dans un terminal et perdu aussitôt. La revue externe a noté, à juste titre, que
ce chiffre n'avait pas été reproduit. Un nombre qu'on ne peut pas recalculer
n'est pas une mesure : c'est une affirmation.

    python pipeline/ruptures.py                 affiche
    python pipeline/ruptures.py --json …        exporte
    python pipeline/ruptures.py --ecrire        met à jour docs/RUPTURES_OBSERVEES.md

LA RÈGLE DE DÉTECTION, ÉNONCÉE
──────────────────────────────
Deux clôtures consécutives dont le rapport sort de [1/1,5 ; 1,5] — soit un
écart de plus de 50 % d'une séance à la suivante.

Pourquoi 1,5 : sous la limite de variation la plus PERMISSIVE que nous ayons
testée (±20 % sur les cinq premières séances suivant l'admission), deux
clôtures consécutives ne peuvent s'écarter que d'un facteur 1,20. Le seuil de
1,5 laisse donc une marge confortable au-delà de tout régime connu — il ne
signale que ce qu'aucun mouvement de marché licite ne peut produire.

⚠️ « Consécutives » signifie consécutives DANS NOTRE FICHIER. Si des séances
manquent entre les deux lignes, l'écart peut recouvrir plusieurs jours de
marché. L'écart de dates est donc publié à côté du rapport.

CE QUE CE SCRIPT NE FAIT PAS
────────────────────────────
Il ne conclut pas. Une rupture est **une alerte à expliquer**, jamais une
preuve de division d'action ni de corruption de fichier. Chaque entrée sépare :

    observation   ce qui est dans le fichier, mesurable aujourd'hui
    hypotheses    les causes compatibles avec cette observation — toutes
    conclusion    None, sauf si une PIÈCE l'établit

Le champ `conclusion` reste `None` tant qu'aucune pièce datée ne l'appuie.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CANDLES = RACINE / "pipeline" / "candles"
CIBLE = RACINE / "docs" / "RUPTURES_OBSERVEES.md"

# Seuil déduit du régime le plus permissif testé (±20 % ⇒ facteur 1,20),
# avec marge. Nommé ici pour qu'un désaccord porte sur la règle.
SEUIL = 1.5

HYPOTHESES = [
    "opération sur titres (division, regroupement, attribution) non appliquée "
    "à l'historique",
    "opération sur titres appliquée DEUX fois",
    "valeur erronée injectée dans l'historique par une source de repli",
    "confusion d'instrument — deux titres différents fusionnés sous un ticker",
    "séances manquantes entre les deux lignes, l'écart recouvrant plusieurs jours",
]


# Écart maximal, en séances, pour qu'une rupture inverse compte comme un retour.
FENETRE_ALLER_RETOUR = 20


def charger_repli_statique() -> dict:
    """La table de repli figée, pour confronter les cours de rupture.

    ⚠️ Cette table a été corrigée le 02/07/2026. Les valeurs fausses qui ont
    fui dans les chandelles AVANT cette date ne s'y retrouvent donc plus : une
    absence de correspondance ne disculpe rien.
    """
    f = RACINE / "pipeline" / "static_fallback.json"
    if not f.exists():
        return {}
    d = json.loads(f.read_text(encoding="utf-8"))
    return {t: v.get("price") for t, v in d.items()
            if isinstance(v, dict) and isinstance(v.get("price"), (int, float))}


def marquer_allers_retours(ruptures: list) -> None:
    """Une rupture suivie de son inverse n'est pas une opération sur titres.

    ⚠️ RAISONNEMENT : une division d'action ne revient jamais. Un cours qui
    chute d'un facteur cinq puis remonte d'un facteur cinq quelques séances
    plus tard décrit une VALEUR INJECTÉE, pas un événement de marché.

    Le signal est mécanique : deux ruptures du même titre, proches dans le
    temps, dont le produit des rapports revient au voisinage de 1.
    """
    from datetime import date
    for i, a in enumerate(ruptures):
        for b in ruptures:
            if b is a or b["titre"] != a["titre"]:
                continue
            if b["date_apres"] <= a["date_apres"]:
                continue
            try:
                ecart = (date.fromisoformat(b["date_avant"])
                         - date.fromisoformat(a["date_apres"])).days
            except ValueError:
                continue
            if ecart > FENETRE_ALLER_RETOUR * 2:
                continue
            produit = a["rapport_observe"] * b["rapport_observe"]
            if 0.8 <= produit <= 1.25:
                a["aller_retour"] = {
                    "avec": b["date_apres"],
                    "produit_des_rapports": round(produit, 4),
                    "jours_entre_les_deux": ecart,
                    "lecture": "le cours revient à son niveau antérieur. Une "
                               "opération sur titres NE REVIENT PAS : cette "
                               "forme oriente vers une valeur injectée, non "
                               "vers un événement de marché.",
                }
                b["aller_retour"] = {
                    "avec": a["date_apres"],
                    "produit_des_rapports": round(produit, 4),
                    "jours_entre_les_deux": ecart,
                    "lecture": "retour du couple signalé plus haut",
                }


def charger_pieces() -> dict:
    """Les opérations établies par une pièce, si le registre existe."""
    f = RACINE / "pipeline" / "operations_titres.json"
    if not f.exists():
        return {}
    reg = json.loads(f.read_text(encoding="utf-8"))
    return reg.get("operations", {})


def detecter(ticker: str, serie: list, pieces: dict) -> list:
    out = []
    for a, b in zip(serie, serie[1:]):
        ca, cb = a.get("c"), b.get("c")
        if not (isinstance(ca, (int, float)) and isinstance(cb, (int, float))):
            continue
        if ca <= 0:
            continue
        r = cb / ca
        if 1.0 / SEUIL <= r <= SEUIL:
            continue

        da, db = str(a.get("d"))[:10], str(b.get("d"))[:10]
        from datetime import date
        ecart = None
        try:
            ecart = (date.fromisoformat(db) - date.fromisoformat(da)).days
        except ValueError:
            pass

        # Une pièce couvre-t-elle cette date ?
        piece = None
        for op in pieces.get(ticker, []):
            if op.get("date_effet") and da < op["date_effet"] <= db:
                piece = op
                break

        out.append({
            "titre": ticker,
            "date_avant": da, "date_apres": db,
            "jours_calendaires_entre_les_deux": ecart,
            "cloture_avant": ca, "cloture_apres": cb,
            "rapport_observe": round(r, 4),
            "bougie_avant": {"o": a.get("o"), "h": a.get("h"),
                             "l": a.get("l"), "c": ca, "v": a.get("v")},
            "bougie_apres": {"o": b.get("o"), "h": b.get("h"),
                             "l": b.get("l"), "c": cb, "v": b.get("v")},
            "volume_avant": a.get("v"), "volume_apres": b.get("v"),
            "rapport_des_volumes": (
                round(b["v"] / a["v"], 4)
                if a.get("v") and b.get("v") and a["v"] > 0 else None),
            "regle_de_detection": (
                f"rapport des clôtures consécutives hors de "
                f"[1/{SEUIL} ; {SEUIL}]"),
            "hypotheses_compatibles": list(HYPOTHESES),
            "piece_couvrant_la_date": piece,
            "aller_retour": None,
            "cours_egal_au_repli_statique": None,
            # ⚠️ Un saut de cours SANS transaction de part et d'autre ne décrit
            # aucun échange. Le prix a changé dans le fichier, pas sur le marché.
            "aucune_transaction_de_part_et_d_autre": (
                not a.get("v") and not b.get("v")),
            "conclusion": None if piece is None else (
                f"opération établie par pièce : {piece.get('nature')} du "
                f"{piece['date_effet']} — ⚠️ la pièce établit l'ÉVÉNEMENT, "
                f"PAS la manière dont notre fichier l'a traité"),
        })
    return out


def mesurer() -> dict:
    pieces = charger_pieces()
    toutes, series = [], 0
    for f in sorted(CANDLES.glob("*.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(s, list):
            continue
        series += 1
        toutes.extend(detecter(f.stem, s, pieces))
    marquer_allers_retours(toutes)
    repli = charger_repli_statique()
    for r in toutes:
        attendu = repli.get(r["titre"])
        if attendu is None:
            continue
        for cle, val in (("cloture_avant", r["cloture_avant"]),
                         ("cloture_apres", r["cloture_apres"])):
            if abs(val - attendu) < 0.01:
                r["cours_egal_au_repli_statique"] = {
                    "champ": cle, "valeur": val,
                    "lecture": "cette clôture est exactement le cours de la "
                               "table de repli figée. Compatible avec une fuite "
                               "du repli dans les chandelles — déjà constatée "
                               "sur ce dépôt. ⚠️ La table ayant été corrigée le "
                               "02/07/2026, une absence de correspondance ne "
                               "disculpe rien.",
                }
    toutes.sort(key=lambda r: (r["titre"], r["date_apres"]))
    return {
        "_quoi": "Ruptures de cours observées. ALERTES À EXPLIQUER, pas des "
                 "conclusions.",
        "seuil": SEUIL,
        "regle": f"rapport des clôtures consécutives hors de [1/{SEUIL} ; {SEUIL}]",
        "series_examinees": series,
        "ruptures": len(toutes),
        "titres_concernes": sorted({r["titre"] for r in toutes}),
        "avec_piece": sum(1 for r in toutes if r["piece_couvrant_la_date"]),
        "sans_piece": sum(1 for r in toutes if not r["piece_couvrant_la_date"]),
        "allers_retours": sum(1 for r in toutes if r["aller_retour"]),
        "sans_transaction": sum(
            1 for r in toutes if r["aucune_transaction_de_part_et_d_autre"]),
        "sens_unique": sum(1 for r in toutes if not r["aller_retour"]),
        "observations": toutes,
    }


def rendre(m: dict) -> str:
    L = ["# Ruptures de cours observées",
         "",
         "> ⚠️ **Généré** par `pipeline/ruptures.py`. Ne pas modifier à la main.",
         "> Une rupture est une **alerte à expliquer**, jamais une preuve de "
         "division d'action ni de corruption de fichier.",
         "",
         "## La règle de détection",
         "",
         f"Rapport de deux clôtures consécutives hors de "
         f"**[1/{m['seuil']} ; {m['seuil']}]**.",
         "",
         "Sous la limite de variation la plus permissive que nous ayons testée "
         "(±20 %), deux clôtures consécutives ne peuvent s'écarter que d'un "
         f"facteur 1,20. Le seuil de {m['seuil']} laisse une marge au-delà de "
         "tout régime connu.",
         "",
         "⚠️ « Consécutives » veut dire **dans notre fichier**. L'écart de "
         "dates est publié pour que l'on voie si des séances manquent entre "
         "les deux lignes.",
         "",
         "## Le compte",
         "",
         f"- **{m['series_examinees']} séries** examinées",
         f"- **{m['ruptures']} ruptures** sur "
         f"**{len(m['titres_concernes'])} titres** : "
         f"{', '.join(m['titres_concernes'])}",
         f"- **{m['avec_piece']}** couverte(s) par une pièce datée, "
         f"**{m['sans_piece']}** sans pièce",
         f"- **{m['allers_retours']}** en **aller-retour**, "
         f"**{m['sens_unique']}** à **sens unique**",
         f"- **{m['sans_transaction']}** sans aucune transaction de part et "
         f"d'autre — le prix a changé dans le fichier, pas sur le marché",
         "",
         "⚠️ La distinction aller-retour / sens unique est le tri le plus utile "
         "de ce tableau. **Une opération sur titres ne revient jamais** : un "
         "cours qui chute puis remonte au même niveau quelques séances plus "
         "tard décrit une valeur injectée dans l'historique, pas un événement "
         "de marché. Les ruptures à sens unique sont les seules candidates à "
         "une opération — et il reste à le vérifier pièce en main.",
         "",
         "## Les observations",
         "",
         "| Titre | Avant | Après | Jours | Clôture avant | Clôture après | Rapport | Vol. avant | Vol. après | Pièce | Forme |",
         "|---|---|---|--:|--:|--:|--:|--:|--:|---|---|"]
    for r in m["observations"]:
        p = "oui" if r["piece_couvrant_la_date"] else "—"
        va = f"{r['volume_avant']:,.0f}" if r["volume_avant"] is not None else "—"
        vp = f"{r['volume_apres']:,.0f}" if r["volume_apres"] is not None else "—"
        forme = "aller-retour" if r["aller_retour"] else "sens unique"
        if r["cours_egal_au_repli_statique"]:
            forme += " · = repli figé"
        if r["aucune_transaction_de_part_et_d_autre"]:
            forme += " · sans transaction"
        L.append(f"| {r['titre']} | {r['date_avant']} | {r['date_apres']} | "
                 f"{r['jours_calendaires_entre_les_deux']} | "
                 f"{r['cloture_avant']:,.2f} | {r['cloture_apres']:,.2f} | "
                 f"{r['rapport_observe']} | {va} | {vp} | {p} | {forme} |")
    L += ["",
          "## Hypothèses compatibles avec une rupture",
          "",
          "Toutes, tant qu'une pièce n'a pas tranché :", ""]
    L += [f"{i}. {h}" for i, h in enumerate(HYPOTHESES, 1)]
    L += ["",
          "⚠️ Une pièce établit l'**événement**. Elle n'établit pas la manière "
          "dont notre fichier l'a traité — c'est une question distincte, qui se "
          "règle en examinant la série, pas le document.",
          ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ecrire", action="store_true")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    m = mesurer()
    if a.json:
        a.json.write_text(json.dumps(m, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        print(f"→ {a.json}")
    if a.ecrire:
        CIBLE.parent.mkdir(parents=True, exist_ok=True)
        CIBLE.write_text(rendre(m) + "\n", encoding="utf-8")
        print(f"→ {CIBLE.relative_to(RACINE)}")
    print(rendre(m))


if __name__ == "__main__":
    main()

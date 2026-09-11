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

Pourquoi 1,5 : l'ordre de grandeur vient des limites de variation que nous
avons testées — sous ±20 %, deux clôtures consécutives ne s'écartent que d'un
facteur 1,20 — et le seuil laisse une marge au-delà.

⚠️ CE SEUIL EST UN SEUIL DE DÉTECTION, PAS UNE RÈGLE. Il n'a AUCUNE portée
réglementaire, et il ne faut pas lui en redonner une : le contrôle d'amplitude
vient précisément d'abandonner cette prétention, faute de disposer du cours de
référence et du régime applicable. Dépasser 1,5 ne rend rien « illicite » —
cela rend une ligne DIGNE D'EXAMEN.

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


def etat_volume(v) -> str:
    """absent · zéro enregistré · positif · invalide. Quatre états distincts.

    ⚠️ « Absent » n'est pas « zéro », et « zéro enregistré » n'est pas « aucune
    transaction ». Même un zéro inscrit par la source reste une AFFIRMATION DE
    LA SOURCE, jamais une preuve indépendante de ce qui s'est passé sur le
    marché — la source peut avoir omis de renseigner le champ.
    """
    if v is None:
        return "absent"
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return "invalide"
    if v != v or v in (float("inf"), float("-inf")):
        return "invalide"
    if v < 0:
        return "invalide"
    return "zéro enregistré" if v == 0 else "positif"


def etat_volumes(va, vb) -> dict:
    """Ce que les deux volumes encadrant une rupture permettent de dire."""
    ea, eb = etat_volume(va), etat_volume(vb)
    if ea == "absent" and eb == "absent":
        lecture = ("volumes ABSENTS des deux côtés : rien n'est renseigné. "
                   "⚠️ Ce n'est PAS « aucune transaction » — c'est une absence "
                   "d'information, qui ne dit rien du marché.")
    elif ea in ("zéro enregistré", "absent") and eb in ("zéro enregistré", "absent"):
        lecture = ("aucun échange RENSEIGNÉ de part et d'autre. ⚠️ Un zéro "
                   "inscrit par la source reste une affirmation de la source, "
                   "pas une preuve indépendante d'absence de transaction.")
    else:
        lecture = "au moins un des deux côtés porte un volume positif"
    return {"avant": ea, "apres": eb, "lecture": lecture,
            "echange_renseigne_d_au_moins_un_cote":
                "positif" in (ea, eb)}


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

    ⚠️ CE MARQUEUR ORIENTE, IL NE CONCLUT PAS.
    Une version antérieure affirmait qu'un retour « décrit une valeur injectée,
    pas un événement de marché ». C'était trop fort. Un retour du prix près d'un
    niveau antérieur ne PROUVE pas une valeur injectée, et il ne suffit pas non
    plus à EXCLURE une opération sur titres — un regroupement suivi d'une
    division, ou deux corrections successives, produiraient la même forme.

    Ce que le marqueur fait : classer les ruptures par forme, pour ordonner les
    recherches. Rien de plus.
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
                    "hypothese_orientee": (
                        "le cours revient près de son niveau antérieur. Cette "
                        "forme est plus SOUVENT celle d'une valeur injectée que "
                        "celle d'une opération sur titres, qui ne revient pas."),
                    "ce_que_cela_ne_prouve_pas": (
                        "⚠️ Un retour ne PROUVE pas une valeur injectée, et "
                        "n'EXCLUT pas une opération sur titres. Le marqueur "
                        "ordonne les recherches ; il ne clôt aucun cas."),
                }
                b["aller_retour"] = {
                    "avec": a["date_apres"],
                    "produit_des_rapports": round(produit, 4),
                    "jours_entre_les_deux": ecart,
                    "hypothese_orientee": "retour du couple signalé plus haut",
                    "ce_que_cela_ne_prouve_pas": (
                        "⚠️ Un retour ne PROUVE pas une valeur injectée, et "
                        "n'EXCLUT pas une opération sur titres."),
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
            # ⚠️ TROIS ÉTATS, PAS DEUX. Une version antérieure écrivait
            # `not a.get("v") and not b.get("v")` : deux volumes ABSENTS
            # produisaient alors « aucune transaction de part et d'autre ».
            # Confondre l'absence d'information avec l'absence d'échange est
            # exactement la faute que ce projet s'interdit ailleurs. Relevé par
            # la revue, reproduit avec None.
            "etat_des_volumes": etat_volumes(a.get("v"), b.get("v")),
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
        "aucun_echange_renseigne": sum(
            1 for r in toutes
            if not r["etat_des_volumes"]["echange_renseigne_d_au_moins_un_cote"]),
        "volumes_absents_des_deux_cotes": sum(
            1 for r in toutes
            if r["etat_des_volumes"]["avant"] == "absent"
            and r["etat_des_volumes"]["apres"] == "absent"),
        "_recouvrement": (
            "⚠️ Les catégories NE SONT PAS DISJOINTES. Une même rupture peut "
            "être à la fois en aller-retour et sans échange renseigné. Les "
            "totaux ne s'additionnent donc pas."),
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
         f"- **{m['aucun_echange_renseigne']}** sans aucun échange RENSEIGNÉ de "
         f"part et d'autre, dont **{m['volumes_absents_des_deux_cotes']}** où "
         f"les volumes sont simplement **absents**",
         "",
         "⚠️ **Les catégories ci-dessus ne sont pas disjointes** : une même "
         "rupture peut être en aller-retour ET sans échange renseigné. Les "
         "totaux ne s'additionnent pas.",
         "",
         "⚠️ **Volume absent ≠ zéro enregistré ≠ absence de transaction.** Une "
         "version antérieure confondait les trois. Même un zéro inscrit par la "
         "source reste une affirmation de la source, pas une preuve "
         "indépendante de ce qui s'est passé sur le marché.",
         "",
         "⚠️ **Ce tri ORDONNE les recherches ; il n'explique aucun cas.** Une "
         "rupture en aller-retour est plus souvent une valeur injectée qu'une "
         "opération sur titres, mais un retour du prix ne le **prouve** pas et "
         "n'**exclut** pas une opération. Les treize restent treize alertes à "
         "expliquer ; seule une pièce datée en referme une.",
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
        if not r["etat_des_volumes"]["echange_renseigne_d_au_moins_un_cote"]:
            forme += " · aucun échange renseigné"
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

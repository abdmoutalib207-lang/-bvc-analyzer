#!/usr/bin/env python3
"""L'état du marché, séance par séance — ce que la source donnait sans qu'on le lise.

⚠️ CE QUE CE MODULE RÉPARE
──────────────────────────
L'endpoint `INDICE-SYNTHESE` de CDG sert **trente champs**. Le moteur en lisait
**trois** : le cours, la variation et la date. Tout le reste partait à la
poubelle à chaque run, quatre fois par jour ouvré, depuis le 28/08.

Le CLAUDE.md le signalait pourtant dès ce jour-là :

    « L'endpoint livre en prime la largeur de marché — hausses, baisses,
      inchangés, nombre de valeurs — NON EXPLOITÉE pour l'instant. »

Un an de données perdu tient dans ce « pour l'instant ».

⚠️ ET UN DÉFAUT DOCUMENTÉ QUE CES CHAMPS CORRIGENT
Le `WeightEngine` porte ce commentaire : « le projet ne stocke aucun historique
de l'indice, donc le YTD réel n'est pas calculable aujourd'hui ». Deux régimes
de pondération — marché baissier sous −5 %, marché haussier au-delà de +10 % —
sont donc **morts depuis l'origine du projet**.

La source fournit l'ancrage : `CoursPremiereCotation` donne la clôture du
31/12/2025. Ce n'était pas incalculable, c'était non lu.

⚠️ **MAIS LE CHAMP TOUT FAIT DE LA SOURCE EST DÉCALÉ D'UNE SÉANCE.**
`VariationAnneeP` décrit `CoursVeille`, pas `Cours` — l'arithmétique de la
charge utile le prouve seule : `CoursPremiereCotation + VariationAnneeV`
redonne `CoursVeille` au dix-millième. Le recopier a fait publier −4,27 %
pour la séance du 24/09, qui est le YTD du **23/09** ; le vrai vaut −5,19 %.
Le module le **recalcule** donc depuis `cours` et l'ancrage (voir `_ytd()`),
et conserve le champ brut sous `ytd_pct_source_veille` pour qu'on puisse
constater l'écart au lieu de le supposer.

⚠️ CE MODULE NE TOUCHE À AUCUN SCORE
Il collecte et il historise. Rien d'autre. Faire entrer la largeur de marché
dans la note exigerait un backtesting et un accord explicite (R8) — et un
historique, qui n'existera que dans quelques semaines. **On ne peut pas mesurer
ce qu'on n'a pas encore enregistré**, et c'est précisément pourquoi il faut
commencer à enregistrer aujourd'hui.

LA LARGEUR DE MARCHÉ, ET POURQUOI ELLE COMPTE
Au 24/09 : 16 hausses, 42 baisses, 10 inchangées sur 68 valeurs traitées. Un
indice peut monter porté par trois grosses capitalisations pendant que le
marché recule — la variation seule ne le dit pas, la largeur si.

C'est le type de mesure sur lequel d'autres terminaux bâtissent un « sentiment
de marché » sans analyser une seule ligne de texte. Elle arrive chaque jour,
sans corpus à exporter et sans question de vie privée.
"""

from __future__ import annotations

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CHEMIN = RACINE / "pipeline" / "marche_history.json"

# Les champs retenus, et la raison de chacun. On ne stocke pas les trente :
# `PTO`, `PTC`, `Etat` ou `DateJour` ne décrivent pas la séance, et une série
# qui garde tout finit par ne plus rien dire.
CHAMPS = {
    "cours":            "Cours",
    "variation_pct":    "VariationP",
    "variation_val":    "VariationV",
    # ── la largeur de marché : combien de titres montent, baissent, stagnent
    "hausses":          "NbrHausse",
    "baisses":          "NbrBaisse",
    "inchanges":        "NbrInchange",
    "valeurs_traitees": "NbrValeur",
    # ── l'activité réelle
    "transactions":     "NbrTransaction",
    "titres_echanges":  "QteEchange",
    "volume_mad":       "Volume",
    # ── la position dans la séance et dans l'année
    "plus_bas":         "PlusBas",
    "plus_haut":        "PlusHaut",
    "cours_veille":     "CoursVeille",
    "plus_haut_annee":  "PlusHautAnnee",
    "plus_bas_annee":   "PlusBasAnnee",
    # ⚠️ Le YTD servi par la source — celui que le WeightEngine croyait
    # incalculable, et qui neutralisait deux régimes de pondération.
    # ⚠️ `ytd_pct` N'EST PLUS LU DANS LA SOURCE — il est RECALCULÉ par
    # `_ytd()`. Le champ `VariationAnneeP` décrit `CoursVeille`, donc la
    # séance PRÉCÉDENTE, et le recopier décalait le terminal d'une séance.
    # On garde `VariationAnneeP` sous son nom propre pour pouvoir constater
    # l'écart plutôt que de le supposer.
    "ytd_pct_source_veille": "VariationAnneeP",
    "cloture_annee_precedente": "CoursPremiereCotation",
    "capitalisation":   "Capitalisation",
}

# Entiers par nature : un nombre de hausses ne vaut pas 16,0.
ENTIERS = {"hausses", "baisses", "inchanges", "valeurs_traitees",
           "transactions", "titres_echanges"}


def _nombre(v, entier=False):
    """Un nombre, ou None. `None` signifie « la source ne l'a pas donné »."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return int(round(f)) if entier else round(f, 4)


def extraire(ligne: dict) -> dict:
    """Les champs utiles d'une réponse `INDICE-SYNTHESE`. Fonction pure.

    ⚠️ Un champ absent devient `None` et non 0. Zéro hausse est une séance
    de marché réelle — et grave — tandis que « on ne sait pas » n'en est pas
    une. Les confondre ferait passer une panne de source pour un krach.
    """
    if not isinstance(ligne, dict):
        return {}
    etat = {nom: _nombre(ligne.get(src), nom in ENTIERS)
            for nom, src in CHAMPS.items()}
    etat["ytd_pct"] = _ytd(etat)
    return etat


def _ytd(etat: dict):
    """La performance annuelle de la clôture QUE NOUS PUBLIONS.

    ⚠️ LE CHAMP `VariationAnneeP` DE LA SOURCE DÉCRIT LA VEILLE, PAS LE JOUR.
    Établi le 25/09/2026 par l'arithmétique de la charge utile elle-même :

        CoursPremiereCotation + VariationAnneeV = CoursVeille   ← exactement
        1485,6472           + (−191,4898)      = 1294,1574      (MASI 20)
        18846,3502          + (−977,2931)      = 17869,0571     (MASI)

    Ce n'est pas `Cours` qui entre dans le calcul, c'est `CoursVeille`.

    **Conséquence, et elle était publiée.** Le terminal affichait −4,27 % pour
    la séance du 24/09. C'est le YTD de la clôture du **23/09** : la base
    annuelle valant 18 846,3502, −4,27 % donne 18 042,45 contre une clôture
    réelle du 23/09 à 18 040,73 — 0,01 % d'écart. Le vrai YTD du 24/09 vaut
    **−5,19 %**. Un décalage d'une séance, invisible et permanent.

    ⚠️ La parade n'est pas de corriger le décalage, c'est de **ne plus recopier
    un champ dérivé quand on a de quoi le calculer**. `CoursPremiereCotation`
    donne l'ancrage au 31/12, `cours` donne la clôture : le quotient est exact
    et porte sur la séance que nous publions, par construction.

    Renvoie `None` si l'ancrage manque — jamais une valeur approchée.
    """
    cours, base = etat.get("cours"), etat.get("cloture_annee_precedente")
    if not cours or not base:
        return None
    return round((cours / base - 1) * 100, 2)


def largeur(etat: dict) -> dict:
    """Ce que la largeur de marché dit, sous une forme comparable.

    `ratio` va de −1 (tout baisse) à +1 (tout monte). Les inchangés comptent
    dans le dénominateur : un marché où rien ne bouge n'est pas un marché
    haussier, et les exclure gonflerait le ratio des séances calmes.
    """
    h, b, i = (etat.get(k) for k in ("hausses", "baisses", "inchanges"))
    if h is None or b is None:
        return {"ratio": None, "_lecture": "largeur non servie par la source"}
    total = h + b + (i or 0)
    if not total:
        return {"ratio": None, "_lecture": "aucune valeur traitée"}
    ratio = (h - b) / total
    return {
        "ratio": round(ratio, 4),
        "participation_pct": round(100 * (h + b) / total, 1),
        "_lecture": (f"{h} hausses contre {b} baisses sur {total} valeurs — "
                     + ("marché porteur" if ratio > 0.2 else
                        "marché en repli" if ratio < -0.2 else
                        "marché partagé")),
    }


def _charger(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("seances") or {}
    except (OSError, json.JSONDecodeError, AttributeError):
        return {}


def enregistrer(ligne: dict, asof: str, chemin: Path | None = None,
                aujourd_hui: str | None = None) -> bool:
    """Ajoute ou rafraîchit l'état d'une séance.

    ⚠️ MÊME RÈGLE QUE POUR L'INDICE, ET POUR LA MÊME RAISON. Une séance PASSÉE
    est gravée ; la séance DU JOUR se rafraîchit. Le 24/09, `masi_history`
    appliquait la règle inverse — « ajout seulement » — et gardait la valeur du
    run de 11h40 : trois séances sur cinq en sont sorties fausses, jusqu'à
    256 points d'écart. On ne refait pas l'erreur ici.

    Renvoie True si la série a changé.
    """
    p = Path(chemin) if chemin else CHEMIN
    etat = extraire(ligne)
    if not etat.get("cours") or not asof or len(str(asof)) < 10:
        return False
    jour = str(asof)[:10]

    if aujourd_hui is None:
        import sys
        from datetime import datetime, timedelta, timezone
        sys.path.insert(0, str(RACINE))
        from bvc_config import decalage_maroc
        n = datetime.now(timezone.utc)
        aujourd_hui = (n + timedelta(hours=decalage_maroc(n.date()))).strftime("%Y-%m-%d")

    seances = _charger(p)
    connu = seances.get(jour)
    if connu is not None:
        if jour != aujourd_hui:
            return False
        if connu == etat:
            return False
    seances[jour] = etat

    charge = {}
    if p.exists():
        try:
            charge = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            charge = {}
    charge.update({
        "_note": ("État du marché par séance, depuis INDICE-SYNTHESE (CDG). "
                  "Une séance PASSÉE n'est jamais réécrite ; celle DU JOUR se "
                  "rafraîchit jusqu'au dernier run. ⚠️ Ces champs ne sont PAS "
                  "utilisés par le score : ils sont collectés pour qu'une "
                  "mesure devienne possible — on ne peut pas mesurer ce qu'on "
                  "n'a pas enregistré."),
        "_champs": {
            "hausses/baisses/inchanges": "largeur de marché — un indice peut "
                                         "monter porté par trois valeurs "
                                         "pendant que le marché recule",
            "ytd_pct": "⚠️ servi par la source. Le WeightEngine le croyait "
                       "incalculable et neutralisait deux régimes de "
                       "pondération depuis l'origine.",
        },
        "seances": dict(sorted(seances.items())),
    })
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(charge, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)
    return True


def dernier(chemin: Path | None = None) -> dict | None:
    """L'état de la dernière séance enregistrée, largeur comprise."""
    s = _charger(Path(chemin) if chemin else CHEMIN)
    if not s:
        return None
    jour = max(s)
    return {"date": jour, **s[jour], "largeur": largeur(s[jour])}


def profondeur(chemin: Path | None = None) -> int:
    return len(_charger(Path(chemin) if chemin else CHEMIN))


def main() -> int:
    d = dernier()
    print(json.dumps({"profondeur": profondeur(), "derniere_seance": d},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

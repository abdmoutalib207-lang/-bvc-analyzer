#!/usr/bin/env python3
"""Couche de données normalisées — distincte de l'instantané conservé.

CE QU'ELLE EST, ET CE QU'ELLE N'EST PAS
───────────────────────────────────────
`datasets/lot1a/` est un INSTANTANÉ des séries du dépôt : une copie conforme,
jamais retraitée. Il reste intact.

Cette couche-ci est DÉRIVÉE : chaque observation y porte ce qu'elle représente
et pour quels usages elle est admissible. Aucune valeur de prix n'est modifiée.

⚠️ RÉSERVE DE L'EXPRESSION « DONNÉES BRUTES FOURNISSEUR »
Ni l'instantané ni cette couche ne sont des charges utiles de fournisseur. Ce
sont des séries du dépôt, écrites par le moteur à des dates inconnues, par des
programmes non enregistrés. L'expression est réservée aux charges utiles
effectivement conservées — nous n'en gardons aucune.

LES QUATRE USAGES, ET POURQUOI ILS SONT SÉPARÉS
───────────────────────────────────────────────
  prix_analyse   valoriser, comparer, mesurer une variation
  volume         mesurer une quantité échangée
  indicateur     alimenter un calcul de série (moyennes, RSI, bandes…)
  execution      supposer qu'un ordre aurait pu être passé à ce prix

⚠️ `execution` est REFUSÉ PAR DÉFAUT, et ce n'est pas une prudence de façade.
Une série ajustée pour l'analyse porte des prix qui n'ont jamais été cotés :
un titre divisé par dix affiche 130 là où le marché traitait 1 300. Croiser ce
prix avec une quantité NON ajustée fabrique un montant faux d'un facteur dix.
Des prix d'analyse ne doivent jamais devenir silencieusement des prix
d'exécution. L'exécution exige donc un ajustement DOCUMENTÉ, pas seulement
probable.

CHAQUE REFUS PORTE SON MOTIF
────────────────────────────
Une liste d'usages vide sans explication est inexploitable. `refus` dit, usage
par usage, ce qui manque.

USAGE
    python pipeline/normaliser.py --sortie datasets/lot1b
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from enum import Enum
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))
from bvc_config import SPLITS, est_suspendu  # noqa: E402
from qualification import (  # noqa: E402
    Seance, Volume, qualifier_bougie, qualifier_seance, qualifier_volume,
)
from regimes_variation import Amplitude, evaluer_amplitude  # noqa: E402

SOURCE = RACINE / "datasets" / "lot1a"
CALENDRIER = RACINE / "pipeline" / "calendrier_bvc.json"


class Preuve(str, Enum):
    """Niveau de preuve d'un diagnostic de base de prix.

    ⚠️ La revue externe a refusé que « ajusté exactement une fois » et « double
    division sur toute la série » soient tenus pour des FAITS sur la seule foi
    d'un rapport de clôtures. Un rapport observé est un fait ; ce qui l'a
    produit est une hypothèse tant que la suite des transformations n'est pas
    tracée. Ces quatre niveaux rendent la distinction obligatoire.
    """

    DOCUMENTE = "ajustement documenté"
    PROBABLE = "ajustement probable, à confirmer"
    INCOHERENT = "base incohérente ou suspecte"
    INCONNU = "état inconnu"


# ── Ce que l'on sait des bases de prix, avec le niveau de preuve ────────────
#
# Chaque entrée sépare trois choses qui étaient confondues :
#   fait_observe      ce qui est MESURABLE dans la série, aujourd'hui
#   hypothese         ce qu'on en déduit, et qui reste une déduction
#   ce_qui_manque     la pièce qui transformerait l'hypothèse en fait
DIAGNOSTICS = {
    "MNG": {
        "niveau": Preuve.PROBABLE,
        "fait_observe": "rapport des clôtures du 24/07/2026 au 27/07/2026 = "
                        "1,091 ; la série ne présente aucune discontinuité au "
                        "passage de l'opération déclarée au registre",
        "hypothese": "la division par 10 a été appliquée une fois à "
                     "l'historique antérieur",
        "ce_qui_manque": "le journal des écritures ayant produit la série. La "
                         "continuité montre qu'une division a eu lieu ; elle ne "
                         "prouve pas qu'elle n'a été appliquée qu'UNE fois, ni "
                         "qu'aucune autre transformation n'a touché la série "
                         "plus tôt.",
        "consequence": "NE PAS réappliquer adjust_splits : le risque est "
                       "d'agir, pas de s'abstenir",
    },
    "SOT": {
        "niveau": Preuve.INCOHERENT,
        "fait_observe": "rapport des clôtures du 04/05/2026 au 05/05/2026 = "
                        "5,000 ; l'ouverture du 05/05 (1700) est d'un ordre de "
                        "grandeur incompatible avec la clôture du même jour "
                        "(369) ; le niveau médian de l'historique antérieur "
                        "(52–74) est cinq fois inférieur à ce qu'impliquerait "
                        "une division unique par 5",
        "hypothese": "l'historique antérieur au 05/05/2026 a subi DEUX "
                     "divisions par 5 au lieu d'une",
        "ce_qui_manque": "une source primaire de cours pré-split. Sans elle, "
                         "ni l'hypothèse ni sa portée exacte — toutes les "
                         "observations, ou seulement certaines — ne sont "
                         "établies observation par observation.",
        "consequence": "mise à l'écart CONSERVATOIRE de l'historique "
                       "antérieur ; AUCUNE correction appliquée",
    },
}


def diagnostic_base(ticker: str) -> dict:
    """Ce que l'on sait de la base de prix, et à quel titre on le sait.

    ⚠️ « Aucune opération au registre » ne prouve NI l'absence d'opération sur
    tout l'historique, NI la validité des bases. Le registre SPLITS recense ce
    que nous y avons inscrit, pas ce qui s'est produit. Le défaut est donc
    « état inconnu », pour tout le monde.
    """
    if ticker in DIAGNOSTICS:
        d = dict(DIAGNOSTICS[ticker])
        d["niveau"] = d["niveau"].value
        d["operations_au_registre"] = SPLITS.get(ticker, [])
        return d
    return {
        "niveau": Preuve.INCONNU.value,
        "fait_observe": "aucun diagnostic n'a été conduit sur cette série",
        "hypothese": None,
        "ce_qui_manque": "un diagnostic. ⚠️ L'absence d'entrée au registre "
                         "SPLITS n'est pas une preuve d'absence d'opération : "
                         "le registre recense ce que nous y avons inscrit.",
        "consequence": "aucun usage supposant une base connue n'est autorisé",
        "operations_au_registre": SPLITS.get(ticker, []),
    }


def charger_calendrier() -> dict:
    if not CALENDRIER.exists():
        return {}
    return json.loads(CALENDRIER.read_text(encoding="utf-8")).get("jours", {})


def marche_ferme(jour: str, cal: dict):
    """True / False / None. ⚠️ None signifie « non confirmé », jamais « ouvert »."""
    e = cal.get(jour)
    if not e:
        return None
    return {"ferme": True, "ouvert": False}.get(e["statut"])


# ── Le contrat d'admissibilité ──────────────────────────────────────────────

def quantite_comparable(ticker: str, jour: str, niveau: str) -> str | None:
    """Motif de refus si la QUANTITÉ n'est pas comparable, sinon None.

    ⚠️ Une opération sur titres ne change pas que les prix : elle change le
    NOMBRE de titres. Une division par dix du cours s'accompagne d'une
    multiplication par dix du nombre d'actions. Si nous ne savons pas comment
    la série a été ajustée côté prix, nous ne le savons pas davantage côté
    quantités.

    La revue a posé le principe : « des prix ajustés pour l'analyse ne doivent
    pas devenir silencieusement des prix d'exécution avec des quantités non
    ajustées ». Le corollaire est ici : avant une opération déclarée, une
    quantité n'est comparable que si l'ajustement est DOCUMENTÉ.
    """
    if niveau == Preuve.DOCUMENTE.value:
        return None
    for op in SPLITS.get(ticker) or []:
        # ⚠️ Le JOUR MÊME de l'opération est inclus : c'est précisément la
        # séance où la quantité peut relever de l'une ou l'autre base, et où
        # l'ambiguïté est maximale plutôt que minimale.
        if jour <= op["date"]:
            return (f"quantité au plus tard au jour de l'opération du "
                    f"{op['date']} (ratio {op['ratio']}), base « {niveau} » : "
                    f"rien n'établit si elle est exprimée avant ou après "
                    f"l'opération")
    return None


def admissibilite(statut: Seance, diag: dict, bougie: dict,
                  amplitude: dict, ticker: str = "", jour: str = "") -> dict:
    """Usages autorisés, et motif de chaque refus.

    Retourne {"admissible_pour": [...], "refus": {usage: motif}}.

    Les conditions sont cumulatives et vérifiées dans cet ordre : la validité
    des VALEURS d'abord, la cohérence de la BOUGIE ensuite, le statut de la
    SÉANCE, puis la base de PRIX. Un usage n'est accordé que si tout tient.
    """
    q = qualifier_bougie(bougie)
    etat_v, val_v = qualifier_volume(bougie.get("v"))
    niveau = diag["niveau"]
    accorde, refus = [], {}

    # ── prix_analyse ────────────────────────────────────────────────────────
    # Il faut au minimum une clôture exploitable. Une bougie sans clôture ne
    # valorise rien, quel que soit son volume.
    if q["valeurs"]["cloture"] is None:
        refus["prix_analyse"] = "clôture absente ou invalide — " + \
            (q["motifs"][0] if q["motifs"] else "valeur inexploitable")
    elif q["ohlc_coherent"] is False:
        refus["prix_analyse"] = next(m for m in q["motifs"] if "OHLC" in m)
    elif niveau == Preuve.INCOHERENT.value:
        refus["prix_analyse"] = (
            f"base de prix : {niveau} — {diag['consequence']}")
    elif amplitude["statut"] == Amplitude.SUSPECTE.value:
        refus["prix_analyse"] = f"amplitude : {amplitude['motif']}"
    else:
        accorde.append("prix_analyse")

    # ── volume ──────────────────────────────────────────────────────────────
    if etat_v is Volume.INCONNU:
        refus["volume"] = "volume non renseigné par la source — inconnu n'est pas zéro"
    elif etat_v is Volume.INVALIDE:
        refus["volume"] = "volume invalide : non numérique, non fini, ou négatif"
    elif statut in (Seance.SUSPENDUE, Seance.MARCHE_FERME):
        refus["volume"] = f"séance {statut.value} — aucune quantité à mesurer"
    elif (motif := quantite_comparable(ticker, jour, niveau)):
        refus["volume"] = motif
    else:
        accorde.append("volume")

    # ── indicateur ──────────────────────────────────────────────────────────
    # Un indicateur de série enchaîne des observations : il exige une base de
    # prix comparable d'un point au suivant. « État inconnu » ne le permet pas.
    if "prix_analyse" not in accorde:
        refus["indicateur"] = "repose sur prix_analyse, refusé ci-dessus"
    elif not q["complete"]:
        refus["indicateur"] = (
            "bougie incomplète — " + " ; ".join(q["motifs"]))
    elif niveau == Preuve.INCONNU.value:
        refus["indicateur"] = (
            "base de prix « état inconnu » : rien ne garantit que deux points "
            "consécutifs s'expriment sur la même base")
    else:
        # ⚠️ Un « contrôle non concluant » NE REFUSE PAS. Ignorer quel régime
        # s'applique n'est pas une preuve que la bougie est mauvaise : ce serait
        # convertir notre ignorance en verdict. Seule une amplitude SUSPECTE —
        # au-delà de TOUS les régimes connus — écarte une observation, et elle
        # l'a déjà fait au niveau de prix_analyse.
        accorde.append("indicateur")

    # ── execution ───────────────────────────────────────────────────────────
    # Refusé par défaut. Voir l'en-tête du module : un prix ajusté croisé avec
    # une quantité non ajustée fabrique un montant faux.
    if "prix_analyse" not in accorde:
        refus["execution"] = "repose sur prix_analyse, refusé ci-dessus"
    elif "volume" not in accorde:
        refus["execution"] = "repose sur volume, refusé ci-dessus"
    elif statut is not Seance.NEGOCIEE:
        refus["execution"] = (
            f"séance {statut.value} : rien n'établit qu'un ordre aurait pu "
            f"être exécuté ce jour-là")
    elif val_v == 0:
        refus["execution"] = "volume mesuré nul — aucune contrepartie constatée"
    elif niveau != Preuve.DOCUMENTE.value:
        refus["execution"] = (
            f"base de prix « {niveau} » : l'exécution exige un ajustement "
            f"DOCUMENTÉ. Un prix ajusté croisé avec une quantité non ajustée "
            f"produit un montant faux.")
    elif amplitude["statut"] != Amplitude.CONFORME.value:
        # Pour l'exécution, et pour elle seule, le doute vaut refus : un ordre
        # supposé passé à un prix dont la licéité n'est pas établie engage un
        # montant. C'est une PRÉCAUTION, pas un constat d'anomalie.
        refus["execution"] = (f"précaution — amplitude non établie comme "
                              f"conforme : {amplitude['motif']}")
    else:
        accorde.append("execution")

    return {"admissible_pour": accorde, "refus": refus,
            "prix": q["etats"], "ohlc_coherent": q["ohlc_coherent"]}


def normaliser(ticker: str, cal: dict) -> dict:
    src = SOURCE / f"{ticker}.json"
    serie = json.loads(src.read_text(encoding="utf-8"))
    diag = diagnostic_base(ticker)
    obs = []

    for b in serie:
        jour = str(b.get("d") or "")[:10]
        susp = bool(est_suspendu(ticker, jour))
        mf = marche_ferme(jour, cal)
        statut = qualifier_seance(b, susp, mf)
        etat_v, val_v = qualifier_volume(b.get("v"))
        amp = evaluer_amplitude(b, ticker, jour)
        verdict = admissibilite(statut, diag, b, amp, ticker, jour)
        obs.append({
            "date": jour,
            "ouverture": b.get("o"), "plus_haut": b.get("h"),
            "plus_bas": b.get("l"), "cloture": b.get("c"),
            "prix_etats": verdict["prix"],
            "ohlc_coherent": verdict["ohlc_coherent"],
            "volume": val_v,
            "volume_etat": etat_v.value,
            "volume_unite": "nombre de titres",
            "volume_certitude_unite": "présumée — non enregistrée dans la donnée",
            "statut_seance": statut.value,
            "calendrier_confirme": mf is not None,
            "base_prix_niveau": diag["niveau"],
            "amplitude": amp,
            "admissible_pour": verdict["admissible_pour"],
            "refus": verdict["refus"],
        })

    journal = [
        {"transformation": "qualification",
         "applique": True,
         "effet": "ajout des statuts et des motifs de refus ; AUCUNE valeur de "
                  "prix ou de volume modifiée"},
        {"transformation": "ajustement des opérations sur titres",
         "applique": False,
         "effet": "AUCUN. Le diagnostic porte un niveau de preuve, et la revue "
                  "a demandé de ne rien corriger automatiquement.",
         "diagnostic": diag},
    ]
    return {"ticker": ticker, "source": str(src.relative_to(RACINE)),
            "empreinte_source": hashlib.sha256(src.read_bytes()).hexdigest(),
            "lignes": len(obs), "diagnostic_base_prix": diag,
            "journal_transformations": journal, "observations": obs}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sortie", type=Path, default=RACINE / "datasets" / "lot1b")
    a = ap.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    cal = charger_calendrier()
    manif = {
        "_quoi": "Couche NORMALISÉE, dérivée de l'instantané datasets/lot1a.",
        "_ce_que_ce_n_est_pas": "Ni une charge utile de fournisseur, ni une "
                                "série corrigée. Aucune valeur de prix n'a été "
                                "modifiée.",
        "_usages": {
            "prix_analyse": "valoriser, comparer, mesurer une variation",
            "volume": "mesurer une quantité échangée",
            "indicateur": "alimenter un calcul de série",
            "execution": "supposer qu'un ordre aurait pu être passé à ce prix — "
                         "REFUSÉ PAR DÉFAUT, exige un ajustement documenté",
        },
        "_genere_le": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "_calendrier": str(CALENDRIER.relative_to(RACINE)),
        "series": {},
    }
    for f in sorted(SOURCE.glob("*.json")):
        if f.stem == "MANIFESTE":
            continue
        n = normaliser(f.stem, cal)
        (a.sortie / f"{f.stem}.json").write_text(
            json.dumps(n, ensure_ascii=False, indent=1), encoding="utf-8")
        usages = Counter(u for o in n["observations"] for u in o["admissible_pour"])
        manif["series"][f.stem] = {
            "lignes": n["lignes"],
            "base_prix_niveau": n["diagnostic_base_prix"]["niveau"],
            "statuts": dict(Counter(o["statut_seance"] for o in n["observations"])),
            "usages_accordes": dict(usages),
            "observations_sans_aucun_usage":
                sum(1 for o in n["observations"] if not o["admissible_pour"]),
            "amplitudes": dict(Counter(o["amplitude"]["statut"]
                                       for o in n["observations"])),
            "empreinte_source": n["empreinte_source"],
        }
        print(f"  {f.stem:5} {n['lignes']:>4} obs · {n['diagnostic_base_prix']['niveau']:32} "
              f"· exéc {usages['execution']:>4} · indic {usages['indicateur']:>4} "
              f"· sans usage {manif['series'][f.stem]['observations_sans_aucun_usage']:>4}")
    (a.sortie / "MANIFESTE.json").write_text(
        json.dumps(manif, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {a.sortie}")


if __name__ == "__main__":
    main()

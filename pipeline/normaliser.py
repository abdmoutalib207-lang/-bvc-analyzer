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

LES USAGES, ET POURQUOI ILS SONT SÉPARÉS
────────────────────────────────────────
  prix_analyse              valoriser, comparer, mesurer une variation
  volume                    mesurer une quantité échangée
  indicateur                alimenter un calcul de série PUBLIABLE
  indicateur_exploratoire   calculer pour VOIR, en signalant les limites
  execution_simulee         rejouer une comptabilité cohérente prix × quantité

⚠️ TROIS SITUATIONS, TROIS ISSUES — et non deux.
La revue a précisé la règle après qu'une première version eut tout bloqué dès
qu'une base restait incertaine :

  valeurs invalides, ou fenêtre traversant une anomalie non résolue
      → REFUSER le calcul, avec son motif
  valeurs exploitables, mais provenance ou ajustement incomplets
      → PERMETTRE un calcul EXPLORATOIRE, explicitement signalé
  fenêtre qualifiée pour l'usage demandé
      → PERMETTRE cet usage, dans le périmètre documenté

⚠️ Un calcul exploratoire n'alimente NI le signal officiel, NI une probabilité,
NI une performance présentée comme validée. C'est sa raison d'être : pouvoir
essayer sans pouvoir tricher.

⚠️ `execution_simulee` n'exige PAS que les prix soient ajustés. Elle exige une
comptabilité COHÉRENTE : ou bien des prix effectivement cotés avec les
opérations sur titres traitées explicitement, ou bien une représentation
transformée dont TOUTES les grandeurs — prix et quantités — restent
compatibles. Un prix divisé par dix croisé avec une quantité non ajustée
fabrique un montant faux d'un facteur dix ; c'est l'incohérence qui est
refusée, pas l'ajustement.

⚠️ Et cette admissibilité ne prouve PAS qu'un ordre aurait été exécuté. La
liquidité et les règles de remplissage appartiennent au protocole de backtest,
pas à la qualification des données.

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


# ── Ce que l'on sait des QUANTITÉS — registre distinct de celui des prix ───
#
# ⚠️ VIDE À DESSEIN. Une preuve portant sur les prix ne documente PAS le
# traitement des volumes : ce sont deux grandeurs, deux transformations
# possibles, deux provenances. La revue externe a relevé que
# `quantite_comparable()` levait la réserve sur les quantités dès que la base
# des PRIX était documentée. C'était un raccourci.
BASES_QUANTITES: dict = {}


def diagnostic_quantites(ticker: str) -> dict:
    """Unité et base des quantités, avec leur PROPRE provenance."""
    if ticker in BASES_QUANTITES:
        return BASES_QUANTITES[ticker]
    return {
        "niveau": Preuve.INCONNU.value,
        "unite": "nombre de titres",
        "unite_etablie": False,
        "fait_observe": "les chandelles portent un entier nommé « v », hérité "
                        "du champ QteEchangee des sources",
        "hypothese": "il s'agit d'un nombre de titres, non d'un montant",
        "ce_qui_manque": "la convention écrite de la source, et le traitement "
                         "appliqué aux quantités lors des opérations sur "
                         "titres. ⚠️ Aucune des deux n'est enregistrée dans la "
                         "donnée.",
        "consequence": "aucun usage supposant une quantité comparable dans le "
                       "temps n'est autorisé",
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

def quantite_comparable(ticker: str, jour: str, diag_qte: dict) -> str | None:
    """Motif de refus si la QUANTITÉ n'est pas comparable, sinon None.

    ⚠️ Ne dépend PLUS du niveau de preuve des PRIX. Une preuve sur les prix ne
    documente pas le traitement des volumes — relevé par la revue externe.

    Une opération sur titres change le nombre d'actions autant que le cours.
    Sans provenance propre aux quantités, rien n'établit de quel côté de
    l'opération une quantité est exprimée.
    """
    if diag_qte["niveau"] == Preuve.DOCUMENTE.value:
        return None
    for op in SPLITS.get(ticker) or []:
        # Le JOUR MÊME est inclus : c'est la séance la plus ambiguë, pas la moins.
        if jour <= op["date"]:
            return (f"quantité au plus tard au jour de l'opération du "
                    f"{op['date']} (ratio {op['ratio']}), base des quantités "
                    f"« {diag_qte['niveau']} » : rien n'établit si elle est "
                    f"exprimée avant ou après l'opération")
    return None


def comptabilite_coherente(diag_prix: dict, diag_qte: dict) -> str | None:
    """Motif de refus si prix et quantités ne sont pas dans des bases compatibles.

    ⚠️ L'exécution simulée n'exige PAS que les prix soient ajustés. Elle exige
    que prix et quantités racontent la MÊME histoire :

      · des prix effectivement cotés, avec les opérations traitées à part ; ou
      · une représentation transformée dont toutes les grandeurs suivent.

    Ce qui est refusé, c'est le mélange : un cours divisé par dix multiplié par
    une quantité qui ne l'a pas été.
    """
    if diag_prix["niveau"] == Preuve.INCOHERENT.value:
        return ("base des prix « incohérente ou suspecte » : aucune "
                "comptabilité ne peut s'appuyer dessus")
    if diag_prix["niveau"] == Preuve.DOCUMENTE.value and \
            diag_qte["niveau"] == Preuve.DOCUMENTE.value:
        return None
    manquants = []
    if diag_prix["niveau"] != Preuve.DOCUMENTE.value:
        manquants.append(f"prix « {diag_prix['niveau']} »")
    if diag_qte["niveau"] != Preuve.DOCUMENTE.value:
        manquants.append(f"quantités « {diag_qte['niveau']} »")
    return ("la cohérence prix × quantité n'est pas établie — " +
            ", ".join(manquants) + ". ⚠️ Ce refus porte sur la COMPTABILITÉ, "
            "pas sur la probabilité qu'un ordre soit exécuté : la liquidité et "
            "les règles de remplissage relèvent du protocole de backtest.")


def admissibilite(statut: Seance, diag: dict, bougie: dict, amplitude: dict,
                  ticker: str = "", jour: str = "",
                  diag_qte: dict | None = None) -> dict:
    """Usages autorisés, et motif de chaque refus.

    Retourne {"admissible_pour": [...], "refus": {usage: motif}}.
    """
    q = qualifier_bougie(bougie)
    etat_v, val_v = qualifier_volume(bougie.get("v"))
    dq = diag_qte if diag_qte is not None else diagnostic_quantites(ticker)
    niveau = diag["niveau"]
    accorde, refus = [], {}

    # ── prix_analyse ────────────────────────────────────────────────────────
    if q["valeurs"]["cloture"] is None:
        refus["prix_analyse"] = "clôture absente ou invalide — " + \
            (q["motifs"][0] if q["motifs"] else "valeur inexploitable")
    elif q["ohlc_coherent"] is False:
        refus["prix_analyse"] = next(m for m in q["motifs"] if "OHLC" in m)
    elif niveau == Preuve.INCOHERENT.value:
        refus["prix_analyse"] = f"base de prix : {niveau} — {diag['consequence']}"
    elif amplitude["statut"] == Amplitude.HORS_ENVELOPPE.value:
        refus["prix_analyse"] = f"alerte de cohérence — {amplitude['motif']}"
    else:
        accorde.append("prix_analyse")

    # ── volume ──────────────────────────────────────────────────────────────
    # ⚠️ Indépendant de prix_analyse : un volume mesuré reste un volume mesuré
    # même sans clôture exploitable. La revue a relevé que ma formulation
    # « rien n'est autorisé » était trop générale — le code, lui, était juste.
    if etat_v is Volume.INCONNU:
        refus["volume"] = "volume non renseigné par la source — inconnu n'est pas zéro"
    elif etat_v is Volume.INVALIDE:
        refus["volume"] = "volume invalide : non numérique, non fini, ou négatif"
    elif statut in (Seance.SUSPENDUE, Seance.MARCHE_FERME):
        refus["volume"] = f"séance {statut.value} — aucune quantité à mesurer"
    elif (motif := quantite_comparable(ticker, jour, dq)):
        refus["volume"] = motif
    else:
        accorde.append("volume")

    # ── indicateur / indicateur_exploratoire ────────────────────────────────
    # Les deux exigent des VALEURS exploitables. Ce qui les sépare est la
    # PROVENANCE : documentée d'un côté, incomplète de l'autre.
    if "prix_analyse" not in accorde:
        motif = "repose sur prix_analyse, refusé ci-dessus"
        refus["indicateur"] = refus["indicateur_exploratoire"] = motif
    elif not q["complete"]:
        # Une bougie incomplète n'interdit pas TOUT indicateur — une moyenne de
        # clôtures n'a besoin que de la clôture. Le tri par besoins réels se
        # fait au niveau de la FENÊTRE (pipeline/fenetre.py), pas ici.
        refus["indicateur"] = (
            "bougie incomplète pour un indicateur exigeant les quatre prix — " +
            " ; ".join(q["motifs"]) +
            ". ⚠️ Un indicateur n'utilisant que la clôture peut rester "
            "calculable : voir la qualification par fenêtre et par besoins.")
        accorde.append("indicateur_exploratoire")
    elif niveau == Preuve.DOCUMENTE.value:
        accorde.append("indicateur")
        accorde.append("indicateur_exploratoire")
    else:
        refus["indicateur"] = (
            f"base de prix « {niveau} » : provenance ou ajustement incomplets. "
            f"Le calcul reste possible À TITRE EXPLORATOIRE, sans alimenter le "
            f"signal officiel, une probabilité, ni une performance validée.")
        accorde.append("indicateur_exploratoire")

    # ── execution_simulee ───────────────────────────────────────────────────
    if "prix_analyse" not in accorde:
        refus["execution_simulee"] = "repose sur prix_analyse, refusé ci-dessus"
    elif "volume" not in accorde:
        refus["execution_simulee"] = "repose sur volume, refusé ci-dessus"
    elif statut is not Seance.NEGOCIEE:
        refus["execution_simulee"] = (
            f"séance {statut.value} : aucune transaction constatée à rejouer")
    elif val_v == 0:
        refus["execution_simulee"] = "volume mesuré nul — aucune contrepartie constatée"
    elif (motif := comptabilite_coherente(diag, dq)):
        refus["execution_simulee"] = motif
    elif amplitude["statut"] == Amplitude.HORS_ENVELOPPE.value:
        refus["execution_simulee"] = f"alerte de cohérence — {amplitude['motif']}"
    else:
        accorde.append("execution_simulee")

    return {"admissible_pour": accorde, "refus": refus,
            "prix": q["etats"], "ohlc_coherent": q["ohlc_coherent"]}


def normaliser(ticker: str, cal: dict) -> dict:
    src = SOURCE / f"{ticker}.json"
    serie = json.loads(src.read_text(encoding="utf-8"))
    diag = diagnostic_base(ticker)
    diag_qte = diagnostic_quantites(ticker)
    obs = []

    for b in serie:
        jour = str(b.get("d") or "")[:10]
        susp = bool(est_suspendu(ticker, jour))
        mf = marche_ferme(jour, cal)
        statut = qualifier_seance(b, susp, mf)
        etat_v, val_v = qualifier_volume(b.get("v"))
        amp = evaluer_amplitude(b, ticker, jour)
        verdict = admissibilite(statut, diag, b, amp, ticker, jour, diag_qte)
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
            "base_quantites_niveau": diag_qte["niveau"],
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
            "diagnostic_quantites": diag_qte,
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
            "indicateur": "alimenter un calcul de série PUBLIABLE",
            "indicateur_exploratoire": "calculer pour VOIR — n'alimente NI le "
                                       "signal officiel, NI une probabilité, "
                                       "NI une performance validée",
            "execution_simulee": "rejouer une comptabilité cohérente "
                                 "prix × quantité. ⚠️ N'établit PAS qu'un ordre "
                                 "aurait été exécuté : liquidité et règles de "
                                 "remplissage relèvent du protocole de backtest",
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
            "base_quantites_niveau": n["diagnostic_quantites"]["niveau"],
            "statuts": dict(Counter(o["statut_seance"] for o in n["observations"])),
            "usages_accordes": dict(usages),
            "observations_sans_aucun_usage":
                sum(1 for o in n["observations"] if not o["admissible_pour"]),
            "amplitudes": dict(Counter(o["amplitude"]["statut"]
                                       for o in n["observations"])),
            "empreinte_source": n["empreinte_source"],
        }
        print(f"  {f.stem:5} {n['lignes']:>4} obs · {n['diagnostic_base_prix']['niveau']:32} "
              f"· indic {usages['indicateur']:>4} · explo {usages['indicateur_exploratoire']:>4} "
              f"· exéc {usages['execution_simulee']:>4} "
              f"· sans usage {manif['series'][f.stem]['observations_sans_aucun_usage']:>4}")
    (a.sortie / "MANIFESTE.json").write_text(
        json.dumps(manif, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {a.sortie}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Le contrat d'identité : à qui appartiennent les cours qu'on écrit ?

CE QUE CE MODULE EMPÊCHE
───────────────────────
Une contamination entre entreprises : le fichier d'un titre recevant les cours
d'une autre société. Établi sur MSA, qui a porté les cours de Mutandis pendant
cinq semaines — 18 clôtures identiques au centime sur les dates comparables.

Aucun contrôle portant sur les NOMBRES ne pouvait l'attraper. Les cours de
Mutandis sont des cours parfaitement valides : ils respectent l'invariant OHLC,
la limite de variation, la continuité. Ils sont simplement ceux d'une autre
entreprise. C'est un défaut d'IDENTITÉ, et il se contrôle à l'identité.

LES TROIS SOURCES QUI DOIVENT S'ACCORDER
────────────────────────────────────────
    bvc_config.py       notre référentiel : ISIN, nom, ticker du fournisseur
    MANUAL_MAP          le nom que le collecteur DEMANDE au fournisseur
    la réponse reçue    l'identité que le fournisseur RENVOIE réellement

Un désaccord entre les deux premières est vérifiable hors ligne, tout de suite.
Le troisième ne se vérifie qu'à l'exécution — et c'est le seul qui protège
vraiment, parce qu'une table peut être cohérente avec elle-même et fausse.

⚠️ NE PAS CORRIGER UNE CHAÎNE PAR UN NOM SUPPOSÉ EXACT
C'est ainsi que le défaut a été introduit : en juin, cinq entrées ont été
« corrigées » à partir de noms jugés corrects, et l'une de ces corrections —
SBS — contredit notre propre référentiel. Une identité s'établit contre la
réponse du fournisseur, pas contre une conviction.

    python pipeline/identites.py            affiche l'état
    python pipeline/identites.py --ecrire   met à jour docs/IDENTITES.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from enum import Enum
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import bvc_config as cfg  # noqa: E402

COLLECTEUR = RACINE / "pipeline" / "collect_history_bvcscrap.py"
CIBLE = RACINE / "docs" / "IDENTITES.md"


class Identite(str, Enum):
    """⚠️ « Non confrontée » n'est pas « correcte » : c'est « jamais vérifiée »."""

    VERIFIEE = "vérifiée contre la réponse du fournisseur"
    NON_CONFRONTEE = "jamais confrontée à une réponse de fournisseur"
    COLLISION = "le nom demandé désigne mieux un AUTRE titre du référentiel"
    DESACCORD_DE_FOND = "le nom demandé ne partage rien avec le nôtre"
    DEMANDE_PAR_CODE = "le collecteur demande le ticker, pas un nom"
    DESACCORD_DE_FORME = "abréviation, troncature ou variante du même nom"
    INCONNUE = "absente du référentiel"


def _ascii(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _mots(s: str) -> set:
    """Mots significatifs d'un nom de société, formes juridiques ôtées."""
    vides = {"ste", "societe", "sa", "sarl", "sca", "group", "groupe", "du",
             "de", "des", "la", "le", "les", "et", "maroc", "marocaine", "s"}
    return {m for m in _ascii(s).split() if m and m not in vides}


def concordance(demande: str, referentiel: str) -> float:
    """Part des mots du nom demandé qu'on retrouve dans le référentiel.

    ⚠️ Comparaison FLOUE, donc indicative. Elle sert à SIGNALER un désaccord,
    jamais à valider un accord : deux noms peuvent se ressembler et désigner
    deux sociétés — « Auto Hall » et « AtlantaSanad » ne se ressemblent pas,
    mais « Marsa Maroc » et « Maroc Leasing » partagent un mot.
    """
    a, b = _mots(demande), _mots(referentiel)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def manual_map() -> dict:
    """Les noms que le collecteur demande, LUS dans son code source."""
    if not COLLECTEUR.exists():
        return {}
    txt = COLLECTEUR.read_text(encoding="utf-8")
    bloc = re.search(r"MANUAL_MAP\s*[:=].*?\{(.*?)\n\}", txt, re.S)
    if not bloc:
        return {}
    return {m.group(1): m.group(2) for m in
            re.finditer(r'"([A-Z0-9]{2,5})"\s*:\s*"([^"]*)"', bloc.group(1))}


# Alias EXACTS et NON AMBIGUS, documentés un par un.
# ⚠️ Une entrée ici autorise une écriture : elle doit donc nommer une source.
# Un alias « probable » n'a rien à y faire — c'est une ressemblance, et une
# ressemblance ne vaut pas identité.
ALIAS_EXACTS: dict = {
    # "IAM": {"alias": "Maroc Telecom",
    #         "source": "à documenter — fiche instrument de la BVC"},
}


# Identités CONFRONTÉES à une réponse de fournisseur et retenues comme établies.
# ⚠️ VIDE. Aucune réponse de fournisseur n'est conservée dans ce dépôt ; aucune
# identité ne peut donc être déclarée vérifiée aujourd'hui. Une entrée écrite
# ici sans charge utile conservée serait une conviction déguisée en preuve.
IDENTITES_VERIFIEES: dict = {}

# Seuil de concordance en deçà duquel le désaccord est jugé franc.
SEUIL_DESACCORD = 0.34


def est_variante(demande: str, referentiel: str) -> str | None:
    """« demande » est-il une écriture ABRÉGÉE du même nom, ou un autre nom ?

    ⚠️ La distinction décide d'un refus d'écriture, il faut donc qu'elle soit
    mécanique et non une impression.

    Deux formes sont reconnues comme le MÊME nom :
      · l'acronyme des initiales — « BOA » pour Bank Of Africa ;
      · la troncature mot à mot — « Afric Indus » pour Afric Industries,
        « Total Maroc » pour TotalEnergies Marketing Maroc.

    Tout le reste partage trop peu pour qu'on suppose la même société. « Super
    Cereales » face à « Société des Boissons du Maroc » ne s'explique par
    aucune abréviation : c'est une AUTRE entreprise, même si elle ne figure pas
    à notre référentiel.
    """
    d, r = _ascii(demande), _ascii(referentiel)
    if not d or not r:
        return None
    md, mr = _mots(demande), _mots(referentiel)

    # Acronyme : les lettres du nom demandé sont les initiales du référentiel.
    compact = d.replace(" ", "")
    initiales = "".join(m[0] for m in _ascii(referentiel).split() if m)
    if len(compact) <= 5 and compact and compact in (initiales, initiales[:len(compact)]):
        return "acronyme des initiales"

    # Troncature : chaque mot demandé amorce un mot du référentiel, ou l'inverse.
    def amorce(a: set, b: set) -> bool:
        return all(any(x.startswith(y) or y.startswith(x) or x in y or y in x
                       for y in b) for x in a)
    if md and (amorce(md, mr) or amorce(mr, md)):
        return "troncature ou variante mot à mot"
    if compact and (compact in r.replace(" ", "") or r.replace(" ", "") in compact):
        return "forme accolée du même nom"
    return None


def vise_un_autre_titre(ticker: str, demande: str) -> dict | None:
    """Le nom demandé désigne-t-il MIEUX une autre société du référentiel ?

    ⚠️ C'EST LE SEUL SIGNAL QUI COMPTE, et une première version l'a manqué.
    Elle comparait le nom demandé à celui du référentiel et criait au désaccord
    dès que les mots différaient : elle signalait alors vingt titres, dont
    « BOA » pour Bank of Africa, « CMT », « Maroc Telecom » pour Itissalat
    Al-Maghrib. Des abréviations et des noms commerciaux — aucun danger.

    Le danger n'est pas qu'un nom soit écrit autrement. C'est qu'il désigne une
    AUTRE ENTREPRISE, parce qu'alors le fournisseur renverra les cours de
    celle-là. C'est exactement ce qui est arrivé à MSA avec « Mutandis ».
    """
    noms = getattr(cfg, "COMPANY_NAMES", {}) or {}
    sien = concordance(demande, noms.get(ticker, ""))
    meilleurs = []
    for autre, nom in noms.items():
        if autre == ticker:
            continue
        c = concordance(demande, nom)
        if c > 0 and c >= max(sien, SEUIL_DESACCORD):
            meilleurs.append({"ticker": autre, "nom": nom, "concordance": round(c, 4)})
    if not meilleurs:
        return None
    meilleurs.sort(key=lambda x: -x["concordance"])
    return {"vise": meilleurs[:3], "concordance_avec_le_sien": round(sien, 4)}


def etat(ticker: str) -> dict:
    demande = manual_map().get(ticker)
    nom = (getattr(cfg, "COMPANY_NAMES", {}) or {}).get(ticker)
    isin = (getattr(cfg, "ISIN_MAP", {}) or {}).get(ticker)
    idb = (getattr(cfg, "IDB_TICKER_MAP", {}) or {}).get(ticker)

    if ticker in IDENTITES_VERIFIEES:
        niveau, motif = Identite.VERIFIEE, None
    elif nom is None:
        niveau = Identite.INCONNUE
        motif = f"« {ticker} » n'a pas de nom dans le référentiel"
    elif demande is None:
        niveau = Identite.NON_CONFRONTEE
        motif = "le collecteur ne demande aucun nom pour ce titre"
    else:
        c = concordance(demande, nom)
        collision = vise_un_autre_titre(ticker, demande)
        variante = est_variante(demande, nom)
        if collision:
            cible = collision["vise"][0]
            niveau = Identite.COLLISION
            motif = (f"le collecteur demande « {demande} », qui désigne mieux "
                     f"{cible['ticker']} — « {cible['nom']} » "
                     f"(concordance {cible['concordance']:.0%} contre "
                     f"{c:.0%} avec « {nom} »)")
        elif demande.strip().upper() == ticker.upper():
            niveau = Identite.DEMANDE_PAR_CODE
            motif = (f"le collecteur demande « {demande} », c'est-à-dire le "
                     f"ticker lui-même : aucune identité de société n'est "
                     f"exprimée, donc rien à confronter hors ligne")
        elif variante:
            niveau = Identite.DESACCORD_DE_FORME
            motif = f"« {demande} » est une {variante} de « {nom} »"
        elif c >= SEUIL_DESACCORD:
            niveau = Identite.NON_CONFRONTEE
            motif = ("les deux tables s'accordent, mais aucune réponse de "
                     "fournisseur ne l'a confirmé")
        else:
            niveau = Identite.DESACCORD_DE_FOND
            motif = (f"« {demande} » ne partage ni mot, ni acronyme, ni "
                     f"troncature avec « {nom} » : rien ne permet de supposer "
                     f"la même société")

    return {
        "ticker": ticker, "niveau": niveau.value, "motif": motif,
        "nom_demande_au_fournisseur": demande,
        "nom_du_referentiel": nom, "isin": isin, "ticker_fournisseur": idb,
        "concordance": (round(concordance(demande, nom), 4)
                        if demande and nom else None),
        "vise_un_autre_titre": (vise_un_autre_titre(ticker, demande)
                                if demande and nom else None),
    }


def autoriser_ecriture(ticker: str, identite_recue: str | None = None) -> dict:
    """Le collecteur a-t-il le droit d'écrire l'historique de ce titre ?

    `identite_recue` est le nom ou le code que le FOURNISSEUR a réellement
    renvoyé. C'est le seul contrôle qui protège vraiment : une table peut être
    cohérente avec elle-même et fausse.

    ⚠️ Le refus porte sur l'ÉCRITURE, pas sur la lecture. Rien n'empêche
    d'interroger le fournisseur et d'examiner ce qu'il renvoie ; ce qui est
    interdit, c'est de le déverser dans un fichier au nom d'un titre dont
    l'identité n'est pas établie.
    """
    e = etat(ticker)

    if e["niveau"] == Identite.DESACCORD_DE_FOND.value:
        return {"autorise": False, "ticker": ticker,
                "motif": f"DÉSACCORD DE FOND — {e['motif']}",
                "quoi_faire": "confronter à une réponse de fournisseur. Le nom "
                              "demandé peut désigner une société réelle absente "
                              "de notre référentiel — le fournisseur renverrait "
                              "alors SES cours.",
                "etat": e}

    if e["niveau"] == Identite.COLLISION.value:
        return {"autorise": False, "ticker": ticker,
                "motif": f"COLLISION D'IDENTITÉ — {e['motif']}",
                "quoi_faire": "confronter le titre à une réponse de "
                              "fournisseur et trancher AVANT toute écriture ; "
                              "ne pas remplacer la chaîne par un nom supposé",
                "etat": e}

    if e["niveau"] == Identite.INCONNUE.value:
        return {"autorise": False, "ticker": ticker,
                "motif": f"identité inconnue — {e['motif']}", "etat": e,
                "quoi_faire": "inscrire le titre au référentiel"}

    if identite_recue is None:
        return {"autorise": False, "ticker": ticker,
                "motif": "le fournisseur n'a renvoyé aucune identité "
                         "vérifiable avec ces données",
                "quoi_faire": "exiger de la source un nom ou un code "
                              "identifiant l'instrument, et le comparer",
                "etat": e}

    # ── UNE RESSEMBLANCE N'AUTORISE RIEN ────────────────────────────────────
    # ⚠️ DÉFAUT CORRIGÉ, RELEVÉ PAR LA REVUE. Cette fonction autorisait dès que
    # la concordance dépassait le seuil. Or « Crédit du Maroc » et « Crédit
    # Eqdom » partagent le mot « Crédit » : concordance 50 %, au-dessus du
    # seuil de 34 %. Le collecteur aurait donc accepté, pour CDM, les cours
    # d'Eqdom — et réciproquement. C'est exactement le défaut qu'on prétendait
    # empêcher, reproduit par le contrôle censé l'empêcher.
    #
    # L'autorisation repose désormais sur une PREUVE EXACTE, jamais sur une
    # distance entre chaînes :
    #     · un identifiant fournisseur qui correspond exactement ;
    #     · un ISIN qui correspond ;
    #     · un alias exact, documenté et non ambigu.
    # Une ressemblance conduit à une VÉRIFICATION, pas à une autorisation.
    attendu = e["nom_du_referentiel"] or ""
    recu = (identite_recue or "").strip()
    c = concordance(recu, attendu)

    codes = {x.upper() for x in
             ((e["ticker_fournisseur"] or ""), ticker) if x}
    if recu.upper() in codes:
        return {"autorise": True, "ticker": ticker, "preuve": "identifiant",
                "motif": f"identifiant fournisseur « {recu} » reconnu",
                "etat": e}

    isin = (e["isin"] or "").upper()
    if isin and recu.upper().replace(" ", "") == isin:
        return {"autorise": True, "ticker": ticker, "preuve": "ISIN",
                "motif": f"ISIN « {recu} » concordant", "etat": e}

    al = ALIAS_EXACTS.get(ticker)
    if al and _ascii(recu) == _ascii(al["alias"]):
        return {"autorise": True, "ticker": ticker, "preuve": "alias documenté",
                "motif": f"alias exact « {al['alias'] }» — {al['source']}",
                "etat": e}

    if _ascii(recu) and _ascii(recu) == _ascii(attendu):
        return {"autorise": True, "ticker": ticker, "preuve": "nom exact",
                "motif": f"nom reçu identique au référentiel : « {recu} »",
                "etat": e}

    # ── À partir d'ici, rien n'est prouvé. Deux refus, deux messages. ───────
    autre = vise_un_autre_titre(ticker, recu)
    if autre:
        v = autre["vise"][0]
        return {"autorise": False, "ticker": ticker,
                "motif": f"LE FOURNISSEUR A RENVOYÉ UNE AUTRE ENTREPRISE : "
                         f"« {recu} » désigne {v['ticker']} — « {v['nom']} » — "
                         f"et non « {attendu} »",
                "quoi_faire": "ne rien écrire. C'est le défaut qui a fait "
                              "porter à MSA les cours de Mutandis pendant cinq "
                              "semaines.",
                "etat": e}

    return {"autorise": False, "ticker": ticker,
            "motif": f"identité NON PROUVÉE : « {recu} » ne correspond ni à un "
                     f"identifiant fournisseur, ni à un ISIN, ni à un alias "
                     f"documenté, ni exactement à « {attendu} » "
                     f"(ressemblance {c:.0%}, qui ne prouve rien)",
            "quoi_faire": "vérifier l'identité auprès de la source, puis "
                          "documenter un alias exact si elle se confirme. "
                          "⚠️ Une ressemblance appelle une vérification, jamais "
                          "une autorisation.",
            "etat": e}


def inventaire() -> dict:
    tickers = sorted(set(manual_map()) | set(getattr(cfg, "COMPANY_NAMES", {})))
    etats = [etat(t) for t in tickers]
    from collections import Counter
    return {
        "_quoi": "État du contrat d'identité, titre par titre.",
        "_ce_qui_n_est_pas_etabli": (
            "⚠️ AUCUNE identité n'est aujourd'hui « vérifiée » : le dépôt ne "
            "conserve aucune réponse de fournisseur. « Non confrontée » est "
            "donc l'état normal, et il ne vaut PAS approbation."),
        "seuil_de_desaccord": SEUIL_DESACCORD,
        "titres": len(etats),
        "par_niveau": dict(Counter(e["niveau"] for e in etats)),
        "collisions": [e for e in etats
                       if e["niveau"] == Identite.COLLISION.value],
        "desaccords_de_fond": [e for e in etats
                               if e["niveau"] == Identite.DESACCORD_DE_FOND.value],
        "desaccords_de_forme": [e for e in etats
                                if e["niveau"] == Identite.DESACCORD_DE_FORME.value],
        "etats": etats,
    }


def rendre(inv: dict) -> str:
    L = ["# Contrat d'identité — à qui appartiennent les cours écrits ?",
         "",
         "> ⚠️ **Généré** par `pipeline/identites.py`.",
         "",
         "## Pourquoi ce contrôle existe",
         "",
         "MSA a porté les cours de **Mutandis** pendant cinq semaines — "
         "18 clôtures identiques au centime sur les dates comparables.",
         "",
         "**Aucun contrôle portant sur les nombres ne pouvait l'attraper.** Les "
         "cours de Mutandis sont valides : invariant OHLC respecté, variation "
         "dans les limites, série continue. Ils appartiennent simplement à une "
         "autre entreprise. C'est un défaut d'**identité**.",
         "",
         "## Les trois sources qui doivent s'accorder", "",
         "| Source | Ce qu'elle dit |", "|---|---|",
         "| `bvc_config.py` | notre référentiel : ISIN, nom, ticker fournisseur |",
         "| `MANUAL_MAP` | le nom que le collecteur **demande** |",
         "| la réponse reçue | l'identité que le fournisseur **renvoie** |",
         "",
         "Les deux premières se vérifient hors ligne. **Seule la troisième "
         "protège vraiment** : une table peut être cohérente avec elle-même et "
         "fausse.",
         "", "## État mesuré", "",
         f"**{inv['titres']} titres examinés.**", "",
         "| Niveau | Titres |", "|---|--:|"]
    for n, c in sorted(inv["par_niveau"].items(), key=lambda x: -x[1]):
        L.append(f"| {n} | {c} |")
    L += ["", inv["_ce_qui_n_est_pas_etabli"], ""]

    if inv["collisions"]:
        L += ["## ⚠️ Collisions d'identité — écriture REFUSÉE", "",
              "Le nom demandé désigne **mieux un autre titre** du référentiel. "
              "C'est le seul signal qui compte : le fournisseur renverra les "
              "cours de cette autre société.", "",
              "| Ticker | Le collecteur demande | Le référentiel dit | Désigne plutôt |",
              "|---|---|---|---|"]
        for e in inv["collisions"]:
            v = e["vise_un_autre_titre"]["vise"][0]
            L.append(f"| **{e['ticker']}** | `{e['nom_demande_au_fournisseur']}` | "
                     f"{e['nom_du_referentiel']} | **{v['ticker']}** — "
                     f"{v['nom']} ({v['concordance']:.0%}) |")
        L += ["",
              "⚠️ **Ne pas remplacer ces chaînes par un nom supposé exact.** "
              "C'est ainsi que le défaut a été introduit : en juin 2026, cinq "
              "entrées ont été « corrigées » depuis des noms jugés corrects, et "
              "l'une d'elles contredit notre propre référentiel. Une identité "
              "s'établit contre la **réponse du fournisseur**.", ""]

    if inv["desaccords_de_fond"]:
        L += ["## ⚠️ Désaccords de fond — écriture REFUSÉE", "",
              "Le nom demandé ne partage **ni mot, ni acronyme, ni troncature** "
              "avec le nôtre. Il peut désigner une société réelle absente de "
              "notre référentiel : le fournisseur renverrait alors **ses** "
              "cours.", "",
              "| Ticker | Le collecteur demande | Le référentiel dit |",
              "|---|---|---|"]
        for e in inv["desaccords_de_fond"]:
            L.append(f"| **{e['ticker']}** | `{e['nom_demande_au_fournisseur']}` | "
                     f"{e['nom_du_referentiel']} |")
        L += ["",
              "⚠️ Certains peuvent être des **noms commerciaux légitimes** — "
              "« Maroc Telecom » pour Itissalat Al-Maghrib en est un. Le "
              "contrôle ne sait pas les distinguer d'une vraie substitution, et "
              "il ne doit pas : dans le doute, il refuse et demande la "
              "confrontation. Un faux refus se lève en une vérification ; une "
              "fausse écriture reste cinq semaines dans l'historique.", ""]

    if inv["desaccords_de_forme"]:
        L += [f"## Désaccords de forme — {len(inv['desaccords_de_forme'])} titres",
              "",
              "Le nom demandé s'écrit autrement mais **ne désigne aucun autre "
              "titre** du référentiel : abréviations et noms commerciaux. "
              "L'écriture n'est pas refusée pour ce motif seul.", "",
              "| Ticker | Demandé | Référentiel |", "|---|---|---|"]
        for e in inv["desaccords_de_forme"]:
            L.append(f"| {e['ticker']} | `{e['nom_demande_au_fournisseur']}` | "
                     f"{e['nom_du_referentiel']} |")
        L += ["",
              "⚠️ Une version antérieure de ce contrôle les classait tous comme "
              "contradictoires — vingt titres signalés, dont « BOA » pour Bank "
              "of Africa. Un contrôle qui crie au loup vingt fois n'est plus "
              "lu la vingt-et-unième.", ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ecrire", action="store_true")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    inv = inventaire()
    if a.json:
        a.json.write_text(json.dumps(inv, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    if a.ecrire:
        CIBLE.parent.mkdir(parents=True, exist_ok=True)
        CIBLE.write_text(rendre(inv) + "\n", encoding="utf-8")
        print(f"→ {CIBLE.relative_to(RACINE)}")
    print(rendre(inv))


if __name__ == "__main__":
    main()

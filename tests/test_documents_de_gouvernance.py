#!/usr/bin/env python3
"""Un document qui dit l'état des données doit dire le VRAI état des données.

CE QUI EST ARRIVÉ LE 16/09/2026
───────────────────────────────
Un audit externe a conclu que la correction des 22 séances de Marsa Maroc
n'était « pas démontrée par le résultat publié », et que MSA restait un « point
de gouvernance ambigu ».

Il avait tort sur le fait, et raison sur la cause.

Tort sur le fait : la correction EST dans les indicateurs servis. La preuve
tient en un chiffre — la MA200 publiée vaut 874,52 ; recalculée
indépendamment, la série CORRIGÉE en donne 873,97 et la série NON corrigée
808,57. Une MA200 à 874 ne peut pas sortir d'une série qui en donnerait 808.

Raison sur la cause : `docs/LOT_MSA_22.md` affirmait encore, noir sur blanc,
« candidat vérifié, NON APPLIQUÉ aux données servies ». Le lot avait été reçu
et appliqué le 15/09 ; la phrase, elle, n'avait pas suivi. L'auditeur l'a lue
et l'a crue — il a eu raison de la croire.

**Un document de gouvernance qui ne suit pas l'état des données est pire qu'un
document absent.** Absent, on va voir les données. Présent et faux, on s'arrête
à ce qu'il dit.

LA RÈGLE
────────
Un ticker qui possède un fichier dans `datasets/corrections_acceptees/` est un
ticker dont les corrections sont APPLIQUÉES — c'est la définition même de ce
dossier, qui INSTRUIT là où `historiques_candidats/` PROPOSE. Aucun document du
dépôt ne peut donc le déclarer non appliqué.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
DOCS = RACINE / "docs"
ACCEPTEES = RACINE / "datasets" / "corrections_acceptees"

# Les tournures qui affirment qu'une correction n'a pas atteint la production.
# ⚠️ Elles se cherchent sur le texte accentué ET sans accent : « applique » et
# « appliqué » doivent tomber pareil.
NON_APPLIQUE = re.compile(
    r"non\s+appliqu\w*\s+aux\s+donn\w*\s+servies"
    r"|candidat\s+v\w*rifi\w*,\s*non\s+appliqu",
    re.IGNORECASE)


def _tickers_appliques() -> set[str]:
    if not ACCEPTEES.is_dir():
        return set()
    return {f.stem for f in ACCEPTEES.glob("*.json")}


def test_aucun_document_ne_declare_non_applique_un_lot_qui_l_est():
    """La règle, et elle vaut pour tous les lots — pas seulement MSA.

    ⚠️ Ce contrôle ne regarde pas SI la phrase existe quelque part : il regarde
    si elle existe dans un document QUI PARLE D'UN TICKER DÉJÀ APPLIQUÉ. Un
    lot réellement en attente a parfaitement le droit de se dire en attente.
    """
    appliques = _tickers_appliques()
    assert appliques, "aucune correction acceptée : le contrôle n'aurait rien à dire"

    fautifs = []
    for doc in sorted(DOCS.rglob("*.md")) if DOCS.is_dir() else []:
        texte = doc.read_text(encoding="utf-8")
        for m in NON_APPLIQUE.finditer(texte):
            # De quel ticker ce document parle-t-il ? On ne retient que les
            # codes cités en toutes lettres, pour ne pas accuser un document
            # générique.
            cites = {t for t in appliques
                     if re.search(rf"\b{re.escape(t)}\b", texte)}
            # La phrase peut être une CITATION de l'erreur passée : un passage
            # qui l'encadre d'un ⚠️ et explique qu'elle était fausse est une
            # mise en garde, pas une affirmation.
            avant = texte[max(0, m.start() - 400):m.start()]
            if "⚠️" in avant and re.search(r"contrair|erreur|induit", avant, re.I):
                continue
            if cites:
                fautifs.append(f"{doc.relative_to(RACINE)} → {sorted(cites)}")
    assert not fautifs, (
        "ces documents déclarent non appliqué un lot qui EST appliqué — c'est "
        "ce qui a induit l'audit du 16/09 en erreur :\n  " + "\n  ".join(fautifs))


def test_le_dossier_des_corrections_acceptees_dit_qu_il_instruit():
    """`corrections_acceptees/` INSTRUIT, `historiques_candidats/` PROPOSE.

    C'est la distinction qui donne son sens au test précédent. Si un fichier de
    ce dossier se présentait comme un signalement, « appliqué » ne voudrait
    plus rien dire.
    """
    import json
    for f in sorted(ACCEPTEES.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        statut = str(d.get("_statut") or "")
        assert "instruction" in statut.lower(), (
            f"{f.name} : statut « {statut} » — un fichier de ce dossier "
            "instruit, il ne signale pas")


@pytest.mark.parametrize("ticker", ["MSA"])
def test_les_corrections_de_msa_sont_dans_la_serie_publiee(ticker):
    """⚠️ LE CONTRÔLE QUI TRANCHE, et qui ne dépend d'aucun document.

    On relit les chandelles servies et on vérifie que les valeurs y sont celles
    du lot reçu, pas celles qu'il remplace. Aucune prose ne peut mentir à ce
    test.
    """
    import json
    lot = json.loads((ACCEPTEES / f"{ticker}.json").read_text(encoding="utf-8"))
    serie = {b["d"]: b for b in json.loads(
        (RACINE / "pipeline" / "candles" / f"{ticker}.json")
        .read_text(encoding="utf-8"))}

    corrigees, restantes = 0, []
    for ligne in lot["lignes"]:
        b = serie.get(ligne["d"])
        if b is None:
            continue
        attendu = ligne.get("corrige") or {}
        remplace = ligne.get("remplace") or {}
        for champ, valeur in attendu.items():
            if b.get(champ) == valeur:
                corrigees += 1
            elif champ in remplace and b.get(champ) == remplace[champ]:
                restantes.append(f"{ligne['d']}.{champ}")
    assert corrigees > 0, f"aucune valeur corrigée trouvée dans la série de {ticker}"
    assert not restantes, (
        f"{len(restantes)} valeurs sont restées celles d'AVANT la correction : "
        f"{restantes[:6]}")

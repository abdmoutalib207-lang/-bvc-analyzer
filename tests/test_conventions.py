#!/usr/bin/env python3
"""Ce que le flux déclare sur ses propres calculs doit être vrai.

⚠️ D'OÙ VIENT CE FICHIER
────────────────────────
Un recoupement avec une source extérieure a donné, sur la moyenne 20 séances
d'un titre, **414,49 contre 416,22**. Ni l'un ni l'autre n'était faux : elle
exclut la séance du jour de sa moyenne, nous l'incluons.

    nos 20 dernières clôtures        414,49
    les 20 clôtures SANS le jour     416,21   ← la source disait 416,22

Un centime. Deux conventions légitimes, et aucune écrite nulle part — il a
fallu chercher l'écart, et pendant ce temps il ressemblait à une erreur de
données.

⚠️ UNE CONVENTION DÉCLARÉE MAIS FAUSSE EST PIRE QUE PAS DE CONVENTION
Elle donne au lecteur extérieur une clé de lecture erronée, et le fait
conclure à une divergence de chiffres là où il n'y a qu'un malentendu — ou
l'inverse. D'où ces tests : ils ne vérifient pas que le bloc existe, ils
vérifient que **ce qu'il affirme correspond au code**.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))


@pytest.fixture(scope="module")
def flux():
    f = RACINE / "data.json"
    if not f.exists():
        pytest.skip("data.json absent de ce clone")
    return json.loads(f.read_text(encoding="utf-8"))


def test_le_flux_declare_ses_conventions(flux):
    c = flux.get("_conventions")
    assert c, "le flux ne dit pas comment ses chiffres sont calculés"
    for champ in ("moyennes_mobiles", "rsi", "macd", "adx",
                  "seances_retenues", "volume"):
        assert c.get(champ), f"convention manquante : {champ}"


# ── ⚠️ Ce qui est déclaré doit être ce qui est fait ────────────────────────

def test_la_moyenne_declaree_inclut_bien_la_seance_du_jour(flux):
    """LE TEST QUI COMPTE. Le bloc affirme « séance du jour INCLUSE » ; c'est
    exactement ce point qui a produit l'écart avec la source extérieure. S'il
    devenait faux, le lecteur serait trompé avec notre bénédiction."""
    import pandas as pd
    from update_data import calc_ma

    closes = pd.Series([10.0] * 19 + [110.0])   # 19 séances à 10, la 20e à 110
    # Moyenne des 20 DERNIÈRES, jour inclus : (19×10 + 110) / 20 = 15,0
    # Si le jour était exclu, on obtiendrait 10,0 — calculé à la main.
    assert calc_ma(closes, 20) == 15.0, (
        "la moyenne n'inclut plus la séance du jour, alors que le flux le "
        "déclare")


def test_une_periode_non_atteinte_ne_rend_pas_une_moyenne_partielle(flux):
    """Le bloc dit « jamais une moyenne sur ce qu'on a ». Trente-deux titres
    affichaient une MA200 calculée sur 52 à 166 séances avant le 15/09."""
    import pandas as pd
    from update_data import calc_ma
    assert calc_ma(pd.Series([10.0] * 30), 200) is None


def test_la_convention_de_volume_est_celle_qui_est_appliquee(flux):
    """Le bloc dit « un NOMBRE DE TITRES, jamais un montant ». Un titre
    réceptionné doit donc porter des volumes de l'ordre des quantités, pas des
    dirhams — l'écart entre les deux est d'un facteur mille au moins."""
    receptions = RACINE / "datasets" / "historiques_importes"
    if not (receptions / "ADI.json").exists():
        pytest.skip("aucune réception ADI dans ce clone")
    serie = json.loads((RACINE / "pipeline" / "candles" / "ADI.json")
                       .read_text(encoding="utf-8"))
    volumes = [b["v"] for b in serie[-60:] if b.get("v")]
    assert volumes and max(volumes) < 100000, (
        "ADI est réceptionné mais ses volumes gardent l'ordre de grandeur "
        "d'un montant en dirhams")


def test_les_seances_exclues_le_sont_vraiment(flux):
    """Le bloc annonce que les jours sans cotation et les séances annulées
    sont hors des fenêtres de calcul. Il doit être vrai dans les séries."""
    from bvc_config import SEANCES_ANNULEES, SEANCES_SANS_COTATION
    exclues = set(SEANCES_ANNULEES) | set(SEANCES_SANS_COTATION)
    dossier = RACINE / "pipeline" / "candles"
    if not dossier.exists():
        pytest.skip("pas de chandelles dans ce clone")
    porteurs = []
    for f in sorted(dossier.glob("*.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if any(str(b.get("d") or "")[:10] in exclues for b in s):
            porteurs.append(f.stem)
    assert not porteurs, (
        f"le flux annonce ces séances exclues, {len(porteurs)} séries les "
        f"portent encore : {porteurs[:5]}")


def test_le_bloc_dit_pourquoi_il_existe(flux):
    """⚠️ Sans cette phrase, le bloc se lit comme de la documentation
    décorative et finira par ne plus être tenu à jour. Il porte une raison
    d'être : permettre un recoupement extérieur honnête."""
    assert "recoupement" in (flux["_conventions"].get("_pourquoi") or "").lower()

#!/usr/bin/env python3
"""Un volume se mesure en dirhams, pas en titres.

⚠️ CE QUE CES TESTS DÉFENDENT
─────────────────────────────
Le plafond de liquidité comptait des TITRES. Or un titre n'est pas une unité
comparable d'une société à l'autre :

    10 titres de CMT à 3 567 DH  =  35 670 DH
    10 titres d'ADH  à    37 DH  =     370 DH

Le même seuil traitait les deux identiquement. Mesuré sur la livraison du
24/09/2026, il ne frappait que **7 titres** alors que **27 échangeaient moins
de 100 000 DH par séance** — et il en laissait deux à 5 sur 5 :

    SRM   6 224 DH par séance — et c'est un MASI 1
    MIC  31 872 DH par séance

Une étude externe de la liquidité de la cote, conduite indépendamment et sur
six critères, compte 32 titres sous 100 kMAD d'ADTV. Le même ordre de
grandeur, par une autre voie.

⚠️ CE QUE LE PLAFOND DIT, ET CE QU'IL NE DIT PAS
Il ne dit pas « cette donnée est fausse ». Il dit « ce signal n'est pas
actionnable » : sur un titre qui échange six mille dirhams par séance, un ordre
de taille normale déplace le cours à lui seul. La nuance est celle entre « je
ne sais pas » et « vous ne pourrez pas », et c'est pourquoi le plafond est à 2
et non à 0.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))


def _serie(volumes, cours):
    import pandas as pd
    return pd.DataFrame({"v": volumes, "c": cours})


# ── ⚠️ La mesure elle-même ─────────────────────────────────────────────────

def test_le_montant_est_le_produit_du_volume_et_du_cours():
    from update_data import _echange_median_dh
    # 10 titres à 100 DH sur 20 séances → 1 000 DH, calculé à la main
    assert _echange_median_dh(_serie([10] * 20, [100.0] * 20)) == 1000.0


def test_deux_titres_au_meme_volume_ne_pesent_pas_pareil():
    """⚠️ LA RAISON D'ÊTRE DU MODULE. Dix titres de CMT et dix titres d'Addoha
    ne sont pas la même activité — un seuil en titres les confondait."""
    from update_data import _echange_median_dh
    cher = _echange_median_dh(_serie([10] * 20, [3567.0] * 20))
    bon_marche = _echange_median_dh(_serie([10] * 20, [37.0] * 20))
    assert cher > bon_marche * 90, "le seuil doit séparer ces deux cas"


def test_le_produit_se_fait_seance_par_seance_avant_la_mediane():
    """⚠️ Sinon l'activité passée serait réévaluée au prix d'aujourd'hui.

    Un titre qui échangeait 100 titres à 10 DH puis 10 titres à 100 DH a
    toujours échangé 1 000 DH par séance. Prendre la médiane des volumes
    (55) fois le dernier cours (100) donnerait 5 500 — faux d'un facteur 5.
    """
    from update_data import _echange_median_dh
    v = [100] * 10 + [10] * 10
    c = [10.0] * 10 + [100.0] * 10
    assert _echange_median_dh(_serie(v, c)) == 1000.0


def test_la_mediane_et_non_la_moyenne():
    """Une seule séance animée sur un titre mort ne doit pas le réhabiliter.
    Médiane de dix-neuf séances à 1 000 DH et d'une à un million : 1 000."""
    from update_data import _echange_median_dh
    v = [10] * 19 + [10000]
    c = [100.0] * 20
    assert _echange_median_dh(_serie(v, c)) == 1000.0


def test_une_serie_absente_ou_vide_rend_none():
    """⚠️ `None` signifie « on ne sait pas » et déclenche le repli en titres.
    Rendre 0 ferait passer une série manquante pour un titre mort."""
    from update_data import _echange_median_dh
    assert _echange_median_dh(None) is None
    assert _echange_median_dh(_serie([], [])) is None


# ── ⚠️ Le plafond appliqué ─────────────────────────────────────────────────

def test_le_plafond_est_bien_en_dirhams_dans_le_moteur():
    """⚠️ Une mesure juste qui n'est branchée nulle part ne protège rien.
    Lu par l'AST, pas à la ligne : le fichier CITE le seuil en titres dans ses
    commentaires pour expliquer pourquoi il a changé."""
    import ast
    arbre = ast.parse((RACINE / "update_data.py").read_text(encoding="utf-8"))
    appels = {n.func.id for n in ast.walk(arbre)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_echange_median_dh" in appels, (
        "le moteur ne calcule pas le montant échangé — le plafond est resté "
        "en titres")


def test_le_seuil_vaut_cent_mille_dirhams():
    """Ce n'est pas un chiffre rond choisi pour sa forme : c'est celui d'une
    étude externe de la liquidité de la cote, et il sépare les titres sur
    lesquels un ordre de taille normale passe de ceux où il déplace le cours."""
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert "echange_dh < 100_000" in src


def test_le_repli_en_titres_subsiste_quand_le_montant_manque():
    """⚠️ Un titre dont on n'a pas les cours ne doit pas échapper au plafond.
    Mieux vaut une mesure grossière que pas de mesure."""
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert "elif echange_dh is None and vol_median is not None" in src


# ── Le flux publié ─────────────────────────────────────────────────────────

def test_tout_titre_sous_le_seuil_est_plafonne(flux_publie=None):
    """⚠️ LE CONTRÔLE SUR LA LIVRAISON. Au 24/09, deux titres passaient à 5 sur
    5 avec moins de 100 000 DH échangés — dont SRM, un MASI 1, à 6 224 DH."""
    import json
    chemin = RACINE / "data.json"
    if not chemin.exists():
        pytest.skip("data.json absent de ce clone")
    t = json.loads(chemin.read_text(encoding="utf-8")).get("tickers") or []
    fautifs = []
    for x in t:
        m = x.get("_meta") or {}
        dh, conf = m.get("echange_median_dh"), m.get("confidence")
        if dh is not None and dh < 100_000 and (conf or 0) > 2:
            fautifs.append(f"{x.get('symbol')} — {dh:,.0f} DH, confiance {conf}")
    assert not fautifs, (
        "des titres peu liquides gardent une confiance élevée : "
        + " ; ".join(fautifs[:5]))


def test_le_montant_echange_est_publie():
    """Un seuil qu'on ne peut pas vérifier ne se discute pas."""
    import json
    chemin = RACINE / "data.json"
    if not chemin.exists():
        pytest.skip("data.json absent de ce clone")
    t = json.loads(chemin.read_text(encoding="utf-8")).get("tickers") or []
    avec = [x for x in t if (x.get("_meta") or {}).get("echange_median_dh") is not None]
    assert len(avec) >= len(t) * 0.8, (
        f"seulement {len(avec)}/{len(t)} titres publient leur montant échangé")

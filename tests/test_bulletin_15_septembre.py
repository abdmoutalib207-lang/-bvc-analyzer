#!/usr/bin/env python3
"""La séance du 15/09 confrontée au bulletin, après une journée de corrections.

⚠️ LE CONTRÔLE QUI COMPTAIT
───────────────────────────
Le 15/09/2026, seize titres ont vu leur historique corrigé — environ 800
séances. Deux contaminations d'identité (Ciments du Maroc portait Minière
Touissit, Sonasid portait Stokvis), une échelle vingt-trois fois trop basse sur
Sothema, un fractionnement jamais répercuté sur HPS, et des dizaines de cours
rediffusés.

Le bulletin de l'opérateur, reçu le soir même, concorde : 65 titres comparés,
zéro écart, et les SEIZE titres corrigés tombent au centime.

⚠️ CE QUE CELA NE PROUVE PAS
Les corrections portent sur l'HISTORIQUE, pas sur la séance du jour. Cette
concordance dit que rien n'a été cassé au passage — elle ne valide aucune des
800 séances corrigées, qui reposent sur les exports de l'opérateur et non sur
ce bulletin.

⚠️ Et ce n'est toujours pas un contrôle extérieur au fournisseur : nos cours
viennent majoritairement de CDG, même éditeur que ce bulletin.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

BULLETIN = RACINE / "pipeline" / "bulletins" / "CDG_indices_2026-09-15.pdf"
SEANCE = "2026-09-15"
SHA256 = "17407897b768d5547c9eec696740771adaddc7169ea83d33261b1d60877f4afa"

pytest.importorskip(
    "pdfplumber",
    reason="déclarée dans requirements.txt, donc présente en CI ; absente, ce "
           "test s'abstient plutôt que de faire échouer une suite locale")


@pytest.fixture(scope="module")
def cotations():
    from parse_cdg_bulletin import parse_cotations
    return parse_cotations(BULLETIN)


def test_la_piece_jointe_est_bien_celle_qui_a_ete_mesuree():
    assert BULLETIN.exists()
    assert hashlib.sha256(BULLETIN.read_bytes()).hexdigest() == SHA256


def test_la_seance_du_15_concorde_avec_nos_chandelles(cotations):
    """⚠️ Le nombre de comparaisons est exigé, pas seulement le nombre
    d'écarts : « 0 écart » sur 0 titre comparé serait une preuve apparente."""
    from parse_cdg_bulletin import comparer
    ecarts, etat = comparer(cotations, SEANCE)
    assert etat["titres_compares"] >= 60, f"seulement {etat['titres_compares']} comparés"
    assert ecarts == [], f"écarts : {ecarts[:5]}"
    assert etat["verdict"] == "CONCORDANCE"


def test_le_controle_discrimine_les_autres_seances(cotations):
    """⚠️ Un comparateur qui concorderait avec n'importe quelle date ne
    daterait rien. Contre le 14/09 et le 11/09, il doit massivement diverger."""
    from parse_cdg_bulletin import comparer
    for autre in ("2026-09-14", "2026-09-11"):
        ecarts, etat = comparer(cotations, autre)
        assert etat["titres_compares"] >= 40
        assert etat["verdict"] == "DISCORDANCE"
        assert len(ecarts) > etat["titres_compares"] / 2, (
            f"le bulletin concorde aussi avec le {autre}")


def test_les_seize_titres_corriges_tombent_au_centime(cotations):
    """⚠️ LE CONTRÔLE QUI COMPTAIT. Après ~800 séances corrigées dans la
    journée, chaque titre touché doit encore coter juste."""
    from parse_cdg_bulletin import vers_nos_tickers
    chez_nous = vers_nos_tickers(cotations)
    corriges = sorted(f.stem for f in
                      (RACINE / "datasets" / "corrections_acceptees").glob("*.json"))
    assert len(corriges) >= 16
    verifies = []
    for t in corriges:
        v = chez_nous.get(t)
        if not v or not v["cours"]:
            continue                      # non coté ce jour-là — CMT, suspendue
        f = RACINE / "pipeline" / "candles" / f"{t}.json"
        b = {x["d"]: x for x in json.loads(f.read_text(encoding="utf-8"))}.get(SEANCE)
        assert b is not None, f"{t} : séance du 15/09 absente de la série"
        assert abs(b["c"] / v["cours"] - 1) < 0.001, (
            f"{t} : nous {b['c']}, bulletin {v['cours']}")
        verifies.append(t)
    assert len(verifies) >= 15, f"seulement {len(verifies)} titres corrigés vérifiés"


def test_cmt_n_a_toujours_pas_cote(cotations):
    """Quatrième bulletin consécutif : tout à zéro, sans heure d'échange."""
    cmt = cotations["CMT"]
    assert cmt["cours"] == 0.0 and cmt["qte"] == 0
    assert not cmt["heure"].startswith(("0", "1", "2"))


def test_le_titre_du_bulletin_porte_ici_la_date_de_la_seance():
    """⚠️ DEUXIÈME CONTRE-EXEMPLE, ET PAS UNE RÈGLE POUR AUTANT.

    « Indices du mardi 15 septembre » contient la séance du mardi 15, comme
    celui du 14. La formulation d'origine — « le titre porte la date de
    publication » — tenait sur le bulletin du 9 septembre, qui décrivait la
    séance du 8. Deux observations contre une ne font pas une règle inverse :
    le dossier doit continuer d'interdire la déduction dans les DEUX sens.
    """
    txt = (RACINE / "pipeline" / "bulletins" / "LISEZ-MOI.txt").read_text(encoding="utf-8")
    assert "dans un sens ni dans l'autre" in txt
    assert "ne font pas une règle inverse" in txt


def test_ce_que_le_dossier_ne_pretend_pas_est_ecrit():
    """⚠️ La concordance du jour ne valide pas les 800 séances corrigées. Le
    dossier doit le dire, sans quoi il se lira comme une validation."""
    txt = (RACINE / "pipeline" / "bulletins" / "LISEZ-MOI.txt").read_text(encoding="utf-8")
    assert "elle ne valide aucune des 800 séances corrigées" in txt

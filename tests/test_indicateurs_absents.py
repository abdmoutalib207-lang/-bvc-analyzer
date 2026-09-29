"""Un indicateur sans historique est ABSENT, jamais inventé — 30/09/2026.

Relevé le 29/09 : cinq titres (SAF, SLM, MDP, DLM, DIS) publiaient un RSI de
50, une MA20 égale au cours ou à un ancien cours, et des extrêmes 90 jours à
cours × 1,15 et × 0,85. `calc_score_tech` les lisait comme des mesures :
Sanlam obtenait 7,2 en technique (RSI « sain » +1, cours « au-dessus de sa
moyenne » +0,8, position « médiane » +0,4) sur sept séances d'historique.

Le mécanisme le plus sournois : un repli recopiait les indicateurs du
data.json précédent, qui les avait lui-même recopiés — une valeur figée se
reconduisait de run en run.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
MOTEUR = re.sub(r"#.*", "", (RACINE / "update_data.py").read_text(encoding="utf-8"))
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("motif", [
    r"\*\s*1\.15", r"\*\s*0\.85",                 # extrêmes 90 j inventés
    r'get\("rsi",\s*50\)', r"rsi\s*=\s*50\b",     # RSI inventé
    r"ma20\s*=\s*price\b", r'get\("ma20",\s*price',
    r"or\s+price\b\s*$",                          # « MA = cours » en repli
])
def test_le_moteur_n_invente_plus_d_indicateur(motif):
    assert not re.search(motif, MOTEUR, flags=re.M), motif


def test_le_repli_du_run_precedent_ne_recopie_que_le_prix():
    brut = (RACINE / "update_data.py").read_text(encoding="utf-8")
    bloc = brut[brut.index("Fallback B : le data.json du run précédent"):
                brut.index("Fallback 3 : financial_data.json")]
    for champ in ("rsi", "ma20", "ma50", "h90", "l90", "macd", "stoch_k", "bb_upper"):
        assert f'ex_t.get("{champ}"' not in bloc, champ


def test_sans_aucune_mesure_la_note_technique_s_abstient():
    import update_data as u
    assert u.calc_score_tech(None, 100.0, None, None, None, None) == 5.0


def test_la_neutralisation_retire_au_lieu_d_inventer():
    import update_data as u
    r = u.neutraliser_si_isin_suspect("SOT", 360.0, 79.6, 1666.0, 1700.0, 1800.0, 1500.0)
    assert r == (None, None, None, None, None, True)


def test_la_note_lit_l_upside_publie():
    """SNA : objectif 540 DH pour un cours de 1 850, retiré de l'affichage
    comme périmé, mais qui pénalisait quand même la note."""
    appel = re.search(r"v53 = compute_v53\((.*?)\)\n", MOTEUR, flags=re.S).group(1)
    assert '_obj["upside"]' in appel and 'fd.get("upside")' not in appel


def test_le_terminal_n_affiche_plus_un_rsi_de_50_par_defaut():
    assert not re.search(r"rsi14\|\|50", SRC)
    assert "Math.max(0,value||50)" not in SRC

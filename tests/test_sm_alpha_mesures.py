"""SM~ et ALPHA : retirés de l'écran (28/10/2026), puis du moteur.

⚠️ 14/10/2026 : `alpha` 0,0 et `win` 0,5 étaient les défauts du corpus
WhatsApp (gelé au 02/07). Publiés, ils s'affichaient « +0 % » et « 50 » comme
des mesures : 61 et 46 titres sur 80. `alpha_mesure` / `win_mesure` les
écartaient. Le 28/10/2026 (retrait du pilier NLP, décision d'Abd Moutalib),
les colonnes sont retirées de l'écran (lot 1), puis les deux fonctions et la
table `SENTIMENT` du moteur (lot 2) : ce fichier garde les deux retraits.
"""
import logging
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
logging.disable(logging.CRITICAL)

import update_data as u  # noqa: E402


def test_le_moteur_ne_mesure_plus_ni_alpha_ni_sm():
    """Plus de table du corpus, plus de fonction qui la lise."""
    for nom in ("SENTIMENT", "alpha_mesure", "win_mesure"):
        assert not hasattr(u, nom), f"update_data.{nom} réapparaît"


def test_sm_et_alpha_ne_s_affichent_plus():
    """⚠️ RETOURNÉ LE 28/10/2026. Ce test exigeait que la légende dise « corpus
    WhatsApp gelé » ; les colonnes SM~ et ALPHA, la cellule « Alpha 12M » de
    la fiche et leur légende sont retirées avec le pilier NLP."""
    src = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    idx = (RACINE / "index.html").read_text(encoding="utf-8")
    for texte in (src, idx):
        assert "dérivé du score composite" not in texte
        assert "SM~" not in texte and "Alpha 12M" not in texte
        assert "corpus WhatsApp gel" not in texte

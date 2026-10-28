"""SM~ et ALPHA : une mesure du corpus, ou « — ». Jamais une valeur par défaut.

⚠️ 14/10/2026 : `alpha` 0,0 et `win` 0,5 sont les défauts du corpus WhatsApp
(gelé au 02/07). Publiés, ils s'affichaient « +0 % » et « 50 » comme des
mesures : 61 et 46 titres sur 80.
"""
import logging
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
logging.disable(logging.CRITICAL)

import update_data as u  # noqa: E402


def test_titre_absent_du_corpus():
    assert u.alpha_mesure("ZZZ_ABSENT", {"alpha": 0, "win": 0.5}) is None
    assert u.win_mesure("ZZZ_ABSENT", {"alpha": 0, "win": 0.5}) is None


def test_defauts_du_corpus_non_publies():
    t = next(iter(u.SENTIMENT))
    assert u.alpha_mesure(t, {"alpha": 0.0, "win": 0.5}) is None
    assert u.win_mesure(t, {"alpha": 0.0, "win": 0.5}) is None


def test_vraie_mesure_conservee():
    t = next(iter(u.SENTIMENT))
    assert u.alpha_mesure(t, {"alpha": 8.5, "win": 0.39}) == 8.5
    assert u.win_mesure(t, {"alpha": 8.5, "win": 0.39}) == 39


def test_sm_et_alpha_ne_s_affichent_plus():
    """⚠️ RETOURNÉ LE 28/10/2026. Ce test exigeait que la légende dise « corpus
    WhatsApp gelé » ; les colonnes SM~ et ALPHA, la cellule « Alpha 12M » de
    la fiche et leur légende sont retirées avec le pilier NLP. Les fonctions
    `alpha_mesure` / `win_mesure` restent dans le moteur jusqu'au lot 2."""
    src = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    idx = (RACINE / "index.html").read_text(encoding="utf-8")
    for texte in (src, idx):
        assert "dérivé du score composite" not in texte
        assert "SM~" not in texte and "Alpha 12M" not in texte
        assert "corpus WhatsApp gel" not in texte

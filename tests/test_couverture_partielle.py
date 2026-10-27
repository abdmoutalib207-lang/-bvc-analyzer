"""Règle de prudence PROVISOIRE (15/10/2026, accord d'Abd Moutalib) : sous
75 % de couverture applicable, la note reste publiée comme indicative mais
aucun verdict de palier n'est émis. Aucune note numérique n'est touchée."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def test_seuil_declare_comme_provisoire():
    import bvc_config
    assert bvc_config.COUVERTURE_VERDICT_MIN == 0.75
    assert "PROVISOIRE" in (RACINE / "bvc_config.py").read_text(encoding="utf-8")


def test_le_signal_seul_change():
    import update_data as U
    assert U._signal_publie("ZZZ", "ÉVITER FORT", None, None, couverture_partielle=True) == (
        "Couverture partielle", None)
    assert U._signal_publie("ZZZ", "ÉVITER FORT", None, None) == ("ÉVITER FORT", None)


def test_une_financiere_n_a_pas_de_critere_sans_objet_gratuit():
    """Dette/EBITDA ne s'applique pas à une banque, mais son équivalent
    (coût du risque, solvabilité) manque : c'est MANQUANT, pas sans objet."""
    from pipeline.smart_money import fond_score as F
    f = {"X": {"secteur": "Banque", "ratios_publies": {"roe_12m": {"valeur": 15}}}}
    b = F.detail_fond_score("X", f, per_publie=12, croissance_sourcee=True)["composantes"]["bilan"]
    assert b["note"] is None and "sans objet" not in b["motif"] and "non intégré" in b["motif"]


def test_terminal_sans_couleur_et_alertes_visibles():
    assert 'const couvPartielle=r=>!!r&&r.sig==="Couverture partielle";' in SRC
    assert "if(couvPartielle(r)||nonComparable(r))return null;" in SRC   # pas de couleur de palier
    assert "Couverture partielle — verdict global limité" in SRC
    assert 'className="alerte-verifiee"' in SRC

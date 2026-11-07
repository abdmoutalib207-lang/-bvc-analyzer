"""Règle de prudence PROVISOIRE (15/10/2026, accord d'Abd Moutalib) : sous
75 % de couverture applicable, la note reste publiée comme indicative mais
aucun verdict de palier n'est émis. Aucune note numérique n'est touchée.

⚠️ 06/11/2026 — retrait de la note v5.3 (lot 2) : le verdict « Couverture
partielle » et son seuil `COUVERTURE_VERDICT_MIN` partent avec le signal. La
couverture APPLICABLE reste publiée (`note_fond.couverture_applicable`). Tests
d'origine : archive/tests/test_couverture_partielle_lot2_2026-11-06.py."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def test_le_seuil_et_le_verdict_sont_retires():
    import bvc_config
    import update_data as U
    assert not hasattr(bvc_config, "COUVERTURE_VERDICT_MIN") and not hasattr(U, "_signal_publie")


def test_une_financiere_n_a_pas_de_critere_sans_objet_gratuit():
    """Dette/EBITDA ne s'applique pas à une banque, mais son équivalent
    (coût du risque, solvabilité) manque : c'est MANQUANT, pas sans objet."""
    from pipeline.smart_money import fond_score as F
    f = {"X": {"secteur": "Banque", "ratios_publies": {"roe_12m": {"valeur": 15}}}}
    b = F.detail_fond_score("X", f, per_publie=12, croissance_sourcee=True)["composantes"]["bilan"]
    assert b["note"] is None and "sans objet" not in b["motif"] and "non intégré" in b["motif"]


def test_terminal_sans_verdict_v53_et_alertes_visibles():
    """Jusqu'au 05/11/2026, le terminal lisait `sig == "Couverture partielle"`
    pour retirer la couleur de palier de la note v5.3. Le 06/11/2026, la note
    v5.3 quitte l'écran (décision d'Abd Moutalib) : le verdict partiel de la
    v5.3 n'y est plus affiché (et le moteur ne le publie plus depuis le
    lot 2). Le Score BVC a son propre état PARTIEL, affiché sans valeur ni
    couleur. Les alertes vérifiées restent visibles."""
    assert "couvPartielle" not in SRC and 'r.sig==="Couverture partielle"' not in SRC
    assert "Couverture partielle — verdict global limité" not in SRC
    assert 's&&s.etat==="PARTIEL"?"partiel":"non calculé"' in SRC      # PastilleBVC
    assert 'className="alerte-verifiee"' in SRC

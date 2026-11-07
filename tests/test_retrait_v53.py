"""Le producteur de la note v5.3 est retiré — 06/11/2026, lot 2.

Décision d'Abd Moutalib du 06/11/2026 : « l'ancien scoring doit disparaître ».
Le terminal affichait déjà le seul Score BVC (#325) ; le lot 1 (#326) a fait
passer au Score BVC tous les LECTEURS de la note v5.3. Ce lot retire le
PRODUCTEUR : `calc_score_tech`, `get_weights`, `compute_v53`, `_signal_publie`,
`_setup_technique`, `SCORE_VERSION`, `COUVERTURE_VERDICT_MIN`, et les champs
publiés `v53`, `sig`, `score_fond`, `score_tech`, `poids`, `bonus`, `setup`,
`verdict_plafonne`, `score_version`.

Trois familles, comme ailleurs dans la suite :
  1. le CODE ne produit plus ces champs (moteur, second pipeline, config) ;
  2. le fichier RÉGÉNÉRÉ par le code actuel ne les porte plus : voir
     `tests/test_audit_chaine.py::test_le_fichier_regenere_ne_porte_plus_la_note_v53`
     (même essai à blanc hors réseau, pour ne pas le refaire deux fois) ;
  3. le fichier PUBLIÉ (data.json du dépôt) : transition ⏳ ci-dessous.

Ce qui RESTE publié et dont dépendaient ces champs est vérifié ici aussi :
`_meta.confidence` (la règle « confiance ≤ 1 → Données insuffisantes » vit à
l'écran), `_meta.non_comparable`, `note_fond`, `note_fond_metier`,
`technique_neutralise`, `score_bvc`.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from conftest import chemin_data_json  # noqa: E402

CHAMPS_V53 = ("v53", "sig", "score_fond", "score_tech", "poids", "bonus", "setup",
              "verdict_plafonne", "score_version")
FONCTIONS_V53 = ("calc_score_tech", "get_weights", "compute_v53", "_signal_publie",
                 "_setup_technique")
TRANSITION = "⏳ À RETIRER APRÈS LE PREMIER RUN update_bvc SUIVANT LA FUSION DU LOT 2 (retrait v5.3)"


# ── 1. Le code ──────────────────────────────────────────────────────────────

def _cles_du_titre_publie(src: str) -> set[str]:
    """Les clés littérales du dictionnaire publié pour chaque titre."""
    cles = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Dict):
            k = {c.value for c in n.keys if isinstance(c, ast.Constant)}
            if {"symbol", "note_fond"} <= k or {"symbol", "note_fond_metier", "partial"} <= k:
                cles |= k
    return cles


def test_le_moteur_ne_publie_plus_aucun_champ_v53():
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    cles = _cles_du_titre_publie(src)
    assert {"symbol", "note_fond", "technique_neutralise", "_meta"} <= cles
    assert not set(CHAMPS_V53) & cles, set(CHAMPS_V53) & cles


def test_les_fonctions_du_producteur_sont_retirees():
    import update_data as u
    presentes = [f for f in FONCTIONS_V53 if hasattr(u, f)]
    assert not presentes, presentes
    assert not hasattr(u, "SIG_NON_COMPARABLE")


def test_la_config_ne_porte_plus_la_version_ni_le_seuil_de_verdict():
    import bvc_config
    assert not hasattr(bvc_config, "SCORE_VERSION")
    assert not hasattr(bvc_config, "COUVERTURE_VERDICT_MIN")
    # Ce qui reste utilisé, et R2 : le référentiel n'est pas touché.
    assert bvc_config.SEUIL_NON_COMPARABLE_DH == 100_000
    assert bvc_config.NOTE_METIER_PUBLIEE is False
    assert len(bvc_config.ISIN_MAP) == 83


def test_le_second_pipeline_ne_publie_plus_la_note_v53(monkeypatch):
    from pipeline import collect_financial_data as c
    monkeypatch.setattr(c, "noter_depuis_fichiers", lambda surcharge=None: {})
    sortie = {"timestamp": "2026-11-06T00:00:00Z", "data": {
        s: {"market": {"price": 100.0}, "technical": {"rsi_14": 55}, "fundamentals": {},
            "flags": {"stale": False, "partial_data": False}} for s in ("ZZB", "AAA")}}
    tickers = c.to_legacy_format(sortie)["tickers"]
    assert [t["symbol"] for t in tickers] == ["AAA", "ZZB"], "tri par symbole"
    for t in tickers:
        assert not set(CHAMPS_V53) & set(t), set(CHAMPS_V53) & set(t)
    src = (RACINE / "pipeline" / "collect_financial_data.py").read_text(encoding="utf-8")
    assert "0.2778" not in src and "0.7222" not in src, "la seconde formule v5.3 est revenue"


def test_le_journal_des_scores_accepte_une_ligne_sans_v53(tmp_path, monkeypatch):
    """Risque 4 du lot 1 : les nouvelles lignes de score_history.json ont v53 et
    sig vides. Le journal enregistre le Score BVC seul."""
    from pipeline import score_history as sh
    monkeypatch.setattr(sh, "CHEMIN", tmp_path / "h.json")
    t = {"symbol": "ADH", "score_bvc": {"valeur": 61.5, "etat": "CALCULABLE"},
         "_meta": {"confidence": 4, "prix_asof": "2026-11-06"}}
    j = sh.enregistrer("2026-11-06", [t])
    s = j["seances"]["2026-11-06"]
    assert len(s["tickers"]) == 1 and "score_version" not in s
    assert sh.valeur(s["tickers"][0], "v53") is None and sh.valeur(s["tickers"][0], "sig") is None


# ── 2. Ce qui reste lu à la place ───────────────────────────────────────────

def test_la_confiance_reste_publiee_et_lue_a_l_ecran_et_au_courriel():
    """Risque 3 du lot 1 : « confiance ≤ 1 → Données insuffisantes » vivait dans
    `sig`. Elle vit désormais à l'écran, qui lit `_meta.confidence`."""
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert '"confidence":' in src
    ecran = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    assert "conf:m.confidence" in ecran
    assert ecran.count('meta(r).conf<=1') >= 2, "classement ET fiche"
    assert "Données insuffisantes" in ecran
    courriel = (RACINE / "pipeline" / "bulletin_mail.py").read_text(encoding="utf-8")
    assert "confidence" in courriel


# ── 3. Le fichier publié — transition ⏳ ─────────────────────────────────────

def test_le_fichier_publie_ne_porte_plus_la_note_v53():
    titres = json.loads(chemin_data_json().read_text(encoding="utf-8")).get("tickers") or []
    if not titres:
        pytest.skip("data.json sans titres")
    porteurs = {t.get("symbol"): sorted(c for c in CHAMPS_V53 if c in t) for t in titres}
    porteurs = {s: k for s, k in porteurs.items() if k}
    # ⏳ À RETIRER APRÈS LE PREMIER RUN update_bvc SUIVANT LA FUSION DU LOT 2
    # (transition du 06/11/2026). Le data.json du dépôt est écrit par le moteur
    # d'AVANT le lot 2 : ses 80 titres portent encore les NEUF champs. TOUS
    # les titres et TOUS les champs = fichier antérieur au code, on le dit ;
    # une PARTIE seulement = vraie incohérence (un producteur non mis à jour,
    # ou un mélange de deux runs), on échoue. Dans la CI (tests.yml) et dans
    # update_bvc, le fichier est généré par le code courant : cette
    # échappatoire ne s'y déclenche pas.
    if len(porteurs) == len(titres) and all(k == sorted(CHAMPS_V53) for k in porteurs.values()):
        pytest.skip(f"{TRANSITION} — data.json antérieur au retrait du producteur v5.3")
    assert not porteurs, f"champs v5.3 encore publiés : {dict(list(porteurs.items())[:5])}"
    # Ce qui les remplace est là, sur chaque titre.
    assert all(isinstance((t.get("_meta") or {}).get("confidence"), int) for t in titres)
    assert all("score_bvc" in t and "note_fond" in t for t in titres)

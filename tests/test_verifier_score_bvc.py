"""Le contrôle du soir lit le Score BVC, plus la note v5.3 — 06/11/2026.

Lot 1 du retrait de la note v5.3 (décision d'Abd Moutalib) :
  · « score v5.3 dans [0, 10] » (bloquant) devient « Score BVC dans [0, 100]
    pour chaque titre qui a une valeur » (bloquant) ;
  · « score BVC publié sur au moins 50 titres » passe d'avertissement à
    BLOQUANT : le calcul est tout ou rien, ce contrôle ne voit que sa panne.
    Mesuré sur les 34 data.json publiés du 04 au 06/11 (jour férié compris) :
    80 blocs sur 80 à chaque fois ;
  · le nombre de VALEURS reste un avertissement : il suit l'activité du jour.
"""
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import bvc_config  # noqa: E402
import verifier_seance as vs  # noqa: E402

INTITULE_BORNES = "Score BVC dans [0, 100]"
INTITULE_PUBLIE = "Score BVC publié sur au moins"
INTITULE_VALEURS = "avertissement : Score BVC avec une valeur"


def _bloc(valeur, etat=None):
    etat = etat or ("CALCULABLE" if valeur is not None else "NON_CALCULABLE")
    return {"valeur": valeur, "etat": etat, "couverture_pct": 100 if valeur is not None else 0,
            "version": "bvc-score-v1", "facteurs": {}, "motif": None}


def _ecrire(tmp_path, monkeypatch, fiches):
    (tmp_path / "data.json").write_text(json.dumps(
        {"updated": "2026-11-05T19:00:00+0000", "tickers": fiches}), encoding="utf-8")
    monkeypatch.setattr(vs, "RACINE", tmp_path)


def _fiches(n=80, asof="2026-11-05", valeur=lambda i: 50.0 + i % 40, **extra):
    syms = list(bvc_config.TICKERS_ALL)[:n]
    return [{"symbol": s, "price": 10.0, "chg": 0.5, "v53": 5.0,
             "_meta": {"prix_asof": asof, "source_prix": "cdg", "stale": False},
             "score_bvc": _bloc(valeur(i)), **extra} for i, s in enumerate(syms)]


def _ligne(debut, jour="2026-11-05"):
    trouve = [(ok, d) for i, ok, d in vs._controles(jour, 0) if i.startswith(debut)]
    assert len(trouve) == 1, f"contrôle « {debut} » absent ou en double"
    return trouve[0]


def test_un_score_bvc_dans_les_bornes_passe(tmp_path, monkeypatch):
    _ecrire(tmp_path, monkeypatch, _fiches())
    assert _ligne(INTITULE_BORNES) == (True, "conforme")
    ok, detail = _ligne(INTITULE_PUBLIE)
    assert ok and detail.startswith("80 titres")
    ok, detail = _ligne(INTITULE_VALEURS)
    assert ok and detail == "80 valeurs"


@pytest.mark.parametrize("mauvais", [100.5, -1, float("nan"), "72", True])
def test_un_score_bvc_hors_bornes_ou_non_numerique_bloque(tmp_path, monkeypatch, mauvais):
    f = _fiches()
    f[3]["score_bvc"]["valeur"] = mauvais
    _ecrire(tmp_path, monkeypatch, f)
    ok, detail = _ligne(INTITULE_BORNES)
    assert ok is False and detail == [f[3]["symbol"]]


def test_un_titre_sans_valeur_n_est_pas_hors_bornes(tmp_path, monkeypatch):
    """PARTIEL et NON_CALCULABLE n'ont pas de valeur : c'est légitime."""
    f = _fiches()
    f[0]["score_bvc"] = _bloc(None, "PARTIEL")
    f[1]["score_bvc"] = _bloc(None, "NON_CALCULABLE")
    _ecrire(tmp_path, monkeypatch, f)
    assert _ligne(INTITULE_BORNES)[0] is True


def test_la_note_v53_n_est_plus_controlee_ici(tmp_path, monkeypatch):
    """Une v53 hors [0, 10] ne fait plus échouer le contrôle du soir : le
    producteur v5.3 garde ses propres contrôles (coherence, audit_chaine)
    jusqu'à son retrait (lot 2)."""
    f = _fiches()
    f[0]["v53"] = 99
    _ecrire(tmp_path, monkeypatch, f)
    assert not [i for i, _ok, _d in vs._controles("2026-11-05", 0) if "v5.3" in i]
    assert _ligne(INTITULE_BORNES)[0] is True


def test_une_panne_du_calcul_bloque(tmp_path, monkeypatch):
    """Le calcul est tout ou rien : sans bloc, c'est une panne, et c'est
    désormais un échec (il était un simple avertissement en mode fantôme)."""
    f = _fiches()
    for x in f:
        x.pop("score_bvc")
    _ecrire(tmp_path, monkeypatch, f)
    ok, detail = _ligne(INTITULE_PUBLIE)
    assert ok is False and "0 titres" in detail and "calcul en échec" in detail


def test_un_jour_ferie_republie_la_veille_et_passe(tmp_path, monkeypatch):
    """Le 06/11/2026 (Marche Verte), le run a republié la séance du 05 : les
    titres non cotés la veille sont périmés et NON_CALCULABLE, mais chacun
    porte son bloc. Le contrôle bloquant passe ; le nombre de valeurs
    avertit seulement s'il tombe sous 50."""
    f = _fiches(valeur=lambda i: None if i % 3 == 0 else 60.0)     # 27 sans valeur
    for x in f:
        if x["score_bvc"]["valeur"] is None:
            x["_meta"].update(stale=True, prix_asof="2026-11-04")
    _ecrire(tmp_path, monkeypatch, f)
    assert _ligne(INTITULE_PUBLIE)[0] is True
    assert _ligne(INTITULE_BORNES)[0] is True
    ok, detail = _ligne(INTITULE_VALEURS)
    assert ok is True and detail.startswith("53 valeurs")


def test_peu_de_valeurs_avertit_sans_bloquer(tmp_path, monkeypatch):
    f = _fiches(valeur=lambda i: 60.0 if i < 30 else None)
    _ecrire(tmp_path, monkeypatch, f)
    ok, detail = _ligne(INTITULE_VALEURS)
    assert ok is True and detail.startswith("30 valeurs") and "séance peu active" in detail
    assert _ligne(INTITULE_PUBLIE)[0] is True


def test_le_controle_passe_sur_le_data_json_publie():
    """Relit les DONNÉES PUBLIÉES (seconde famille de tests). Saute si le
    data.json est antérieur au code qui émet `score_bvc` — comme
    `test_score_bvc.test_publie_score_bvc`."""
    d = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    t = d.get("tickers") or []
    if not any("score_bvc" in x for x in t):
        pytest.skip("data.json antérieur au code qui émet `score_bvc`.")
    from collections import Counter
    jour = Counter((x.get("_meta") or {}).get("prix_asof") for x in t).most_common(1)[0][0]
    assert _ligne(INTITULE_BORNES, jour)[0] is True

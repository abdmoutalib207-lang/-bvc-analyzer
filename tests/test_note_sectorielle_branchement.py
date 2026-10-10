"""Branchement de la note par famille dans le moteur — 10/10/2026.

Les POIDS des piliers (Fond 65,28 % / Tech 34,72 % / NLP 0) ne bougent pas ; le
second passage d'`update_data.py` remplace la note provisoire de la boucle ; un
titre sans note ne reçoit ni ACHETER ni ÉVITER ; le second pipeline (v9) note
de la même façon. Les grilles elles-mêmes sont dans test_note_sectorielle.py.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bvc_config  # noqa: E402


def _fiche(secteur="Industrie", s1=True, **ratios):
    f = {"secteur": secteur, "ratios_publies": {k: {"valeur": v, "date": "2025-12-31"}
                                                for k, v in ratios.items()}}
    if s1:
        f["source_s1_2026"] = "https://www.ammc.ma/x.pdf"
    return f


# ── 13. les poids des piliers ne bougent pas ────────────────────────────

def test_poids_des_piliers_inchanges():
    import update_data
    # Base historique 25/47/28 repliée : le pilier NLP à zéro, 47/72 et 25/72.
    w = update_data._replier_comportemental({"technique": 0.25, "fondamental": 0.47, "comportemental": 0.28})
    assert round(w["fondamental"], 4) == 0.6528 and round(w["technique"], 4) == 0.3472
    assert w["comportemental"] == 0.0
    # Pondération en vigueur, mesurée le 10/10/2026 avant le changement de note :
    # base 65,28 / 34,72 / 0 ; marché fermé 72,22 / 27,78 / 0 ; technique
    # neutralisé 100 / 0 / 0. Aucune ne dépend de la note fondamentale.
    for ctx, attendu in (({}, (0.6528, 0.3472)), ({"market_status": "OPEN"}, (0.6528, 0.3472)),
                         ({"market_status": "CLOSED"}, (0.7222, 0.2778)),
                         ({"market_status": "CLOSED", "tech_non_fiable": True}, (1.0, 0.0))):
        p = update_data.get_weights(ctx)
        assert (round(p["fondamental"], 4), round(p["technique"], 4), p["comportemental"]) == attendu + (0.0,), ctx
    src = (Path(bvc_config.__file__).parent / "pipeline" / "collect_financial_data.py").read_text(encoding="utf-8")
    assert "score_tech * 0.3472 + fond_score * 0.6528" in src


def test_v53_reste_lineaire_en_note_fondamentale_aux_memes_poids():
    import update_data
    ctx = {"market_status": "CLOSED"}
    a = update_data.compute_v53("ZZZ", 4.0, 5.0, 0, 0, ctx)
    b = update_data.compute_v53("ZZZ", 4.0, 7.0, 0, 0, ctx)
    assert a["poids"] == b["poids"]
    wf = update_data.get_weights(ctx)["fondamental"]
    assert abs((b["v53"] - a["v53"]) - 2.0 * wf) <= 0.011       # arrondis des deux notes


# ── 14. second passage du moteur et signal ──────────────────────────────

def _passe1(sym, price=100.0):
    return {"score_tech": 5.0, "ctx": {"market_status": "CLOSED"}, "tech_nf": None,
            "depuis_reprise": None, "price": price, "ma20": None, "ma50": None,
            "meta_args": (sym, "cdg", "2026-10-09", {}, None, False), "meta_kw": {}}


def _fiche_sortie(sym, price=100.0):
    return {"symbol": sym, "price": price, "pb": None, "rsi": 50,
            "_meta": {"suspendu": False, "confidence": 5},
            "score_fond": 9.99, "v53": 9.99, "sig": "ACHETER ★★", "setup": "X",
            "verdict_plafonne": None}


def test_un_titre_sans_note_ne_recoit_ni_acheter_ni_eviter(monkeypatch):
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    out = [_fiche_sortie("ALU")]
    update_data.appliquer_note_sectorielle(out, {"ALU": _passe1("ALU")}, fondamentaux={}, bpa={}, faits={}, s1={})
    e = out[0]
    assert e["score_fond"] is None and e["v53"] is None
    assert e["sig"] == "Données insuffisantes" and e["verdict_plafonne"] is None
    assert e["note_fond"]["note"] is None and e["note_fond"]["poids_disponible"] == 0
    assert e["setup"] == "NEUTRE"


@pytest.mark.parametrize("sig", ["ACHETER ★★", "SURVEILLER ★", "ATTENDRE", "ÉVITER", "ÉVITER FORT"])
def test_signal_publie_sans_note_est_toujours_donnees_insuffisantes(monkeypatch, sig):
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    monkeypatch.setattr(update_data, "sans_comptes", lambda t: None)
    assert update_data._signal_publie("ALU", sig, None, None, sans_note=True) == ("Données insuffisantes", None)


def test_un_titre_note_recoit_la_note_de_sa_famille_et_son_v53(monkeypatch):
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    monkeypatch.setattr(update_data, "sans_comptes", lambda t: None)
    fond = {"ALU": _fiche(roic=25.0, dette_nette_ebitda=0.3, cash_conversion=150.0) | {"croissance_bpa": 50.0, "croissance_ca": 50.0}}
    out = [_fiche_sortie("ALU")]
    update_data.appliquer_note_sectorielle(out, {"ALU": _passe1("ALU")}, fondamentaux=fond,
                                           bpa={"ALU": {"bpa_12m": 10.0}}, faits={}, s1={})
    e = out[0]
    # Seul titre de l'univers : aucun pair, aucun marché hors lui → la valorisation
    # s'abstient (elle ne se compare plus à elle-même). Reste, sur 80 points :
    # rentabilité 9,5 (×40) ; croissance 9,0 (×30) ; bilan 9,0 (×10)
    # (380 + 270 + 90) ÷ 80 = 9,25
    assert e["score_fond"] == 9.25 and e["note_fond"]["famille"] == "autre"
    assert e["note_fond"]["poids_disponible"] == 80 and "valorisation" in e["note_fond"]["abstentions"]
    # v53 = 5,0 × t + 9,25 × f aux poids du contexte, jamais d'autres poids.
    p = update_data.get_weights({"market_status": "CLOSED"})
    assert e["v53"] == round(min(max(5.0 * p["technique"] + 9.25 * p["fondamental"], 0), 10), 2)
    assert e["sig"].startswith("ACHETER")


def test_le_second_pipeline_note_par_famille(monkeypatch):
    from pipeline import collect_financial_data as c
    monkeypatch.setattr(c, "noter_depuis_fichiers", lambda surcharge=None: {
        "AAA": {"note": None}, "BBB": {"note": 6.0}})
    sortie = {"timestamp": "2026-10-10T00:00:00Z", "data": {
        s: {"market": {"price": 100.0}, "technical": {"rsi_14": 50}, "fundamentals": {},
            "smart_money": {}, "flags": {"stale": False, "partial_data": False}} for s in ("AAA", "BBB")}}
    par = {t["symbol"]: t for t in c.to_legacy_format(sortie)["tickers"]}
    assert par["AAA"]["score_fond"] is None and par["AAA"]["v53"] is None
    assert par["AAA"]["sig"] == "Données insuffisantes"
    assert par["BBB"]["score_fond"] == 6.0
    assert par["BBB"]["v53"] == round(par["BBB"]["v53"], 2)
    assert par["BBB"]["sig"].startswith("SURVEILLER") or par["BBB"]["sig"].startswith("ACHETER")


def test_la_confiance_est_plafonnee_a_1_sans_note_fondamentale(monkeypatch):
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    monkeypatch.setitem(update_data._FOND_COMPUTED, "ALU", 5.0)
    avec = update_data._meta_ticker("ALU", "cdg", "2026-10-09", {}, None, False, note_fond_ok=True)
    sans = update_data._meta_ticker("ALU", "cdg", "2026-10-09", {}, None, False, note_fond_ok=False)
    assert avec["confidence"] - sans["confidence"] >= 1
    assert sans["confidence"] <= 1


def test_un_titre_sans_note_a_une_confiance_au_plus_1_meme_hors_fondamentaux_json(monkeypatch):
    # T2S (confiance 4 à côté de « Données insuffisantes ») n'était pas dans
    # fondamentaux.json : la correction ne doit pas dépendre de _FOND_COMPUTED.
    import update_data
    monkeypatch.setattr(update_data, "_suspendu_maintenant", lambda t: False)
    monkeypatch.setattr(update_data, "sans_comptes", lambda t: None)
    assert "T2S" not in update_data._FOND_COMPUTED
    out = [_fiche_sortie("T2S")]
    out[0]["_meta"]["confidence"] = 4
    update_data.appliquer_note_sectorielle(out, {"T2S": _passe1("T2S")}, fondamentaux={}, bpa={}, faits={}, s1={})
    assert out[0]["sig"] == "Données insuffisantes" and out[0]["_meta"]["confidence"] <= 1

"""17/11/2026 — Score BVC de la semaine close (décision d'Abd Moutalib :
« Figé à la clôture de semaine »).

Même formule, calculée sur la dernière clôture de la semaine close, affichée
telle quelle toute la semaine suivante avec sa date. Le score du jour reste
calculé (score_bvc_jour) pour le journal, mais n'est plus celui publié.
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import score_bvc as sb  # noqa: E402

SEANCES = ["2026-11-06", "2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12",
           "2026-11-13", "2026-11-16", "2026-11-17"]


# ── la fin de semaine close ───────────────────────────────────────────────

def test_en_semaine_on_prend_la_derniere_seance_avant_lundi():
    assert sb.fin_de_semaine_close(SEANCES, "2026-11-17") == "2026-11-13"   # mardi
    assert sb.fin_de_semaine_close(SEANCES, "2026-11-16") == "2026-11-13"   # lundi


def test_le_week_end_la_semaine_qui_vient_de_finir_est_close():
    assert sb.fin_de_semaine_close(SEANCES[:6], "2026-11-14") == "2026-11-13"  # samedi
    assert sb.fin_de_semaine_close(SEANCES[:6], "2026-11-15") == "2026-11-13"  # dimanche


def test_vendredi_ferie_la_semaine_se_clot_au_jeudi():
    seances = ["2026-11-05", "2026-11-09"]       # 06/11 Marche Verte
    assert sb.fin_de_semaine_close(seances, "2026-11-10") == "2026-11-05"


def test_aucune_seance_connue():
    assert sb.fin_de_semaine_close([], "2026-11-17") is None


# ── le score à une date ───────────────────────────────────────────────────

def _bougies(n=260, fin="2026-11-17"):
    import pandas as pd
    jours = [d.date().isoformat() for d in pd.bdate_range(end=fin, periods=n)]
    return [{"d": d, "o": 100 + i * .1, "h": 101 + i * .1, "l": 99 + i * .1,
             "c": 100 + i * .1, "v": 1000 + i} for i, d in enumerate(jours)]


def test_le_score_de_la_semaine_ignore_les_seances_posterieures():
    bg = _bougies()
    rec = {"symbol": "XXX", "price": 999.0, "_meta": {"stale": False, "prix_asof": "2026-11-17"}}
    s = sb.score_titre_bvc_semaine(rec, bg, "2026-11-13")
    assert s["semaine"]["fin"] == "2026-11-13"
    assert s["semaine"]["cours_du"] == "2026-11-13"
    attendu = next(b["c"] for b in bg if b["d"] == "2026-11-13")
    assert s["semaine"]["cours"] == attendu
    # contrôle : la même série coupée au 13 donne exactement le même score
    coupee = [b for b in bg if b["d"] <= "2026-11-13"]
    assert sb.score_titre_bvc_semaine(rec, coupee, "2026-11-13")["valeur"] == s["valeur"]


def test_un_titre_sans_echange_avant_la_fin_de_semaine_n_est_pas_calcule():
    bg = [{"d": "2026-11-16", "o": 170, "h": 172, "l": 169, "c": 171.55, "v": 5000}]
    s = sb.score_titre_bvc_semaine({"symbol": "NRJ", "_meta": {}}, bg, "2026-11-13")
    assert s["etat"] == "NON_CALCULABLE" and s["valeur"] is None
    assert "13/11/2026" in s["motif"]


def test_annexer_garde_le_score_du_jour_a_cote():
    bg = _bougies()
    t = {"symbol": "XXX", "price": 120.0, "_meta": {"stale": False, "prix_asof": "2026-11-17"},
         "score_bvc": {"valeur": 1.0, "etat": "CALCULABLE"}}
    sb.annexer_bvc_semaine([t], lambda s: bg, "2026-11-13")
    assert t["score_bvc_jour"] == {"valeur": 1.0, "etat": "CALCULABLE"}
    assert t["score_bvc"]["semaine"]["fin"] == "2026-11-13"


# ── sur les données publiées ──────────────────────────────────────────────

def test_les_donnees_publiees_portent_la_semaine():
    data = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    avec = [t for t in data["tickers"] if isinstance((t.get("score_bvc") or {}).get("semaine"), dict)]
    if not avec:                       # moteur pas encore passé sur ce code
        return
    fins = {t["score_bvc"]["semaine"]["fin"] for t in avec}
    assert len(fins) == 1, fins        # une seule semaine pour tout le marché
    for t in avec:
        du = t["score_bvc"]["semaine"]["cours_du"]
        if du is None:                 # aucune séance échangée, ou suspension
            assert t["score_bvc"]["etat"] == "NON_CALCULABLE"
        if du is not None:
            assert du <= next(iter(fins))
        assert "score_bvc_jour" in t


def test_l_ecran_affiche_la_date_de_la_semaine():
    ecran = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
    assert "Score de la semaine · clôture du" in ecran
    assert "semaine close le" in ecran


# ── relecture du 17/11 (relecteur-pipeline) ───────────────────────────────

def test_une_bougie_isolee_ne_deplace_pas_la_semaine():
    reel = [[{"d": d} for d in SEANCES[:6]] for _ in range(30)]
    fantome = [[{"d": "2026-11-14"}], [{"d": "2026-11-15"}]] + [[{"d": "2026-11-11"}]]
    s = sb.seances_du_marche(reel + fantome)
    assert "2026-11-14" not in s and "2026-11-15" not in s
    # contrôle : un samedi porté par tout le marché reste écarté (jour non ouvré)
    assert "2026-11-14" not in sb.seances_du_marche([[{"d": "2026-11-14"}]] * 50)
    assert sb.fin_de_semaine_close(s, "2026-11-17") == "2026-11-13"


def test_tout_ou_rien_une_erreur_laisse_le_score_du_jour(monkeypatch):
    bg = _bougies()
    a = {"symbol": "AAA", "price": 1.0, "_meta": {}, "score_bvc": {"valeur": 11.0}}
    b = {"symbol": "BBB", "price": 1.0, "_meta": {}, "score_bvc": {"valeur": 22.0}}
    vrai = sb._indicateurs_au

    def panne(bougies, fin):
        if panne.n:
            raise RuntimeError("recalcul impossible")
        panne.n += 1
        return vrai(bougies, fin)
    panne.n = 0
    monkeypatch.setattr(sb, "_indicateurs_au", panne)
    try:
        sb.annexer_bvc_semaine([a, b], lambda s: bg, "2026-11-13")
        assert False, "l'erreur devait remonter"
    except RuntimeError:
        pass
    assert a["score_bvc"] == {"valeur": 11.0} and "score_bvc_jour" not in a
    assert b["score_bvc"] == {"valeur": 22.0}


def test_second_appel_ne_range_pas_la_semaine_sous_le_jour():
    bg = _bougies()
    t = {"symbol": "XXX", "price": 1.0, "_meta": {}, "score_bvc": {"valeur": 5.0}}
    sb.annexer_bvc_semaine([t], lambda s: bg, "2026-11-13")
    sb.annexer_bvc_semaine([t], lambda s: bg, "2026-11-13")
    assert t["score_bvc_jour"] == {"valeur": 5.0}


def test_les_indicateurs_sont_ceux_de_la_fin_de_semaine():
    """Contrôle positif : sur une série qui monte, la MM20 au 13/11 est plus
    basse que celle au 17/11 — c'est bien la série arrêtée qui est lue."""
    bg = _bougies()
    au13 = sb._indicateurs_au([b for b in bg if b["d"] <= "2026-11-13"], "2026-11-13")
    au17 = sb._indicateurs_au(bg, "2026-11-17")
    assert au13["ma20"] < au17["ma20"]


def test_un_titre_suspendu_aujourd_hui_reste_non_calculable():
    bg = _bougies()
    s = sb.score_titre_bvc_semaine({"symbol": "XXX", "price": 1.0,
                                    "_meta": {"suspendu": True}}, bg, "2026-11-13")
    assert s["etat"] == "NON_CALCULABLE" and s["valeur"] is None


def test_la_constante_de_reprise_est_celle_du_moteur():
    import update_data as ud
    assert sb.SEANCES_APRES_REPRISE == ud.SEANCES_APRES_REPRISE


def test_le_briefing_ne_lit_jamais_l_activite_de_la_semaine():
    from pipeline import briefing
    sem = {"semaine": {"fin": "2026-11-13"}, "facteurs": {"activité": {"ratio": 9.0, "mediane": 10}}}
    jour = {"facteurs": {"activité": {"ratio": 2.0, "mediane": 10}}}
    assert briefing.activite_du_score({"score_bvc": sem, "score_bvc_jour": jour})[0] == 2.0
    assert briefing.activite_du_score({"score_bvc": sem})[0] is None
    assert briefing.activite_du_score({"score_bvc": jour})[0] == 2.0     # avant ce code


def test_le_journal_ne_prend_jamais_le_score_de_la_semaine():
    from pipeline import score_history as sh
    import inspect
    src = inspect.getsource(sh)
    assert 'not isinstance(_b.get("semaine"), dict)' in src


def test_controle_du_soir_semaine():
    from pipeline import verifier_seance as vs
    bon = {"A": {"semaine": {"fin": "2026-11-13"}}, "B": {"semaine": {"fin": "2026-11-13"}}}
    assert vs._controle_semaine(bon, "2026-11-17")[1] is True
    assert vs._controle_semaine(bon, "2026-11-13")[1] is True          # passage du week-end
    assert vs._controle_semaine(bon, "2026-11-12")[1] is False         # semaine pas close
    assert vs._controle_semaine({"A": {"valeur": 3}}, "2026-11-17")[1] is False
    deux = {"A": {"semaine": {"fin": "2026-11-13"}}, "B": {"semaine": {"fin": "2026-11-06"}}}
    assert vs._controle_semaine(deux, "2026-11-17")[1] is False
    assert vs._controle_semaine({"A": {"semaine": {"fin": "2026-11-06"}}}, "2026-11-24")[1] is False


def test_le_courriel_dit_la_semaine():
    from pipeline import bulletin_mail as bm
    assert bm.ligne_semaine("2026-11-13").startswith("Score de la semaine close le 13/11/2026")

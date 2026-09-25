#!/usr/bin/env python3
"""Le bilan de semaine, et les deux erreurs silencieuses qui le guettent.

⚠️ LES DEUX DÉFAUTS QUI NE SE VOIENT PAS
────────────────────────────────────────
Un bilan hebdomadaire faux reste **plausible**. C'est ce qui le rend
dangereux : personne ne recalcule à la main une performance sur cinq séances.

  1. **La référence.** Prendre la PREMIÈRE clôture de la semaine comme base
     exclut le mouvement du lundi — le plus gros de la semaine une fois sur
     cinq. Le chiffre reste crédible, il est simplement faux.

  2. **Le compte des séances.** « Sept jours en arrière » donne tantôt quatre
     séances, tantôt six, selon les fériés. La performance affichée ne porte
     alors pas toujours sur la même chose, et deux semaines ne se comparent
     plus.

⚠️ CE QU'IL NE PEUT PAS DIRE, ET DOIT DIRE QU'IL NE PEUT PAS
La largeur de marché et le journal des scores ont été ouverts les 24 et
25/09/2026 : une séance chacun. L'évolution hebdomadaire des signaux n'est
pas calculable, et le bilan l'ÉNONCE plutôt que de la simuler. Reconstituer
un signal passé depuis les données d'aujourd'hui donnerait au modèle la
connaissance du futur.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import briefing as bf            # noqa: E402
from pipeline import briefing_hebdo as bh      # noqa: E402


# ── ⚠️ La référence : le défaut le plus coûteux ────────────────────────────

def test_la_reference_est_la_cloture_AVANT_la_semaine():
    """⚠️ Attendu calculé à la main, jamais par la fonction testée.

    Série : vendredi 100, puis lundi 110, mardi 121.
    La semaine porte lundi et mardi. La performance correcte est
    121 / 100 − 1 = +21 %. Partir du lundi donnerait 121/110 − 1 = +10 %,
    et perdrait exactement le mouvement du lundi.
    """
    serie = [("2026-09-18", 100.0), ("2026-09-21", 110.0), ("2026-09-22", 121.0)]
    p = bh._perf(serie, ["2026-09-21", "2026-09-22"])
    assert p["reference"] == 100.0
    assert p["perf_pct"] == 21.0


def test_sans_cloture_anterieure_aucune_performance_n_est_publiee():
    """⚠️ Un titre introduit lundi n'a pas de performance hebdomadaire. En
    inventer une à partir de sa première clôture afficherait 0 %, ce qui se
    lirait comme « stable » alors que c'est « on ne sait pas »."""
    serie = [("2026-09-21", 110.0), ("2026-09-22", 121.0)]
    assert bh._perf(serie, ["2026-09-21", "2026-09-22"]) is None


def test_un_titre_cotant_une_seule_fois_est_ecarte():
    """Sur une seule séance, l'écart mesuré porte autant sur l'illiquidité
    que sur le titre."""
    serie = [("2026-09-18", 100.0), ("2026-09-22", 150.0)]
    assert bh._perf(serie, ["2026-09-21", "2026-09-22"]) is None


# ── ⚠️ La semaine se compte en séances ─────────────────────────────────────

def test_la_semaine_ne_retient_que_les_seances_reellement_cotees():
    """⚠️ Aucun calendrier de fériés n'est codé : les jours marocains suivent
    en partie le calendrier lunaire et une liste en dur ne serait pas tenue.
    La semaine se déduit des dates PRÉSENTES."""
    dates = ["2026-09-18",                      # vendredi précédent
             "2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24"]
    s = bh.seances_de_la_semaine(dates, "2026-09-24")
    assert s == ["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24"]


def test_la_semaine_s_arrete_a_la_derniere_seance_close():
    """Le vendredi ne figure pas dans la semaine d'un bilan produit jeudi."""
    dates = ["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25"]
    assert "2026-09-25" not in bh.seances_de_la_semaine(dates, "2026-09-24")


def test_un_ferie_en_milieu_de_semaine_ne_cree_pas_de_seance():
    """Mercredi absent des données : la semaine compte trois séances, pas
    quatre."""
    dates = ["2026-09-21", "2026-09-22", "2026-09-24"]
    assert len(bh.seances_de_la_semaine(dates, "2026-09-24")) == 3


# ── ⚠️ Ce que le bilan doit avouer ─────────────────────────────────────────

def test_le_bilan_declare_ce_qu_il_ne_peut_pas_mesurer():
    """⚠️ La largeur et les signaux n'ont qu'une séance d'historique. Le
    bilan doit le DIRE, pas les simuler."""
    b = bh.composer({"tickers": []}, masi_history={}, series={}, articles=[])
    joint = " ".join(b["non_mesurable"]).lower()
    assert "largeur" in joint and "journal des scores" in joint
    assert "cause" in joint


def test_le_bilan_signale_une_reprise_de_cotation_au_palmares():
    """⚠️ R11 — une reprise après OPA change la RÉFÉRENCE, pas seulement le
    cours. La performance est réelle et ne se compare pas aux autres. On la
    signale plutôt que de la retirer : la retirer effacerait un mouvement qui
    a bien eu lieu.
    """
    data = {"tickers": [{"symbol": "CMT", "name": "Minière Touissit",
                         "_meta": {"prix_asof": "2026-09-24",
                                   "reprise_recente": True}}]}
    series = {"CMT": [("2026-09-18", 2681.0), ("2026-09-21", 2949.0),
                      ("2026-09-24", 3923.0)]}
    b = bh.composer(data, masi_history={"seances": {}}, series=series,
                    articles=[])
    assert b["hausses"][0]["reprise_recente"] is True
    assert any("reprendre sa cotation" in c for c in b["constats"])


def test_aucun_constat_du_bilan_n_avance_de_cause():
    b = bh.composer(json.loads((RACINE / "data.json").read_text(encoding="utf-8")))
    for c in b["constats"]:
        for mot in (" parce que", " à cause de", " sur fond de", " grâce à"):
            assert mot not in c.lower(), f"le bilan avance une cause : {c}"


def test_le_bilan_s_ecrit_dans_un_fichier_distinct(tmp_path):
    """⚠️ Un bilan de semaine ne remplace pas la lecture de la dernière
    séance : les deux doivent pouvoir coexister."""
    p = tmp_path / "hebdo.json"
    bh.ecrire({"type": "hebdomadaire"}, p)
    assert json.loads(p.read_text(encoding="utf-8"))["type"] == "hebdomadaire"
    assert bh.ecrire.__doc__ and "distinct" in bh.ecrire.__doc__


def test_le_moteur_produit_le_bilan_et_le_terminal_le_lit():
    import ast
    arbre = ast.parse((RACINE / "update_data.py").read_text(encoding="utf-8"))
    assert any(isinstance(n, ast.ImportFrom)
               and (n.module or "").endswith("briefing_hebdo")
               for n in ast.walk(arbre)), "le moteur ne génère pas le bilan"
    ecran = (RACINE / "index.html").read_text(encoding="utf-8")
    assert "briefing_hebdo.json" in ecran, "le terminal ne lit pas le bilan"


# ── ⚠️ Les séries à la limite de variation ─────────────────────────────────

def _serie_limite(n, depart=1000.0, sens=1):
    """n variations consécutives à ±9,97 % — ce que la BVC autorise au plus."""
    s, c = [("2026-09-01", depart)], depart
    for i in range(n):
        c = round(c * (1 + sens * 0.0997), 2)
        s.append((f"2026-09-{2+i:02d}", c))
    return s


def test_une_serie_de_limites_est_detectee():
    """⚠️ LE FAIT QUI A FAIT ÉCRIRE CE CONSTAT. CMT a touché le plafond cinq
    séances d'affilée après sa reprise : 2 438 → 2 681 → 2 949 → 3 243 →
    3 567 → 3 923. Un titre au plafond n'a pas fini de monter, il a fini la
    séance — et « +9,98 % » ne dit pas la même chose que « +9,98 % pour la
    cinquième fois ».
    """
    r = bf.series_a_la_limite({"X": _serie_limite(5)}, "2026-09-24")
    assert r and r[0]["seances"] == 5 and r[0]["sens"] == "hausse"


def test_six_clotures_font_cinq_variations():
    """⚠️ L'ERREUR D'UNE UNITÉ. Une première lecture annonçait « six séances »
    là où il y en avait cinq : six clôtures ne font que cinq variations. Se
    tromper d'une unité sur un chiffre affiché suffit à faire douter de tous
    les autres."""
    serie = [("2026-09-16", 2438.0), ("2026-09-18", 2681.0),
             ("2026-09-21", 2949.0), ("2026-09-22", 3243.0),
             ("2026-09-23", 3567.0), ("2026-09-24", 3923.0)]
    assert len(serie) == 6
    assert bf.series_a_la_limite({"CMT": serie}, "2026-09-24")[0]["seances"] == 5


def test_deux_seances_ne_font_pas_une_serie():
    """Un titre touche la limite assez souvent pour que deux jours d'affilée
    arrivent par hasard. Trois, non."""
    assert bf.series_a_la_limite({"X": _serie_limite(2)}, "2026-09-24") == []


def test_une_variation_ordinaire_n_est_pas_une_limite():
    """⚠️ Le seuil de 9,9 % se lit dans la distribution : effectifs uniformes
    autour de dix jusqu'à 9,8 %, puis 52 à 9,9 % et 286 à 10,0 %."""
    s = [("2026-09-01", 100.0), ("2026-09-02", 109.0),
         ("2026-09-03", 118.8), ("2026-09-04", 129.5)]     # ~ +9,0 % chacune
    assert bf.series_a_la_limite({"X": s}, "2026-09-24") == []


def test_un_changement_de_sens_rompt_la_serie():
    """⚠️ Un titre au plafond puis au plancher n'est pas dans une série :
    c'est de la volatilité, et les additionner masquerait la différence."""
    s = _serie_limite(3) + [("2026-09-06", round(_serie_limite(3)[-1][1] * 0.9003, 2))]
    r = bf.series_a_la_limite({"X": s}, "2026-09-24")
    assert not r or r[0]["seances"] < 3


def test_un_decrochage_au_dela_de_la_limite_rompt_la_serie():
    """⚠️ Au-delà de 10,5 %, ce n'est plus le plafond : c'est une opération
    sur titres ou une donnée fausse (R10/R11). Compter un décrochage comme un
    plafond confondrait deux faits opposés."""
    s = _serie_limite(3)
    s.append(("2026-09-06", round(s[-1][1] * 1.44, 2)))     # +44 %, comme CMT le 16/09
    r = bf.series_a_la_limite({"X": s}, "2026-09-24")
    assert not r, "un décrochage a été compté comme une séance au plafond"

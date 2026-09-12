#!/usr/bin/env python3
"""Le RSI PUBLIÉ — `update_data.py::calc_rsi`.

⚠️ POURQUOI CE FICHIER EXISTE
`pipeline/indicateurs.py` porte un RSI correct et éprouvé, mais il appartient
à la couche de recherche : il n'est pas fusionné, et ce n'est pas lui qui écrit
`data.json`. La fonction qui alimente le terminal est `calc_rsi`, et elle
portait deux défauts que la revue du 12/09 a reproduits.

Un test qui éprouve la bonne fonction dans le mauvais module ne protège rien.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")
RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def calc_rsi():
    sys.argv = ["update_data.py"]
    spec = importlib.util.spec_from_file_location("ud_rsi", RACINE / "update_data.py")
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    return m.calc_rsi


def test_une_hausse_continue_rend_cent(calc_rsi):
    """⚠️ DÉFAUT 1, REPRODUIT PAR LA REVUE.

    Sans aucune baisse, RS est infini et le RSI vaut 100 — c'est la définition.
    `ema_down.replace(0, np.nan)` en faisait un `nan`, qui traverse ensuite
    `calc_score_tech` sans déclencher aucune branche : le titre recevait le
    score neutre en silence.
    """
    assert calc_rsi(pd.Series([100 + i for i in range(20)])) == 100.0


def test_une_baisse_continue_rend_zero(calc_rsi):
    assert calc_rsi(pd.Series([120 - i for i in range(20)])) == 0.0


def test_l_alternance_rend_cinquante(calc_rsi):
    """⚠️ DÉFAUT 2, REPRODUIT PAR LA REVUE — la série exacte qu'elle donne.

    Sept hausses d'un point, sept baisses d'un point : autant de l'un que de
    l'autre, de même amplitude. Le RSI vaut 50.

    L'ancienne forme rendait **66,5** parce que `ewm(com=13, adjust=False)`
    amorce le lissage sur la PREMIÈRE variation au lieu de la moyenne
    arithmétique des quatorze premières. La série s'en souvient longtemps.
    """
    serie = [100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100]
    assert len(serie) == 15
    assert calc_rsi(pd.Series(serie)) == 50.0


def test_une_serie_plate_rend_cinquante(calc_rsi):
    """Ni hausse ni baisse : indéterminé, rendu neutre. C'est le SEUL cas où
    50 sort du calcul lui-même."""
    assert calc_rsi(pd.Series([100.0] * 20)) == 50.0


@pytest.mark.parametrize("n", [0, 1, 5, 13, 14])
def test_sous_la_longueur_minimale_la_fonction_s_abstient(calc_rsi, n):
    """⚠️ `period + 1` clôtures au minimum — QUINZE pour un RSI(14).

    En deçà, la fonction rend `None`. Jamais 50 : un RSI absent n'est pas un
    RSI neutre, et le faire passer pour neutre revient à inventer une mesure.
    """
    assert calc_rsi(pd.Series([100 + i for i in range(n)])) is None


def test_a_quinze_cloture_la_fonction_se_prononce(calc_rsi):
    """La borne est bien à `period + 1`, pas plus haut."""
    assert calc_rsi(pd.Series([100 + i for i in range(15)])) is not None


def test_l_amorcage_est_la_moyenne_arithmetique_des_quatorze_premieres(calc_rsi):
    """⚠️ Vérification par une SECONDE implémentation, écrite ici.

    On ne réutilise pas la fonction éprouvée : on recalcule Wilder à la main,
    et les deux doivent tomber d'accord. Comparer une fonction à elle-même ne
    prouve rien.
    """
    serie = [100, 102, 101, 105, 103, 107, 106, 110, 108, 112,
             111, 115, 113, 117, 116, 120, 118, 122]

    def wilder(vals, n=14):
        var = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
        g = [max(d, 0.0) for d in var]
        p = [max(-d, 0.0) for d in var]
        mg, mp = sum(g[:n]) / n, sum(p[:n]) / n
        for i in range(n, len(var)):
            mg = (mg * (n - 1) + g[i]) / n
            mp = (mp * (n - 1) + p[i]) / n
        if mp == 0:
            return 100.0 if mg > 0 else 50.0
        if mg == 0:
            return 0.0
        return round(100.0 - 100.0 / (1.0 + mg / mp), 1)

    assert calc_rsi(pd.Series(serie)) == wilder(serie)


def test_un_rsi_absent_ne_contribue_pas_au_score_technique():
    """⚠️ Une absence ne doit pas être lue comme « zone idéale » ni comme
    « suracheté ». Elle ne contribue pas, et cela se voit dans le code."""
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    i = src.index("def calc_score_tech")
    corps = src[i:i + 1200]
    assert "if rsi is None:" in corps, (
        "l'absence de RSI n'est pas traitée explicitement dans calc_score_tech")


# ═══ FINITUDE, ABSENCES, ET LA DATE DU RÉSULTAT ═══════════════════════════

@pytest.fixture(scope="module")
def calc_rsi_collecteur():
    """⚠️ L'AUTRE exemplaire — celui qui produit RÉELLEMENT les valeurs.

    73 des 74 RSI publiés viennent de `pipeline/historical_data.json`, écrit
    par le collecteur. Corriger `update_data.py` seul n'aurait presque rien
    changé à l'écran.
    """
    sys.argv = ["collect_history_bvcscrap.py"]
    sys.path.insert(0, str(RACINE / "pipeline"))
    spec = importlib.util.spec_from_file_location(
        "col_rsi", RACINE / "pipeline" / "collect_history_bvcscrap.py")
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    return m.calc_rsi


SERIES = [
    [100 + i for i in range(20)],
    [120 - i for i in range(20)],
    [100.0] * 20,
    [100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100, 101, 100],
    [100 + i for i in range(19)] + [None],
    [100 + i for i in range(19)] + [float("inf")],
    [100 + i for i in range(10)] + [None] + [110 + i for i in range(9)],
    [100 + i for i in range(13)],
]


@pytest.mark.parametrize("serie", SERIES)
def test_les_deux_exemplaires_ne_divergent_jamais(calc_rsi, calc_rsi_collecteur, serie):
    """⚠️ La fonction est DUPLIQUÉE dans deux fichiers. Tant qu'elle l'est,
    leur divergence doit être impossible à introduire sans qu'on le voie."""
    s = pd.Series(serie, dtype=object)
    assert calc_rsi(s) == calc_rsi_collecteur(s)


@pytest.mark.parametrize("fin", [None, float("inf"), float("-inf"), float("nan")])
def test_une_serie_croissante_terminee_par_une_valeur_inexploitable(calc_rsi, fin):
    """⚠️ DÉFAUT RELEVÉ PAR LA REVUE DU 12/09.

    Ma correction écartait les valeurs absentes AVANT de calculer. Une série
    croissante terminée par `None` rendait donc 100 — un RSI daté de la séance
    PRÉCÉDENTE, présenté comme celui de la dernière. Le trou était refermé sans
    que personne le sache.

    `+inf` traversait `pd.isna` sans être vu et contaminait toute la récurrence.
    """
    serie = [100 + i for i in range(19)] + [fin]
    assert calc_rsi(pd.Series(serie, dtype=object)) is None


def test_un_trou_au_milieu_interdit_le_calcul(calc_rsi):
    """Le lissage de Wilder est RÉCURSIF : un trou propage sa correction
    jusqu'au bout. Une série percée ne donne pas un RSI approximatif — elle
    donne le RSI d'une AUTRE série."""
    serie = [100 + i for i in range(10)] + [None] + [110 + i for i in range(9)]
    assert calc_rsi(pd.Series(serie, dtype=object)) is None


def test_le_resultat_porte_sur_la_derniere_cloture_recue(calc_rsi):
    """⚠️ La date du résultat est tenue : ajouter une séance CHANGE la valeur.

    Si la fonction pouvait ignorer la dernière observation, les deux appels
    rendraient la même chose — et le RSI serait daté d'hier sans le dire.
    """
    base = [100, 102, 101, 105, 103, 107, 106, 110, 108, 112,
            111, 115, 113, 117, 116]
    avant = calc_rsi(pd.Series(base))
    apres = calc_rsi(pd.Series(base + [90]))
    assert avant is not None and apres is not None
    assert apres < avant, "une clôture en forte baisse n'a pas déplacé le RSI"

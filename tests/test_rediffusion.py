"""Détection de rediffusion titre par titre — prouvée par le bulletin officiel.

Le 01/09/2026, le bulletin de CDG Capital Bourse a révélé deux valeurs du
MASI 1 que notre terminal présentait comme cotées ce jour-là alors qu'elles ne
l'étaient pas. Le détecteur de séance fantôme ne pouvait pas les voir : il
raisonne à l'échelle du marché, et le marché avait bien coté.

⚠️ La règle R9 était documentée depuis l'origine du projet — « chg=0 ET vol=0
⇒ donnée périmée » — mais elle n'alimentait que des messages de journal. Elle
ne touchait pas `_meta.stale`, donc le frontend n'en savait rien.
"""

import pandas as pd


def _candles(points):
    return pd.DataFrame(points)


# ── Signature 1 : R9 littérale ─────────────────────────────────────────────

def test_variation_et_volume_nuls_sont_une_rediffusion(ud):
    """Le cas Minière Touissit : prix daté du jour, mais aucune cotation.

    Le bulletin officiel portait « cours 0,00 » pendant que nous affichions
    4 350 DH au 01/09, non périmé.
    """
    assert ud._est_rediffusion(0.0, 0, None) is True
    assert ud._est_rediffusion(0, 0, _candles([{"d": "2026-08-31", "c": 4350.0, "v": 0}])) is True


# ── Signature 2 : le volume rejoué ─────────────────────────────────────────

def test_volume_identique_a_la_veille_est_une_rediffusion(ud):
    """Le cas Réalisations Mécaniques : 465,0 DH pour 56 titres, deux jours de suite.

    Un volume réel ne se répète pas au titre près.
    """
    veille = _candles([{"d": "2026-08-28", "c": 465.0, "v": 37},
                       {"d": "2026-08-31", "c": 465.0, "v": 56}])
    assert ud._est_rediffusion(0.0, 56, veille, "2026-09-01") is True


def test_la_bougie_du_jour_ne_sert_pas_de_reference(ud):
    """⚠️ Le faux positif du 01/09, trouvé par le bulletin officiel.

    Le cache de chandelles contient DÉJÀ la bougie du jour, écrite par un run
    antérieur. Sans la date de séance, on compare la ligne du jour à elle-même
    — toujours vrai. AtlantaSanad et CFG Bank ont été marqués périmés alors que
    le bulletin leur donnait 962 et 3 745 titres échangés.

    Ici : la veille du 01/09 est le 31/08 (173 titres), pas la bougie du 01/09
    déjà écrite (962). Le titre a bien coté.
    """
    avec_aujourdhui = _candles([{"d": "2026-08-31", "c": 127.0, "v": 173},
                                {"d": "2026-09-01", "c": 127.0, "v": 962}])
    assert ud._est_rediffusion(0.0, 962, avec_aujourdhui, "2026-09-01") is False
    # et sans la date, l'ancien défaut se reproduirait — d'où son caractère
    # obligatoire : sans `seance`, on ne conclut rien plutôt que de se tromper.
    assert ud._est_rediffusion(0.0, 962, avec_aujourdhui) is False


def test_volume_different_de_la_veille_est_une_vraie_cotation(ud):
    """⚠️ Le contre-test qui empêche le remède d'être pire que le mal.

    Le 28/08, six valeurs affichaient `chg=0` avec des volumes de 1 à 37
    titres, tous différents de la veille. Elles avaient bien coté à prix
    inchangé — c'est banal sur les petites capitalisations de la place.
    C'est la RÉPÉTITION qui trahit, pas la stabilité du cours.
    """
    veille = _candles([{"d": "2026-08-28", "c": 465.0, "v": 37},
                       {"d": "2026-08-31", "c": 465.0, "v": 56}])
    assert ud._est_rediffusion(0.0, 12, veille, "2026-09-01") is False


def test_une_variation_non_nulle_n_est_jamais_une_rediffusion(ud):
    """Si le cours a bougé, le titre a coté. Aucune ambiguïté."""
    veille = _candles([{"d": "2026-08-31", "c": 465.0, "v": 56}])
    assert ud._est_rediffusion(2.5, 56, veille, "2026-09-01") is False
    assert ud._est_rediffusion(-1.2, 0, veille, "2026-09-01") is False


def test_sans_historique_on_ne_conclut_pas(ud):
    """Faute de séance précédente, le volume rejoué n'est pas observable.

    On ne marque alors rien : mieux vaut ne pas savoir que supposer à tort.
    """
    assert ud._est_rediffusion(0.0, 56, None, "2026-09-01") is False
    assert ud._est_rediffusion(
        0.0, 56, _candles([{"d": "2026-08-31", "c": 465.0, "v": 56}]), "2026-09-01") is False


def test_entrees_absentes_ne_font_pas_lever(ud):
    assert ud._est_rediffusion(None, None, None) is False


# ── L'effet sur le bloc de provenance ──────────────────────────────────────

def test_une_rediffusion_est_marquee_perimee(ud):
    """C'est tout l'objet : que le frontend le sache et affiche le badge."""
    veille = _candles([{"d": f"2026-08-{d:02d}", "c": 465.0, "v": 56} for d in range(1, 29)])
    m = ud._meta_ticker("SRM", "bmce", "2026-09-01", {"mentions": 0, "win": None},
                        veille, chg=0.0, vol=56)
    assert m["stale"] is True, "un titre qui n'a pas coté ne doit pas passer pour frais"

"""R10 et la détection d'ISIN suspect — deux règles longtemps enfouies.

Ces deux garde-fous vivaient au niveau 3 de la boucle par ticker, dans les
405 lignes qui traitent chaque valeur. Extraits le 31/08, ils deviennent
vérifiables — et ce sont deux des règles les plus structurantes du produit.
"""

import pandas as pd
import pytest

SEANCE = "2026-08-28"


def _candles(points):
    """Chandelles au format attendu par `_cloture_precedente`."""
    return pd.DataFrame(points)


# ── R10 : la variation est plafonnée à ±10 % par séance ────────────────────

def test_variation_recalculee_depuis_la_cloture_connue(ud):
    """La source dit 0 % alors que le cours a bougé — cas R9 typique.

    IDBourse sert le cours de référence de la veille comme cours du jour pour
    les titres peu échangés. Nos chandelles, elles, portent la vraie clôture.
    """
    c = _candles([{"d": "2026-08-27", "c": 100.0}, {"d": SEANCE, "c": 100.0}])
    assert ud.recalculer_variation("TST", 102.0, 0.0, c, SEANCE) == 2.0


def test_variation_impossible_est_annulee(ud):
    """⚠️ R10 : au-delà de ±10 %, ce n'est jamais un mouvement réel.

    C'est un cours de référence erroné. On garde 0 plutôt que d'afficher une
    variation impossible — un lecteur qui voit +45 % sur une valeur de la
    place conclut à un événement, pas à un bug.
    """
    c = _candles([{"d": "2026-08-27", "c": 100.0}, {"d": SEANCE, "c": 100.0}])
    assert ud.recalculer_variation("TST", 145.0, 45.0, c, SEANCE) == 0.0
    assert ud.recalculer_variation("TST", 50.0, -50.0, c, SEANCE) == 0.0


def test_variation_exactement_a_la_limite_est_acceptee(ud):
    """La limite est réglementaire : +10,00 % est légal, pas une anomalie."""
    c = _candles([{"d": "2026-08-27", "c": 100.0}, {"d": SEANCE, "c": 100.0}])
    assert ud.recalculer_variation("TST", 110.0, 0.0, c, SEANCE) == 10.0


def test_ecart_d_arrondi_ne_declenche_pas_de_recalcul(ud):
    """Sans ce seuil, chaque run réécrirait une variation infinitésimale."""
    c = _candles([{"d": "2026-08-27", "c": 100.0}, {"d": SEANCE, "c": 100.0}])
    assert ud.recalculer_variation("TST", 100.005, 0.0, c, SEANCE) == 0.0


@pytest.mark.parametrize("candles,prix,attendu", [
    (None,                                    102.0, 7.7),   # pas de chandelles
    (_candles([]),                            102.0, 7.7),   # série vide
    (_candles([{"d": SEANCE, "c": 100.0}]),      0.0, 7.7),   # prix nul
])
def test_sans_matiere_la_variation_de_la_source_est_conservee(ud, candles, prix, attendu):
    """Faute de contre-épreuve, on ne réécrit rien. On n'invente pas."""
    assert ud.recalculer_variation("TST", prix, 7.7, candles, SEANCE) == attendu


# ── ISIN suspect : le garde-fou Sothema ────────────────────────────────────

def test_moyenne_incoherente_avec_le_prix_neutralise_les_indicateurs(ud):
    """Le cas d'école : Sothema cote ~360 DH, la MA20 en annonce 1 666.

    Une moyenne mobile qui s'écarte du prix d'un facteur 3 ne décrit pas le
    même instrument. C'est la signature d'un ISIN erroné — on croise le cours
    d'une société avec l'historique d'une autre.
    """
    rsi, ma20, ma50, h90, l90, suspect = ud.neutraliser_si_isin_suspect(
        "SOT", 360.0, 79.6, 1666.0, 1700.0, 1800.0, 1500.0)
    assert suspect is True
    assert rsi == 50.0
    assert ma20 == 360.0 and ma50 == 360.0
    assert h90 == 414.0 and l90 == 306.0


def test_prix_aberrant_face_a_une_moyenne_saine_declenche_aussi(ud):
    """La détection joue dans les deux sens : c'est l'ÉCART qui est suspect.

    Un prix de 1 580 DH sur une valeur dont la moyenne est à 360 est le même
    défaut, vu de l'autre côté.
    """
    _, _, _, _, _, suspect = ud.neutraliser_si_isin_suspect(
        "SOT", 1580.0, 60.0, 360.0, 358.0, 380.0, 340.0)
    assert suspect is True


def test_ecart_normal_ne_declenche_pas(ud):
    """Un titre en tendance s'écarte de sa moyenne — sans que rien ne cloche.

    Le facteur 3 est délibérément large : la BVC plafonnant à ±10 % par
    séance, une MA20 ne peut pas s'éloigner autant par le marché seul.
    """
    rsi, ma20, _, _, _, suspect = ud.neutraliser_si_isin_suspect(
        "IAM", 102.75, 79.6, 96.74, 93.77, 130.0, 89.99)
    assert suspect is False
    assert rsi == 79.6 and ma20 == 96.74, "rien ne doit être touché"


@pytest.mark.parametrize("prix,ma20", [(0.0, 100.0), (100.0, 0.0), (0.0, 0.0)])
def test_valeurs_absentes_ne_declenchent_rien(ud, prix, ma20):
    """Sans les deux termes, la comparaison n'a pas de sens."""
    _, _, _, _, _, suspect = ud.neutraliser_si_isin_suspect(
        "TST", prix, 50.0, ma20, 0.0, 0.0, 0.0)
    assert suspect is False


# ── Le drapeau doit atteindre la confiance, pas mourir chez l'appelant ──────

def test_isin_suspect_plafonne_la_confiance(ud):
    """Relevé par `relecteur-pipeline` le 31/08 : le garde-fou n'était pas branché.

    La détection renvoyait bien son drapeau, mais l'appelant le jetait dans un
    `_`. Conséquence : un titre à l'ISIN croisé gardait 5 sur 5 — ses chandelles
    sont nombreuses (celles de la mauvaise société), ses fondamentaux présents,
    son corpus fourni. Le terminal affichait donc un ACHETER en couleur pleine
    sur une donnée dont le moteur venait de journaliser l'incohérence.

    Sous une confiance de 1, le frontend grise le signal — c'est la promesse
    « pas de signal sans confiance » du CLAUDE.md.
    """
    import pandas as pd
    sent = {"mentions": 500, "win": 60}
    bougies = pd.DataFrame([{"d": f"2026-0{1 + i // 28}-{1 + i % 28:02d}", "c": 100.0}
                            for i in range(60)])

    sain = ud._meta_ticker("IAM", "cdg", "2026-08-31", sent, bougies,
                           isin_suspect=False)
    suspect = ud._meta_ticker("IAM", "cdg", "2026-08-31", sent, bougies,
                              isin_suspect=True)

    assert sain["confidence"] > 1, "un titre sain doit garder sa confiance"
    assert suspect["confidence"] <= 1, "un ISIN suspect doit faire griser le signal"


def test_le_plafond_ne_remonte_jamais_une_confiance_basse(ud):
    """Le plafond abaisse, il ne relève pas : `min`, pas une affectation."""
    m = ud._meta_ticker("XXX", "static", "", {"mentions": 0, "win": None}, None,
                        isin_suspect=True)
    assert m["confidence"] == 0

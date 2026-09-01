"""Le référentiel — R2 : `ISIN_MAP` est le point de vérité unique.

Un ISIN erroné donne des données fausses pour ce ticker à jamais, et l'erreur
est silencieuse : le titre affiche le cours d'une autre société. C'est arrivé
quatre fois (RIS, RDS, SMI, SRM) et une fois de façon spectaculaire — Sanlam
affichait 430 DH, le prix de Salafin, au lieu de ~2 990.
"""

import re

import pytest


def test_isin_bien_formes(config):
    """Un ISIN marocain : « MA » + 10 chiffres."""
    faux = {t: i for t, i in config.ISIN_MAP.items()
            if not re.fullmatch(r"MA\d{10}", str(i))}
    assert not faux, f"ISIN mal formés : {faux}"


def test_aucun_isin_partage_par_deux_titres_actifs(config):
    """Un ISIN dupliqué = un titre qui affiche silencieusement le cours d'un autre.

    Constaté le 01/07 : STR portait l'ISIN d'Ennakl et affichait ~54 DH.

    ⚠️ Le contrôle porte sur `TICKERS_ALL`, pas sur `ISIN_MAP` entier : la table
    contient aussi des ALIAS hérités qui pointent volontairement le même
    instrument (`TGC`→TGCC, `SON`→SNA). Un alias hors univers est inoffensif —
    rien ne le collecte. Deux titres COLLECTÉS partageant un ISIN, en revanche,
    se voleraient leur cours.
    """
    univers = set(config.TICKERS_ALL)
    vus, doublons = {}, {}
    for t, i in config.ISIN_MAP.items():
        if t not in univers:
            continue
        if i in vus:
            doublons.setdefault(i, [vus[i]]).append(t)
        vus[i] = t
    assert not doublons, f"ISIN partagés entre titres collectés : {doublons}"


def test_alias_hors_univers_documentes(config):
    """Fige les seuls doublons tolérés, pour qu'un nouveau saute aux yeux.

    Si ce test échoue, un ISIN vient d'être dupliqué sans être déclaré ici :
    vérifier qu'il s'agit bien d'un alias et non d'une erreur de saisie.
    """
    univers = set(config.TICKERS_ALL)
    par_isin = {}
    for t, i in config.ISIN_MAP.items():
        par_isin.setdefault(i, []).append(t)
    alias = {i: sorted(ts) for i, ts in par_isin.items() if len(ts) > 1}
    assert alias == {
        "MA0000012528": ["TGC", "TGCC"],   # TGCC — ancien symbole
        "MA0000010019": ["SNA", "SON"],    # Sonasid — ancien symbole
    }, f"nouveau doublon d'ISIN non documenté : {alias}"
    for tickers in alias.values():
        assert sum(1 for t in tickers if t in univers) == 1, \
            f"un seul de {tickers} doit être dans TICKERS_ALL"


def test_valeurs_radiees_hors_univers(config):
    """Une société radiée n'a plus de cours — la publier, c'est inventer.

    Timar est sortie de la cote le 10/06/2024, après une offre publique de
    retrait obligatoire à 660 DH. Vingt-sept mois plus tard, le terminal
    l'affichait encore à 195 DH avec un PER : aucune source ne la servant, elle
    tombait jusqu'au dernier repli, qui recopiait le run précédent
    indéfiniment.

    ⚠️ Elles restent dans COMPANY_NAMES et ISIN_MAP : on archive, on ne supprime
    pas. L'historique des chandelles et le corpus NLP les mentionnent encore, et
    un nom manquant ferait apparaître « ? » là où une explication est due.
    """
    for sym, info in config.VALEURS_RADIEES.items():
        assert sym not in config.TICKERS_ALL, \
            f"{sym} est radiée depuis le {info['date']} — elle ne doit plus être collectée"
        assert sym not in config.TICKERS_ACTIFS


def test_registre_des_radiees_documente(config):
    """Chaque radiation porte sa date et son motif, pour qu'on n'ait pas à

    rouvrir l'enquête si la question revient dans six mois.
    """
    for sym, info in config.VALEURS_RADIEES.items():
        assert info.get("date") and info.get("motif"), f"{sym} mal documentée"


def test_isin_maroc_leasing_fige(config):
    """MRL — question ouverte depuis le 02/07/2026, refermée le 01/09.

    Le référentiel portait MA0000012270, que le journal du projet signalait déjà
    comme « absent du référentiel BVC officiel » sans savoir par quoi le
    remplacer. La fiche société de CDG Capital Bourse donne MA0000010035 pour
    « MLE · MAROC LEASING ».

    ⚠️ Ce n'est pas le code qui a emporté la décision, c'est l'arithmétique :
    capital social 277 676 800 ÷ valeur nominale 100 = 2 776 768 titres, et la
    capitalisation de la fiche divisée par ce nombre redonne exactement le cours
    que nous publions. Deux sources qui citent le même code peuvent se tromper
    ensemble ; une identité qui se recoupe par le calcul, non.

    Ce test fige la valeur pour qu'un futur audit ne la défasse pas par
    inadvertance.
    """
    assert config.ISIN_MAP["MRL"] == "MA0000010035"
    assert config.IDB_TICKER_MAP["MRL"] == "MLE", "ticker officiel BVC"


def test_recoupement_arithmetique_maroc_leasing():
    """Fige le calcul qui a servi de preuve, pour qu'il reste vérifiable."""
    titres = 277_676_800 // 100
    assert titres == 2_776_768
    assert round(1_081_689_974.40 / titres, 2) == 389.55


def test_tickers_actifs_inclus_dans_tickers_all(config):
    manquants = set(config.TICKERS_ACTIFS) - set(config.TICKERS_ALL)
    assert not manquants, f"MASI 1 absents de TICKERS_ALL : {manquants}"


def test_tickers_actifs_ont_un_isin(config):
    """R1 : les 19 titres du MASI 1 doivent être collectables."""
    manquants = [t for t in config.TICKERS_ACTIFS if t not in config.ISIN_MAP]
    assert not manquants, f"MASI 1 sans ISIN : {manquants}"


def test_traduction_des_tickers_reversible(config):
    """⚠️ Le piège le plus coûteux du projet.

    Les sources externes (CDG, BMCE, bulletin PDF) utilisent les tickers
    OFFICIELS BVC : leur `SNA` est Stokvis, notre `SNA` est Sonasid. Sans
    traduction, l'écart affiché atteint 96 % et l'on croit à une panne.
    Ce test garantit que la table reste bijective.
    """
    inverse = {}
    collisions = {}
    for notre, officiel in config.IDB_TICKER_MAP.items():
        if officiel in inverse:
            collisions.setdefault(officiel, [inverse[officiel]]).append(notre)
        inverse[officiel] = notre
    assert not collisions, f"deux de nos tickers pointent le même code BVC : {collisions}"


def test_inversions_critiques_figees(config):
    """Les trois inversions qui ont réellement causé des dégâts."""
    assert config.IDB_TICKER_MAP.get("STK") == "SNA", "Stokvis → SNA côté BVC"
    assert config.IDB_TICKER_MAP.get("SNA") == "SID", "Sonasid → SID côté BVC"
    assert config.IDB_TICKER_MAP.get("SBS") == "SBM", "Bs. Maroc → SBM côté BVC"


@pytest.mark.parametrize("date_iso,attendu", [
    ("2026-01-01", True),    # Nouvel An
    ("2026-05-01", True),    # Fête du Travail
    ("2026-08-14", True),    # Oued Ed-Dahab
    ("2026-08-28", False),   # séance ordinaire
    ("2026-08-27", False),
    ("", False),             # entrée vide : ne doit pas lever
    (None, False),           # entrée nulle : ne doit pas lever
])
def test_feries_a_date_fixe(config, date_iso, attendu):
    assert config.est_ferie_fixe(date_iso) is attendu


def test_feries_lunaires_absents_volontairement(config):
    """⚠️ Le Mawlid des 25–26/08/2026 ne DOIT PAS être dans la table.

    Les fêtes religieuses marocaines suivent le calendrier lunaire et ne sont
    confirmées par décret que peu de temps avant. Une liste écrite d'avance
    vieillirait sans prévenir. Ces jours-là sont détectés par les données, via
    `purger_seance_fantome`.
    """
    assert not config.est_ferie_fixe("2026-08-25")
    assert not config.est_ferie_fixe("2026-08-26")


def test_ajustement_split_managem(config):
    """Split 10:1 du 27/07/2026 : avant, on divise ; après, on ne touche pas."""
    serie = [{"d": "2026-07-24", "o": 13000, "h": 13200, "l": 12900, "c": 13060, "v": 500},
             {"d": "2026-07-27", "o": 1250, "h": 1380, "l": 1240, "c": 1364, "v": 900}]
    r = config.adjust_splits("MNG", [dict(x) for x in serie])
    assert r[0]["c"] == 1306, "la séance pré-split doit être divisée par 10"
    assert r[1]["c"] == 1364, "la séance du jour du split ne doit pas bouger"


def test_ajustement_split_ne_touche_pas_les_volumes(config):
    """Un split ne change pas la quantité échangée — le ×10 du 31/07 était une erreur."""
    serie = [{"d": "2026-07-24", "c": 13060, "v": 500}]
    assert config.adjust_splits("MNG", [dict(x) for x in serie])[0]["v"] == 500


def test_ajustement_split_ignore_les_tickers_sans_split(config):
    serie = [{"d": "2020-01-01", "c": 100, "v": 10}]
    assert config.adjust_splits("IAM", [dict(x) for x in serie])[0]["c"] == 100

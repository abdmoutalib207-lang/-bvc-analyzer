"""`fusionner_cotations` — le cœur de R3, et le berceau des deux bugs jumeaux.

Ce bloc vivait à l'intérieur de `run()`, au milieu de 768 lignes. Il y était
intestable, et il a produit DEUX FOIS le même défaut en deux jours : une source
oubliée dans la liste de celles autorisées à écrire une bougie.

Extrait le 31/08, il accepte désormais ses sources en paramètres — c'est ce qui
permet de le vérifier sans toucher au réseau.

RÈGLE CENTRALE : l'arbitrage se fait ligne par ligne et par la DATE, jamais par
la préférence. Une source « préférée » qui l'emporterait toujours ne serait plus
une chaîne de repli mais un point unique de défaillance déguisé.
"""

import pytest

HIER, JOUR = "2026-08-27", "2026-08-28"


def _idb(prix, asof, cap=1000):
    return {"price": prix, "asof": asof, "src": "idbourse", "cap": cap}


def _ext(prix, asof):
    return {"price": prix, "asof": asof}


# ── CDG en tête, mais seulement si elle est au moins aussi fraîche ──────────

def test_cdg_plus_fraiche_prend_la_main(ud):
    lp = {"IAM": _idb(100.0, HIER)}
    r = ud.fusionner_cotations(lp, HIER, cdg={"IAM": _ext(102.75, JOUR)},
                               bmce={}, lignes_cdg=[])
    assert lp["IAM"]["price"] == 102.75
    assert lp["IAM"]["src"] == "cdg"
    assert r == JOUR, "la séance de référence doit avancer avec CDG"


def test_cdg_plus_ancienne_ne_prend_pas_la_main(ud):
    """Si CDG retarde, IDBourse reprend la main d'elle-même.

    C'est ce mécanisme, dans l'autre sens, qui a sauvé la séance du 27/08.
    Sans lui, « CDG en tête » deviendrait une préférence aveugle.
    """
    lp = {"IAM": _idb(102.75, JOUR)}
    r = ud.fusionner_cotations(lp, JOUR, cdg={"IAM": _ext(100.0, HIER)},
                               bmce={}, lignes_cdg=[])
    assert lp["IAM"]["price"] == 102.75
    assert lp["IAM"]["src"] == "idbourse"
    assert r == JOUR


def test_capitalisation_idbourse_toujours_preservee(ud):
    """⚠️ IDBourse est la SEULE source de la capitalisation boursière.

    Elle est absente des 26 champs de CDG. La perdre viderait le classement
    par taille — un titre sans `cap` disparaît du tri principal.
    """
    lp = {"IAM": _idb(100.0, HIER, cap=90327)}
    ud.fusionner_cotations(lp, HIER, cdg={"IAM": _ext(102.75, JOUR)},
                           bmce={}, lignes_cdg=[])
    assert lp["IAM"]["cap"] == 90327, "la capitalisation ne doit jamais être perdue"


def test_titres_hors_perimetre_cdg_conservent_leur_ligne(ud):
    """CDG ne cote pas tout. Les absents gardent leur ligne IDBourse, datée."""
    lp = {"IAM": _idb(100.0, JOUR), "ZLD": _idb(201.2, HIER)}
    ud.fusionner_cotations(lp, JOUR, cdg={"IAM": _ext(102.75, JOUR)},
                           bmce={}, lignes_cdg=[])
    assert lp["ZLD"]["price"] == 201.2
    assert lp["ZLD"]["src"] == "idbourse"


# ── BMCE : elle comble, elle ne remplace pas ───────────────────────────────

def test_bmce_comble_un_titre_absent_de_cdg(ud):
    """Le 28/08, BMCE a comblé 10 titres, dont SRM — un titre du MASI 1.

    Sans elle, SRM retombait sur les chandelles, daté de la veille.
    """
    lp = {"IAM": _idb(100.0, HIER), "SRM": _idb(465.0, HIER)}
    ud.fusionner_cotations(lp, HIER, cdg={"IAM": _ext(102.75, JOUR)},
                           bmce={"SRM": _ext(465.0, JOUR)}, lignes_cdg=[])
    assert lp["SRM"]["src"] == "bmce"
    assert lp["SRM"]["asof"] == JOUR


def test_a_seance_egale_cdg_garde_la_main(ud):
    """À information égale, on préfère la source qui apparie par CODE.

    CDG identifie par code officiel BVC ; BMCE est appariée par RAISON SOCIALE
    contre la table que CDG fournit. Un appariement par nom est ce qui a mis
    les cours de Marsa Maroc dans Maroc Leasing (ERRORS.md, famille 13).
    """
    lp = {"IAM": _idb(100.0, HIER)}
    ud.fusionner_cotations(lp, HIER, cdg={"IAM": _ext(102.75, JOUR)},
                           bmce={"IAM": _ext(103.0, JOUR)}, lignes_cdg=[])
    assert lp["IAM"]["price"] == 102.75
    assert lp["IAM"]["src"] == "cdg"


def test_bmce_strictement_plus_fraiche_prend_la_main(ud):
    """⚠️ CE TEST EXIGEAIT L'INVERSE, ET IL AVAIT TORT.

    Il s'appelait « bmce_ne_remplace_jamais_une_ligne_cdg » et affirmait que
    « BMCE ne prime pas sur CDG, même à date égale ». La première moitié de la
    phrase est juste — à date ÉGALE, voir le test précédent. La seconde a
    coûté une matinée de publication.

    Le 17/09/2026 à 11h18, séance ouverte depuis 9h30 : CDG servait 69 titres
    datés du 16 et BMCE 53 titres datés du 17. Le terminal a publié la veille.
    La docstring de `fusionner_cotations` dit pourtant que « l'arbitrage se
    fait par la DATE, jamais par la préférence » (R3) ; le code disait le
    contraire.
    """
    lp = {"IAM": _idb(100.0, HIER)}
    r = ud.fusionner_cotations(lp, HIER, cdg={"IAM": _ext(102.75, HIER)},
                               bmce={"IAM": _ext(103.5, JOUR)}, lignes_cdg=[])
    assert lp["IAM"]["price"] == 103.5
    assert lp["IAM"]["src"] == "bmce"
    assert r == JOUR, "la séance de référence doit avancer avec BMCE"


def test_une_ligne_bmce_hors_plafond_est_refusee(ud):
    """⚠️ LA GARDE D'IDENTITÉ QUI MANQUAIT.

    BMCE est appariée par raison sociale. Un appariement qui se trompe de
    société produit un saut de cours : la BVC plafonne à ±10 % par séance
    (R10), au-delà ce n'est pas le même titre.

    ⚠️ Mesuré avant d'écrire cette garde : sur les 53 titres où BMCE était plus
    fraîche que CDG le 17/09, le plus grand écart valait 4,8 % et AUCUN ne
    dépassait 10 %. La garde ne refuse donc rien de légitime aujourd'hui — elle
    attend le jour où l'appariement dérapera.
    """
    lp = {"IAM": _idb(100.0, HIER)}
    ud.fusionner_cotations(lp, HIER, cdg={"IAM": _ext(102.75, HIER)},
                           bmce={"IAM": _ext(999.0, JOUR)}, lignes_cdg=[])
    assert lp["IAM"]["price"] == 102.75, "une ligne aberrante a été retenue"
    assert lp["IAM"]["src"] == "cdg"


def test_un_ecart_sous_le_plafond_passe(ud):
    """Contre-épreuve : une garde qui refuserait tout gèlerait la séance."""
    lp = {"IAM": _idb(100.0, HIER)}
    ud.fusionner_cotations(lp, HIER, cdg={"IAM": _ext(100.0, HIER)},
                           bmce={"IAM": _ext(109.0, JOUR)}, lignes_cdg=[])
    assert lp["IAM"]["price"] == 109.0 and lp["IAM"]["src"] == "bmce"


def test_bmce_plus_ancienne_est_ignoree(ud):
    lp = {"SRM": _idb(465.0, JOUR)}
    ud.fusionner_cotations(lp, JOUR, cdg={"IAM": _ext(102.75, JOUR)},
                           bmce={"SRM": _ext(460.0, HIER)}, lignes_cdg=[])
    assert lp["SRM"]["price"] == 465.0
    assert lp["SRM"]["src"] == "idbourse"


def test_bmce_preserve_aussi_la_capitalisation(ud):
    lp = {"SRM": _idb(465.0, HIER, cap=1330)}
    ud.fusionner_cotations(lp, HIER, cdg={"IAM": _ext(102.75, JOUR)},
                           bmce={"SRM": _ext(465.0, JOUR)}, lignes_cdg=[])
    assert lp["SRM"]["cap"] == 1330


# ── Pannes de sources ──────────────────────────────────────────────────────

def test_cdg_muette_laisse_idbourse_en_tete(ud):
    """Et BMCE n'est PAS interrogée : sans les libellés officiels de CDG,

    l'appariement par raison sociale n'a plus de référence. Un appariement
    faux serait pire qu'un appariement manquant (R2).
    """
    lp = {"IAM": _idb(100.0, JOUR)}
    r = ud.fusionner_cotations(lp, JOUR, cdg={},
                               bmce={"IAM": _ext(999.0, JOUR)}, lignes_cdg=[])
    assert lp["IAM"]["price"] == 100.0
    assert lp["IAM"]["src"] == "idbourse"
    assert r == JOUR


def test_seance_de_reference_avance_si_idbourse_muette(ud):
    """Panne IDBourse : CDG donne à elle seule la séance de référence."""
    lp = {}
    r = ud.fusionner_cotations(lp, "", cdg={"IAM": _ext(102.75, JOUR)},
                               bmce={}, lignes_cdg=[])
    assert r == JOUR
    assert lp["IAM"]["src"] == "cdg"


def test_la_source_est_toujours_declaree(ud):
    """Sans `src`, `_meta.source_prix` serait faux et le frontend aveugle."""
    lp = {"IAM": _idb(100.0, HIER), "SRM": _idb(465.0, HIER), "ZLD": _idb(201.2, HIER)}
    ud.fusionner_cotations(lp, HIER, cdg={"IAM": _ext(102.75, JOUR)},
                           bmce={"SRM": _ext(465.0, JOUR)}, lignes_cdg=[])
    assert {s: v["src"] for s, v in lp.items()} == {
        "IAM": "cdg", "SRM": "bmce", "ZLD": "idbourse"}


@pytest.mark.parametrize("cdg_asof,idb_asof,attendu", [
    (JOUR,  HIER,  JOUR),   # CDG devance : la référence avance
    (HIER,  JOUR,  JOUR),   # IDBourse devance : la référence ne recule pas
    (JOUR,  JOUR,  JOUR),   # égalité
    (JOUR,  "",    JOUR),   # IDBourse muette
])
def test_seance_de_reference_ne_recule_jamais(ud, cdg_asof, idb_asof, attendu):
    lp = {"IAM": _idb(100.0, idb_asof)} if idb_asof else {}
    r = ud.fusionner_cotations(lp, idb_asof, cdg={"IAM": _ext(102.0, cdg_asof)},
                               bmce={}, lignes_cdg=[])
    assert r == attendu


# ── BMCE rediffuse la dernière transaction d'un titre non coté (30/09/2026) ──
#
# Prouvé sur la séance du 29/09 par le bulletin CDG : les 12 bougies identiques
# à la veille sont exactement 12 des titres déclarés non cotés. Valeurs de
# M2M telles que servies : 391 / 391 / 390 / 390 pour 51 titres.

def _bmce_m2m(asof):
    return {"price": 390.0, "open": 391.0, "high": 391.0, "low": 390.0,
            "vol": 51, "asof": asof}


BOUGIE_M2M = {"d": HIER, "o": 391.0, "h": 391.0, "l": 390.0, "c": 390.0, "v": 51}


def test_bmce_ecartee_quand_cdg_a_jour_dit_non_cote(ud):
    lp = {"M2M": _idb(390.0, HIER)}
    lignes = [{"Symbol": "M2M", "Libelle": "M2M Group", "Cours": "", "CoursDeReferance": 390}]
    r = ud.fusionner_cotations(lp, HIER, cdg={"IAM": _ext(102.75, JOUR)},
                               bmce={"M2M": _bmce_m2m(JOUR)}, lignes_cdg=lignes,
                               derniere_bougie=lambda s: None)
    assert lp["M2M"]["src"] == "idbourse" and lp["M2M"]["asof"] == HIER
    assert r == JOUR, "la séance avance par CDG, pas par la rediffusion"


def test_bmce_ecartee_quand_elle_copie_la_derniere_bougie(ud):
    """CDG en retard (le cas du 17/09) : c'est la bougie qui tranche."""
    lp = {"M2M": _idb(390.0, HIER)}
    r = ud.fusionner_cotations(lp, HIER, cdg={"IAM": _ext(102.75, HIER)},
                               bmce={"M2M": _bmce_m2m(JOUR)}, lignes_cdg=[],
                               derniere_bougie=lambda s: BOUGIE_M2M)
    assert lp["M2M"]["src"] == "idbourse"
    assert r == HIER, "une rediffusion écartée ne fait pas avancer la séance"


def test_une_vraie_seance_bmce_passe_toujours(ud):
    """Contre-épreuve : même cours, mais une autre quantité échangée."""
    lp = {"M2M": _idb(390.0, HIER)}
    vraie = {**_bmce_m2m(JOUR), "vol": 12}
    ud.fusionner_cotations(lp, HIER, cdg={"IAM": _ext(102.75, HIER)},
                           bmce={"M2M": vraie}, lignes_cdg=[],
                           derniere_bougie=lambda s: BOUGIE_M2M)
    assert lp["M2M"]["src"] == "bmce" and lp["M2M"]["asof"] == JOUR


def test_cdg_en_retard_ne_disqualifie_pas_bmce(ud):
    """« Non coté » selon une CDG restée sur la veille ne dit rien du jour."""
    lp = {"M2M": _idb(390.0, HIER)}
    lignes = [{"Symbol": "M2M", "Cours": ""}]
    ud.fusionner_cotations(lp, HIER, cdg={"IAM": _ext(102.75, HIER)},
                           bmce={"M2M": {**_bmce_m2m(JOUR), "vol": 12}},
                           lignes_cdg=lignes, derniere_bougie=lambda s: None)
    assert lp["M2M"]["src"] == "bmce"


def test_idbourse_redatee_quand_cdg_dit_non_cote(ud):
    """Sanlam, nuit du 30/09 : IDBourse le datait du 29 avec la transaction
    du 28. La ligne garde sa capitalisation, mais reprend sa vraie date."""
    lp = {"SAF": {**_idb(2999.0, JOUR, cap=16020), "vol": 6}}
    lignes = [{"Symbol": "SAH", "Cours": "", "CoursDeReferance": 2999}]
    ud.fusionner_cotations(lp, JOUR, cdg={"IAM": _ext(94.03, JOUR)}, bmce={},
                           lignes_cdg=lignes,
                           derniere_bougie=lambda s: {"d": HIER, "c": 2999.0})
    assert lp["SAF"]["asof"] == HIER and lp["SAF"]["cap"] == 16020
    assert lp["SAF"]["rediffusion"] is True


def test_redatation_sans_bougie_correspondante_laisse_sans_date(ud):
    lp = {"SAF": _idb(3050.0, JOUR)}
    lignes = [{"Symbol": "SAH", "Cours": ""}]
    ud.fusionner_cotations(lp, JOUR, cdg={"IAM": _ext(94.03, JOUR)}, bmce={},
                           lignes_cdg=lignes,
                           derniere_bougie=lambda s: {"d": HIER, "c": 2999.0})
    assert lp["SAF"]["asof"] == ""


def test_un_titre_cote_selon_cdg_n_est_jamais_redate(ud):
    lp = {"IAM": _idb(94.03, JOUR)}
    ud.fusionner_cotations(lp, JOUR, cdg={"IAM": _ext(94.03, JOUR)}, bmce={},
                           lignes_cdg=[{"Symbol": "IAM", "Cours": 94.03}],
                           derniere_bougie=lambda s: {"d": HIER, "c": 94.03})
    assert lp["IAM"]["asof"] == JOUR and "rediffusion" not in lp["IAM"]

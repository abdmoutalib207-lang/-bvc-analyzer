#!/usr/bin/env python3
"""Le briefing de clôture enrichi — six blocs, tous MESURÉS.

⚠️ LE MODÈLE ET SES DÉFAUTS
───────────────────────────
Un briefing rédigé par un autre assistant pour la séance du 29/09/2026 donnait
la trajectoire de l'indice, la comparaison à la veille, les publications, les
secteurs, les matières premières et des « niveaux ». Il y mêlait des
probabilités de scénarios, des « supports » sans méthode et trois titres qui
n'avaient pas coté. On reprend les six blocs, et rien du reste.

Attendus écrits à la main. Aucun accès réseau, aucun fichier du dépôt : le
contexte est injecté.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import briefing as bf  # noqa: E402

SEANCE = "2026-09-29"


def _traj(veille, ouv, haut, bas, clo, hh="10:15", hb="12:00"):
    return {"veille": veille, "ouverture": ouv, "heure_ouverture": "09:31",
            "plus_haut": haut, "heure_plus_haut": hh, "plus_bas": bas,
            "heure_plus_bas": hb, "cloture": clo}


# ── La trajectoire ─────────────────────────────────────────────────────────

def test_gain_d_ouverture_conserve():
    p = bf.phrase_trajectoire(_traj(100, 101, 103, 100.5, 102))
    assert "Le gain d'ouverture a été conservé jusqu'à la clôture." in p
    assert "pas descendu sous la clôture de la veille" in p
    # (102 − 100,5) / (103 − 100,5) = 1,5 / 2,5 = 60 %
    assert "à 60 % de l'amplitude de séance (2,50 points)" in p
    assert "première valeur calculée 101,00 (09:31)" in p
    assert "série intrajournalière s'arrête" not in p and "plus haut 103,00 (10:15)" in p


def test_gain_d_ouverture_partiellement_rendu_puis_efface():
    p = bf.phrase_trajectoire(_traj(100, 101, 101.5, 99, 100.5))
    assert "partiellement rendu" in p
    assert "pas descendu sous" not in p          # le plus bas 99 < veille 100
    p = bf.phrase_trajectoire(_traj(100, 101, 101.5, 99, 99.5))
    assert "Le gain d'ouverture a été effacé" in p


def test_baisse_d_ouverture_prolongee():
    # Clôture AU plus bas : la baisse s'est bien prolongée jusqu'au bout.
    p = bf.phrase_trajectoire(_traj(100, 99, 99.5, 97, 97))
    assert "La baisse d'ouverture s'est prolongée jusqu'à la clôture." in p
    assert "pas remonté au-dessus de la clôture de la veille" in p


def test_baisse_d_ouverture_creusee_puis_reprise():
    """06/10/2026 : plus bas à 97, clôture à 98 sous l'ouverture à 99. Dire
    « prolongée jusqu'à la clôture » cachait le rebond depuis le plus bas."""
    p = bf.phrase_trajectoire(_traj(100, 99, 99.5, 97, 98))
    assert "prolongée jusqu'à la clôture" not in p
    assert "creusée en séance, puis a été en partie reprise" in p


def test_une_serie_en_retard_est_signalee():
    t = dict(_traj(100, 101, 103, 100.5, 102), serie_rejoint_cloture=False,
             serie_jusqu_a="12:59:59")
    p = bf.phrase_trajectoire(t)
    assert ("(La série intrajournalière s'arrête à 12:59:59 ; clôture et "
            "extrêmes viennent de la synthèse CDG.)") in p


def test_une_heure_inconnue_n_est_pas_ecrite():
    p = bf.phrase_trajectoire(_traj(100, 101, 103, 100.5, 102, hh=None))
    assert "plus haut 103,00," in p


def test_sans_trajectoire_le_briefing_le_dit():
    b = bf.composer({"tickers": [], "masi": {}}, series={}, contexte={})
    assert any("trajectoire" in x for x in b["non_mesurable"])


# ── La veille ──────────────────────────────────────────────────────────────

HISTO = {
    "2026-09-26": {"cours": 99.0, "variation_pct": -0.95, "volume_mad": 500e6,
                   "hausses": 12, "baisses": 40, "inchanges": 12},
    "2026-09-29": {"cours": 100.0, "variation_pct": 0.60, "volume_mad": 400e6,
                   "hausses": 36, "baisses": 18, "inchanges": 13},
    "2026-09-30": {"cours": 101.0, "variation_pct": 1.0, "volume_mad": 1e6},
}


def test_la_veille_est_la_seance_precedente_enregistree():
    c = bf.comparaison_veille(HISTO, SEANCE)
    assert c["seance_veille"] == "2026-09-26"
    assert c["ecart_volume_pct"] == -20.0          # 400 / 500 − 1
    p = bf.phrase_veille(c)
    assert p == ("Par rapport à la séance du 26/09 : indice à +0,60 % après "
                 "-0,95 %, volume global 400,0 M DH contre 500,0 M DH "
                 "(-20,0 %), 36 hausses et 18 baisses contre 12 et 40.")


def test_sans_seance_precedente_rien_n_est_compare():
    assert bf.comparaison_veille({SEANCE: HISTO[SEANCE]}, SEANCE) is None
    assert bf.comparaison_veille(HISTO, "2026-09-27") is None


# ── Les publications officielles ───────────────────────────────────────────

def test_depots_de_la_seance_seulement_resultats_et_rattaches():
    entrees = [
        {"date": SEANCE, "titre": "Sothema - CP relatif aux résultats du 1er semestre 2026",
         "url": "https://www.ammc.ma/a.pdf"},
        {"date": SEANCE, "titre": "OCP - Résultats financiers du 1er semestre 2026",
         "url": "https://www.ammc.ma/b.pdf"},
        # ⚠️ Un chiffre d'affaires trimestriel n'est pas un dépôt de comptes.
        {"date": SEANCE, "titre": "RDS - CP relatif aux indicateurs du 2ème trimestre 2026",
         "url": "https://www.ammc.ma/c.pdf"},
        {"date": "2026-09-28", "titre": "Salafin - Résultats financiers du 1er semestre 2026",
         "url": "https://www.ammc.ma/d.pdf"},
    ]
    d = bf.depots_du_jour(entrees, SEANCE, resoudre={"Sothema": "SOT", "RDS": "RDS"}.get)
    assert [(x["ticker"], x["url"]) for x in d["titres"]] == [("SOT", "https://www.ammc.ma/a.pdf")]
    assert [x["emetteur"] for x in d["autres_emetteurs"]] == ["OCP"]


# ── Les niveaux ────────────────────────────────────────────────────────────

def _b(d, h, lo):
    return {"d": d, "o": lo, "h": h, "l": lo, "c": lo, "v": 10}


def _titre(sym, montant, stale=False, asof=SEANCE):
    return {"symbol": sym, "name": sym, "price": 100.0, "vol": 10,
            "echange_dh": montant, "_meta": {"prix_asof": asof, "stale": stale}}


def test_niveaux_des_titres_les_plus_echanges_et_reellement_cotes():
    bougies = {"AAA": [_b("2026-09-24", 110, 95), _b("2026-09-25", 108, 97),
                       _b("2026-09-26", 112, 99), _b(SEANCE, 104, 100)],
               "BBB": [_b(SEANCE, 50, 49)]}
    titres = [_titre("AAA", 5e6), _titre("BBB", 1e6),
              _titre("DAR", 9e9, stale=True)]              # rediffusion : exclu
    nv = bf.niveaux_titres(titres, SEANCE, bougies, n=3, top=5)
    assert [x["symbol"] for x in nv] == ["AAA", "BBB"]
    a = nv[0]
    assert (a["seance_bas"], a["seance_haut"]) == (100, 104)
    # Fenêtre des 3 dernières bougies : 25/09, 26/09, 29/09.
    assert a["fenetre"] == {"n": 3, "du": "2026-09-25", "au": SEANCE,
                            "plus_haut": 112, "date_plus_haut": "2026-09-26",
                            "plus_bas": 97, "date_plus_bas": "2026-09-25"}
    p = bf.phrase_niveaux_titres(nv)
    assert p.startswith("Titres les plus échangés — extrêmes des 3 dernières "
                        "séances (du 25/09 au 29/09) : AAA")
    assert "support" not in p.lower() and "résistance" not in p.lower()


def test_la_fenetre_de_l_indice_se_compte_en_seances_cotees():
    """⚠️ Mesuré le 30/09 : les 20 dernières clôtures de `masi_history.json`
    couvraient 27 séances. La fenêtre se compte donc en séances COTÉES, et la
    phrase dit combien de clôtures de l'indice y sont enregistrées."""
    clotures = {"2026-09-22": 90.0, "2026-09-24": 105.0, SEANCE: 100.0}
    cotees = {"2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25",
              "2026-09-26", SEANCE}
    histo = {SEANCE: {"plus_haut": 101.0, "plus_bas": 98.0,
                      "plus_haut_annee": 120.0, "plus_bas_annee": 80.0}}
    nv = bf.niveaux_masi(histo, clotures, SEANCE, n=4, seances_cotees=cotees)
    c = nv["clotures"]
    # 4 dernières séances cotées : 24, 25, 26, 29 → clôtures du 24 et du 29.
    assert (c["n_seances"], c["n"], c["du"]) == (4, 2, "2026-09-24")
    assert (c["plus_haute"], c["date_plus_haute"]) == (105.0, "2026-09-24")
    assert (c["plus_basse"], c["date_plus_basse"]) == (100.0, SEANCE)
    p = bf.phrase_niveaux_masi(nv)
    assert "sur les 4 dernières séances (du 24/09 au 29/09), sur les 2 clôtures" in p
    assert "plus haut de séance 101,00, plus bas 98,00" in p


# ── Les secteurs ───────────────────────────────────────────────────────────

def test_phrase_secteurs_tete_et_queue():
    sect = [{"libelle": l, "variation_pct": v} for l, v in (
        ("BOISSONS", 4.98), ("SOCIETE DE FINANCEMENT", 1.79), ("SANTE", 1.35),
        ("PHARMA", 0.0), ("CHIMIE", -2.7), ("SYLVICULTURE ET PAPIER", -3.72),
        ("ASSURANCES", -0.51))]
    sect.sort(key=lambda x: -x["variation_pct"])
    p = bf.phrase_secteurs(sect, k=2)
    assert p == ("Indices sectoriels (7 servis par CDG) : 3 en hausse, 3 en "
                 "baisse. En tête : Boissons +4,98 %, Societe de financement "
                 "+1,79 %. En queue : Sylviculture et papier -3,72 %, "
                 "Chimie -2,70 %.")


# ── L'ensemble ─────────────────────────────────────────────────────────────

MOTS_INTERDITS = ("probabilit", "scénario", "scenario", "support", "résistance",
                  "acheter", "vendre", "parce que", "à cause de", "sur fond de")


def test_le_briefing_complet_ne_conseille_ni_ne_probabilise():
    data = {"masi": {"change_pct": 0.6, "hausses": 36, "baisses": 18,
                     "inchanges": 13},
            "tickers": [_titre("AAA", 5e6)]}
    ctx = {"marche": HISTO, "masi": {SEANCE: 100.0},
           "depots": [], "resoudre": lambda n: None,
           "seance_marche": {SEANCE: {
               "trajectoire": _traj(99.0, 99.5, 100.4, 98.9, 100.0),
               "secteurs": [], "matieres": [
                   {"nom": "Brent", "valeur": 96.39, "variation_pct": 0.24,
                    "horodatage_utc": "2026-09-29T15:40:00Z"}]}},
           "bougies": {"AAA": [_b(SEANCE, 104, 100)]}}
    b = bf.composer(data, series={}, contexte=ctx)
    assert b["constats"][0].startswith("MASI : première valeur calculée 99,50 (09:31)")
    assert b["constats"][1].startswith("Par rapport à la séance du 26/09")
    assert b["matieres"][0]["horodatage_utc"] == "2026-09-29T15:40:00Z"
    tout = " ".join(b["constats"]).lower()
    for mot in MOTS_INTERDITS:
        assert mot not in tout, f"« {mot} » dans le briefing"
    assert any("sectoriels" in x for x in b["non_mesurable"])

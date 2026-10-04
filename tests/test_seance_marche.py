#!/usr/bin/env python3
"""Le relevé de la séance : trajectoire du MASI, secteurs, matières premières.

⚠️ CE QUE CES TESTS DÉFENDENT
─────────────────────────────
Chaque valeur publiée porte son identité vérifiée et sa DATE. Une valeur sans
date, une série qui ne rejoint pas la clôture servie, un code sectoriel creux :
tout cela est ÉCARTÉ, et le briefing dit ce qui manque.

Hors réseau : les réponses sont écrites à la main, sur le modèle exact de
celles reçues le 30/09/2026. Les attendus aussi — jamais recopiés d'une
exécution de la fonction testée.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import seance_marche as sm  # noqa: E402

SEANCE = "2026-09-29"


def _masi(**kw):
    d = {"Symbol": "MASI", "Libelle": "MASI", "Cours": 17754.9077,
         "CoursVeille": 17648.8955, "PlusHaut": 17825.7617,
         "PlusBas": 17647.3055, "DateCotation": "29/09/2026 08:03:01"}
    d.update(kw)
    return d


def _pt(h, c, jour="29/09/2026"):
    return {"HoroDatage": f"{jour} {h}:00", "Cours": c, "PlusHaut": "",
            "PlusBas": "", "Cloture": ""}


SERIE = [_pt("08:03", 17648.8955),            # pré-ouverture : la veille
         _pt("09:31", 17700.0), _pt("10:15", 17825.7617),
         _pt("12:00", 17647.3055), _pt("15:30", 17754.9077)]


# ── La trajectoire ─────────────────────────────────────────────────────────

def test_la_trajectoire_se_lit_sur_la_serie_datee_de_la_seance():
    t = sm.trajectoire(_masi(), SERIE, SEANCE)
    # ⚠️ L'ouverture est le premier point à partir de 09:30, pas le point de
    # 08:03 qui recopie la veille.
    assert t["ouverture"] == 17700.0 and t["heure_ouverture"] == "09:31:00"
    assert t["plus_haut"] == 17825.7617 and t["heure_plus_haut"] == "10:15:00"
    assert t["plus_bas"] == 17647.3055 and t["heure_plus_bas"] == "12:00:00"
    assert t["cloture"] == 17754.9077 and t["veille"] == 17648.8955
    assert t["n_points"] == 4
    assert t["serie_jusqu_a"] == "15:30:00" and t["serie_rejoint_cloture"] is True


def test_l_ordre_servi_est_garde_dans_une_meme_seconde():
    """La série porte jusqu'à 59 points par minute, plusieurs par seconde
    (relevé du 30/09 : trois points à 12:59:59). Le premier servi reste le
    premier, quelle que soit sa valeur."""
    serie = [_pt("09:30", 17700.0), _pt("09:30", 17690.0)]
    serie = [dict(p, HoroDatage="29/09/2026 09:30:05") for p in serie]
    t = sm.trajectoire(_masi(Cours=17690.0), serie, SEANCE)
    assert t["ouverture"] == 17700.0


def test_une_serie_servie_dans_le_desordre_est_remise_dans_l_ordre():
    """02/10/2026 : CDG a servi un point de 10:22:22 en premier et un point de
    09:37:13 en dernier. Le briefing publiait une ouverture à 10h22 et une
    série « arrêtée » à 9h37."""
    serie = [SERIE[2], SERIE[4], SERIE[1], SERIE[3]]      # 10:15, 15:30, 09:31, 12:00
    t = sm.trajectoire(_masi(), serie, SEANCE)
    assert t["heure_ouverture"] == "09:31:00" and t["ouverture"] == 17700.0
    assert t["serie_jusqu_a"] == "15:30:00" and t["serie_rejoint_cloture"] is True


def test_le_lendemain_matin_la_serie_ne_porte_plus_la_seance():
    """Relevé le 30/09 à 08h46 : un seul point, daté du 30, portant la clôture
    du 29. Il ne décrit pas la séance du 29 : refusé."""
    lendemain = [_pt("08:03", 17754.9077, jour="30/09/2026")]
    assert sm.trajectoire(_masi(), lendemain, SEANCE) is None


def test_une_serie_en_retard_est_gardee_et_son_retard_dit():
    """⚠️ Mesuré le 30/09 à 13h15 : la série s'arrêtait à 12:59:59 quand la
    synthèse était plus récente. Elle n'est pas fausse, elle est en retard :
    la clôture vient de la synthèse, et le relevé dit jusqu'où va la série."""
    serie = SERIE[:3] + [_pt("12:59", 17760.0)]
    t = sm.trajectoire(_masi(), serie, SEANCE)
    assert t["cloture"] == 17754.9077
    assert t["serie_jusqu_a"] == "12:59:00"
    assert t["serie_rejoint_cloture"] is False


def test_l_identite_et_la_date_de_la_synthese_sont_exigees():
    assert sm.trajectoire(_masi(Symbol="MSI20"), SERIE, SEANCE) is None
    assert sm.trajectoire(_masi(DateCotation="28/09/2026 08:03:01"),
                          SERIE, SEANCE) is None
    assert sm.trajectoire(None, SERIE, SEANCE) is None


def test_l_heure_d_un_extreme_absent_de_la_serie_n_est_pas_approchee():
    """⚠️ La série est échantillonnée : son maximum peut manquer le vrai plus
    haut. L'heure est alors inconnue, jamais celle du point le plus proche."""
    serie = [_pt("09:31", 17700.0), _pt("10:15", 17800.0),
             _pt("12:00", 17647.3055), _pt("15:30", 17754.9077)]
    t = sm.trajectoire(_masi(), serie, SEANCE)
    assert t["plus_haut"] == 17825.7617
    assert t["heure_plus_haut"] is None
    assert t["heure_plus_bas"] == "12:00:00"


# ── Les secteurs ───────────────────────────────────────────────────────────

def _sect(code, lib, var, date="29/09/2026 08:03:01"):
    return {"Symbol": code, "Libelle": lib, "Cours": 100.0, "VariationP": var,
            "CoursVeille": 99.0, "DateCotation": date}


def test_un_code_sectoriel_creux_n_est_pas_publie_a_zero():
    """⚠️ Un code inconnu renvoie des champs VIDES sans erreur (constaté sur
    `SAC`, `AGR`, `EEE` le 30/09). Sans contrôle, il s'afficherait à 0,00 %."""
    lignes = {"BANK": _sect("BANK", "BANQUES", 0.45),
              "SAC": {"Symbol": "", "Libelle": "", "Cours": "",
                      "VariationP": "", "DateCotation": ""},
              "S&P": _sect("S&P", "SYLVICULTURE ET PAPIER", -3.72),
              "BOISS": _sect("BOISS", "BOISSONS", 4.98),
              "VIEUX": _sect("VIEUX", "PÉRIMÉ", 1.0, date="26/09/2026 08:03:01"),
              "DECALE": _sect("AUTRE", "DÉCALÉ", 2.0)}
    s = sm.secteurs(lignes, SEANCE)
    assert [x["code"] for x in s] == ["BOISS", "BANK", "S&P"]
    assert s[0]["variation_pct"] == 4.98


def test_la_requete_apparie_les_blocs_par_position():
    """Le fournisseur renvoie les blocs dans l'ordre des actions demandées."""
    rep = ([{"INDICE-SYNTHESE": {"Valid": True, "Data": [_masi()]}},
            {"INDICE-O-GRAPH-INTRA": {"Valid": True, "Data": SERIE}}]
           + [{"INDICE-SYNTHESE": {"Valid": True, "Data": [_sect("BANK", "BANQUES", 0.45)]}},
              {"INDICE-SYNTHESE": {"Valid": False, "Data": []}}])
    lu = sm.lire_cdg(rep, secteurs=("BANK", "MINES"))
    assert lu["masi"]["Symbol"] == "MASI"
    assert len(lu["intra"]) == 5
    assert set(lu["secteurs"]) == {"BANK"}
    corps = sm.actions_cdg(("BANK", "MINES"))
    assert [a["ACTION"]["NAME"] for a in corps] == [
        "INDICE-SYNTHESE", "INDICE-O-GRAPH-INTRA", "INDICE-SYNTHESE", "INDICE-SYNTHESE"]


# ── Les matières premières ─────────────────────────────────────────────────

def _tv(lignes):
    return {"totalCount": len(lignes), "data": [{"s": s, "d": d} for s, d in lignes]}


def test_une_matiere_premiere_porte_son_horodatage_ou_n_est_pas_publiee():
    """⚠️ Jamais de valeur sans date. 1790758206 = 2026-09-30 08:50:06 UTC."""
    rep = _tv([
        ("ICEEUR:BRN1!", ["Brent Crude Futures", 96.39, 0.2391, "USD",
                          1790758206, "delayed_streaming_600"]),
        ("NYMEX:CL1!", ["Crude Oil Futures", 89.49, 0.12, "USD", None,
                        "delayed_streaming_600"]),
    ])
    m = sm.matieres(rep, attendus=(("ICEEUR:BRN1!", "Brent"), ("NYMEX:CL1!", "WTI")))
    assert [x["nom"] for x in m] == ["Brent"]
    b = m[0]
    assert b["valeur"] == 96.39 and b["variation_pct"] == 0.24
    assert b["horodatage_utc"] == "2026-09-30T08:50:06Z"
    # Le mode de diffusion est recopié tel que la source le déclare.
    assert b["mode_source"] == "delayed_streaming_600"
    assert b["devise"] == "USD"


def test_une_ligne_d_un_autre_contrat_n_est_pas_prise():
    rep = _tv([("TVC:UKOIL", ["Brent", 96.0, 0.1, "USD", 1790758206, "streaming"])])
    assert sm.matieres(rep, attendus=(("ICEEUR:BRN1!", "Brent"),)) == []


# ── L'historisation ────────────────────────────────────────────────────────

def test_un_passage_du_lendemain_n_efface_rien():
    """⚠️ Le lendemain matin, la série ne porte plus la séance et les
    matières premières décrivent la nuit suivante : ni l'une ni l'autre ne
    doit remplacer ce qui a été relevé le jour même."""
    ancien = {"trajectoire": {"cloture": 1.0}, "secteurs": [{"code": "BANK"}],
              "matieres": [{"nom": "Brent", "valeur": 96.0}]}
    nouveau = {"trajectoire": None, "secteurs": [{"code": "BANK", "v": 2}],
               "matieres": [{"nom": "Brent", "valeur": 99.0}]}
    e = sm.fusionner(ancien, nouveau, SEANCE, "2026-09-30")
    assert e["trajectoire"] == {"cloture": 1.0}
    assert e["matieres"] == [{"nom": "Brent", "valeur": 96.0}]
    assert e["secteurs"] == [{"code": "BANK", "v": 2}]


def test_le_jour_meme_les_matieres_se_rafraichissent():
    e = sm.fusionner({"matieres": [{"valeur": 1}]}, {"matieres": [{"valeur": 2}]},
                     SEANCE, SEANCE)
    assert e["matieres"] == [{"valeur": 2}]


def test_mettre_a_jour_ecrit_le_fichier_et_survit_a_une_source_en_panne(tmp_path):
    """Hors réseau : les deux sources sont injectées ; CDG répond, TradingView
    lève. Le fichier s'écrit quand même, avec ce qui a été lu."""
    def cdg(_actions):
        return ([{"INDICE-SYNTHESE": {"Valid": True, "Data": [_masi()]}},
                 {"INDICE-O-GRAPH-INTRA": {"Valid": True, "Data": SERIE}}]
                + [{"INDICE-SYNTHESE": {"Valid": True, "Data": [_sect("BANK", "BANQUES", 0.45)]}}])

    def tv(_tickers):
        raise RuntimeError("HTTP 403")

    chemin = tmp_path / "seance_marche.json"
    e = sm.mettre_a_jour(SEANCE, SEANCE, chemin=chemin, cdg=cdg, tv=tv)
    assert e["trajectoire"]["cloture"] == 17754.9077
    assert [x["code"] for x in e["secteurs"]] == ["BANK"]
    assert "matieres" not in e
    lu = json.loads(chemin.read_text(encoding="utf-8"))
    assert set(lu["seances"]) == {SEANCE}


def test_aucun_user_agent_deguise_en_navigateur():
    """⚠️ Si une source refuse un robot qui dit son nom, on s'en passe."""
    assert "Mozilla" not in sm.UA and "BVC-Analyzer" in sm.UA

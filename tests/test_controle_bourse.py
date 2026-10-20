"""Contrôles Bourse de Casablanca — 20/10/2026.

Famille « code » : aucune requête réseau. L'analyse des pages est écrite en
JavaScript (tools/bourse_casablanca.js) et éprouvée ici par `node` sur un
échantillon figé, relevé le 20/10/2026.
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import controle_bourse as cb  # noqa: E402
from pipeline.file_attente_comptes import ajouter_bourse, rapport  # noqa: E402

# Extrait du innerText de l'accueil, 20/10/2026 vers 15h00 (séance ouverte).
# Le carrousel duplique ses blocs : la duplication est conservée.
ACCUEIL = """Mardi 20 octobre 2026
|
Séance ouverte
Français
Émetteurs
CAPITALISATION
998 007 899 516
MAD
VOLUME GLOBAL
74 527 166
MAD
MASI 20
 +0,05%
1 226,96
MASI
 -0,06%
16 966,23
CAPITALISATION
998 007 899 516
MAD
VOLUME GLOBAL
74 527 166
MAD
MASI 20
 +0,05%
1 226,96
MASI
 -0,06%
16 966,23
AFMA
1 249,00
MASI20 FUTURE DEC26	1 215,00	+0,59%
"""

CSV = ("﻿Séance;Marché;Volume (MAD);Transactions;Titres échangés\n"
       "19/10/2026;Marché central;113 956 983.12;3 671;876 356\n"
       "12/10/2026;Augmentation capital numéraire;142 531 609.60;1;798 944\n"
       "12/10/2026;Marché central;52 945 136.05;3 317;199 770\n"
       "12/10/2026;Transferts;136 755.25;10;1 619\n")

JS = RACINE / "tools" / "bourse_casablanca.js"


def _node(expr: str, *args):
    if not shutil.which("node"):
        pytest.skip("node absent")
    code = (f"const m = require({json.dumps(str(JS))}); const a = process.argv.slice(1);"
            f"process.stdout.write(JSON.stringify({expr}));")
    sortie = subprocess.run(["node", "-e", code, *args], capture_output=True, text=True, check=True)
    return json.loads(sortie.stdout)


# ── Analyse du texte de l'accueil ────────────────────────────────────────

def test_accueil_echantillon_fige():
    a = _node("m.analyserAccueil(a[0])", ACCUEIL)
    assert a["date_affichee"] == "2026-10-20"
    assert a["etat_seance"] == "Séance ouverte"
    assert a["capitalisation_mad"] == 998007899516
    assert a["volume_global_mad"] == 74527166
    assert a["masi"] == 16966.23 and a["masi_variation_pct"] == -0.06
    assert a["masi20"] == 1226.96          # « MASI 20 » n'est pas « MASI »
    assert a["anomalies"] == []


def test_accueil_occurrences_discordantes_signalees():
    texte = ACCUEIL.replace("74 527 166", "74 999 999", 1)
    a = _node("m.analyserAccueil(a[0])", texte)
    assert a["volume_global_mad"] == 74999999
    assert any(x["bloc"] == "VOLUME GLOBAL" for x in a["anomalies"])


def test_accueil_champ_absent_vaut_null():
    a = _node("m.analyserAccueil(a[0])", "Page en maintenance\n")
    assert a["date_affichee"] is None and a["volume_global_mad"] is None and a["masi"] is None


def test_nombre_illisible_vaut_null():
    assert _node("[m.nombre('1 2a'), m.nombre('16 966,23'), m.nombre('113 956 983.12')]") == [
        None, 16966.23, 113956983.12]


def test_historique_csv():
    h = _node("m.analyserHistoriqueCsv(a[0])", CSV)
    assert h[0] == {"seance": "2026-10-19", "marche": "Marché central", "volume_mad": 113956983.12,
                    "transactions": 3671, "titres": 876356}
    assert len(h) == 4
    assert _node("m.analyserHistoriqueCsv('<html>erreur</html>')") is None


def test_page_volume_sous_marches():
    vd = {"MARKET_INFO": {"comptant": {"totalVol": 74569732.84000001, "transactions": 607209}},
          "SUB_MARKET_DATA": {"comptant": [{"name": "Carnet Central", "volume": 74569732.84}]}}
    v = _node("m.analyserPageVolume(a[0], JSON.parse(a[1]))", "x\nSéance du 20/10/2026\n", json.dumps(vd))
    assert v == {"seance": "2026-10-20", "volume_global_mad": 74569732.84, "quantites_echangees": 607209,
                 "sous_marches": [{"marche": "Carnet Central", "volume_mad": 74569732.84}]}


def test_emetteur_du_titre():
    assert _node("[m.emetteurDuTitre('Auto Nejma - Résultats financiers du 1er semestre 2026'),"
                 " m.emetteurDuTitre('IAM : 2016 consolidated results'),"
                 " m.emetteurDuTitre('FINANCIAL STATEMENTS 2010')]") == ["Auto Nejma", "IAM", None]


# ── Écart de volume et mode observation ──────────────────────────────────

def test_ecart_pct():
    assert cb.ecart_pct(100.0, 99.3) == -0.7
    assert cb.ecart_pct(200.0, 201.8) == 0.9
    assert cb.ecart_pct(None, 5.0) is None and cb.ecart_pct(0, 5.0) is None


def _bougies(tmp_path, seance):
    (tmp_path / "AAA.json").write_text(json.dumps([{"d": seance, "o": 10, "h": 10, "l": 10, "c": 10, "v": 1000}]))
    (tmp_path / "BBB.json").write_text(json.dumps({"candles": [{"d": seance, "o": 5, "h": 5, "l": 5, "c": 5, "v": 200},
                                                                 {"d": "2026-10-16", "c": 5, "v": 9}]}))
    return tmp_path


def _accueil(seance, vg, etat="Séance fermée", hist=None):
    return {"date_affichee": seance, "etat_seance": etat, "volume_global_mad": vg,
            "page_volume": {"seance": seance, "volume_global_mad": vg, "sous_marches": []},
            "historique_volumes": hist or [], "releve_le": "2026-10-19T19:40:00Z"}


SOIR = datetime(2026, 10, 19, 19, 40, tzinfo=timezone.utc)


def test_montant_bougies(tmp_path):
    assert cb.montant_bougies("2026-10-19", _bougies(tmp_path, "2026-10-19")) == (11000.0, 2)


def test_observation_ne_bloque_jamais_meme_ecart_enorme(tmp_path):
    m = cb.mesurer_volume(_accueil("2026-10-19", 1.0), SOIR, _bougies(tmp_path, "2026-10-19"))
    assert m["statut"] == "observation" and m["bloquant"] is False
    assert m["ecart_pct"] > 1e5
    assert cb.TOLERANCE_PCT is None
    assert cb.code_sortie(m) == 0


def test_le_seuil_ne_joue_que_s_il_est_renseigne(tmp_path, monkeypatch):
    """Garde contre un mutant : sans cette preuve, `code_sortie` pourrait rendre 0 toujours."""
    monkeypatch.setattr(cb, "TOLERANCE_PCT", 2.0)
    m = cb.mesurer_volume(_accueil("2026-10-19", 1.0), SOIR, _bougies(tmp_path, "2026-10-19"))
    assert m["statut"] == "hors_tolerance" and cb.code_sortie(m) == 1


def test_main_rend_zero_en_observation(tmp_path, monkeypatch):
    (tmp_path / "c").mkdir()
    monkeypatch.setattr(cb, "CANDLES", _bougies(tmp_path / "c", "2026-10-19"))
    monkeypatch.setattr(cb, "REFERENCE", tmp_path / "absent.json")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    acc = tmp_path / "a.json"
    acc.write_text(json.dumps(_accueil("2026-10-19", 1.0)))
    assert cb.main(["--accueil", str(acc), "--sortie", str(tmp_path / "out")]) == 0
    # Un relevé absent (site injoignable) ne fait pas échouer non plus.
    assert cb.main(["--accueil", str(tmp_path / "rien.json"), "--publications", str(tmp_path / "rien2.json")]) == 0


def test_seance_ouverte_ou_future_non_mesuree(tmp_path):
    d = _bougies(tmp_path, "2026-10-20")
    midi = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
    assert cb.mesurer_volume(_accueil("2026-10-20", 7e7, "Séance ouverte"), midi, d)["statut"] == "seance_non_echue"
    # Même après 15h30, un état « ouverte » affiché interdit la mesure.
    tard = datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)
    assert cb.mesurer_volume(_accueil("2026-10-20", 7e7, "Séance ouverte"), tard, d)["statut"] == "seance_non_echue"
    assert cb.mesurer_volume(_accueil("2026-10-20", 7e7), tard, d)["statut"] == "observation"


def test_bougies_absentes(tmp_path):
    m = cb.mesurer_volume(_accueil("2026-10-19", 7e7), SOIR, tmp_path)
    assert m["statut"] == "bougies_absentes" and m["bloquant"] is False


def test_perimetre():
    assert cb.perimetre(100.0, 100.0, {}).startswith("non discriminant")
    assert cb.perimetre(100.0, 100.0, {"Transferts": 5.0}) == "marché central seul"
    assert cb.perimetre(105.0, 100.0, {"Transferts": 5.0}) == "marché central + Transferts"
    assert cb.perimetre(150.0, 100.0, {"Transferts": 5.0}) == "aucun des deux"
    assert cb.perimetre(None, 100.0, {}) == "inconnu"


def test_mesure_relisible_dans_la_reference(tmp_path):
    hist = [{"seance": "2026-10-19", "marche": "Marché central", "volume_mad": 11000.0},
            {"seance": "2026-10-19", "marche": "Transferts", "volume_mad": 50.0}]
    m = cb.mesurer_volume(_accueil("2026-10-19", 11050.0, hist=hist), SOIR, _bougies(tmp_path, "2026-10-19"))
    assert m["perimetre_volume_global"] == "marché central + Transferts"
    assert m["ecart_pct_vs_marche_central"] == 0.0
    ref = cb.ajouter_mesure({"seances": [1], cb.CLE_MESURES: [{"seance": "2026-10-16"}]}, m)
    ref = cb.ajouter_mesure(ref, m)                     # même séance : pas de doublon
    assert [x["seance"] for x in ref[cb.CLE_MESURES]] == ["2026-10-16", "2026-10-19"]
    assert ref["seances"] == [1]
    (tmp_path / "vide").mkdir()
    non = cb.mesurer_volume(_accueil("2026-10-19", 7e7), SOIR, tmp_path / "vide")
    assert non["statut"] == "bougies_absentes"
    # Un passage sans mesure n'efface pas la mesure de la même séance.
    assert cb.ajouter_mesure(ref, non)[cb.CLE_MESURES] == ref[cb.CLE_MESURES]


# ── Appariement des publications ─────────────────────────────────────────

def test_appariement_par_nom():
    assert cb.apparier("Auto Nejma")[0] == "NEJ"
    assert cb.apparier("Attijariwafa Bank")[0] == "ATW"
    assert cb.apparier("Ennakl Automobiles")[0] == "ENK"          # alias relevé à l'AMMC


def test_code_ambigu_jamais_tranche():
    # « SNA » : notre Sonasid, mais Stokvis (notre STK) au code officiel.
    t, methode, cands = cb.apparier("SNA")
    assert t is None and methode == "ambigu" and cands == ["SNA", "STK"]


def test_code_officiel_traduit():
    # « SID » est le code officiel de Sonasid, notre SNA.
    assert cb.apparier("SID")[0] == "SNA"


def test_non_apparie():
    assert cb.apparier("Autoroutes du Maroc")[:2] == (None, "non_apparie")
    assert cb.apparier("Crédit")[:2] == (None, "non_apparie")    # pas de rapprochement partiel
    assert cb.apparier(None)[:2] == (None, "sans_emetteur")


def test_type_presume():
    assert cb.type_presume("Auto Nejma - Résultats financiers du 1er semestre 2026") == "semestriel"
    assert cb.type_presume("X - Rapport financier annuel 2025") == "annuel"
    assert cb.type_presume("IAM : 2016 consolidated results") == "annuel"
    assert cb.type_presume("Disty Technologies - CP relatif au changement du CA") == "communiqué"
    assert cb.type_presume("Seuil franchi", "Annonces") == "autre"


CONNU = {"urls": {"https://x/deja.pdf"}, "fichiers": {"deja.pdf"}, "s1_integres": {"NEJ"},
         "s1_ecartes": {"SAF"}, "annuels_2025": {"ATW"}, "depuis": "2026-06-30",
         "ammc": {"ADH": {"date": "2026-09-30", "url": "https://ammc/adh.pdf"}}}


def _pub(titre, url, date=None, modif="2026-10-05", emetteur=None):
    return {"titre": titre, "url": url, "date": date, "fichier_modifie_le": modif,
            "emetteur": emetteur or titre.split(" - ")[0]}


def test_classement_publications():
    pubs = [
        _pub("Auto Nejma - Résultats financiers du 1er semestre 2026", "https://b/nej.pdf"),
        _pub("Addoha - Résultats financiers du 1er semestre 2026", "https://b/adh.pdf"),
        _pub("Sanlam Maroc - Résultats du 1er semestre 2026", "https://b/saf.pdf"),
        _pub("Attijariwafa Bank - Rapport financier annuel 2025", "https://b/atw.pdf"),
        _pub("Attijariwafa Bank - CP acquisition", "https://x/deja.pdf"),
        _pub("Autoroutes du Maroc - Résultats du 1er semestre 2026", "https://b/adm.pdf"),
        _pub("SNA - Résultats du 1er semestre 2026", "https://b/sna.pdf"),
        _pub("Sans émetteur dans le titre", "https://b/x.pdf", emetteur=None),
        _pub("IAM : 2016 consolidated results", "https://b/iam.pdf", date="2017-02-27", emetteur="IAM"),
    ]
    pubs[7]["emetteur"] = None
    c = cb.classer_publications(pubs, CONNU)
    assert [e["ticker"] for e in c["nouvelles"]] == ["ADH"]
    assert c["nouvelles"][0]["deja_vu_ammc"] == "https://ammc/adh.pdf"
    assert sorted(e["ticker"] for e in c["integrees"]) == ["ATW", "ATW", "NEJ"]
    assert [e["ticker"] for e in c["ecartees"]] == ["SAF"]
    assert sorted(e["url"] for e in c["non_appariees"]) == ["https://b/adm.pdf", "https://b/x.pdf"]
    assert [e["candidats"] for e in c["ambigues"]] == [["SNA", "STK"]]
    assert [e["url"] for e in c["archives"]] == ["https://b/iam.pdf"]
    n = sum(len(v) for v in c.values())
    assert n == len(pubs)                       # chaque publication dans une seule liste
    assert [x["ticker"] for x in cb.candidats_comptes(c)] == ["ADH"]


def test_date_inconnue_reste_listee():
    p = _pub("Addoha - Résultats financiers du 1er semestre 2026", "https://b/adh.pdf", modif=None)
    c = cb.classer_publications([p], CONNU)
    assert c["nouvelles"][0]["date"] is None and not c["archives"]


# ── Seconde source dans la file d'attente des comptes ───────────────────

def test_file_attente_seconde_source_sans_remplacer_ammc():
    f = {"a_lire": [{"ticker": "AAA", "date": "2026-09-20", "titre": "t", "url": "u"}],
         "avertissements": [], "ecartes": []}
    jeu = {"titres": {"BBB": {}}, "_ecartes": {"CCC": "m"}}
    cands = [{"ticker": t, "date": "2026-10-05", "titre": f"{t} - S1", "url": f"b/{t}"}
             for t in ("AAA", "BBB", "CCC", "DDD", "DDD")]
    g = ajouter_bourse(f, cands, jeu)
    assert g["a_lire"] == f["a_lire"]                     # l'AMMC n'est pas touchée
    assert [e["ticker"] for e in g["bourse"]] == ["DDD"]
    assert g["bourse"][0]["source"] == "Bourse de Casablanca"
    texte = rapport(g)
    assert "pas encore intégrés : 1" in texte and "Seconde source" in texte and "[DDD - S1](b/DDD)" in texte


def test_file_attente_sans_bourse_inchangee():
    f = {"a_lire": [], "avertissements": [], "ecartes": []}
    assert "Seconde source" not in rapport(f)

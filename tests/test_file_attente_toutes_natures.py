"""File d'attente des comptes à toutes natures — 11/11/2026.

Deux familles : des cas CONSTRUITS (le code), et le classement des dépôts RÉELLEMENT
publiés (`pipeline/depots_ammc.json`, les données). La seconde ne fige pas de
chiffres exacts — le cache grossit à chaque run d'update_bvc — mais des invariants et
des planchers mesurés le 11/11/2026 sur 179 dépôts.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import file_attente_comptes as fa  # noqa: E402
from pipeline.file_attente_comptes import (  # noqa: E402
    ANNUELS, AUTRE, AVERTISSEMENT, SEMESTRIELS, TRIMESTRIELS,
    charger_integres, classer, classer_depots, file_attente, file_attente_etendue,
    rapport, rapport_etendu, sortie_json,
)


# ── classer : une nature par cas construit ──────────────────────────────

@pytest.mark.parametrize("titre,attendu", [
    # indicateurs trimestriels
    ("Maroc Telecom - CP relatif aux indicateurs du 3ème trimestre 2026", (TRIMESTRIELS, "T3-2026")),
    ("CMT - CP relatif aux indicateurs du 2ème trimestre 2026", (TRIMESTRIELS, "T2-2026")),
    ("Alpha - CP relatif aux indicateurs du 1er trimestre 2027", (TRIMESTRIELS, "T1-2027")),
    ("Alpha - Indicateurs du quatrième trimestre 2026", (TRIMESTRIELS, "T4-2026")),
    ("Alpha - Chiffre d'affaires du 3e trimestre 2026", (TRIMESTRIELS, "T3-2026")),
    ("Alpha - Indicateurs T3 2026", (TRIMESTRIELS, "T3-2026")),
    # semestriels
    ("Taqa - Résultats financiers du 1er semestre 2026", (SEMESTRIELS, "S1-2026")),
    ("Risma - CP relatif aux résultats du 1er semestre 2026", (SEMESTRIELS, "S1-2026")),
    ("Mutandis - RFS juin 2026", (SEMESTRIELS, "S1-2026")),
    ("Vicenne - CP relatif au RFS du 1er semestre 2026", (SEMESTRIELS, "S1-2026")),
    ("Alpha - Comptes au 30 juin 2025", (SEMESTRIELS, "S1-2025")),
    # annuels
    ("Alpha - Résultats annuels 2025", (ANNUELS, "FY2025")),
    ("Alpha - Rapport financier annuel 2025", (ANNUELS, "FY2025")),
    ("Alpha - RFA 2026", (ANNUELS, "FY2026")),
    ("Alpha - Comptes annuels 2026", (ANNUELS, "FY2026")),
    ("Alpha - États de synthèse de l'exercice 2026", (ANNUELS, "FY2026")),
    ("Alpha - Résultats financiers de l'exercice 2025", (ANNUELS, "FY2025")),
    # avertissement sur résultats (période lue si elle est au titre)
    ("Cartier Saada - CP relatif à la publication d'un profit warning sur les résultats du 1er semestre 2026",
     (AVERTISSEMENT, "S1-2026")),
    ("Alpha - Avertissement sur résultats", (AVERTISSEMENT, None)),
])
def test_nature_et_periode(titre, attendu):
    assert classer(titre) == attendu


@pytest.mark.parametrize("titre", [
    "Immorente Invest - CP relatif au paiement du 3e rendement trimestriel de l'année 2026",  # trimestriel != trimestre
    "TGCC - CP suite au visa de l'AMMC sur la mise à jour annuelle du dossier d'information",  # annuelle != annuels
    "Alpha - Avis de convocation à l'AG des obligataires du 28 septembre 2026 (EO juin 2025)",
    "Alpha - Dividende au titre de l'exercice 2025, convocation à l'AGO",
    "Auto Hall - CP relatif aux résultats de l'augmentation de capital",
    "SRM - Publication d'un erratum relatif à la publication financière du 1er semestre 2026",
    "Managem - Communiqué de presse",
    "",
    None,
])
def test_ce_qui_n_est_pas_un_compte_est_autre(titre):
    assert classer(titre) == (AUTRE, None)


def test_periode_jamais_devinee():
    # Année absente, ou deux années différentes : « autre », pas d'année choisie.
    assert classer("Alpha - Résultats annuels") == (AUTRE, None)
    assert classer("Alpha - Résultats annuels 2025 et perspectives 2026") == (AUTRE, None)
    assert classer("Alpha - Indicateurs du trimestre") == (AUTRE, None)
    assert classer("Alpha - 1er semestre") == (AUTRE, None)
    assert classer("Alpha - RFS") == (AUTRE, None)


def test_trimestre_sans_contenu_financier_est_autre():
    assert classer("Alpha - Avis de convocation du 3ème trimestre 2026") == (AUTRE, None)


# ── file étendue : intégré ou non, par nature ───────────────────────────

def _dep(ticker, date, titre):
    return {"date": date, "titre": f"{ticker} - {titre}", "url": f"u/{ticker}/{date}"}


def _res(titre):
    return titre.split(" - ")[0] if not titre.startswith("Inconnu") else None


JEU = {"fin_periode": "2026-06-30", "titres": {"S1OK": {}}, "_ecartes": {"ECAR": "motif"}}
INTEGRES = {"ANOK": {"FY2025", "H1-2025"}, "ETAT": {"H1-2026"}}
ENTREES = [
    _dep("S1OK", "2026-09-30", "Résultats financiers du 1er semestre 2026"),
    _dep("S1NO", "2026-09-30", "Résultats financiers du 1er semestre 2026"),
    _dep("ETAT", "2026-09-30", "Résultats financiers du 1er semestre 2026"),
    _dep("ECAR", "2026-09-30", "Résultats financiers du 1er semestre 2026"),
    _dep("AVER", "2026-10-02", "CP relatif à un profit warning sur les résultats du 1er semestre 2026"),
    _dep("ANOK", "2027-03-30", "Résultats annuels 2025"),
    _dep("ANNO", "2027-03-30", "Résultats annuels 2025"),
    _dep("ANNO", "2027-03-31", "CP relatif aux résultats annuels 2025"),
    _dep("S1NO", "2026-11-03", "CP relatif aux indicateurs du 3ème trimestre 2026"),
    _dep("TRIM", "2026-11-05", "CP relatif aux indicateurs du 3ème trimestre 2026"),
    _dep("SEM5", "2027-03-01", "Résultats financiers du 1er semestre 2025"),
    _dep("ANOK", "2027-03-30", "Résultats financiers du 1er semestre 2025"),
    {"date": "2026-09-30", "titre": "Inconnu SA - Résultats financiers du 1er semestre 2026", "url": "x"},
    _dep("AUTR", "2026-10-05", "Avis de convocation à l'AGO"),
]


@pytest.fixture(scope="module")
def etendue():
    return file_attente_etendue(ENTREES, JEU, INTEGRES, resoudre=_res)


def _tickers(liste):
    return [e["ticker"] for e in liste]


def test_semestriel_integre_absent_de_a_lire(etendue):
    # S1OK est dans le jeu, ETAT a H1-2026 dans etats_financiers : tous deux intégrés.
    a_lire = _tickers(etendue["a_lire"][SEMESTRIELS])
    assert "S1OK" not in a_lire and "ETAT" not in a_lire
    assert "S1NO" in a_lire and a_lire.count("S1NO") == 1


def test_ecarte_et_avertissement_a_part(etendue):
    assert _tickers(etendue["ecartes"]) == ["ECAR"]
    assert _tickers(etendue["avertissements"]) == ["AVER"]
    assert "AVER" not in _tickers(etendue["a_lire"][SEMESTRIELS])


def test_annuel_integre_absent_de_a_lire_un_seul_par_titre(etendue):
    annuels = etendue["a_lire"][ANNUELS]
    assert _tickers(annuels) == ["ANNO"]                 # ANOK a FY2025 dans etats_financiers
    assert annuels[0]["date"] == "2027-03-31" and annuels[0]["periode"] == "FY2025"


def test_autre_semestre_lu_dans_etats_financiers(etendue):
    # S1 2025 : SEM5 absent d'etats_financiers => à lire ; ANOK a H1-2025 => intégré.
    sem = {(e["ticker"], e["periode"]) for e in etendue["a_lire"][SEMESTRIELS]}
    assert ("SEM5", "S1-2025") in sem and ("ANOK", "S1-2025") not in sem


def test_trimestriels_listes_a_part_jamais_un_retard(etendue):
    assert _tickers(etendue["non_suivis"][TRIMESTRIELS]) == ["S1NO", "TRIM"]
    tous_a_lire = [e for v in etendue["a_lire"].values() for e in v]
    assert all(e["nature"] != TRIMESTRIELS for e in tous_a_lire)
    assert "TRIM" not in _tickers(tous_a_lire)


def test_trimestriel_tardif_ne_masque_pas_le_semestre(etendue):
    # S1NO a un dépôt S1 (30/09) PUIS un T3 (03/11) : le S1 reste à lire.
    assert any(e["ticker"] == "S1NO" and e["periode"] == "S1-2026" for e in etendue["a_lire"][SEMESTRIELS])


def test_comptes_toutes_entrees_emetteur_non_cote_compte_mais_ignore(etendue):
    c = etendue["comptes"]
    assert c["depots"] == len(ENTREES) and c["emetteurs_non_cotes"] == 1
    assert sum(c["par_nature"].values()) == len(ENTREES)
    assert "Inconnu SA" not in json.dumps(etendue["a_lire"])


def test_sortie_json_structure_stable(etendue):
    j = sortie_json(etendue)
    assert set(j) == {"schema", "depuis", "a_lire", "avertissements", "ecartes", "non_suivis", "non_classes", "comptes"}
    assert set(j["a_lire"]) == {SEMESTRIELS, ANNUELS} and set(j["non_suivis"]) == {TRIMESTRIELS}
    assert j["comptes"]["a_lire"] == sum(len(v) for v in j["a_lire"].values())
    assert j["comptes"]["non_suivis"] == 2
    json.dumps(j)                                        # sérialisable
    for e in j["a_lire"][ANNUELS] + j["non_suivis"][TRIMESTRIELS]:
        assert set(e) == {"ticker", "date", "nature", "periode", "titre", "url"}


def test_json_vide_garde_ses_cles():
    j = sortie_json(file_attente_etendue([], JEU, {}, resoudre=_res))
    assert j["a_lire"] == {SEMESTRIELS: [], ANNUELS: []} and j["non_suivis"] == {TRIMESTRIELS: []}
    assert j["comptes"]["depots"] == 0


# ── la sortie historique reste inchangée sur l'ancien périmètre ─────────

def test_sortie_texte_historique_inchangee():
    # Mêmes données que tests/test_file_attente_comptes.py (copiées : pas d'import entre tests).
    DEPOTS = {
        "AAA": {"date": "2026-09-20", "titre": "Aaa - Résultats financiers du 1er semestre 2026", "url": "u1"},
        "BBB": {"date": "2026-09-21", "titre": "Bbb - CP relatif aux résultats du 1er semestre 2026", "url": "u2"},
        "CCC": {"date": "2026-09-22", "titre": "Ccc - CP relatif à un profit warning sur le 1er semestre 2026",
                "url": "u3", "avertissement": True},
        "DDD": {"date": "2026-09-23", "titre": "Ddd - Résultats financiers du 1er semestre 2026", "url": "u4"},
        "EEE": {"date": "2026-04-10", "titre": "Eee - Résultats annuels 2025", "url": "u5"},
        "FFF": {"date": "2026-07-15", "titre": "Fff - Rapport financier annuel 2025", "url": "u6"},
        "GGG": {"date": "2026-09-07", "titre": "Ggg - RFS juin 2026", "url": "u7"},
    }
    JEU_ANCIEN = {"titres": {"BBB": {}}, "_ecartes": {"DDD": "motif"}}
    entrees = [{"date": d["date"], "titre": d["titre"], "url": d["url"]} for d in DEPOTS.values()]
    ancien = file_attente(DEPOTS, JEU_ANCIEN, "2026-06-30")
    jeu = {**JEU_ANCIEN, "fin_periode": "2026-06-30"}
    f = file_attente_etendue(entrees, jeu, {}, resoudre=lambda t: t.split(" - ")[0][:3].upper())
    assert f["_s1"] == ancien
    texte = rapport_etendu(f)
    assert texte.startswith(rapport(ancien))
    assert "pas encore intégrés : 2" in texte


def test_sans_ajout_le_texte_est_exactement_l_ancien():
    f = file_attente_etendue([], JEU, {}, resoudre=_res)
    assert rapport_etendu(f) == rapport(f["_s1"])


def test_integration_etats_financiers_charge(tmp_path):
    (tmp_path / "AAA.json").write_text(json.dumps({"ticker": "AAA", "periodes": {
        "FY2025": {"donnees": {"chiffre_affaires": {"valeur_mdh": 12.5}}},
        "FY2024": {"donnees": {"chiffre_affaires": {"valeur_mdh": None, "raison_null": "non relevé"}}},
        "H1-2026": {"donnees": {}},
    }}), encoding="utf-8")
    (tmp_path / "cassé.json").write_text("{pas du json", encoding="utf-8")
    assert charger_integres(tmp_path) == {"AAA": {"FY2025"}}      # null et vide ne comptent pas


def test_etats_financiers_reels_chargeables():
    integres = charger_integres()
    assert {"ADI", "ATW", "IAM", "LHM", "MNG"} <= set(integres)
    assert "FY2025" in integres["ATW"]


# ── main : --json, code 0 ───────────────────────────────────────────────

def test_main_json_et_texte_sortent_en_zero(capsys):
    assert fa.main(["--json"]) == 0
    j = json.loads(capsys.readouterr().out)
    assert j["schema"] == "file_attente_comptes/1" and "a_lire" in j
    assert fa.main([]) == 0
    assert capsys.readouterr().out.startswith("## Comptes déposés à l'AMMC, pas encore intégrés")


def test_main_json_avec_bourse(tmp_path, capsys):
    p = tmp_path / "c.json"
    p.write_text(json.dumps([{"ticker": "ZZZ", "date": "2026-10-05", "titre": "ZZZ - S1", "url": "b/ZZZ"}]),
                 encoding="utf-8")
    assert fa.main(["--json", "--bourse", str(p)]) == 0
    j = json.loads(capsys.readouterr().out)
    assert [e["ticker"] for e in j["bourse"]] == ["ZZZ"]


# ── les dépôts RÉELS : classement des 179 titres de depots_ammc.json ────

def test_classement_des_depots_reels(capsys):
    from pipeline.depots_ammc import charger
    entrees = charger()
    classes = classer_depots(entrees)
    compte = Counter(e["nature"] for e in classes)
    with capsys.disabled():
        print(f"\n[depots_ammc] {len(entrees)} dépôts par nature : "
              + ", ".join(f"{n}={compte.get(n, 0)}" for n in fa.NATURES))
    assert len(classes) == len(entrees) >= 179
    assert sum(compte.values()) == len(entrees)
    # Planchers mesurés le 11/11/2026 : 123 semestriels, 14 trimestriels, 2 avertissements.
    assert compte[SEMESTRIELS] >= 123 and compte[TRIMESTRIELS] >= 14 and compte[AVERTISSEMENT] >= 2
    # T3 : les 9 communiqués déposés depuis le 15/10 sont reconnus.
    t3 = [e for e in classes if e["periode"] == "T3-2026" and e["nature"] == TRIMESTRIELS]
    assert len(t3) >= 9 and all("trimestre" in e["titre"] for e in t3)
    # Invariants : toute période est lue, jamais vide ; aucun compte reconnaissable n'échappe.
    for e in classes:
        if e["nature"] in (SEMESTRIELS, TRIMESTRIELS, ANNUELS):
            assert e["periode"], e
        if e["nature"] == AUTRE:
            assert e["periode"] is None
            assert "indicateurs du" not in e["titre"].lower() or "trimestre" not in e["titre"].lower(), e
            assert "résultats financiers du 1er semestre" not in e["titre"].lower(), e


def test_file_reelle_coherente():
    from pipeline.depots_ammc import charger
    jeu = json.loads(fa.JEU.read_text(encoding="utf-8"))
    f = file_attente_etendue(charger(), jeu, charger_integres())
    # Un titre déjà intégré (jeu S1 2026) n'est jamais à lire.
    deja = set(jeu["titres"])
    assert not deja & set(_tickers(f["a_lire"][SEMESTRIELS]))
    # Les indicateurs trimestriels ne sont pas un retard.
    assert len(f["non_suivis"][TRIMESTRIELS]) >= 9
    assert all(e["nature"] == SEMESTRIELS for e in f["a_lire"][SEMESTRIELS])

"""La mesure du Score BVC affichée est LUE dans l'artefact daté (lot 1.7).

Avant le 20/11/2026, `terminal.src.html` portait des chiffres écrits à la main
(43 031 observations, 31,9 % sous 40, p = 0,049…) qui venaient de l'artefact
QUOTIDIEN du 03/11, alors que le score publié est HEBDOMADAIRE (décision D2) :
la mesure affichée n'était pas celle du score affiché.

Trois garanties :
  1. aucun chiffre de mesure en dur dans la source du terminal ;
  2. `datasets/backtests/score_bvc_mesure_courante.json` est EXACTEMENT ce que
     `pipeline/mesure_courante.py` tire de l'artefact qu'il référence (chemin,
     empreinte SHA-256, chaque chiffre) et cet artefact est le plus récent ;
  3. le terminal lit ce fichier et dit « mesure indisponible » s'il manque.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

from pipeline import mesure_courante as mc  # noqa: E402

CHEMIN = RACINE / "datasets" / "backtests" / "score_bvc_mesure_courante.json"
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
PUBLIE = json.loads(CHEMIN.read_text(encoding="utf-8"))


def _sans_commentaires(src):
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("//"))


# ── 1. Rien en dur ─────────────────────────────────────────────────────────

def _chiffres_de_mesure():
    """Tout ce que la mesure publiée (et l'ancienne, du 03/11) pourrait avoir
    laissé dans la source : effectifs, parts, p-values, dates d'artefact."""
    anciens = ["43 031", "43031", "14574", "9840", "10933", "7684", "818,", "0,049", "0,053",
               "31,9", "30,6", "32,6", "33,7", "32,1", "score_bvc_2026-11-03", "03/11/2026"]
    actuels = [f"{PUBLIE['observations']:,}".replace(",", " "), str(PUBLIE["observations"])]
    for t in PUBLIE["tranches"]:
        actuels += [str(t["n"]), f"{t['part_battu_masi_pct']:.1f}".replace(".", ","), f"{t['part_battu_masi_pct']:.1f}"]
    actuels += [f"{PUBLIE['base_pct']:.1f}".replace(".", ","), PUBLIE["artefact"], PUBLIE["date_artefact"]]
    return anciens + actuels


def test_aucun_chiffre_de_mesure_en_dur_dans_le_terminal():
    code = _sans_commentaires(SRC)
    trouves = [c for c in _chiffres_de_mesure() if c in code]
    assert not trouves, f"chiffres de mesure écrits en dur dans terminal.src.html : {trouves}"


def test_aucun_chiffre_de_mesure_dans_les_commentaires_du_terminal():
    """Un commentaire qui cite 43 031 observations vieillit en silence."""
    assert "43 031" not in SRC and "43031" not in SRC
    assert "score_bvc_2026-11-03.json" not in SRC


# ── 2. Le fichier publié = l'artefact ──────────────────────────────────────

def test_le_fichier_publie_est_exactement_celui_que_l_artefact_produit():
    art = RACINE / PUBLIE["artefact"]
    assert art.is_file(), PUBLIE["artefact"]
    assert mc.construire(art) == PUBLIE, "relancer `python3 pipeline/mesure_courante.py`"


def test_l_empreinte_est_celle_de_l_artefact():
    art = RACINE / PUBLIE["artefact"]
    assert hashlib.sha256(art.read_bytes()).hexdigest() == PUBLIE["artefact_sha256"]


def test_l_artefact_pointe_est_le_plus_recent():
    assert (RACINE / PUBLIE["artefact"]).name == mc.dernier_artefact().name


def test_les_chiffres_se_relisent_dans_l_artefact():
    """Contrôle indépendant du générateur : on relit l'artefact à la main."""
    art = json.loads((RACINE / PUBLIE["artefact"]).read_text(encoding="utf-8"))
    r = art["resultats"]["principal_echange_a_la_cloture_de_la_semaine"]["sans_rentabilite"]
    assert PUBLIE["observations"] == r["observations_total"] == sum(t["n"] for t in PUBLIE["tranches"])
    assert PUBLIE["base_pct"] == round(r["taux_de_base_global"] * 100, 1)
    assert [t["plage"] for t in PUBLIE["tranches"]] == [k.replace(" – ", "–") for k in r["tranches"]]
    for t, (k, a) in zip(PUBLIE["tranches"], r["tranches"].items()):
        assert t["n"] == a["n"], k
        assert t["part_battu_masi_pct"] == round(a["frequence_surperformance"] * 100, 1), k
    assert PUBLIE["date_artefact"] == art["date_artefact"]
    assert PUBLIE["horizon_seances"] == art["horizon_seances"] == 20
    assert PUBLIE["variante"] == "sans_rentabilite"


def test_la_conclusion_suit_les_tests_et_garde_ses_reserves():
    distinctes = [t["plage"] for t in PUBLIE["tranches"] if t["p_newey_west"] < 0.05 and t["p_bootstrap_blocs"] < 0.05]
    assert PUBLIE["conclusion"]["tranche_distincte_a_5pct"] == distinctes
    if not distinctes:
        assert "Aucune tranche ne se distingue de façon robuste" in PUBLIE["conclusion"]["texte"]
    texte = json.dumps(PUBLIE, ensure_ascii=False)
    assert "pas une prévision" in texte
    assert "automne 2027" in texte and "2026-11-04" in texte
    assert "un seul cycle" in texte.lower()


def test_aucun_mot_d_action_dans_le_fichier_publie():
    assert not re.search(r"\b(ACHETER|VENDRE|ÉVITER|SURVEILLER)\b", json.dumps(PUBLIE, ensure_ascii=False), re.I)


def test_une_nouvelle_mesure_se_propage_sans_toucher_au_terminal(tmp_path):
    """On fabrique un artefact plus récent aux chiffres différents : le fichier
    publié suit, aucune ligne du terminal n'est concernée."""
    art = json.loads((RACINE / PUBLIE["artefact"]).read_text(encoding="utf-8"))
    r = art["resultats"]["principal_echange_a_la_cloture_de_la_semaine"]["sans_rentabilite"]
    r["tranches"]["≥ 75"]["frequence_surperformance"] = 0.4444
    r["tranches"]["≥ 75"]["p_newey_west"] = r["tranches"]["≥ 75"]["p_bootstrap_blocs"] = 0.01
    art["date_artefact"] = "2099-01-01"
    f = tmp_path / "score_bvc_hebdo_2099-01-01.json"
    f.write_text(json.dumps(art, ensure_ascii=False), encoding="utf-8")
    sortie = mc.publier(f, tmp_path / "mesure.json")
    nouveau = json.loads(sortie.read_text(encoding="utf-8"))
    assert nouveau["date_artefact"] == "2099-01-01"
    assert nouveau["tranches"][3]["part_battu_masi_pct"] == 44.4
    assert nouveau["conclusion"]["tranche_distincte_a_5pct"] == ["≥ 75"]
    assert "Aucune tranche" not in nouveau["conclusion"]["texte"]


# ── 3. Le terminal lit le fichier ──────────────────────────────────────────

def test_le_terminal_charge_le_fichier_publie():
    assert 'fetch("datasets/backtests/score_bvc_mesure_courante.json?t="' in SRC
    assert "let MESURE_BVC=null" in SRC
    assert SRC.count("useMesureBVC()") >= 2, "l'onglet Facteurs ET le guide lisent le fichier"


def test_mesure_indisponible_plutot_qu_un_chiffre_perime():
    assert "Mesure indisponible" in SRC
    assert "mesureValide(j)?j:null" in SRC, "un fichier illisible ou d'un autre schéma doit donner null"
    assert 'j.schema==="mesure_score_bvc/1"' in SRC and PUBLIE["schema"] == "mesure_score_bvc/1"
    # Aucun repli sur une valeur par défaut chiffrée
    assert "MESURE_BVC||" not in SRC and "MESURE_BVC={" not in SRC


def test_le_fichier_est_servi_par_pages():
    """Publié sous datasets/, comme frequences_publiees.json : rien à exclure."""
    assert CHEMIN.is_file()
    assert not any(l.strip() in ("datasets/", "datasets/backtests/") for l in
                   (RACINE / ".gitignore").read_text(encoding="utf-8").splitlines())

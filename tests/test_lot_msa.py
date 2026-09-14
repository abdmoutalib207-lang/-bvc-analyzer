"""Contrats du lot candidat : preuve, périmètre et propagation dans le moteur."""
import copy
import json
import pytest

from pipeline import preparer_msa as msa


@pytest.fixture
def donnees():
    plan = json.loads((msa.LOT / "plan.json").read_text())
    sources = {t: msa.lire_export(msa.LOT, ref, t) for t, ref in plan["sources"].items()}
    # Reconstruire le témoin depuis les pièces figées du lot. Une actualisation
    # quotidienne de main ne doit pas changer les données d'entrée de ce test.
    serie = json.loads((msa.LOT / "resultat/MSA.json").read_text())
    anciens = {r["d"]: r["ancien"] for r in plan["lignes"]}
    serie = [{**b, **anciens.get(b["d"], {})} for b in serie]
    return serie, plan, sources


def test_exactement_22_remplacements_sans_changer_les_autres_lignes(donnees):
    serie, plan, sources = donnees
    original = copy.deepcopy(serie)
    # Un champ inconnu doit survivre, y compris sur une date remplacée.
    next(b for b in serie if b["d"] == msa.DATES[0])["preuve_anterieure"] = "conserver"
    candidate, journal = msa.remplacer(serie, plan, sources)
    assert len(candidate) == len(serie) == 569
    assert [b["d"] for b in candidate] == [b["d"] for b in serie]
    changes = [a["d"] for a, b in zip(serie, candidate) if a != b]
    assert changes == list(msa.DATES)
    assert len(journal) == 22
    assert sum(a[k] != b[k] for a, b in zip(serie, candidate) for k in msa.CHAMPS) == 110
    for row in journal:
        assert row["propose"]["v"] == int(sources["MSA"][row["d"]]["Titres Échangés"])
        assert row["volume_mad_source"] == float(sources["MSA"][row["d"]]["Volume (MAD)"])
        assert row["volume_mad_source"] != row["propose"]["v"]
        assert row["ancien"]["c"] == float(sources["MUT"][row["d"]]["Dernier Cours"])
    assert journal[0]["propose"]["preuve_anterieure"] == "conserver"
    # Les paramètres ne sont pas mutés par l'application.
    assert serie[-1] == original[-1]
    assert next(b for b in serie if b["d"] == msa.DATES[0])["c"] == 239


@pytest.mark.parametrize("defaut", ["etat_initial", "proposition", "date_en_plus", "date_absente",
                                    "doublon", "quantite_absente", "non_fini", "ohlc"])
def test_refus_des_preconditions_fausses(donnees, defaut):
    serie, plan, sources = donnees
    row = next(b for b in serie if b["d"] == msa.DATES[0])
    if defaut == "etat_initial":
        row["c"] += 1
    elif defaut == "proposition":
        plan["lignes"][0]["propose"]["c"] += 1
    elif defaut == "date_en_plus":
        plan["lignes"].append(copy.deepcopy(plan["lignes"][-1]))
    elif defaut == "date_absente":
        serie.remove(row)
    elif defaut == "doublon":
        serie.append(serie[-1])
    elif defaut == "quantite_absente":
        sources["MSA"][msa.DATES[0]]["Titres Échangés"] = "-"
    elif defaut == "non_fini":
        sources["MSA"][msa.DATES[0]]["Dernier Cours"] = "inf"
    elif defaut == "ohlc":
        sources["MSA"][msa.DATES[0]]["Plus Haut"] = "1"
    with pytest.raises(ValueError):
        msa.remplacer(serie, plan, sources)


def test_identite_controlee_meme_si_empreinte_mise_a_jour(tmp_path, donnees):
    _, plan, _ = donnees
    ref = copy.deepcopy(plan["sources"]["MSA"])
    path = tmp_path / "MSA.csv"
    path.write_bytes((msa.LOT / ref["fichier"]).read_bytes().replace(b"SODEP-Marsa Maroc", b"MUTANDIS SCA"))
    ref.update(fichier=path.name, sha256=msa.sha(path))
    with pytest.raises(ValueError, match="identité"):
        msa.lire_export(tmp_path, ref, "MSA")
    ref["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="empreinte"):
        msa.lire_export(tmp_path, ref, "MSA")


def test_construction_candidate_preserve_les_fichiers_servis(tmp_path, donnees):
    serie, _, _ = donnees
    root = tmp_path / "repo"
    (root / "pipeline/candles").mkdir(parents=True)
    msa.ecrire_json(root / "pipeline/candles/MSA.json", serie)
    msa.ecrire_json(root / "pipeline/candles/SOT.json", [{"d": "2026-05-05", "h": 1700}])
    initial = json.loads((msa.LOT / "resultat/cache_MSA_initial.json").read_text())
    msa.ecrire_json(root / "pipeline/historical_data.json", {
        "MSA": initial, "SOT": {"h52w": 380}, "SGTM": {"l52w": 508.1}})
    msa.ecrire_json(root / "data.json", {"temoin": "ne pas écrire"})
    paths = list(root.rglob("*.json"))
    before = {str(p): msa.sha(p) for p in paths}
    result = tmp_path / "candidat"
    r = msa.preparer(root, msa.LOT, result, "2026-09-13")
    assert r["valeurs_ohlcv_remplacees"] == 110
    assert r["dates_ajoutees"] == r["dates_supprimees"] == []
    assert before == {str(p): msa.sha(p) for p in paths}
    for name in ("MSA.json", "cache_MSA_candidat.json", "journal.json"):
        assert json.loads((result / name).read_text()) == json.loads((msa.LOT / "resultat" / name).read_text())
    with pytest.raises(ValueError, match="existe déjà"):
        msa.preparer(root, msa.LOT, result, "2026-09-13")
    with pytest.raises(ValueError, match="sortie interdite"):
        msa.preparer(root, msa.LOT, root / "pipeline/candles/INTERDIT", "2026-09-13")

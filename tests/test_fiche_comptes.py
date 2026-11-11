"""La fiche : « Dernier semestre » et « À savoir » (pipeline/fiche_comptes.py) — 09/11/2026.

Demande d'Abd Moutalib du 09/11/2026 : enrichir la fiche de chaque titre avec
des données DÉJÀ relevées sur pièce, sans rien retirer. Deux familles ici,
l'écran dans tests/test_fiche_terminal.py :

1. LE CODE — construction des blocs sur les vrais relevés du dépôt (ADI et sa
   réserve des commissaires, ATW et son PNB, HPS et sa base négative, TMA et
   son EBITDA) et sur les registres (CMT, MNG, ATW) ; titres sans relevé, avec
   et sans raison ; tout ou rien.
2. L'INVARIANCE — essai à blanc JUMEAU, mêmes entrées, avec et sans ce bloc :
   tout le reste du data.json est identique, 80/80, à commencer par
   `score_bvc`, `confidence`, `note_fond` et `rang_secteur`.
Plus le contrôle des DONNÉES PUBLIÉES (saute si le moteur n'a pas tourné).
"""
import copy
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import bvc_config as C  # noqa: E402
from pipeline import fiche_comptes as F  # noqa: E402

JEUX = F.charger()
S1 = JEUX["s1"]


def _bloc(t):
    return F.comptes_s1(t, S1["titres"].get(t), ecartes=S1.get("_ecartes", {}),
                        ebitda=JEUX["ebitda"].get(t), exercice=JEUX["exercice"])


def _ligne(bloc, cle):
    return next(l for l in bloc["lignes"] if l["cle"] == cle)


# ── 1. Le code ───────────────────────────────────────────────────────────────

def test_adi_chiffres_recopies_et_reserves_affichees():
    b = _bloc("ADI")
    assert b["etat"] == "releve" and b["unite"] == "MDH"
    ca, rn, mn = _ligne(b, "ca"), _ligne(b, "rnpg"), _ligne(b, "marge_nette")
    # recopiés du relevé, à l'identique
    assert (ca["s1_2025"], ca["s1_2026"]) == (1333.468, 1418.702)
    assert (rn["s1_2025"], rn["s1_2026"]) == (210.272, 229.599)
    # seuls calculs : rapports entre chiffres relevés
    assert ca["variation_pct"] == round((1418.702 / 1333.468 - 1) * 100, 1) == 6.4
    assert rn["variation_pct"] == 9.2
    assert (mn["s1_2025"], mn["s1_2026"], mn["variation_pts"]) == (15.8, 16.2, 0.4)
    # la source telle qu'elle est relevée : document, URL, pages
    s = b["sources"][0]
    assert s["document"] == "ADI_S1_26.pdf" and s["url"] == S1["titres"]["ADI"]["url"]
    assert s["pages"] == S1["titres"]["ADI"]["pages"]
    # ⚠️ les réserves : conclusion « sous réserve » ET reprises d'exploitation
    textes = " ".join(r["texte"] for r in b["reserves"])
    assert "« sous réserve »" in textes and "REPRISES d'exploitation de 210,3" in textes


def test_banque_ligne_pnb_et_source_du_document():
    b = _bloc("ATW")
    assert _ligne(b, "ca")["libelle"] == "Produit net bancaire"
    assert b["sources"][0]["document"] == "AWB_S1_26.pdf"
    assert _ligne(b, "marge_nette")["libelle"] == "Marge nette (RNPG / produit net bancaire)"


def test_base_negative_pas_de_pourcentage_mais_un_motif():
    b = _bloc("HPS")
    rn = _ligne(b, "rnpg")
    assert rn["s1_2025"] < 0 and rn["variation_pct"] is None
    assert "négative" in rn["variation_motif"]


def test_ebitda_releve_avec_sa_propre_source():
    b = _bloc("TMA")
    e = _ligne(b, "ebitda")
    assert (e["s1_2025"], e["s1_2026"]) == (731.903, 562.182)
    src = b["sources"][e["source"]]
    assert src["releve"].startswith(F.SOURCE_EBITDA) and src["pages"] == "p.4"
    assert _ligne(b, "marge_ebitda")["unite"] == "%"


def test_reserve_cac_structuree_en_tete_avec_sa_source():
    b = _bloc("M2M")
    assert b["reserves"][0]["champ"] == "reserve_cac"
    assert b["reserves"][0]["source"] == S1["titres"]["M2M"]["source_reserve_cac"]


def test_sans_releve_avec_raison():
    saf = _bloc("SAF")      # écarté au relevé (fusion Allianz)
    assert saf["etat"] == "non_releve" and saf["lignes"] == []
    assert saf["motif"].startswith("Fusion-absorption") and "_ecartes" in saf["motif_source"]
    ibm = _bloc("IBM")      # registre SANS_COMPTES
    assert ibm["etat"] == "non_releve" and "aucun compte déposé" in ibm["motif"]
    car = _bloc("CAR")      # exercice décalé
    assert car["etat"] == "non_releve" and "31/03/2026" in car["motif"]


def test_sans_releve_sans_raison_jamais_un_tableau_vide_presente_comme_releve():
    b = F.comptes_s1("ZZZ", None)
    assert b["etat"] == "non_releve" and b["motif"] is None and b["lignes"] == []


def test_a_savoir_cmt_suspension_reprise_sur_reference_et_opa():
    f = F.a_savoir("CMT", {}, "2026-11-09")
    natures = [x["nature"] for x in f]
    assert natures == ["offre_publique", "reprise", "suspension"]          # plus récent d'abord
    reprise = f[1]
    assert "2 217,00 DH" in reprise["texte"] and "n'est pas ajusté" in reprise["texte"]
    assert reprise["sha256"] == C.SUSPENSIONS["CMT"][0]["reference_piece_sha256"]
    assert "Prix de l'offre 2 217,00 DH" in f[0]["texte"] and f[0]["url"].startswith("https://")


def test_a_savoir_mng_split_et_suspension_avec_pieces():
    f = F.a_savoir("MNG", {}, "2026-11-09")
    par = {x["nature"]: x for x in f}
    assert par["split"]["date"] == "2026-07-27" and "1 action devient 10" in par["split"]["titre"]
    assert "pièce non citée" in par["split"]["source"]          # le registre le DIT
    assert par["suspension"]["sha256"] == C.SUSPENSIONS["MNG"][0]["piece_sha256"]
    assert par["reprise"]["date"] == "2026-11-03"
    dates = [F._cle_tri(x) for x in f]
    assert dates == sorted(dates, reverse=True)


def test_a_savoir_lit_le_meta_publie_autodetenues():
    meta = {"pb_actions_autodetenues": {"nombre": 13602015, "au": "2025-12-31", "page": 110,
                                        "source": "RFA 2025", "nature": "titres détenus par une filiale",
                                        "accord": "accord R8"}}
    f = F.a_savoir("ATW", meta, "2026-11-09")
    assert [x["nature"] for x in f] == ["actions_autodetenues"]
    assert "13 602 015 actions" in f[0]["texte"] and f[0]["pages"] == [110]


def test_a_savoir_vide_et_chaque_fait_porte_une_source():
    assert F.a_savoir("ADI", {}, "2026-11-09") == []
    for t in C.TICKERS_ALL:
        for x in F.a_savoir(t, {}, "2026-11-09"):
            assert x["source"] or x["url"], (t, x["titre"])
            assert x["titre"] and x["texte"], t


def test_annexer_ne_pose_que_ses_deux_champs():
    data = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    avant = copy.deepcopy(data["tickers"])
    for t in data["tickers"]:
        t.pop("comptes_s1", None)
        t.pop("a_savoir", None)
    nettoye = copy.deepcopy(data["tickers"])
    F.annexer_fiche(data["tickers"], jour="2026-11-09")
    for a, b in zip(nettoye, data["tickers"]):
        assert {k: v for k, v in b.items() if k not in ("comptes_s1", "a_savoir")} == a
        assert set(b) - set(a) == {"comptes_s1", "a_savoir"}
    assert len(avant) == len(data["tickers"])


def test_annexer_tout_ou_rien(monkeypatch):
    lignes = [{"symbol": "ADI", "_meta": {}}, {"symbol": "CMT", "_meta": {}}]

    def boom(t, meta=None, jour=None):
        if t == "CMT":
            raise RuntimeError("registre illisible")
        return []
    monkeypatch.setattr(F, "a_savoir", boom)
    with pytest.raises(RuntimeError):
        F.annexer_fiche(lignes)
    assert all("comptes_s1" not in x and "a_savoir" not in x for x in lignes)


def test_branchement_moteur_apres_la_note_et_exception_signalee():
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    i = src.index("from pipeline.fiche_comptes import annexer_fiche")
    assert src.index("_bvc_annexer(") < i and src.index("_rangs(tickers_out)") < i
    bloc = src[i:i + 900]
    assert "logger.exception(" in bloc and "except Exception" in bloc
    # aucun autre module ne lit ces deux champs (descriptifs, hors score)
    for p in sorted((RACINE / "pipeline").rglob("*.py")):
        if p.name == "fiche_comptes.py":
            continue
        code = re.sub(r"#.*", "", p.read_text(encoding="utf-8"))
        assert "comptes_s1" not in code and "a_savoir" not in code, p.name


# ── 2. L'invariance : essai à blanc jumeau ───────────────────────────────────

PILOTE = '''
import socket, sys, json
sys.path.insert(0, ".")
SANS = sys.argv[1] == "sans"

def _refus(*a, **k):
    raise OSError("réseau interdit dans ce test")
socket.socket.connect = _refus
socket.getaddrinfo = _refus
import update_data as u
import pipeline.fiche_comptes as fc
if SANS:
    fc.annexer_fiche = lambda tickers, racine=None, jour=None: {}

data = json.load(open("data.json"))
lignes = [{"name": t["symbol"], "url": "https://idbourse.invalid/instruments/" + u.IDB_TICKER_MAP.get(t["symbol"], t["symbol"]),
           "dernier_cours": t["price"], "variation": t["chg"], "volume_en_titres": str(t["vol"]),
           "ouverture": str(t.get("open") or ""), "capitalisation_boursiere": str((t.get("cap") or 0) * 1e6),
           "updated_at": ((t.get("_meta") or {}).get("prix_asof") or "2026-10-09") + "T00:00:00"}
          for t in data["tickers"]]
u.idb_get = lambda endpoint, timeout=10: lignes if endpoint == "/api/proxy/get_all_data" else None
sortie = u.run(dry_run=True, push=False)
json.dump(sortie, open(sys.argv[1] + ".json", "w", encoding="utf-8"), ensure_ascii=False)
print("RUN_TERMINE")
'''


@pytest.fixture(scope="module")
def jumeaux(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("jumeaux") / "depot"
    shutil.copytree(RACINE, dossier, ignore=shutil.ignore_patterns(
        ".git", "node_modules", "__pycache__", ".pytest_cache", ".claude"))
    (dossier / "_pilote.py").write_text(PILOTE, encoding="utf-8")
    sorties = {}
    for mode in ("avec", "sans"):
        r = subprocess.run([sys.executable, "_pilote.py", mode], cwd=dossier, capture_output=True,
                           text=True, timeout=600)
        assert "RUN_TERMINE" in r.stdout, f"essai à blanc « {mode} » :\n{r.stdout[-800:]}\n{r.stderr[-1500:]}"
        sorties[mode] = json.loads((dossier / f"{mode}.json").read_text(encoding="utf-8"))
    return sorties


def test_invariance_80_sur_80_avec_et_sans_le_bloc(jumeaux):
    avec = {t["symbol"]: t for t in jumeaux["avec"]["tickers"]}
    sans = {t["symbol"]: t for t in jumeaux["sans"]["tickers"]}
    assert set(avec) == set(sans) and len(avec) == len(C.TICKERS_ALL) == 80
    # le bloc est bien publié d'un côté, absent de l'autre
    assert all("comptes_s1" in t and "a_savoir" in t for t in avec.values())
    assert not any("comptes_s1" in t or "a_savoir" in t for t in sans.values())
    for s in avec:
        a, b = avec[s], sans[s]
        # les quatre champs nommés par la demande, un par un
        assert a.get("score_bvc") == b.get("score_bvc"), s
        assert a["_meta"]["confidence"] == b["_meta"]["confidence"], s
        assert a.get("note_fond") == b.get("note_fond"), s
        assert a.get("rang_secteur") == b.get("rang_secteur"), s
        # et tout le reste, horodatage du run excepté
        ra = {k: v for k, v in a.items() if k not in ("comptes_s1", "a_savoir", "_meta")}
        rb = {k: v for k, v in b.items() if k != "_meta"}
        assert ra == rb, s
        ma = {k: v for k, v in a["_meta"].items() if k != "generated_at"}
        mb = {k: v for k, v in b["_meta"].items() if k != "generated_at"}
        assert ma == mb, s
    for k in set(jumeaux["avec"]) | set(jumeaux["sans"]):
        if k not in ("tickers", "updated"):
            assert jumeaux["avec"].get(k) == jumeaux["sans"].get(k), k


def test_regenere_compte_les_blocs(jumeaux):
    t = jumeaux["avec"]["tickers"]
    releves = [x["symbol"] for x in t if x["comptes_s1"]["etat"] == "releve"]
    assert len(releves) == len(S1["titres"]) == 73
    sans = [x for x in t if x["comptes_s1"]["etat"] == "non_releve"]
    assert {x["symbol"] for x in sans} == {"SAF", "CAR", "ENK", "STK", "IBM", "DLM", "DIS"}
    assert all(x["comptes_s1"]["motif"] for x in sans)          # chacun dit pourquoi


# ── Données publiées (seconde famille : saute si le moteur n'a pas tourné) ──

def test_publie_les_deux_blocs(titres):
    if not any("comptes_s1" in t for t in titres.values()):
        pytest.skip("data.json antérieur au code qui émet `comptes_s1` et `a_savoir`.")
    for s, t in titres.items():
        c = t["comptes_s1"]
        assert c["etat"] in {"releve", "non_releve"}, s
        if c["etat"] == "releve":
            assert c["lignes"] and c["sources"][0]["url"], s
        assert isinstance(t["a_savoir"], list), s

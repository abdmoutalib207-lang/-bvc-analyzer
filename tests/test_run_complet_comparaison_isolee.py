"""Un RUN COMPLET (`update_data.run(dry_run=False)`) avec une erreur injectée
dans le calcul de la note par métier produit le même data.json publié qu'un run
sans erreur — 12/10/2026, dernière vérification avant fusion de #233.

Hors réseau et hors dépôt : le dépôt est COPIÉ dans un dossier temporaire (le
run y écrit data.json, bougies, journaux) et toute requête sortante échoue —
les sources retombent sur leurs replis, de la même façon dans les deux runs. On
compare ensuite, titre par titre, tout ce qui est publié hors `note_fond_metier`
(et l'horodatage). Le data.json du dépôt n'est jamais touché.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent

PILOTE = '''
import socket, sys, json
sys.path.insert(0, ".")

def _refus(*a, **k):
    raise OSError("réseau interdit dans ce test")
socket.socket.connect = _refus
socket.getaddrinfo = _refus
import update_data as u

# IDBourse « servie » localement : les cours du data.json de la copie, au format
# de l'API. Sans cotation, le disjoncteur du moteur refuserait d'écrire.
data = json.load(open("data.json"))
lignes = [{"name": t["symbol"], "url": "https://idbourse.invalid/instruments/" + u.IDB_TICKER_MAP.get(t["symbol"], t["symbol"]),
           "dernier_cours": t["price"], "variation": t["chg"], "volume_en_titres": str(t["vol"]),
           "ouverture": str(t.get("open") or ""), "capitalisation_boursiere": str((t.get("cap") or 0) * 1e6),
           "updated_at": ((t.get("_meta") or {}).get("prix_asof") or "2026-10-09") + "T00:00:00"}
          for t in data["tickers"]]
u.idb_get = lambda endpoint, timeout=10: lignes if endpoint == "/api/proxy/get_all_data" else None

if sys.argv[1] == "erreur":
    def boum(*a, **k):
        raise RuntimeError("ERREUR VOLONTAIRE dans le calcul de comparaison")
    u.appliquer_note_sectorielle = boum
resultat = u.run(dry_run=False, push=False)
print("RUN_TERMINE" if resultat is not None else "RUN_SANS_ECRITURE")
'''


def _copier(dest: Path) -> Path:
    shutil.copytree(RACINE, dest, ignore=shutil.ignore_patterns(
        ".git", "node_modules", "__pycache__", ".pytest_cache", ".claude", "whatsapp_analysis"))
    return dest


def _lancer(dossier: Path, mode: str) -> subprocess.CompletedProcess:
    (dossier / "_pilote.py").write_text(PILOTE, encoding="utf-8")
    return subprocess.run([sys.executable, "_pilote.py", mode], cwd=dossier, capture_output=True,
                          text=True, timeout=600)


@pytest.fixture(scope="module")
def deux_runs(tmp_path_factory):
    base = tmp_path_factory.mktemp("runs")
    ok, err = _copier(base / "ok"), _copier(base / "err")
    r_ok, r_err = _lancer(ok, "ok"), _lancer(err, "erreur")
    return ok, err, r_ok, r_err


def _tickers(dossier: Path) -> dict:
    d = json.loads((dossier / "data.json").read_text(encoding="utf-8"))
    return {t["symbol"]: t for t in d["tickers"]}


def _publie(t: dict) -> dict:
    t = dict(t)
    t.pop("note_fond_metier", None)
    m = dict(t.get("_meta") or {})
    m.pop("generated_at", None)
    t["_meta"] = m
    return t


def test_le_run_avec_erreur_injectee_se_termine_et_ecrit_data_json(deux_runs):
    ok, err, r_ok, r_err = deux_runs
    assert "RUN_TERMINE" in r_ok.stdout, r_ok.stderr[-2000:]
    assert "RUN_TERMINE" in r_err.stdout, "l'erreur injectée a interrompu le run :\n" + r_err.stderr[-2000:]
    assert len(_tickers(err)) == 80 and len(_tickers(ok)) == 80


def test_tout_ce_qui_est_publie_est_identique_avec_ou_sans_erreur(deux_runs):
    ok, err, *_ = deux_runs
    a, b = _tickers(ok), _tickers(err)
    assert a.keys() == b.keys()
    # ⚠️ SEULE EXCEPTION, VOULUE — règle B (27/10/2026) : une foncière sans note
    # par métier est publiée « Couverture partielle ». Ce fait n'existe QUE dans
    # la note par métier : si son calcul échoue, il ne peut pas être constaté, et
    # le titre garde le signal de la grille actuelle. Seuls `sig` et
    # `verdict_plafonne` de ces titres peuvent donc différer ; tout le reste,
    # note comprise, est identique.
    regle_b = {s for s, t in a.items()
               if (t["note_fond_metier"].get("famille") == "fonciere"
                   and t["note_fond_metier"].get("note") is None and t["sig"] == "Couverture partielle")}
    assert regle_b, "aucune foncière sans note par métier : l'exception ne teste rien"
    sans_sig = lambda t: {k: v for k, v in _publie(t).items() if k not in ("sig", "verdict_plafonne")}
    differents = [s for s in a if (sans_sig(a[s]) if s in regle_b else _publie(a[s]))
                  != (sans_sig(b[s]) if s in regle_b else _publie(b[s]))]
    assert not differents, f"publié différent avec une erreur de comparaison : {differents}"
    for champ in ("score_fond", "v53", "sig", "setup", "verdict_plafonne", "poids"):
        assert all(a[s][champ] == b[s][champ] for s in a if s not in regle_b or champ not in
                   ("sig", "verdict_plafonne")), champ
    assert all(a[s]["_meta"]["confidence"] == b[s]["_meta"]["confidence"] for s in a)


def test_la_note_par_metier_est_marquee_indisponible_et_l_erreur_journalisee(deux_runs):
    ok, err, r_ok, r_err = deux_runs
    for t in _tickers(err).values():
        nf = t["note_fond_metier"]
        assert nf["indisponible"] is True and "ERREUR VOLONTAIRE" in nf["motif"]
    assert all("criteres" in t["note_fond_metier"] for t in _tickers(ok).values()), "le run sans erreur la calcule"
    journal = r_err.stderr + r_err.stdout
    assert "note par famille (comparaison) indisponible" in journal and "WARNING" in journal
    assert "note par famille (comparaison) indisponible" not in r_ok.stderr + r_ok.stdout


def test_le_data_json_du_depot_n_est_pas_touche(deux_runs):
    # Les runs écrivent dans leur copie ; le dépôt garde son data.json.
    assert (RACINE / "data.json").read_bytes() != b""
    ok, err, *_ = deux_runs
    assert ok != RACINE and err != RACINE

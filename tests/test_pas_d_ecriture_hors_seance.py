#!/usr/bin/env python3
"""Pas d'écriture sans séance — lot 3.3 de la feuille de route (20/11/2026).

⚠️ LE DÉFAUT QUE CE TEST EMPÊCHE DE REVENIR
───────────────────────────────────────────
Mesuré sur `origin/main` du 21/10 au 20/11/2026 : 35 commits `data:` un
week-end ou un jour férié (26 d'`update_bvc`, 7 du pipeline v9, 2 de
`fetch_historical_data`). Sur les 26 d'`update_bvc`, AUCUN ne changeait un
cours, une variation, un volume ou une date de séance : seulement
l'horodatage. Les 7 de v9 ne changeaient que `timestamp`, les 2 de
l'historique que `_updated` et une fenêtre calendaire. Chacun reconstruisait
GitHub Pages pour republier la veille.

COMMENT IL LE VÉRIFIE
─────────────────────
Pas en lisant le texte du workflow : en EXÉCUTANT son étape de commit, telle
qu'elle est écrite dans le YAML, dans un dépôt git jetable dont l'« origin »
est un dépôt nu local. Seules trois lignes sont neutralisées — l'URL du dépôt
GitHub, le jeton, l'écriture de l'état du service — et la date du jour est
fixée par `--date`. Ce que le test lit ensuite, c'est le dernier commit de
l'origin : son message et ses fichiers.

Contrôle négatif : sur `origin/main` d'avant le correctif, les scénarios
« samedi » et « férié » échouent — data.json part dans un commit `data:`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
WORKFLOWS = RACINE / ".github" / "workflows"


# ── Fabrication des données ─────────────────────────────────────────────────

def _data(seance: str, ecrit: str, decalage: float = 0.0, n: int = 30) -> dict:
    """Un data.json minimal : n titres datés de `seance`."""
    return {
        "updated": f"{ecrit}+0000",
        "masi": {"value": 17000.0 + decalage, "change_pct": 0.1 + decalage, "asof": seance},
        "tickers": [{
            "symbol": f"T{i:02d}", "price": round(100.0 + i + decalage, 2),
            "chg": round(0.5 + decalage, 2), "vol": 1000 + i, "echange_dh": 1e5 + i,
            "seuil_haut": 110.0 + i,
            "_meta": {"prix_asof": seance, "generated_at": f"{ecrit}+00:00"},
        } for i in range(n)],
    }


def _ecrire(racine: Path, chemin: str, contenu) -> None:
    p = racine / chemin
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(contenu if isinstance(contenu, str) else json.dumps(contenu), encoding="utf-8")


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=_ENV)
    assert r.returncode == 0, f"git {' '.join(args)} : {r.stderr}"
    return r.stdout


_ENV: dict = {}


@pytest.fixture
def depot(tmp_path):
    """Un dépôt de travail et son origin nue, publiés avec la séance `publie`.

    HOME isolé : ni crochet, ni signature, ni identité globale de la machine.
    """
    _ENV.clear()
    _ENV.update(os.environ, HOME=str(tmp_path), GIT_CONFIG_NOSYSTEM="1",
                PYTHONPATH=str(RACINE), GIT_TERMINAL_PROMPT="0")
    origin, travail = tmp_path / "origin.git", tmp_path / "travail"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True, env=_ENV)
    subprocess.run(["git", "init", "-q", "-b", "main", str(travail)], check=True, env=_ENV)
    _git(travail, "config", "user.name", "test")
    _git(travail, "config", "user.email", "test@example.invalid")
    _git(travail, "remote", "add", "origin", str(origin))

    def publier(fichiers: dict) -> None:
        for chemin, contenu in fichiers.items():
            _ecrire(travail, chemin, contenu)
        _git(travail, "add", "-A")
        _git(travail, "commit", "-q", "-m", "état publié")
        _git(travail, "push", "-q", "origin", "HEAD:main")

    return travail, origin, publier


def _etape(workflow: str, nom: str) -> str:
    doc = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))
    for job in doc["jobs"].values():
        for e in job["steps"]:
            if e.get("name") == nom:
                return e["run"]
    raise AssertionError(f"étape « {nom} » introuvable dans {workflow}")


def _executer(script: str, cwd: Path, date: str, forcer: str = "") -> subprocess.CompletedProcess:
    """Exécute une étape de workflow telle qu'écrite, trois lignes neutralisées."""
    lignes = [l for l in script.splitlines() if "git remote set-url origin" not in l]
    s = "\n".join(lignes)
    s = s.replace("${{ github.event.inputs.forcer_ecriture }}", forcer)
    s = s.replace("${{ github.event.inputs.dry_run }}", "")
    s = s.replace("${{ github.event.inputs.tickers }}", "")
    # La garde du dépôt testé, à la date du scénario (si elle existe : sur la
    # version d'avant le correctif, l'étape ne l'appelle pas).
    garde = RACINE / "pipeline" / "garde_hors_seance.py"
    s = s.replace("python3 pipeline/garde_hors_seance.py cotation",
                  f"python3 {garde} cotation --date {date}")
    s = s.replace("python3 pipeline/garde_hors_seance.py seance",
                  f"python3 {garde} seance --date {date}")
    # L'état du service écrirait dans le dépôt réel : remplacé par un témoin.
    s = s.replace("python3 pipeline/etat_service.py",
                  "python3 -c \"open('etat_service.json','w').write('{}')\"")
    return subprocess.run(["bash", "-e", "-c", s], cwd=cwd, capture_output=True,
                          text=True, env=_ENV, timeout=120)


def _dernier_commit(origin: Path) -> tuple[str, set[str]]:
    msg = _git(origin, "log", "-1", "--format=%s", "main").strip()
    fichiers = set(_git(origin, "show", "--name-only", "--format=", "main").split())
    return msg, fichiers


def _nb_commits(origin: Path) -> int:
    return int(_git(origin, "rev-list", "--count", "main").strip())


ETAPE_BVC = ("update_bvc.yml", "Commit data.json si modifié")
CANDLE = [{"d": "2026-11-19", "o": 100, "h": 101, "l": 99, "c": 100, "v": 10}]


def _publier_veille(publier, seance: str, ecrit: str) -> None:
    publier({
        "data.json": _data(seance, ecrit),
        "news.json": {"updated": ecrit, "articles": ["a"]},
        "marches_mondiaux.json": {"releve_utc": ecrit},
        "briefing.json": {"seance": seance, "ecrit_a": ecrit},
        "pipeline/candles/T00.json": CANDLE,
        # Passé sans condition à `git add` par le workflow : il doit exister.
        "pipeline/masi_history.json": [],
    })


# ── 1. update_bvc, exécuté ──────────────────────────────────────────────────

def test_samedi_seules_les_actualites_partent(depot):
    """Samedi 21/11 : la séance du 20 est publiée, le run ne change que
    l'horodatage de data.json et du briefing — et les actualités."""
    travail, origin, publier = depot
    _publier_veille(publier, "2026-11-20", "2026-11-20T18:00:00")
    _ecrire(travail, "data.json", _data("2026-11-20", "2026-11-21T11:00:00"))
    _ecrire(travail, "briefing.json", {"seance": "2026-11-20", "ecrit_a": "2026-11-21 11:00"})
    _ecrire(travail, "news.json", {"updated": "2026-11-21T11:00", "articles": ["a", "b"]})
    _ecrire(travail, "marches_mondiaux.json", {"releve_utc": "2026-11-21T11:00"})
    r = _executer(_etape(*ETAPE_BVC), travail, "2026-11-21")
    assert r.returncode == 0, r.stdout + r.stderr
    msg, fichiers = _dernier_commit(origin)
    assert fichiers == {"news.json", "marches_mondiaux.json"}, (
        f"un samedi, seuls les fichiers hors cotation peuvent partir — commit : {fichiers}")
    assert msg.startswith("news:"), f"un commit sans séance n'est pas un commit `data:` : {msg}"


def test_samedi_sans_actualite_aucun_commit(depot):
    travail, origin, publier = depot
    _publier_veille(publier, "2026-11-20", "2026-11-20T18:00:00")
    avant = _nb_commits(origin)
    _ecrire(travail, "data.json", _data("2026-11-20", "2026-11-21T15:00:00"))
    _ecrire(travail, "briefing.json", {"seance": "2026-11-20", "ecrit_a": "2026-11-21 15:00"})
    r = _executer(_etape(*ETAPE_BVC), travail, "2026-11-21")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _nb_commits(origin) == avant, "seul l'horodatage a changé : aucun commit"


def test_ferie_rediffusion_de_la_veille_datee_du_jour(depot):
    """18/11 (férié) : la source rediffuse la clôture du 17 datée du 18, et le
    recalage du moteur n'a pas joué — tous les titres portent le 18, aux cours
    exacts du 17, et une bougie du 18 a été écrite. Rien de cela ne part."""
    travail, origin, publier = depot
    _publier_veille(publier, "2026-11-17", "2026-11-17T18:00:00")
    _ecrire(travail, "data.json", _data("2026-11-18", "2026-11-18T10:00:00"))
    _ecrire(travail, "pipeline/candles/T00.json",
            CANDLE + [{"d": "2026-11-18", "o": 100, "h": 101, "l": 99, "c": 100, "v": 10}])
    _ecrire(travail, "news.json", {"updated": "2026-11-18T10:00", "articles": ["a", "c"]})
    r = _executer(_etape(*ETAPE_BVC), travail, "2026-11-18")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "rediffusion" in r.stdout, r.stdout
    msg, fichiers = _dernier_commit(origin)
    assert fichiers == {"news.json"}, f"un férié, ni data.json ni bougie : {fichiers}"
    assert msg.startswith("news:"), msg


def test_seance_normale_ecrit_tout(depot):
    """19/11 : une vraie séance, cours nouveaux et bougie du jour."""
    travail, origin, publier = depot
    _publier_veille(publier, "2026-11-17", "2026-11-17T18:00:00")
    _ecrire(travail, "data.json", _data("2026-11-19", "2026-11-19T15:45:00", decalage=1.37))
    _ecrire(travail, "pipeline/candles/T00.json",
            CANDLE + [{"d": "2026-11-19", "o": 101, "h": 102, "l": 100, "c": 101.37, "v": 12}])
    _ecrire(travail, "news.json", {"updated": "2026-11-19T15:45", "articles": ["a", "d"]})
    r = _executer(_etape(*ETAPE_BVC), travail, "2026-11-19")
    assert r.returncode == 0, r.stdout + r.stderr
    msg, fichiers = _dernier_commit(origin)
    assert msg.startswith("data: BVC update"), msg
    assert {"data.json", "pipeline/candles/T00.json", "news.json",
            "etat_service.json"} <= fichiers, fichiers


def test_jour_de_seance_seules_les_actualites_changent(depot):
    """19/11, passage du soir : la séance du jour est déjà publiée et ses cours
    n'ont pas bougé ; seules les actualités sont nouvelles. Un jour de séance,
    la garde ne retire rien — le soir, les figures et la lecture de clôture
    changent sans que les cours bougent, et doivent partir."""
    travail, origin, publier = depot
    _publier_veille(publier, "2026-11-19", "2026-11-19T15:45:00")
    _ecrire(travail, "data.json", _data("2026-11-19", "2026-11-19T18:00:00"))
    _ecrire(travail, "news.json", {"updated": "2026-11-19T18:00", "articles": ["a", "e"]})
    r = _executer(_etape(*ETAPE_BVC), travail, "2026-11-19")
    assert r.returncode == 0, r.stdout + r.stderr
    msg, fichiers = _dernier_commit(origin)
    assert msg.startswith("data: BVC update"), msg
    assert {"data.json", "news.json"} <= fichiers, fichiers


def test_rattrapage_apres_minuit_ecrit_la_cloture(depot):
    """20/11 à 00h55 : la publication porte le 19 à un cours de mi-séance, le
    run ramène la clôture du 19. C'est une séance nouvelle à dire : elle part."""
    travail, origin, publier = depot
    _publier_veille(publier, "2026-11-19", "2026-11-19T12:00:00")
    _ecrire(travail, "data.json", _data("2026-11-19", "2026-11-20T00:55:00", decalage=0.4))
    r = _executer(_etape(*ETAPE_BVC), travail, "2026-11-20")
    assert r.returncode == 0, r.stdout + r.stderr
    msg, fichiers = _dernier_commit(origin)
    assert msg.startswith("data: BVC update") and "data.json" in fichiers, (msg, fichiers)


def test_forcer_ecriture_publie_sans_seance(depot):
    """Le recours humain : un changement de code fusionné un jour férié."""
    travail, origin, publier = depot
    _publier_veille(publier, "2026-11-20", "2026-11-20T18:00:00")
    d = _data("2026-11-20", "2026-11-21T11:00:00")
    d["tickers"][0]["cap"] = 1234
    _ecrire(travail, "data.json", d)
    r = _executer(_etape(*ETAPE_BVC), travail, "2026-11-21", forcer="true")
    assert r.returncode == 0, r.stdout + r.stderr
    msg, fichiers = _dernier_commit(origin)
    assert msg.startswith("data: BVC update") and "data.json" in fichiers, (msg, fichiers)


# ── 2. v9 et historique, exécutés ───────────────────────────────────────────

def test_v9_ne_commite_pas_un_jour_ferie(depot):
    travail, origin, publier = depot
    _publier_veille(publier, "2026-11-17", "2026-11-17T18:00:00")
    publier({"financial_data.json": {"timestamp": "2026-11-17T22:00:00Z", "data": {}}})
    avant = _nb_commits(origin)
    _ecrire(travail, "financial_data.json", {"timestamp": "2026-11-18T22:10:00Z", "data": {}})
    r = _executer(_etape("update_financial_data.yml", "Commit & push data files"),
                  travail, "2026-11-18")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _nb_commits(origin) == avant, "v9 a commité un horodatage un jour férié"


def test_v9_commite_un_jour_de_seance(depot):
    travail, origin, publier = depot
    _publier_veille(publier, "2026-11-19", "2026-11-19T12:00:00")
    publier({"financial_data.json": {"timestamp": "2026-11-19T09:00:00Z", "data": {}}})
    _ecrire(travail, "financial_data.json", {"timestamp": "2026-11-19T12:00:00Z", "data": {"A": 1}})
    r = _executer(_etape("update_financial_data.yml", "Commit & push data files"),
                  travail, "2026-11-19")
    assert r.returncode == 0, r.stdout + r.stderr
    msg, fichiers = _dernier_commit(origin)
    assert fichiers == {"financial_data.json"} and msg.startswith("data: BVC pipeline v9"), msg


def test_historique_ne_commite_pas_un_jour_ferie_sans_bougie(depot):
    travail, origin, publier = depot
    _publier_veille(publier, "2026-11-17", "2026-11-17T18:00:00")
    publier({"pipeline/historical_data.json": {"_updated": "2026-11-17", "T00": {"h90": 120}}})
    avant = _nb_commits(origin)
    _ecrire(travail, "pipeline/historical_data.json", {"_updated": "2026-11-18", "T00": {"h90": 119}})
    r = _executer(_etape("fetch_historical_data.yml", "Commit and push results"),
                  travail, "2026-11-18")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _nb_commits(origin) == avant, "l'historique a commité une fenêtre calendaire un jour férié"


def test_historique_commite_une_bougie_reparee_meme_sans_seance(depot):
    travail, origin, publier = depot
    _publier_veille(publier, "2026-11-17", "2026-11-17T18:00:00")
    publier({"pipeline/historical_data.json": {"_updated": "2026-11-17"}})
    _ecrire(travail, "pipeline/candles/T00.json", [dict(CANDLE[0], c=100.5)])
    r = _executer(_etape("fetch_historical_data.yml", "Commit and push results"),
                  travail, "2026-11-18")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "pipeline/candles/T00.json" in _dernier_commit(origin)[1]


# ── 3. La décision, pure ────────────────────────────────────────────────────

def test_decision_sur_donnees_fabriquees():
    from pipeline.garde_hors_seance import decider
    veille = _data("2026-11-17", "2026-11-17T18:00:00")
    # Pas de séance : seul l'horodatage change.
    ok, pourquoi = decider(_data("2026-11-17", "2026-11-18T10:00:00"), veille, "2026-11-18")
    assert not ok and "pas de séance" in pourquoi
    # Des seuils qui apparaissent et disparaissent ne sont pas une cotation.
    d = _data("2026-11-17", "2026-11-18T10:00:00")
    for t in d["tickers"]:
        t["seuil_haut"] = None
    assert not decider(d, veille, "2026-11-18")[0]
    # Le MASI seul corrigé : c'est une cotation.
    d = _data("2026-11-17", "2026-11-18T10:00:00")
    d["masi"]["value"] += 1
    assert decider(d, veille, "2026-11-18")[0]
    # Rediffusion datée du jour.
    ok, pourquoi = decider(_data("2026-11-18", "2026-11-18T10:00:00"), veille, "2026-11-18")
    assert not ok and "rediffusion" in pourquoi
    # Vraie séance du jour : quelques cours inchangés ne la rendent pas fantôme.
    d = _data("2026-11-18", "2026-11-18T10:00:00", decalage=0.5)
    for t in d["tickers"][:6]:
        t["price"] -= 0.5
    assert decider(d, veille, "2026-11-18")[0]
    # Moins de 20 titres comparables : l'échantillon ne dit rien, on écrit.
    assert decider(_data("2026-11-18", "x", n=10), _data("2026-11-17", "y", n=10), "2026-11-18")[0]
    # Rien de publié : on écrit.
    assert decider(veille, None, "2026-11-18")[0]


def test_la_liste_hors_seance_du_workflow_est_celle_du_module():
    """La liste vit à deux endroits ; ils ne doivent pas diverger. Et aucun
    fichier de cotation n'y figure."""
    from pipeline.garde_hors_seance import FICHIERS_HORS_SEANCE
    script = _etape(*ETAPE_BVC)
    lignes = [l.strip() for l in script.splitlines()
              if l.strip().startswith("for f in news.json")]
    assert len(lignes) == 1, "la boucle des fichiers hors séance a disparu"
    liste = tuple(lignes[0][len("for f in "):].split(";")[0].split())
    assert liste == FICHIERS_HORS_SEANCE
    for interdit in ("data.json", "pipeline/candles/", "briefing.json",
                     "pipeline/historical_data.json", "pipeline/score_history.json",
                     "etat_service.json", "datasets/figures_publiees.json"):
        assert interdit not in liste


def test_la_garde_n_avale_pas_ses_erreurs(tmp_path):
    """R5 : un data.json généré illisible fait échouer la garde — jamais
    « pas de séance » par défaut, qui jetterait la séance en silence."""
    (tmp_path / "data.json").write_text("{tronqué", encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(RACINE))
    r = subprocess.run([sys.executable, str(RACINE / "pipeline" / "garde_hors_seance.py"),
                        "cotation", "--date", "2026-11-18"],
                       cwd=tmp_path, capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "cotation=false" not in r.stdout

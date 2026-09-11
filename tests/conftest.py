"""Fixtures partagées du filet de sécurité BVC Analyzer.

⚠️ Deux règles non négociables pour toute la suite :

1. **Aucun test ne touche le réseau.** Une suite qui dépend d'un serveur tiers
   échoue les jours où ce serveur est lent, et une alarme peu fiable finit
   ignorée puis désactivée. Le projet a déjà payé cette leçon avec le drapeau
   `stale` d'IDBourse le 14/08.

2. **Aucun test n'écrit dans `data.json`, `news.json` ou `pipeline/candles/`.**
   Un test qui pollue les données de production est pire que pas de test. Tout
   ce qui écrit passe par `tmp_path`.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))


def chemin_data_json() -> Path:
    """Le fichier PUBLIÉ que les contrôles de données relisent.

    ⚠️ POURQUOI CE POINT EST PARAMÉTRABLE — ET CE QUE CELA NE DOIT PAS DEVENIR
    ────────────────────────────────────────────────────────────────────────
    La suite compte deux familles : celle qui décrit le CODE, et celle qui
    relit les DONNÉES PUBLIÉES. La seconde juge un fichier, pas un programme.

    Sur une demande de fusion, ce fichier est celui du dépôt — écrit par
    l'ANCIEN moteur. Les contrôles de la seconde famille échouent alors, et ils
    ont raison : le fichier publié ne satisfait pas encore le nouveau contrat.
    Ce n'est pas un défaut de la demande, et ce n'est pas non plus un échec à
    écarter à la main : il faut leur donner un fichier écrit par le code qu'on
    juge.

    `BVC_DATA_JSON` désigne ce fichier. La CI l'utilise après l'avoir GÉNÉRÉ
    avec le moteur de la demande ; un relecteur peut l'utiliser pour rejouer
    une livraison sur le fichier exact qui l'accompagne.

    ⚠️ Ce n'est PAS une soupape pour rendre la suite verte. Pointer vers un
    fichier arbitraire ne prouve rien : le fichier doit être identifié —
    empreinte et provenance — et c'est ce que la CI et le dossier de réception
    publient à côté du résultat.
    """
    surcharge = os.environ.get("BVC_DATA_JSON")
    if surcharge:
        p = Path(surcharge)
        if not p.is_absolute():
            p = RACINE / p
        if not p.exists():
            raise FileNotFoundError(
                f"BVC_DATA_JSON désigne {p}, qui n'existe pas. Un contrôle de "
                f"données ne doit pas retomber en silence sur un autre fichier.")
        return p
    return RACINE / "data.json"


@pytest.fixture(scope="session")
def racine():
    return RACINE


@pytest.fixture(scope="session")
def ud():
    """Le moteur `update_data.py`, importé sans exécuter son `main()`.

    Vérifié : l'import ne déclenche aucune connexion réseau. Portée `session`
    parce qu'il charge les fondamentaux et l'export DATA+ au passage.
    """
    sys.argv = ["update_data.py"]
    spec = importlib.util.spec_from_file_location("ud", RACINE / "update_data.py")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit:          # argparse sur un module importé
        pass
    return module


@pytest.fixture(scope="session")
def config():
    import bvc_config
    return bvc_config


@pytest.fixture(scope="session")
def data():
    """`data.json` tel qu'il est publié. C'est le contrat avec le frontend."""
    return json.loads(chemin_data_json().read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def titres(data):
    """Les tickers de `data.json`, indexés par symbole."""
    lignes = data.get("tickers") or []
    if isinstance(lignes, dict):
        lignes = list(lignes.values())
    return {t["symbol"]: t for t in lignes if t.get("symbol")}


@pytest.fixture
def dossier_chandelles(tmp_path):
    """Fabrique un dossier de chandelles jetable.

    Utilisation : `dossier_chandelles({"IAM": [{"d": "2026-08-27", "c": 100}]})`
    """
    def _fabrique(series):
        d = tmp_path / "candles"
        d.mkdir(exist_ok=True)
        for sym, points in series.items():
            (d / f"{sym}.json").write_text(json.dumps(points), encoding="utf-8")
        return d
    return _fabrique

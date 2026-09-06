"""Historique du MASI — la série que le projet n'avait jamais conservée.

POURQUOI CE FICHIER EXISTE
──────────────────────────
Le WeightEngine décide du régime de marché sur `masi_ytd`, la performance de
l'indice depuis le 1er janvier. Or le projet ne gardait **aucune** valeur
passée de l'indice : `data.json` n'en porte qu'une, celle du jour, écrasée à
chaque run. Le YTD était donc incalculable, et l'appelant y passait faute de
mieux la variation de la séance — un chiffre cent fois trop petit, qui
n'atteignait jamais les seuils annuels de ±5 % et +10 %.

Corriger l'appelant ne suffisait pas : sans série, il n'y a rien à calculer.
Ce module conserve une valeur par séance, en ajout seulement.

CE QUE CE MODULE NE FAIT PAS
────────────────────────────
⚠️ Il ne fabrique pas le passé. Tant que la série ne remonte pas au dernier
jour coté de l'année précédente, `performance_ytd()` renvoie `None`, et le
bloc de régime reste neutralisé. Un `0` voudrait dire « marché plat » : ce
serait une affirmation, alors que nous ne savons pas.

Deux façons de combler l'amorce, le jour où on le voudra :
- la page officielle `casablanca-bourse.com/market-data/cours` publie
  l'historique par instrument sur 3 ans, avec export Excel ;
- le bulletin PDF de CDG Capital Bourse, déjà lu par
  `pipeline/parse_cdg_bulletin.py`.

Une clôture d'ancrage saisie à la main est légitime — mais elle doit porter
sa date et sa source, comme toute donnée du projet.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

CHEMIN = Path(__file__).parent / "masi_history.json"

# En deçà, la série ne dit rien d'utile sur un régime de marché.
MIN_SEANCES = 10


def _charger(chemin: Path | None = None) -> dict:
    p = Path(chemin) if chemin else CHEMIN
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        log.warning(f"{p.name} illisible — historique MASI ignoré")
        return {}
    return d.get("seances", {}) if isinstance(d, dict) else {}


def _apports(chemin: Path | None = None) -> list:
    p = Path(chemin) if chemin else CHEMIN
    if not p.exists():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    return list(d.get("_apports", [])) if isinstance(d, dict) else []


def _ecrire(p: Path, seances: dict, apports: list) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    charge = {
        "_note": ("Une clôture par séance, en AJOUT SEULEMENT : une date déjà "
                  "connue n'est jamais réécrite. Le YTD reste indisponible "
                  "tant que la série ne couvre pas la dernière séance de "
                  "l'année précédente."),
        "_apports": apports,
        "seances": dict(sorted(seances.items())),
    }
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(charge, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def enregistrer(valeur, asof: str, chemin: Path | None = None,
                source: str = "pipeline") -> bool:
    """Ajoute la clôture d'une séance. Ne réécrit jamais une date connue.

    L'écriture est idempotente : quatre runs par jour ouvré déposent la même
    date, et seul le premier compte. La valeur d'une séance déjà enregistrée
    n'est PAS mise à jour — l'indice de 12h00 ne doit pas devenir la clôture.
    Le run de 15h45, qui fixe le cours, est aussi celui qui fixe l'indice ;
    pour le reste, `data.json` reste la source du jour.

    Renvoie True si une nouvelle séance a été ajoutée.
    """
    p = Path(chemin) if chemin else CHEMIN
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return False
    if v <= 0 or not asof or len(str(asof)) < 10:
        return False
    jour = str(asof)[:10]

    seances = _charger(p)
    if jour in seances:
        return False
    seances[jour] = round(v, 4)

    apports = _apports(p)
    for a in apports:
        if a.get("source") == source:
            a["n"] = int(a.get("n", 0)) + 1
            a["jusqu_au"] = max(str(a.get("jusqu_au", "")), jour)
            break
    else:
        apports.append({"source": source, "depuis": jour, "jusqu_au": jour, "n": 1})

    _ecrire(p, seances, apports)
    return True


def importer(series: dict, source: str, url: str = "",
             chemin: Path | None = None) -> int:
    """Insère un lot de clôtures datées venues d'une source extérieure.

    ⚠️ Les dates déjà présentes ne sont PAS écrasées. C'est ce qui rend
    l'import rejouable et empêche une source tierce de contredire en silence
    ce que notre propre chaîne a mesuré. Si une divergence existe, elle doit
    se voir et se trancher à la main, pas se résoudre par ordre d'écriture.

    Renvoie le nombre de séances réellement ajoutées.
    """
    p = Path(chemin) if chemin else CHEMIN
    seances = _charger(p)
    ajout = {}
    for d, v in series.items():
        jour = str(d)[:10]
        if jour in seances or len(jour) < 10:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f > 0:
            ajout[jour] = round(f, 4)
    if not ajout:
        return 0

    seances.update(ajout)
    apports = _apports(p)
    apports.append({
        "source": source, "url": url,
        "depuis": min(ajout), "jusqu_au": max(ajout), "n": len(ajout),
    })
    _ecrire(p, seances, apports)
    return len(ajout)


def performance_ytd(asof: str | None = None, chemin: Path | None = None):
    """Performance de l'indice depuis la dernière clôture de l'an passé, en %.

    Renvoie `None` — et non zéro — dès qu'un des éléments manque :
    - aucune séance de l'année précédente dans la série, donc pas d'ancrage ;
    - moins de `MIN_SEANCES` points sur l'année en cours ;
    - aucune valeur à la date demandée ou avant.

    `None` neutralise le bloc de régime dans `get_weights()`. C'est la bonne
    réponse à « nous ne savons pas ».
    """
    seances = _charger(chemin)
    if not seances:
        return None

    jour = str(asof)[:10] if asof else date.today().isoformat()
    annee = jour[:4]

    anterieures = [d for d in seances if d[:4] < annee]
    if not anterieures:
        return None  # pas d'ancrage : la série ne remonte pas assez loin
    base = seances[max(anterieures)]

    courantes = sorted(d for d in seances if d[:4] == annee and d <= jour)
    if len(courantes) < MIN_SEANCES or not base:
        return None

    return round((seances[courantes[-1]] / base - 1) * 100, 2)


def profondeur(chemin: Path | None = None) -> int:
    """Nombre de séances enregistrées — sert aux contrôles et aux journaux."""
    return len(_charger(chemin))


def serie(debut: str | None = None, fin: str | None = None,
          chemin: Path | None = None) -> dict:
    """Les clôtures de l'indice sur une période, triées par date.

    C'est le point d'entrée des consommateurs extérieurs au moteur de prix —
    en particulier `phase11_backtest.py`, qui fabriquait jusqu'ici son propre
    « MASI » en moyennant les titres dont il disposait. Comparer une stratégie
    à une référence qu'on construit soi-même revient à se noter sur sa propre
    copie : la référence bouge avec l'univers testé.

    Bornes incluses. Renvoie un dictionnaire vide si rien ne correspond.
    """
    s = _charger(chemin)
    d = str(debut)[:10] if debut else ""
    f = str(fin)[:10] if fin else "9999-99-99"
    return {k: v for k, v in sorted(s.items()) if d <= k <= f}

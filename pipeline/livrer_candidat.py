#!/usr/bin/env python3
"""Produit un dossier de réception dont la provenance ne peut pas dériver.

POURQUOI CE SCRIPT EXISTE
─────────────────────────
Deux livraisons de suite ont été refusées par l'audit externe pour des raisons
de forme, jamais de fond :

  10/09, 12h58  le manifeste décrivait une AUTRE expérience que les fichiers
                qu'il accompagnait — un « avant » de 03h19 empaqueté avec un
                candidat de 12h58, marché fermé contre marché ouvert.

  10/09, 14h15  le manifeste annonçait le commit 36fba5a9 alors que le code
                exécuté était celui de 46c1f78e. Cause : `git rev-parse HEAD`
                appelé AVANT de commiter, sur un arbre de travail modifié. Le
                manifeste enregistrait donc le commit PARENT, et le code
                réellement exécuté n'était dans aucun commit.

Les deux fois, la donnée était juste et le dossier faux. C'est un défaut de
procédure, et une procédure se corrige par un programme, pas par de l'attention.

CE QUE CE SCRIPT GARANTIT
─────────────────────────
  1. Il REFUSE de tourner sur un arbre de travail modifié. Un dossier de
     réception qui cite un commit doit décrire ce commit, pas un état
     intermédiaire que personne ne peut retrouver.
  2. Il extrait les deux versions par `git archive`, donc depuis les commits
     eux-mêmes — jamais depuis les fichiers du disque.
  3. Il empreinte les SOURCES exécutées, pas seulement les données produites.
     Une empreinte correcte du JSON ne dit rien du code qui l'a écrit ;
     l'auditeur l'a fait remarquer.
  4. Il fixe `BVC_DATE_ANALYSE` pour les deux exécutions, afin que la date de
     décision soit identique et déclarée.
  5. Il écrit le manifeste EN LISANT les fichiers produits. Aucune valeur n'y
     est recopiée d'une note ; le texte ne peut pas contredire les données.

USAGE
    python pipeline/livrer_candidat.py [--base origin/main] [--sortie DOSSIER]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Les fichiers dont le contenu détermine ce que le moteur calcule. Leur
# empreinte répond à « quel code a produit ce JSON ? », question à laquelle
# l'empreinte du JSON ne répond pas.
SOURCES_MOTEUR = [
    "update_data.py",
    "bvc_config.py",
    "bpa.json",
    "pipeline/faits_financiers.json",
    "pipeline/seance.py",
    "pipeline/smart_money/fond_score.py",
]

# Ce qui doit être imposé aux DEUX exécutions pour que seul le code diffère.
ENTREES_PARTAGEES = ["pipeline/candles", "pipeline/historical_data.json", "data.json"]


def git(*args: str, cwd: Path = RACINE) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} : {r.stderr.strip()}")
    return r.stdout.strip()


def empreinte(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            h.update(bloc)
    return h.hexdigest()


def exiger_arbre_propre() -> None:
    """Un dossier de réception ne peut pas citer un commit qu'il n'exécute pas."""
    sale = git("status", "--porcelain")
    if sale:
        print("REFUS — l'arbre de travail porte des modifications non commitées :\n",
              file=sys.stderr)
        print(sale, file=sys.stderr)
        print("\nCommitez-les d'abord. Un manifeste qui annonce un commit doit",
              file=sys.stderr)
        print("décrire CE commit ; sinon le code exécuté n'est retrouvable nulle part.",
              file=sys.stderr)
        raise SystemExit(2)


def extraire(ref: str, dest: Path) -> None:
    """Extrait un commit — jamais les fichiers du disque."""
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
        chemin = tmp.name
    try:
        subprocess.run(["git", "archive", "-o", chemin, ref], cwd=RACINE, check=True)
        with tarfile.open(chemin) as t:
            t.extractall(dest)
    finally:
        Path(chemin).unlink(missing_ok=True)


def aligner_entrees(source: Path, cible: Path) -> None:
    for rel in ENTREES_PARTAGEES:
        s, c = source / rel, cible / rel
        if not s.exists():
            continue
        if s.is_dir():
            shutil.copytree(s, c, dirs_exist_ok=True)
        else:
            c.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, c)


def executer(dossier: Path, date_analyse: str) -> Path:
    env = dict(os.environ, BVC_DATE_ANALYSE=date_analyse)
    journal = dossier / "run.log"
    with open(journal, "w") as log:
        r = subprocess.run([sys.executable, "update_data.py"], cwd=dossier,
                           stdout=subprocess.DEVNULL, stderr=log, env=env, timeout=600)
    if r.returncode != 0:
        raise SystemExit(f"le moteur a échoué dans {dossier} — voir {journal}")
    return dossier / "data.json"


def rediger_manifeste(avant: Path, apres: Path, meta: dict) -> str:
    """Tout est LU dans les fichiers. Rien n'est recopié d'une note."""
    a, b = json.loads(avant.read_text()), json.loads(apres.read_text())
    ta = {x["symbol"]: x for x in a["tickers"]}
    tb = {x["symbol"]: x for x in b["tickers"]}

    bouge = {s: (ta[s].get("price"), tb[s].get("price"))
             for s in ta if ta[s].get("price") != tb[s].get("price")}
    champs: dict[str, list] = {}
    for s in ta:
        for k in set(ta[s]) | set(tb[s]):
            if k == "_meta":
                continue
            if ta[s].get(k) != tb[s].get(k):
                champs.setdefault(k, []).append(s)

    L: list[str] = []
    w = L.append
    w("DOSSIER DE RÉCEPTION — BVC Analyzer")
    w("=" * 35)
    w("")
    w("Généré par pipeline/livrer_candidat.py, qui LIT les fichiers joints pour")
    w("écrire ce texte. Aucune valeur n'y est recopiée à la main : le manifeste")
    w("ne peut pas contredire les données qu'il décrit.")
    w("")
    w("CODE RÉELLEMENT EXÉCUTÉ")
    w(f"  candidat   {meta['commit_apres']}   {meta['sujet_apres']}")
    w(f"  avant      {meta['commit_avant']}   ({meta['ref_avant']})")
    w(f"  arbre de travail au moment de la génération : {meta['etat_arbre']}")
    w("  Les deux versions sont extraites par `git archive` DEPUIS LES COMMITS,")
    w("  jamais depuis les fichiers du disque.")
    w("")
    w("EMPREINTES DES SOURCES DU MOTEUR — candidat")
    for rel, h in meta["sources_apres"].items():
        w(f"  {h}  {rel}")
    w("")
    w("EMPREINTES DES FICHIERS PRODUITS")
    w(f"  {empreinte(avant)}  data_avant.json")
    w(f"  {empreinte(apres)}  data_candidat.json")
    w("")
    w("CONDITIONS D'EXÉCUTION")
    w(f"  date d'analyse imposée aux deux runs : {meta['date_analyse']}")
    w(f"  avant     généré {a['updated']}   marché {a['market_status']}")
    w(f"  candidat  généré {b['updated']}   marché {b['market_status']}")
    w("  entrées   chandelles, historique et data.json de départ de la version")
    w("            « avant » imposés AUX DEUX copies")
    w("")
    if bouge:
        w(f"⚠️ {len(bouge)} cours ont bougé entre les deux exécutions. Ces écarts")
        w("   viennent du MARCHÉ, pas du code :")
        for s, (x, y) in sorted(bouge.items()):
            w(f"     {s:6} {x} → {y}")
        w(f"   Les {len(ta) - len(bouge)} autres sont identiques. Les champs techniques")
        w("   dérivés de ces cours bougent en conséquence.")
        w("")
        w("   ⚠️ Marché ouvert : la comparaison reste DESCRIPTIVE. Elle ne permet")
        w("   pas d'attribuer chaque différence au seul code. Une attribution")
        w("   stricte demande une exécution hors séance.")
    else:
        w(f"Les {len(ta)} cours sont identiques entre les deux exécutions : toute")
        w("différence est imputable au code et aux fichiers de faits.")
    w("")
    w("CHAMPS QUI DIFFÈRENT — comptés sur les titres communs")
    for k, v in sorted(champs.items(), key=lambda x: -len(x[1])):
        w(f"  {k:14} {len(v):>3}")
    w("")
    w("RÉSERVE")
    w("  Ce fichier n'est pas celui que sert le site. Rien n'est fusionné.")
    return "\n".join(L) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", default="origin/main", help="version de comparaison")
    p.add_argument("--sortie", default=None, help="dossier de sortie")
    p.add_argument("--date-analyse", default=None,
                   help="date de décision imposée (défaut : aujourd'hui)")
    args = p.parse_args()

    exiger_arbre_propre()
    date_analyse = args.date_analyse or datetime.now().strftime("%Y-%m-%d")
    sortie = Path(args.sortie or tempfile.mkdtemp(prefix="reception_"))
    sortie.mkdir(parents=True, exist_ok=True)

    travail = Path(tempfile.mkdtemp(prefix="livraison_"))
    d_avant, d_apres = travail / "avant", travail / "apres"
    print(f"Extraction de {args.base} et de HEAD…")
    extraire(args.base, d_avant)
    extraire("HEAD", d_apres)
    aligner_entrees(d_avant, d_apres)

    print("Exécution des deux moteurs…")
    f_avant = executer(d_avant, date_analyse)
    f_apres = executer(d_apres, date_analyse)

    shutil.copy2(f_avant, sortie / "data_avant.json")
    shutil.copy2(f_apres, sortie / "data_candidat.json")

    meta = {
        "commit_apres": git("rev-parse", "HEAD"),
        "sujet_apres": git("log", "-1", "--format=%s"),
        "commit_avant": git("rev-parse", args.base),
        "ref_avant": args.base,
        "etat_arbre": "propre (vérifié avant extraction)",
        "date_analyse": date_analyse,
        "sources_apres": {rel: empreinte(d_apres / rel)
                          for rel in SOURCES_MOTEUR if (d_apres / rel).exists()},
    }
    (sortie / "MANIFESTE.txt").write_text(
        rediger_manifeste(sortie / "data_avant.json", sortie / "data_candidat.json", meta),
        encoding="utf-8")
    shutil.rmtree(travail, ignore_errors=True)
    print(f"\nDossier prêt : {sortie}")
    for f in sorted(sortie.iterdir()):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()

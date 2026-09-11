#!/usr/bin/env python3
"""Construit le candidat de fusion LIMITÉ, et dit ce qu'il laisse dehors.

⚠️ POURQUOI CE FICHIER EXISTE
─────────────────────────────
Une proposition de fusion écrite en prose ne se vérifie pas. Celle-ci se
REJOUE : ce programme reconstruit, à partir de `origin/main` et de la branche,
l'arbre exact qui serait fusionné. Deux exécutions donnent le même arbre, et
quiconque doute peut le refaire.

LA COUPURE, ET CE QUI LA JUSTIFIE
─────────────────────────────────
Deux ensembles, séparés par une question simple : **est-ce que cela change ce
que le site sert ?**

  LOT A — CE QUI SERAIT MIS EN LIGNE
  Le moteur qui écrit `data.json`, le terminal qui l'affiche, les pièces
  comptables qu'ils lisent, les garde-fous de publication, et les tests qui
  décrivent tout cela. Chaque élément corrige un défaut constaté.

  LOT B — CE QUI EST RETENU
  La couche de qualification et d'identité (lots 1A à 1G). Elle ne change rien
  à ce qui est servi : elle juge ce qui a le droit d'ENTRER dans l'historique.
  Elle n'a pas encore été reçue par la revue externe. La retenir ne retarde
  aucune correction visible.

⚠️ LA DÉPENDANCE QUE CETTE COUPURE SUPPOSE — ET QUI EST MESURÉE
Le lot A ne doit rien importer du lot B, sans quoi la coupure produirait un
arbre qui ne démarre pas. `verifier_independance()` le vérifie sur l'arbre
syntaxique, et un test permanent l'appelle. **Aucune pièce du lot B ne remonte
dans le lot A.**

⚠️ L'HISTORIQUE N'EST PAS TOUCHÉ, ET CE N'EST PAS UN DÉTAIL
Une version antérieure importait `pipeline/historical_data.json` depuis la
branche et résolvait le conflit de la fusion globale. La revue a montré que
c'était une dépendance inutile : en construisant DEPUIS main par reprise de
fichiers, il n'y a pas de conflit à résoudre — il suffit de ne pas y toucher.
Le patch ne changeait d'ailleurs aucune valeur : il ajoutait un bloc
`_resolution` qui déclarait quatre arbitrages d'extrema que la revue n'a pas
validés. Déclarer « la fenêtre a glissé, les deux valeurs sont justes » est une
affirmation, pas une mesure.

    historique existant conservé, assainissement hors périmètre.

CE QUE CE PROGRAMME NE FAIT PAS
───────────────────────────────
⚠️ Il ne fusionne pas, ne pousse pas, ne publie pas. Il prépare un arbre dans
un dossier jetable et rend compte. La décision appartient au propriétaire.

    python pipeline/candidat_fusion.py --sortie /tmp/candidat
    python pipeline/candidat_fusion.py --verifier-seulement
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BRANCHE = "claude/terminal-bvc-review-AmnBU"
BASE = "origin/main"

# ── LOT A ──────────────────────────────────────────────────────────────────
# Ce qui change ce que le site sert. Un fichier n'entre ici que si l'on peut
# dire QUEL défaut constaté il corrige (voir docs/CANDIDAT_FUSION.md).
LOT_A = [
    # Le moteur qui écrit data.json, et ce qu'il lit
    "update_data.py",
    "bpa.json",
    "pipeline/faits_financiers.json",
    "pipeline/smart_money/fond_score.py",
    # Le terminal
    "index.html",
    # Les autres écrivains du pipeline
    "pipeline/seance.py",
    "pipeline/generate_candles.py",
    # Outil du bulletin PDF : importé par `masi_history.py`, déjà dans main,
    # et par `tests/test_comparateur_bulletin.py` du lot A.
    "pipeline/parse_cdg_bulletin.py",
    "whatsapp_analysis/phase11_backtest.py",
    # Les garde-fous de publication
    ".github/workflows/update_bvc.yml",
    ".github/workflows/bulletin_mail.yml",
    ".github/workflows/tests.yml",
    # Les tests qui décrivent tout ce qui précède, et leur socle commun.
    # ⚠️ `conftest.py` porte le point d'entrée unique vers le fichier publié
    # soumis aux contrôles (`BVC_DATA_JSON`) : c'est lui qui permet de REJOUER
    # une livraison hors ligne sur le fichier exact qui l'accompagne.
    "tests/conftest.py",
    "tests/test_bpa_verifies.py",
    "tests/test_contrat_data_json.py",
    "tests/test_regles_donnees.py",
    "tests/test_suspension.py",
    "tests/test_suspension_comportement.py",
    "tests/test_price_to_book.py",
    "tests/test_raccordement_composantes.py",
    "tests/test_audit_20260909.py",
    "tests/test_backtest_comptabilite.py",
    "tests/test_backtest_identite.py",
    "tests/test_comparateur_bulletin.py",
    "tests/test_pseudonymes.py",
    # ⚠️ Ces deux-là ne portent aucune correction : ils sont repris parce
    # qu'ils LISENT le fichier publié. Les laisser en arrière ferait lire à
    # une partie de la suite la livraison et à l'autre le dépôt.
    "tests/test_faits_financiers.py",
    "tests/test_univers.py",
    # Le workflow de tests est dans le lot A : le contrôle qui le relit aussi.
    "tests/test_workflow_tests.py",
    "requirements_dev.txt",
]

# ⚠️ NON REPRIS. Celui de main est conservé tel quel, à l'octet près.
# L'assainissement de l'historique est hors périmètre de cette livraison.
HISTORIQUE_CONSERVE = "pipeline/historical_data.json"

# ── LOT B ──────────────────────────────────────────────────────────────────
# Retenu. Aucune de ces pièces n'est lue par le lot A (mesuré, pas supposé).
PREFIXES_LOT_B = (
    "docs/", "datasets/", "sources/", "pipeline/bulletins/",
    "ROADMAP.md", "AUDIT_TRACKER.csv",
)
MODULES_LOT_B = {
    "identites", "identite_source", "contamination", "fenetre", "indicateurs",
    "qualification", "regimes_variation", "ruptures", "normaliser",
    "import_source", "importer_export", "journal_differences",
    "unites_volume", "confronter_export", "graphique", "calculer_indicateur",
    "bilan_lot", "inventaire", "livrer_candidat", "resoudre_historique",
}


def _git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(["git", *args], text=True,
                                   cwd=str(cwd or RACINE)).strip()


def verifier_independance(fichiers: list[str] | None = None) -> dict:
    """Le lot A importe-t-il quelque chose du lot B ?

    ⚠️ Mesuré sur l'arbre syntaxique, pas par une recherche de texte : un nom
    de module cité dans un commentaire n'est pas un import, et un import écrit
    autrement qu'attendu ne doit pas passer inaperçu.
    """
    manquants, fautes = [], []
    for rel in (fichiers or LOT_A):
        if not rel.endswith(".py"):
            continue
        chemin = RACINE / rel
        if not chemin.exists():
            manquants.append(rel)
            continue
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for n in ast.walk(arbre):
            noms = []
            if isinstance(n, ast.Import):
                noms = [a.name.split(".")[0] for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module:
                noms = [n.module.split(".")[0]]
            for nom in noms:
                if nom in MODULES_LOT_B:
                    fautes.append({"fichier": rel, "importe": nom,
                                   "ligne": n.lineno})
    return {
        "independant": not fautes,
        "imports_interdits": fautes,
        "fichiers_absents": manquants,
        "_lecture": "le lot A ne doit rien importer de la couche retenue, "
                    "sinon la coupure produirait un arbre qui ne démarre pas",
    }


def construire(sortie: Path, base: str = BASE, branche: str = BRANCHE) -> dict:
    """Monte l'arbre candidat dans `sortie`. Ne fusionne rien, ne pousse rien."""
    if sortie.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(sortie)],
                       cwd=str(RACINE), capture_output=True)
    subprocess.run(["git", "worktree", "prune"], cwd=str(RACINE), check=True,
                   capture_output=True)
    _git("worktree", "add", "--detach", str(sortie), base)

    _git("checkout", branche, "--", *LOT_A, cwd=sortie)

    # ⚠️ L'HISTORIQUE DE `main` EST CONSERVÉ TEL QUEL, ET ON LE VÉRIFIE.
    # Ne pas y toucher est une décision, pas un oubli : elle doit donc se
    # constater. Si un fichier du lot A venait un jour à l'emporter avec lui,
    # ce contrôle le dirait au lieu de le laisser passer.
    empreinte_main = _git("rev-parse", f"{base}:{HISTORIQUE_CONSERVE}")
    empreinte_candidat = _git("hash-object", HISTORIQUE_CONSERVE, cwd=sortie)

    return {
        "_quoi": "candidat de fusion limité — construit, pas fusionné",
        "base": _git("rev-parse", "--short", base),
        "branche": _git("rev-parse", "--short", branche),
        "sortie": str(sortie),
        "lot_a_fichiers": len(LOT_A),
        "historique": {
            "fichier": HISTORIQUE_CONSERVE,
            "conserve_a_l_identique": empreinte_main == empreinte_candidat,
            "empreinte": empreinte_main[:12],
            "_lecture": "historique existant conservé, assainissement hors "
                        "périmètre. Ce candidat ne prétend RIEN sur la "
                        "justesse de cet historique : il n'y touche pas.",
        },
        "independance_du_lot_a": verifier_independance(),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sortie", type=Path, default=Path("/tmp/candidat"))
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--branche", default=BRANCHE)
    ap.add_argument("--verifier-seulement", action="store_true")
    a = ap.parse_args()

    if a.verifier_seulement:
        print(json.dumps(verifier_independance(), ensure_ascii=False, indent=2))
        return
    print(json.dumps(construire(a.sortie, a.base, a.branche),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

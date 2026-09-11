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
syntaxique, et un test permanent l'appelle. Une seule pièce du lot B remonte
dans le lot A, et elle est nommée : `resoudre_historique.py`, parce que la
résolution du conflit en dépend.

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
    # ⚠️ SEULE PIÈCE DU LOT B REMONTÉE ICI, et pour une raison nommée :
    # la résolution du conflit historical_data.json en dépend.
    "pipeline/resoudre_historique.py",
    # Les tests qui décrivent tout ce qui précède
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
]

# Le fichier en conflit : ni repris tel quel de la branche, ni de main.
CONFLIT = "pipeline/historical_data.json"

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
    "bilan_lot", "inventaire", "livrer_candidat",
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
                # `resoudre_historique` est la pièce nommée, remontée exprès.
                if nom in MODULES_LOT_B and rel != "pipeline/resoudre_historique.py":
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

    # ── Le conflit, résolu entrée par entrée (jamais sur la date du fichier)
    sys.path.insert(0, str(sortie / "pipeline"))
    from resoudre_historique import resoudre  # noqa: E402

    cible = sortie / CONFLIT
    cote_main = json.loads(cible.read_text(encoding="utf-8"))
    cote_branche = json.loads(_git("show", f"{branche}:{CONFLIT}"))
    r = resoudre(cote_branche, cote_main, "branche", "main")

    sortie_json = {k: v for k, v in cote_main.items() if k.startswith("_")}
    sortie_json["_resolution"] = {
        "quoi": "conflit de fusion résolu entrée par entrée",
        "regle": "séance la plus récente ; à séance égale, seuls les extrema "
                 "glissants sont arbitrés ; tout autre désaccord est signalé "
                 "et non tranché",
        "decisions_par_cas": r["decisions_par_cas"],
        "non_arbitres": [x["titre"] for x in r["non_arbitres"]],
    }
    sortie_json["_tickers"] = len(r["resolu"])
    sortie_json.update(r["resolu"])
    cible.write_text(json.dumps(sortie_json, ensure_ascii=False), encoding="utf-8")

    # ── Contrôles d'acceptation sur la résolution
    titres = {k for k in cote_branche if not k.startswith("_")} | \
             {k for k in cote_main if not k.startswith("_")}
    recul = [t for t in titres
             if (r["resolu"][t].get("last_date") or "")
             < max((cote_branche.get(t, {}).get("last_date") or ""),
                   (cote_main.get(t, {}).get("last_date") or ""))]

    return {
        "_quoi": "candidat de fusion limité — construit, pas fusionné",
        "base": _git("rev-parse", "--short", base),
        "branche": _git("rev-parse", "--short", branche),
        "sortie": str(sortie),
        "lot_a_fichiers": len(LOT_A),
        "conflit_resolu": {
            "fichier": CONFLIT,
            "titres": len(r["resolu"]),
            "decisions_par_cas": r["decisions_par_cas"],
            "non_arbitres": [x["titre"] for x in r["non_arbitres"]],
            "titres_perdus": sorted(titres - set(r["resolu"])),
            "seances_en_recul": recul,
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

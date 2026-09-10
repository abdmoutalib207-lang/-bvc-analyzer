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
    # ⚠️ Mode audit : une date invalide arrête la livraison plutôt que de la
    # laisser annoncer une date que le moteur n'utilise pas.
    env = dict(os.environ, BVC_DATE_ANALYSE=date_analyse, BVC_MODE_AUDIT="1")
    journal = dossier / "run.log"
    with open(journal, "w") as log:
        r = subprocess.run([sys.executable, "update_data.py"], cwd=dossier,
                           stdout=subprocess.DEVNULL, stderr=log, env=env, timeout=600)
    if r.returncode != 0:
        raise SystemExit(f"le moteur a échoué dans {dossier} — voir {journal}")
    return dossier / "data.json"


def eprouver(dossier: Path, rapport: Path) -> dict:
    """Lance la suite SUR le fichier candidat, dans son propre dossier.

    ⚠️ Ajouté le 10/09/2026, après avoir livré un candidat ROUGE en annonçant
    361 tests verts. Ma suite tournait sur le `data.json` du dépôt, daté du
    08/09, qui ne contenait pas la nouvelle valeur `source_prix` ; le candidat,
    lui, la portait. J'avais donc mesuré un autre fichier que celui que je
    livrais — la « seconde famille » du CLAUDE.md, dans laquelle je suis tombé
    en la documentant.

    Le résultat entre au manifeste. Un dossier de réception qui annonce une
    suite verte doit l'avoir exécutée sur le fichier qu'il contient.

    ⚠️ LE CODE DE RETOUR FAIT FOI, ajouté le 10/09/2026 sur remarque de
    l'auditeur. La première version se contentait de LIRE la sortie : elle
    relevait les échecs sans les rendre bloquants, et la livraison continuait
    jusqu'à « Dossier prêt ». Pire, sur une erreur interne de pytest — sortie
    non analysable, aucune ligne commençant par FAILED — le manifeste pouvait
    afficher « résumé illisible » ET « aucun échec » en même temps.

    Un garde-fou qui constate sans arrêter n'est pas un garde-fou. Le code de
    retour est désormais conservé, et tout code non nul fait échouer la
    livraison.

    Un rapport JUnit XML est produit en parallèle : il porte les échecs, les
    erreurs ET LES RAISONS DES TESTS IGNORÉS, que la ligne de résumé ne donne
    pas. Il voyage avec le dossier.
    """
    # ⚠️ NE PAS ajouter `-q` : pytest.ini le pose déjà, et un second `-q`
    # devient `-qq`, qui SUPPRIME la ligne de résumé. Le script rendait alors
    # « résumé illisible » sur une suite parfaitement verte — un dossier de
    # réception qui n'arrive pas à lire son propre résultat ne vaut rien.
    r = subprocess.run([sys.executable, "-m", "pytest", "--tb=line",
                        f"--junitxml={rapport}"],
                       cwd=dossier, capture_output=True, text=True, timeout=900)
    sortie = (r.stdout or "") + (r.stderr or "")
    import re as _re
    # ⚠️ pytest colore et découpe sa dernière ligne ; on cherche le compte,
    # pas une ligne entière. Une première version rendait « résumé illisible »
    # alors que la suite avait bien tourné.
    m = [l for l in sortie.splitlines()
         if _re.search(r"\d+ (passed|failed|error)", l)]
    resume = m[-1].strip() if m else f"résumé illisible (code {r.returncode})"
    echecs = "\n".join(l.strip() for l in sortie.splitlines()
                       if l.startswith("FAILED") or l.startswith("ERROR"))
    # Les raisons d'IGNORÉ sont lues dans le rapport structuré : la ligne de
    # résumé les compte sans jamais les nommer.
    ignores = []
    if rapport.exists():
        try:
            import xml.etree.ElementTree as ET
            for cas in ET.parse(rapport).getroot().iter("testcase"):
                for sk in cas.findall("skipped"):
                    ignores.append(f"{cas.get('classname','')}::{cas.get('name','')}"
                                   f" — {(sk.get('message') or '').strip()[:150]}")
        except Exception as e:                                # pragma: no cover
            ignores.append(f"(rapport JUnit illisible : {e})")
    return {"code": r.returncode, "resume": resume, "echecs": echecs,
            "ignores": ignores, "sortie": sortie}


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
    w("SUITE DE TESTS EXÉCUTÉE SUR LE CANDIDAT")
    w(f"  {meta['tests_resume']}")
    w(f"  code de retour de pytest : {meta['tests_code']}  "
      f"({'succès' if meta['tests_code'] == 0 else 'ÉCHEC'})")
    w("  ⚠️ C'est le CODE DE RETOUR qui fait foi, pas la lecture de la sortie :")
    w("  sur une erreur interne, celle-ci peut être illisible sans qu'aucune")
    w("  ligne ne commence par FAILED. Un code non nul interrompt la livraison")
    w("  et produit un fichier CANDIDAT_NON_VALIDE.txt au lieu d'un manifeste.")
    if meta["tests_echecs"]:
        w("  ⚠️ ÉCHECS :")
        for l in meta["tests_echecs"].splitlines():
            w(f"    {l}")
    else:
        w("  aucun échec")
    if meta["tests_ignores"]:
        w(f"  {len(meta['tests_ignores'])} test(s) ignoré(s), avec leur raison :")
        for l in meta["tests_ignores"]:
            w(f"    {l}")
    w("  Rapport structuré joint : rapport_tests.xml (JUnit)")
    w("  Exécutée dans le dossier du candidat, donc sur le data.json joint —")
    w("  et non sur celui du dépôt. La distinction n'est pas théorique : une")
    w("  livraison précédente annonçait 361 verts mesurés sur un autre fichier.")
    w("")
    w("CONDITIONS D'EXÉCUTION")
    w(f"  date d'analyse DEMANDÉE  : {meta['date_analyse']}")
    w(f"  date d'analyse ENREGISTRÉE dans les fichiers produits :")
    w(f"      avant    {a.get('date_analyse', '(champ absent)')}")
    w(f"      candidat {b.get('date_analyse', '(champ absent)')}")
    w( "      (lue dans le JSON, pas recopiée de la demande : c'est le moteur")
    w( "       qui l'écrit, donc elle ne peut pas diverger de ce qu'il a fait)")
    w(f"  avant     généré {a['updated']}   marché {a['market_status']}")
    w(f"  candidat  généré {b['updated']}   marché {b['market_status']}")
    w("  entrées   chandelles, historique et data.json de départ de la version")
    w("            « avant » imposés AUX DEUX copies")
    w("")
    # ── ce qui a été VÉRIFIÉ identique, nommé un par un ──────────────────
    #
    # ⚠️ La version précédente concluait « toute différence est imputable au
    # code ». L'auditeur a jugé cette promesse trop forte, et il a raison : des
    # cours identiques ne prouvent pas que TOUTES les informations reçues le
    # soient. Volumes, actualités, réponses de repli et contexte temporel
    # peuvent différer sans que les prix bougent.
    #
    # Le script impose les chandelles, l'historique et le data.json de départ ;
    # il ne rejoue PAS les réponses des fournisseurs. Une garantie de rejeu
    # complet demanderait de les enregistrer une fois et de servir exactement
    # les mêmes aux deux moteurs. Tant que ce n'est pas fait, on énumère ce
    # qu'on a contrôlé et on s'arrête là.
    # ⚠️ Un champ absent d'un côté est un champ NOUVEAU, pas une différence de
    # contexte. Les confondre ferait crier au loup à chaque ajout.
    def _compare(cle, extraire):
        va, vb = extraire(a), extraire(b)
        if va is None and vb is not None:
            return "nouveau"
        return "identique" if va == vb else "DIFFÉRENT"

    def _tous(champ):
        return ("identique" if all(ta[s].get(champ) == tb[s].get(champ) for s in ta)
                else "DIFFÉRENT")

    contexte = {
        "MASI (valeur)": _compare("masi", lambda d: d.get("masi", {}).get("value")),
        "MASI (date)": _compare("masi", lambda d: d.get("masi", {}).get("asof")),
        "statut du marché": _compare("ms", lambda d: d.get("market_status")),
        "date d'analyse": _compare("da", lambda d: d.get("date_analyse")),
        "univers (symboles)": "identique" if set(ta) == set(tb) else "DIFFÉRENT",
        "pondérations": _tous("poids"),
        "cours": _tous("price"),
        "volumes": _tous("vol"),
        "scores techniques": _tous("score_tech"),
    }
    w("CONTEXTE CONTRÔLÉ ENTRE LES DEUX EXÉCUTIONS")
    for nom, etat in contexte.items():
        w(f"  {etat:<11}{nom}")
    w("")

    # ⚠️ NE PAS ATTRIBUER CE QU'ON NE PEUT PAS ÉTABLIR. La version précédente
    # rangeait TOUT écart de cours sous « vient du marché ». C'était faux : sur
    # un titre suspendu, c'est le code qui fixe le prix de référence. On sépare
    # donc ce qu'on sait expliquer de ce qu'on ne sait pas.
    suspendus = {s for s in tb
                 if (tb[s].get("_meta") or {}).get("suspendu")
                 or (ta[s].get("_meta") or {}).get("suspendu")}
    expliques = {s: v for s, v in bouge.items() if s in suspendus}
    inexpliques = {s: v for s, v in bouge.items() if s not in suspendus}
    vol_diff = [s for s in ta if ta[s].get("vol") != tb[s].get("vol")]

    if expliques:
        w("ÉCARTS DE COURS COMPATIBLES AVEC LE CORRECTIF")
        for s, (x, y) in sorted(expliques.items()):
            w(f"  {s:6} {x} → {y}   titre suspendu")
        w("  Le correctif ramène la référence d'un titre suspendu à sa dernière")
        w("  cotation portant un volume, ce qui produirait exactement cet écart.")
        w("  ⚠️ « Compatible », pas « expliqué » : la suspension seule ne prouve")
        w("  pas que le correctif soit la cause. Le script ne fait pas cette")
        w("  démonstration, il constate la compatibilité.")
        w("")
    if inexpliques:
        w("ÉCARTS DE COURS NON EXPLIQUÉS PAR LE CODE")
        for s, (x, y) in sorted(inexpliques.items()):
            w(f"  {s:6} {x} → {y}")
        w("  Ces titres ne sont pas suspendus : l'écart vient vraisemblablement")
        w("  du marché ou de la source, mais le script ne peut pas le CERTIFIER.")
        w("")
    if vol_diff:
        w(f"VOLUMES DIFFÉRENTS SUR {len(vol_diff)} TITRE(S)")
        w(f"  {', '.join(sorted(vol_diff))}")
        w("  ⚠️ Les cours peuvent être identiques pendant que d'autres champs")
        w("  varient. Ces JSON prouvent une différence de SORTIE ; ils n'en")
        w("  établissent pas l'origine. Attribuer ces écarts aux réponses des")
        w("  fournisseurs exigerait leurs réponses brutes, que le script")
        w("  n'enregistre pas.")
        w("")

    w("PORTÉE DE LA COMPARAISON")
    non_explique = [n for n, e in contexte.items() if e == "DIFFÉRENT"
                    and not (n == "cours" and not inexpliques)
                    and not (n == "scores techniques" and set(bouge) <= suspendus)]
    if not non_explique:
        w("  Tout écart de contexte constaté s'explique par les modifications")
        w("  apportées. Les différences observées sont COMPATIBLES avec elles.")
    else:
        w(f"  ⚠️ Écarts de contexte non expliqués : {', '.join(non_explique)}.")
        w("  Les différences ne peuvent pas être attribuées aux seules")
        w("  modifications de code.")
    w("")
    w("  ⚠️ SANS GARANTIE GÉNÉRALE DE REJEU FIGÉ. Le script impose les")
    w("  chandelles, l'historique et le data.json de départ, mais chaque moteur")
    w("  interroge les fournisseurs pour son compte. Des cours identiques ne")
    w("  prouvent pas que toutes les réponses reçues le soient — volumes,")
    w("  actualités, replis et contexte temporel peuvent différer. Fermer le")
    w("  marché ne suffit pas à figer les sources. Une garantie complète exige")
    w("  d'enregistrer les réponses externes une fois, puis de servir exactement")
    w("  les mêmes aux deux moteurs. Ce n'est pas fait à ce jour.")
    w("")
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

    # ⚠️ Les pièces CITÉES doivent voyager avec le dossier. L'auditeur a
    # relevé, à raison, qu'il ne pouvait certifier « trois bulletins
    # consécutifs » à partir d'une archive qui ne les contenait pas. Un
    # dossier de réception qui invoque une preuve doit la joindre.
    pieces = sorted((RACINE / "pipeline" / "bulletins").glob("*.pdf")) \
        if (RACINE / "pipeline" / "bulletins").exists() else []
    if pieces:
        (sortie / "pieces").mkdir(exist_ok=True)
        for p in pieces:
            shutil.copy2(p, sortie / "pieces" / p.name)

    print("Exécution de la suite sur le candidat…")
    rapport = sortie / "rapport_tests.xml"
    verdict = eprouver(d_apres, rapport)
    print(f"  {verdict['resume']}")

    # ⚠️ ARRÊT BLOQUANT. Le code de retour de pytest fait foi — pas l'analyse
    # de sa sortie, qui peut être illisible sur erreur interne. Un dossier
    # produit malgré des tests rouges serait présenté comme une livraison
    # validée alors qu'il n'en est pas une.
    if verdict["code"] != 0:
        (sortie / "CANDIDAT_NON_VALIDE.txt").write_text(
            "CANDIDAT NON VALIDÉ\n"
            "===================\n\n"
            f"pytest a retourné le code {verdict['code']} sur le fichier candidat.\n"
            f"Résumé : {verdict['resume']}\n\n"
            + (f"Échecs :\n{verdict['echecs']}\n\n" if verdict["echecs"] else "")
            + "Ce dossier est un DIAGNOSTIC, pas une livraison. Il ne doit pas\n"
              "être présenté comme validé. Le rapport structuré des tests est\n"
              "joint sous rapport_tests.xml.\n",
            encoding="utf-8")
        (sortie / "sortie_tests.txt").write_text(verdict["sortie"], encoding="utf-8")
        print(f"\n❌ CANDIDAT NON VALIDÉ — pytest code {verdict['code']}", file=sys.stderr)
        print(f"   {verdict['resume']}", file=sys.stderr)
        if verdict["echecs"]:
            print(verdict["echecs"], file=sys.stderr)
        print(f"   Diagnostic conservé dans {sortie}", file=sys.stderr)
        raise SystemExit(1)

    meta = {
        "tests_code": verdict["code"],
        "tests_resume": verdict["resume"],
        "tests_echecs": verdict["echecs"],
        "tests_ignores": verdict["ignores"],
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

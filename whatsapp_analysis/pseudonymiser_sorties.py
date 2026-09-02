"""
Remplace les noms des membres par leurs pseudonymes dans les sorties versionnées.

À LANCER APRÈS CHAQUE RUN DU PIPELINE, AVANT TOUT COMMIT :

    python -m whatsapp_analysis.pseudonymiser_sorties

Le pipeline produit ses fichiers avec les noms réels — c'est normal, il
travaille en local sur le corpus. Ce script est l'écluse entre ce travail local
et le dépôt public. Rien de ce qu'il n'a pas traité ne doit être commité.

⚠️ Il modifie les fichiers SUR PLACE. Les noms d'origine restent disponibles
dans la table de correspondance (`data/pseudonymes.json`, hors dépôt) et dans
les sorties non versionnées.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from whatsapp_analysis.pseudonymes import TablePseudonymes, _normaliser

RACINE = Path(__file__).resolve().parent.parent
SORTIES = RACINE / "whatsapp_analysis" / "output"

# Fichiers versionnés qui portent une colonne d'auteurs.
CSV_A_TRAITER = ("smart_money_ranking.csv", "network_metrics.csv")
# Fichiers versionnés où les noms apparaissent en texte libre.
HTML_A_TRAITER = ("report.html",)

# ⚠️ Hors du dossier de sorties : le FRONTEND lui-même. `index.html` nommait
# 17 membres réels dans ses tables `MEMBERS` et `CHAT` — avec leur rang, leur
# taux de réussite et des messages qui leur étaient attribués. C'est la page
# publiée sur GitHub Pages : plus exposée encore que les fichiers de données,
# parce qu'elle se lit sans savoir ce qu'est un dépôt.
AUTRES_A_TRAITER = (RACINE / "index.html",)

COLONNES_AUTEUR = ("author", "auteur", "member", "source", "target", "from", "to")


def _traiter_csv(chemin: Path, table: TablePseudonymes) -> int:
    if not chemin.exists():
        return 0
    with open(chemin, encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f))
    if not lignes:
        return 0
    champs = list(lignes[0].keys())
    cibles = [c for c in champs if c and c.lower() in COLONNES_AUTEUR]
    if not cibles:
        return 0

    # Amorcer d'abord sur TOUTE la colonne : l'attribution suit le condensat,
    # pas l'ordre des lignes — sinon le numéro trahirait le classement, qui est
    # précisément ce que le fichier publie.
    for c in cibles:
        table.amorcer(l.get(c, "") for l in lignes)

    n = 0
    for l in lignes:
        for c in cibles:
            if (l.get(c) or "").strip():
                l[c] = table.pseudonyme(l[c])
                n += 1

    tmp = chemin.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=champs)
        w.writeheader()
        w.writerows(lignes)
    tmp.replace(chemin)
    return n


def _noms_originaux(chemins) -> set[str]:
    """Récupère les noms tels qu'ils sont écrits dans les CSV, AVANT nettoyage.

    Le HTML doit être traité avec ces orthographes-là : la table ne conserve
    que des clés normalisées (minuscules, espaces réduits), qui ne se
    retrouveraient pas telles quelles dans le rapport.
    """
    noms = set()
    for chemin in chemins:
        if not chemin.exists():
            continue
        with open(chemin, encoding="utf-8", newline="") as f:
            for ligne in csv.DictReader(f):
                for champ, valeur in ligne.items():
                    if champ and champ.lower() in COLONNES_AUTEUR and (valeur or "").strip():
                        noms.add(valeur.strip())
    return noms


def _traiter_html(chemin: Path, table: TablePseudonymes, noms) -> int:
    """Remplace les noms connus dans un fichier texte.

    Les plus longs d'abord : sans cela « Mehdi » remplacerait le début de
    « Karim Doe Groupe Test » et laisserait la fin du nom en clair.
    """
    if not chemin.exists():
        return 0
    texte = chemin.read_text(encoding="utf-8", errors="ignore")
    n = 0
    for nom in sorted(noms, key=len, reverse=True):
        if len(nom) < 4:
            continue  # trop court : mordrait sur des fragments de mots
        # Le « ~ » que WhatsApp place devant un membre absent du carnet
        # d'adresses fait partie de l'affichage, pas du nom. Sans l'absorber,
        # « M9925 » deviendrait « ~ M0421 » et garderait sa marque.
        motif = r"~?\s*" + re.escape(nom)
        texte, k = re.subn(motif, table.pseudonyme(nom), texte, flags=re.IGNORECASE)
        n += k
    if n:
        chemin.write_text(texte, encoding="utf-8")
    return n


def _noms_du_frontend(chemin: Path) -> set[str]:
    """Relève les noms de personnes codés en dur dans le frontend.

    Ils vivent dans les tables de démonstration `MEMBERS` et `CHAT`, sous les
    clés `name:` et `member:`. On ne retient que ceux que le corpus connaît :
    les autres champs `name:` du fichier désignent des sociétés cotées, qu'il
    ne faut évidemment pas toucher.
    """
    if not chemin.exists():
        return set()
    texte = chemin.read_text(encoding="utf-8", errors="ignore")
    return set(re.findall(r'(?:name|member)\s*:\s*"([^"]+)"', texte))


def main() -> int:
    if not SORTIES.exists():
        print(f"Aucune sortie à traiter dans {SORTIES}")
        return 0

    table = TablePseudonymes()
    avant = len(table)

    # Les noms sont relevés AVANT toute écriture : une fois les CSV nettoyés,
    # les orthographes d'origine nécessaires au HTML auraient disparu.
    chemins_csv = [SORTIES / n for n in CSV_A_TRAITER]
    noms = _noms_originaux(chemins_csv)
    table.amorcer(noms)

    total = 0
    for nom in HTML_A_TRAITER:
        n = _traiter_html(SORTIES / nom, table, noms)
        total += n
        print(f"  {nom:28} {n:>7,} occurrences remplacées".replace(",", " "))

    for nom in CSV_A_TRAITER:
        n = _traiter_csv(SORTIES / nom, table)
        total += n
        print(f"  {nom:28} {n:>7,} valeurs pseudonymisées".replace(",", " "))

    # Le frontend en dernier : seuls les noms que le corpus reconnaît sont
    # remplacés, pour ne pas toucher aux raisons sociales des 80 titres qui
    # partagent la même clé `name:` dans le fichier.
    for chemin in AUTRES_A_TRAITER:
        candidats = _noms_du_frontend(chemin)
        connus = {c for c in candidats if _normaliser(c.lstrip("~ ")) in table._table}
        n = _traiter_html(chemin, table, {c.lstrip("~ ").strip() for c in connus})
        total += n
        print(f"  {chemin.name:28} {n:>7,} occurrences remplacées "
              f"({len(connus)} membres)".replace(",", " "))

    table.enregistrer()
    print(
        f"\n  Membres connus : {len(table):,} "
        f"({len(table) - avant:+,} nouveaux)".replace(",", " ")
    )
    print(f"  Table (hors dépôt) : {table.chemin}")
    if total == 0:
        print("\n  ⚠️ Aucun remplacement — vérifier que le pipeline a bien tourné.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Garde : le corpus WhatsApp, ses identités et leur table ne reviennent pas.

Ce fichier testait jusqu'au 29/10/2026 `whatsapp_analysis/pseudonymes.py` —
le mécanisme qui remplaçait chaque membre du groupe par un `M####`. Le corpus
et tout ce qui est NLP sont SUPPRIMÉS (décision d'Abd Moutalib du 28/10/2026,
lot 3) : il n'y a plus de mécanisme à tester, il reste un RÉSULTAT à garder.

Le dépôt est public et a exposé 2 013 noms pendant trois mois
(`.claude/memory/INCIDENT_VIE_PRIVEE.md`). Ce qui suit refuse qu'entre de
nouveau dans le dépôt — versionné, ou prêt à l'être au prochain `git add -A` :
  1. un module de pseudonymisation ou une table de correspondance membre → M#### ;
  2. une sortie CSV du corpus, ou tout CSV portant une colonne d'auteur ;
  3. le corpus lui-même ;
  4. une table de membres dans la page servie ou dans sa source.

⚠️ Aucun nom de personne réelle dans ce fichier (règle 1 de l'incident) : les
contrôles négatifs n'emploient que des valeurs INVENTÉES.
"""

import csv
import io
import re
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent

# Modules et tables du mécanisme retiré. Le NOM DE BASE suffit : où qu'ils
# reviennent, ils n'ont plus de raison d'être.
MODULES_RETIRES = {"pseudonymes.py", "pseudonymiser_sorties.py", "pseudonymes.json"}
# Sorties de l'ancien pipeline NLP, toutes dérivées du corpus.
SORTIES_DU_CORPUS = {"messages.csv", "final_rankings.csv", "stock_scores.csv",
                     "network_metrics.csv", "smart_money_ranking.csv"}
# Colonnes qui désignent une PERSONNE. « source » / « target » / « from » ne
# sont pas retenues : ces mots servent aussi à nos données de marché.
COLONNES_AUTEUR = {"author", "auteur", "member", "membre", "sender", "expediteur"}


def _fichiers_du_depot():
    """Fichiers versionnés ET non ignorés en attente : ce qui est public, et
    ce qui le deviendrait au prochain `git add -A`."""
    if subprocess.run(["git", "rev-parse", "--git-dir"], cwd=RACINE,
                      capture_output=True).returncode != 0:
        # Hors dépôt git (copie extraite par `git archive`), ce contrôle ne
        # peut rien AFFIRMER : il s'abstient au lieu de condamner.
        pytest.skip("hors dépôt git : le contrôle des fichiers versionnés est sans objet ici")
    r = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                       cwd=RACINE, capture_output=True, text=True, check=True)
    return [p for p in r.stdout.splitlines() if p and (RACINE / p).exists()]


def _interdits(chemins):
    """Les chemins qui ne doivent pas exister dans le dépôt, avec la raison."""
    fautes = []
    for p in chemins:
        nom = Path(p).name
        if p.split("/")[0] == "whatsapp_analysis":
            fautes.append(f"{p} (dossier du corpus)")
        elif nom in MODULES_RETIRES:
            fautes.append(f"{p} (pseudonymisation)")
        elif nom in SORTIES_DU_CORPUS:
            fautes.append(f"{p} (sortie du corpus)")
        elif "_chat" in nom or "chat_part" in p:
            fautes.append(f"{p} (corpus)")
    return fautes


def _colonnes_auteur(entete: str) -> set:
    lu = next(csv.reader(io.StringIO(entete)), [])
    return {c.strip().strip('"').lower() for c in lu} & COLONNES_AUTEUR


# ── 1-3. Rien du corpus dans le dépôt ─────────────────────────────────────

def test_aucun_module_table_ni_sortie_du_corpus_dans_le_depot():
    fautes = _interdits(_fichiers_du_depot())
    assert not fautes, (
        "le corpus, sa pseudonymisation ou ses sorties réapparaissent dans un "
        f"dépôt PUBLIC : {fautes[:10]}")


def test_aucun_csv_ne_porte_une_colonne_d_auteur():
    """Un CSV qui nomme des auteurs, sous n'importe quel nom de fichier."""
    fautes = []
    for p in _fichiers_du_depot():
        if not p.lower().endswith(".csv"):
            continue
        with open(RACINE / p, encoding="utf-8", errors="ignore", newline="") as f:
            entete = f.readline()
        cols = _colonnes_auteur(entete)
        if cols:
            fautes.append(f"{p} {sorted(cols)}")
    assert not fautes, f"CSV à colonne d'auteur dans le dépôt : {fautes[:10]}"


def test_data_reste_ignore_en_entier():
    """`data/` est l'endroit où vivaient le corpus et la table d'identité. Il
    reste ignoré EN ENTIER : une liste de fichiers nommés un par un laisse
    passer le prochain fichier sensible qu'on y déposera."""
    _fichiers_du_depot()  # s'abstient hors dépôt git
    for p in ("data/pseudonymes.json", "data/_chat.txt", "data/nouveau_fichier.csv"):
        r = subprocess.run(["git", "check-ignore", "-q", p], cwd=RACINE, capture_output=True)
        assert r.returncode == 0, f"{p} serait versionné"


def test_le_controle_voit_bien_un_retour():
    """Contrôle négatif : une garde jamais vue rouge ne prouve rien."""
    for faux in ("whatsapp_analysis/phase3_nlp.py", "pipeline/pseudonymes.py",
                 "outils/pseudonymiser_sorties.py", "datasets/pseudonymes.json",
                 "datasets/final_rankings.csv", "sorties/network_metrics.csv",
                 "data2/_chat.txt", "x/chat_parts/1.txt"):
        assert _interdits([faux]), faux
    assert not _interdits(["pipeline/backtest.py", "tests/test_pseudonymes.py",
                           "datasets/referentiel/cote_casablanca_2026-09-16.csv"])
    assert _colonnes_auteur('date,"Author",text\n') == {"author"}
    assert _colonnes_auteur("membre;x\n".replace(";", ",")) == {"membre"}
    assert not _colonnes_auteur("date,source,cours,volume\n")


# ── 4. Aucune table de membres dans le terminal ───────────────────────────

TABLE_DE_MEMBRES = re.compile(r"\{[^{}]*\btier\s*:[^{}]*\}")


@pytest.mark.parametrize("nom", ["index.html", "terminal.src.html"])
def test_le_terminal_ne_contient_aucune_table_de_membres(nom):
    """index.html nommait 17 membres du groupe jusqu'au 02/09/2026. Les tables
    de membres (onglets SMART MONEY et NLP CORPUS, champ `tier:`) sont retirées
    depuis le 28/10 : il ne doit plus y en avoir AUCUNE, nommée ou non."""
    f = RACINE / nom
    if not f.exists():
        pytest.skip(f"{nom} absent")
    tables = TABLE_DE_MEMBRES.findall(f.read_text(encoding="utf-8", errors="ignore"))
    assert not tables, f"{nom} : {len(tables)} entrée(s) de table de membres"


def test_la_detection_de_table_de_membres_voit_un_retour():
    assert TABLE_DE_MEMBRES.search('{name:"M9999",tier:"Tier 1",win:0.5}')
    assert not TABLE_DE_MEMBRES.search('{name:"Minière Touissit",sym:"CMT"}')

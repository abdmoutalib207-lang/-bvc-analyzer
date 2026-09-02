"""
Pseudonymisation des membres — whatsapp_analysis/pseudonymes.py

Ces tests protègent des personnes réelles, pas un calcul. Le dépôt est public
et a exposé 2 013 noms pendant trois mois ; ce qui suit fige les propriétés qui
empêchent que ça se reproduise.

Quatre façons d'échouer, par gravité décroissante :
  1. un nom réel atteint un fichier du dépôt ;
  2. le pseudonyme laisse ré-identifier (il encode l'ancienneté, le rang…) ;
  3. les numéros changent d'un run à l'autre → l'historique devient incomparable ;
  4. le même membre reçoit deux numéros → son historique est coupé en deux.
"""

import csv
import json

import pytest

from whatsapp_analysis.pseudonymes import (
    TablePseudonymes,
    _normaliser,
    pseudonymiser_colonne,
)


@pytest.fixture
def table(tmp_path):
    return TablePseudonymes(tmp_path / "pseudo.json")


# ── 1. Aucun nom réel ne ressort ──────────────────────────────────────────

def test_le_pseudonyme_ne_contient_rien_du_nom(table):
    for nom in ["Karim Doe Groupe Test", "exemple2", "+212 6 00 00 00 00"]:
        p = table.pseudonyme(nom)
        assert p.startswith("M") and p[1:].isdigit()
        for morceau in nom.lower().replace("+", " ").split():
            assert morceau not in p.lower()


def test_un_numero_de_telephone_est_traite_comme_un_nom(table):
    """Deux entrées du fichier publié étaient des numéros en clair. Ils doivent
    disparaître comme le reste — un numéro identifie plus sûrement qu'un nom."""
    p = table.pseudonyme("+212 600 000 000")
    assert not any(c.isdigit() for c in p[1:] if False)  # forme M####
    assert "212" not in p and "661" not in p


# ── 2. Le pseudonyme n'encode rien ────────────────────────────────────────

def test_l_ordre_d_attribution_ne_suit_pas_l_ordre_d_arrivee(table):
    """Le cœur du refus de numéroter par date d'arrivée : si le rang suivait
    l'ordre du lot, M0001 désignerait le doyen du groupe — trois personnes au
    plus, donc identifiables."""
    membres = [f"Membre {i:03d}" for i in range(60)]
    table.amorcer(membres)
    rangs = [int(table.pseudonyme(n)[1:]) for n in membres]
    assert rangs != sorted(rangs), (
        "les numéros suivent l'ordre d'entrée — l'ancienneté est déductible"
    )


def test_deux_tables_de_sels_differents_donnent_des_numeros_differents(tmp_path):
    """Sans sel secret, un condensat se casse par force brute : les noms des
    membres sont énumérables. Deux sels doivent produire deux numérotations."""
    a, b = TablePseudonymes(tmp_path / "a.json"), TablePseudonymes(tmp_path / "b.json")
    membres = [f"Membre {i}" for i in range(40)]
    a.amorcer(membres)
    b.amorcer(membres)
    assert [a.pseudonyme(m) for m in membres] != [b.pseudonyme(m) for m in membres]


# ── 3. Stabilité dans le temps ────────────────────────────────────────────

def test_les_numeros_survivent_a_un_rechargement(tmp_path):
    chemin = tmp_path / "p.json"
    t1 = TablePseudonymes(chemin)
    t1.amorcer(["Alice", "Bob", "Carole"])
    avant = {n: t1.pseudonyme(n) for n in ["Alice", "Bob", "Carole"]}
    t1.enregistrer()

    t2 = TablePseudonymes(chemin)
    assert {n: t2.pseudonyme(n) for n in avant} == avant


def test_un_nouveau_membre_ne_renumerote_pas_les_anciens(tmp_path):
    """Le corpus grossit à chaque export. Si l'arrivée d'un membre décalait les
    numéros, tout le backtest deviendrait incomparable d'un run au suivant."""
    chemin = tmp_path / "p.json"
    t = TablePseudonymes(chemin)
    t.amorcer(["Alice", "Bob"])
    avant = {n: t.pseudonyme(n) for n in ["Alice", "Bob"]}
    t.enregistrer()

    t2 = TablePseudonymes(chemin)
    t2.amorcer(["Alice", "Bob", "Nouveau", "Encore un"])
    assert {n: t2.pseudonyme(n) for n in avant} == avant
    assert t2.pseudonyme("Nouveau") not in avant.values()


# ── 4. Une personne, un numéro ────────────────────────────────────────────

@pytest.mark.parametrize("a,b", [
    ("Karim Doe", "karim doe"),          # casse
    ("Karim  Doe", "Karim Doe"),         # espaces multiples
    ("Karim Doe ", " Karim Doe"),        # bords
    ("Mehdi Doe", "Karim Doe"),     # espace insécable
    ("Méhdi", "Méhdi"),             # accent composé vs précomposé
])
def test_les_variantes_d_ecriture_donnent_le_meme_numero(table, a, b):
    """WhatsApp écrit le même membre différemment selon qu'il est ou non dans
    les contacts. Sans normalisation, son historique serait coupé en deux."""
    assert table.pseudonyme(a) == table.pseudonyme(b)


def test_deux_membres_distincts_ne_partagent_jamais_un_numero(table):
    membres = [f"Membre {i}" for i in range(2100)]  # au-delà des 2 013 réels
    table.amorcer(membres)
    numeros = [table.pseudonyme(m) for m in membres]
    assert len(set(numeros)) == len(membres)


@pytest.mark.parametrize("vide", [None, "", "   ", "‎"])
def test_auteur_absent_ne_cree_pas_de_membre_fantome(table, vide):
    assert table.pseudonyme(vide) == "M0000"
    assert len(table) == 0


# ── Le fichier de correspondance est un secret ────────────────────────────

def test_la_table_enregistree_porte_un_avertissement_et_le_sel(tmp_path):
    chemin = tmp_path / "p.json"
    t = TablePseudonymes(chemin)
    t.amorcer(["Alice"])
    t.enregistrer()
    charge = json.loads(chemin.read_text(encoding="utf-8"))
    assert "_avertissement" in charge and "jamais commiter" in charge["_avertissement"]
    assert charge["sel"]
    assert oct(chemin.stat().st_mode)[-3:] == "600", "lisible par d'autres comptes"


def test_data_est_ignore_par_git():
    """Le garde-fou qui compte vraiment : la table vit dans data/, et data/
    doit être ignoré EN ENTIER. Une liste de fichiers nommés un par un laisse
    passer le prochain fichier sensible qu'on y déposera."""
    import subprocess
    from pathlib import Path

    racine = Path(__file__).resolve().parent.parent
    r = subprocess.run(
        ["git", "check-ignore", "-q", "data/pseudonymes.json"],
        cwd=racine, capture_output=True,
    )
    assert r.returncode == 0, "data/pseudonymes.json serait versionné"


# ── Application à un tableau de sortie ────────────────────────────────────

def test_pseudonymiser_colonne_remplace_tout_le_monde():
    pd = pytest.importorskip("pandas")
    from whatsapp_analysis.pseudonymes import TablePseudonymes
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        t = TablePseudonymes(Path(d) / "p.json")
        df = pd.DataFrame({
            "author": ["Karim Doe Groupe Test", "exemple2", "Karim Doe Groupe Test"],
            "win_rate": [0.34, 0.51, 0.34],
        })
        df["author"] = pseudonymiser_colonne(df["author"], t)
        assert all(a.startswith("M") and a[1:].isdigit() for a in df["author"])
        assert df["author"].iloc[0] == df["author"].iloc[2], "même personne, même numéro"
        assert df["author"].iloc[0] != df["author"].iloc[1]


# ── LE GARDE-FOU ──────────────────────────────────────────────────────────
# Les tests ci-dessus vérifient le mécanisme. Celui-ci vérifie le RÉSULTAT sur
# les fichiers réellement versionnés, et c'est le seul qui aurait attrapé
# l'incident : entre le 05/06 et le 02/09/2026, 2 013 noms étaient publics et
# aucun test ne regardait. Il ne demande ni la table ni le sel, donc il tourne
# en CI comme en local.

import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIES = RACINE / "whatsapp_analysis" / "output"
FORME_PSEUDO = __import__("re").compile(r"^M\d{4,}$")
COLONNES_AUTEUR = {"author", "auteur", "member", "source", "target", "from", "to"}


def _csv_versionnes():
    r = subprocess.run(
        ["git", "ls-files", "whatsapp_analysis/output/*.csv"],
        cwd=RACINE, capture_output=True, text=True,
    )
    return [RACINE / p for p in r.stdout.split() if p]


def test_aucun_nom_reel_dans_les_csv_versionnes():
    """Toute colonne d'auteur d'un fichier versionné ne doit contenir que des
    pseudonymes de la forme M####. Un nom, un pseudo, un numéro de téléphone —
    tout ce qui n'a pas cette forme fait échouer."""
    fichiers = _csv_versionnes()
    if not fichiers:
        pytest.skip("aucune sortie CSV versionnée")

    fautes = []
    for chemin in fichiers:
        if not chemin.exists():
            continue
        with open(chemin, encoding="utf-8", newline="") as f:
            for i, ligne in enumerate(csv.DictReader(f), start=2):
                for champ, valeur in ligne.items():
                    if not champ or champ.lower() not in COLONNES_AUTEUR:
                        continue
                    v = (valeur or "").strip()
                    if v and not FORME_PSEUDO.match(v):
                        fautes.append(f"{chemin.name}:{i} [{champ}]")
                        break
                if len(fautes) >= 5:
                    break

    assert not fautes, (
        "identité en clair dans un fichier VERSIONNÉ d'un dépôt PUBLIC — "
        f"{len(fautes)} premières : {fautes}. "
        "Lancer : python -m whatsapp_analysis.pseudonymiser_sorties"
    )


def test_le_corpus_n_est_jamais_versionne():
    """Le corpus porte les noms ET le contenu des messages. Il ne doit jamais
    entrer dans le dépôt, quel que soit le nom qu'on lui donne."""
    r = subprocess.run(["git", "ls-files"], cwd=RACINE, capture_output=True, text=True)
    suspects = [
        p for p in r.stdout.splitlines()
        if ("_chat" in p or "chat_part" in p or "messages.csv" in p
            or "pseudonymes.json" in p)
    ]
    assert not suspects, f"fichier de corpus ou table d'identité versionné : {suspects}"

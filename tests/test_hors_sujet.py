"""
Filtre hors-sujet (football) — whatsapp_analysis/hors_sujet.py

Ce filtre a deux façons d'échouer, et la seconde est de loin la pire :
  1. laisser passer du football → un peu de bruit dans le sentiment ;
  2. **manger des messages financiers légitimes** → on détruit le signal qu'on
     prétend nettoyer.

La mesure sur le corpus dit que (2) est le vrai risque : « but », « match »,
« transfert » sont à 91-99 % hors football. Ces tests figent l'étroitesse du
filtre pour qu'un élargissement bien intentionné casse la suite au lieu de
passer inaperçu.
"""

import pytest

from whatsapp_analysis.hors_sujet import (
    TERMES_ECARTES_A_DESSEIN,
    est_hors_sujet,
    motif_hors_sujet,
)


# ── Ce qui DOIT être écarté ────────────────────────────────────────────────

@pytest.mark.parametrize("texte,categorie", [
    ("Le Raja a gagné hier soir",                        "clubs_marocains"),
    ("wydad wydad wydad 💚",                             "clubs_marocains"),
    ("Barça vs Real Madrid ce soir",                     "clubs_etrangers"),
    ("Manchester a encore perdu",                        "clubs_etrangers"),
    ("La botola reprend samedi",                         "competitions"),
    ("Ligue des champions ce soir les amis",             "competitions"),
    ("Hakimi est énorme",                                "joueurs"),
    ("Les Lions de l'Atlas en finale",                   "joueurs"),
    ("penalty scandaleux",                               "lexique"),
    ("le mercato ferme demain",                          "lexique"),
])
def test_football_est_ecarte(texte, categorie):
    assert est_hors_sujet(texte), f"non détecté : {texte!r}"
    assert motif_hors_sujet(texte) == categorie


def test_football_melange_a_un_ticker_est_ecarte():
    """Le cas qui justifie le filtre : un message qui parle des deux.
    Sans filtre, l'enthousiasme footballistique se lit comme un signal ATW."""
    assert est_hors_sujet("ATW monte bien, et le Raja a gagné hier 🔥")


# ── Ce qui NE DOIT SURTOUT PAS être écarté ────────────────────────────────

@pytest.mark.parametrize("texte", [
    # « but » = objectif, 97 % des occurrences du corpus
    "Dans le but de sécuriser mes gains je vends la moitié",
    "Mon but c'est 250 dh sur TGCC",
    # « match » = correspondre
    "Le volume ne match pas avec l'annonce",
    # « transfert » = virement — 99 % des occurrences
    "J'ai fait le transfert vers mon compte titres",
    "Le transfert d'actions est passé ce matin",
    # « stade » = étape
    "Au stade actuel je préfère attendre le résultat annuel",
    # « can » anglais / darija
    "You can check the bulletin",
    # ordinaire
    "CDM publie ses résultats semestriels demain",
    "Je renforce SMI sous 6000",
    "Le MASI casse sa résistance",
])
def test_message_financier_est_conserve(texte):
    assert not est_hors_sujet(texte), f"faux positif — message détruit : {texte!r}"


def test_les_termes_ambigus_restent_hors_du_filtre():
    """Garde-fou explicite. Chacun de ces mots a été mesuré majoritairement
    hors football ; les réintroduire coûterait ~19 messages financiers pour
    1 message de foot écarté. Ce test échoue si quelqu'un les rajoute."""
    for terme in TERMES_ECARTES_A_DESSEIN:
        assert not est_hors_sujet(terme), (
            f"« {terme} » déclenche le filtre alors qu'il est écarté à dessein — "
            "refaire la mesure documentée dans hors_sujet.py avant d'élargir"
        )


# ── Robustesse ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("valeur", [None, "", 42, [], float("nan")])
def test_valeurs_non_textuelles_ne_plantent_pas(valeur):
    """Le parseur produit des lignes médias et système au corps vide ou absent.
    Le filtre est appelé sur toute la colonne, il doit les traverser."""
    assert est_hors_sujet(valeur) is False
    assert motif_hors_sujet(valeur) is None


def test_insensible_a_la_casse_et_aux_accents_courants():
    assert est_hors_sujet("RAJA")
    assert est_hors_sujet("Mbappé")
    assert est_hors_sujet("mbappe")


# ── Le filtre est-il vraiment branché ? ───────────────────────────────────

def test_le_filtre_est_applique_par_explode_tickers():
    """Le défaut à ne pas reproduire : un drapeau calculé que personne ne lit
    (`is_spam` l'est depuis toujours). `_explode_tickers` est le passage obligé
    de toute métrique par titre — si le filtre n'agit pas là, il n'agit nulle
    part."""
    pd = pytest.importorskip("pandas")
    from whatsapp_analysis.phase7_stocks import _explode_tickers

    df = pd.DataFrame([
        {"message_type": "text", "tickers": ["ATW"],
         "message_text": "ATW en forme, comme le Raja hier"},
        {"message_type": "text", "tickers": ["ATW"],
         "message_text": "ATW franchit sa moyenne 50"},
    ])
    sortie = _explode_tickers(df)
    assert len(sortie) == 1, "le message de football n'a pas été écarté"
    assert "Raja" not in sortie.iloc[0]["message_text"]

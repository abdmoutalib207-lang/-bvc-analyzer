"""
Découpage en fils — whatsapp_analysis/fils.py

Ce module décide de ce qui compte comme « matière disponible » pour un titre.
S'il se trompe, tout ce qui vient après — annotation, entraînement, signal —
est bâti sur une attribution fausse, et rien en aval ne le rattrapera.

Trois façons d'échouer :
  1. rattacher au titre une conversation qui n'en parle plus (bruit injecté) ;
  2. couper un fil trop tôt et retomber sur le comptage littéral (×12 perdu) ;
  3. échantillonner sans plafond et n'annoter que cinq personnes.
"""

import re
from datetime import datetime, timedelta

import pytest

from whatsapp_analysis.fils import (
    Message,
    decouper_en_fils,
    echantillonner,
)

T0 = datetime(2026, 3, 12, 10, 0, 0)


def msg(minute, texte, auteur="A", tickers=None):
    """Fabrique un message. `tickers` explicite pour tester le découpage seul,
    sans dépendre de la détection."""
    return Message(
        ts=T0 + timedelta(minutes=minute),
        auteur=auteur,
        texte=texte,
        tickers=frozenset(tickers or []),
    )


# ── Le cœur : la conversation qui suit compte ─────────────────────────────

def test_les_messages_qui_suivent_sont_rattaches_au_titre():
    """Le comportement qui justifie tout le module. « ADI ? » puis quatre
    réponses qui ne nomment jamais ADI : les cinq appartiennent au fil."""
    fils = decouper_en_fils([
        msg(0, "ADI ?", tickers=["ADI"]),
        msg(1, "ça remonte doucement"),
        msg(2, "j'ai renforcé ce matin"),
        msg(3, "le volume est faible quand même"),
        msg(4, "patience"),
    ])
    assert len(fils) == 1
    assert fils[0].ticker == "ADI"
    assert len(fils[0]) == 5, "les réponses sans le code ont été perdues"


def test_un_fil_se_ferme_quand_un_autre_titre_est_cite():
    fils = decouper_en_fils([
        msg(0, "ADI ?", tickers=["ADI"]),
        msg(1, "ça monte"),
        msg(2, "et RDS alors", tickers=["RDS"]),
        msg(3, "RDS c'est mort"),
    ])
    assert [f.ticker for f in fils] == ["ADI", "RDS"]
    assert len(fils[0]) == 2 and len(fils[1]) == 2


def test_un_fil_se_ferme_apres_le_silence():
    """Deux heures de silence séparent deux conversations, même sans autre
    titre cité entre les deux."""
    fils = decouper_en_fils([
        msg(0, "ADI ?", tickers=["ADI"]),
        msg(1, "ça monte"),
        msg(120, "quelqu'un ?"),
    ], trou_minutes=10)
    assert len(fils) == 1 and len(fils[0]) == 2


def test_le_seuil_de_silence_change_le_resultat():
    """Le seuil est un réglage, pas une vérité — le test le rend visible."""
    messages = [msg(0, "ADI ?", tickers=["ADI"]), msg(20, "toujours là ?")]
    assert len(decouper_en_fils(messages, trou_minutes=10)[0]) == 1
    assert len(decouper_en_fils(messages, trou_minutes=30)[0]) == 2


# ── Ce qui ne doit PAS ouvrir un fil ──────────────────────────────────────

def test_un_message_citant_deux_titres_n_ouvre_pas_de_fil():
    """« J'arbitre ADI contre RDS » ne désigne pas un sujet unique : on ne
    peut pas attribuer la suite de la conversation à l'un des deux."""
    fils = decouper_en_fils([
        msg(0, "j'arbitre ADI contre RDS", tickers=["ADI", "RDS"]),
        msg(1, "bonne idée"),
    ])
    assert fils == []


def test_les_messages_avant_l_amorce_ne_sont_pas_rattaches():
    """On ne sait pas de quoi parlaient les messages qui précèdent la première
    mention. Les rattacher serait inventer."""
    fils = decouper_en_fils([
        msg(0, "salam"),
        msg(1, "quelqu'un suit le marché ?"),
        msg(2, "ADI ?", tickers=["ADI"]),
        msg(3, "oui ça bouge"),
    ])
    assert len(fils) == 1 and len(fils[0]) == 2
    assert fils[0].messages[0].texte == "ADI ?"


def test_corpus_vide_ou_sans_ticker():
    assert decouper_en_fils([]) == []
    assert decouper_en_fils([msg(0, "salam"), msg(1, "labas")]) == []


# ── Propriétés d'un fil ───────────────────────────────────────────────────

def test_la_seance_est_celle_de_l_ouverture_pas_de_la_fin():
    """Un fil ouvert à 23h50 déborde sur le lendemain. Il appartient à la
    séance où l'information a circulé, donc celle de son ouverture."""
    tard = datetime(2026, 3, 12, 23, 50)
    fils = decouper_en_fils([
        Message(tard, "A", "ADI ?", frozenset(["ADI"])),
        Message(tard + timedelta(minutes=15), "B", "oui", frozenset()),
    ], trou_minutes=30)
    assert fils[0].seance == "2026-03-12"
    assert fils[0].fin.day == 13


def test_auteurs_du_fil():
    fils = decouper_en_fils([
        msg(0, "ADI ?", auteur="A", tickers=["ADI"]),
        msg(1, "oui", auteur="B"),
        msg(2, "aussi", auteur="A"),
    ])
    assert fils[0].auteurs == {"A", "B"}


# ── Échantillonnage : le plafond par auteur ───────────────────────────────

def test_le_plafond_empeche_un_auteur_de_dominer_l_echantillon():
    """Sans plafond, l'échantillon reflète cinq personnes : mesuré le 03/09,
    les 5 auteurs les plus actifs écrivent 35,6 % du corpus."""
    fils = []
    for i in range(100):
        auteur = "bavard" if i < 80 else f"autre{i}"
        fils.extend(decouper_en_fils([msg(i * 60, "ADI ?", auteur=auteur, tickers=["ADI"])]))

    ech = echantillonner(fils, n=20, plafond_auteur=0.20)
    assert len(ech) == 20
    part = sum(1 for f in ech if f.messages[0].auteur == "bavard") / len(ech)
    assert part <= 0.25, f"un seul auteur occupe {part:.0%} de l'échantillon"


def test_l_echantillon_est_complet_meme_si_le_plafond_est_serre():
    """Mieux vaut un échantillon plein légèrement déséquilibré qu'un
    échantillon trop petit pour conclure."""
    fils = [decouper_en_fils([msg(i * 60, "ADI ?", auteur="seul", tickers=["ADI"])])[0]
            for i in range(30)]
    assert len(echantillonner(fils, n=10, plafond_auteur=0.1)) == 10


def test_l_echantillon_est_reproductible():
    """Même graine, même tirage : l'annotation doit pouvoir être rejouée."""
    fils = [decouper_en_fils([msg(i * 60, "ADI ?", auteur=f"a{i}", tickers=["ADI"])])[0]
            for i in range(50)]
    a = [f.debut for f in echantillonner(fils, 10)]
    b = [f.debut for f in echantillonner(fils, 10)]
    assert a == b


def test_echantillon_vide_ou_degenere():
    assert echantillonner([], 10) == []
    fils = [decouper_en_fils([msg(0, "ADI ?", tickers=["ADI"])])[0]]
    assert echantillonner(fils, 0) == []


# ── Lecture du corpus ─────────────────────────────────────────────────────

def test_les_lignes_de_continuation_restent_avec_leur_message(tmp_path):
    """Un message multi-lignes n'a d'horodatage que sur la première. Jeter les
    suivantes couperait la moitié des messages longs."""
    from whatsapp_analysis.fils import lire_corpus

    f = tmp_path / "chat.txt"
    f.write_text(
        "[12/03/2026 10:00:00] A: résultats ADI\n"
        "chiffre d'affaires en hausse\n"
        "et marge stable\n"
        "[12/03/2026 10:05:00] B: intéressant\n",
        encoding="utf-8",
    )
    msgs = list(lire_corpus(f))
    assert len(msgs) == 2
    assert "marge stable" in msgs[0].texte
    assert "ADI" in msgs[0].tickers


def test_une_ligne_mal_formee_ne_fait_pas_planter(tmp_path):
    from whatsapp_analysis.fils import lire_corpus

    f = tmp_path / "chat.txt"
    f.write_text(
        "[99/99/9999 99:99:99] A: date impossible\n"
        "[12/03/2026 10:00:00] B: ADI monte\n",
        encoding="utf-8",
    )
    msgs = list(lire_corpus(f))
    assert len(msgs) == 1 and msgs[0].auteur == "B"


# ── Marques Unicode invisibles ────────────────────────────────────────────

def test_les_marques_invisibles_ne_masquent_pas_un_message(tmp_path):
    """WhatsApp insère des marques de direction invisibles (U+200E, U+200F…)
    en tête de certaines lignes — fréquent dans un corpus arabe/darija, où le
    sens d'écriture change.

    Ancrer le motif sur « ^[ » sans les retirer fait manquer ces lignes : elles
    sont recollées au message précédent, et LE NOM DE L'AUTEUR se retrouve dans
    le corps du texte, là où la pseudonymisation ne le cherche pas.

    Mesuré le 03/09/2026 : 116 940 messages avalés sur 1 036 309, soit plus de
    11 % du corpus — et un nom réel visible dans le premier échantillon relu.
    """
    from whatsapp_analysis.fils import lire_corpus

    f = tmp_path / "chat.txt"
    f.write_text(
        "[12/03/2026 10:00:00] Alice: ADI monte\n"
        "‎[12/03/2026 10:01:00] Bob Dupont: je confirme\n"
        "‏[12/03/2026 10:02:00] Carole: موافق\n",
        encoding="utf-8",
    )
    msgs = list(lire_corpus(f))

    assert len(msgs) == 3, "une ligne précédée d'une marque invisible a été avalée"
    assert [m.auteur for m in msgs] == ["Alice", "Bob Dupont", "Carole"]
    for m in msgs:
        assert "Bob Dupont" not in m.texte, "nom d'auteur recollé dans le corps"
        assert not re.search(r"\[\d{2}/\d{2}/\d{4}", m.texte), "en-tête recollé"


def test_aucun_en_tete_ne_survit_dans_le_corps_d_un_message(tmp_path):
    """Garde-fou général : quelle que soit la marque, un en-tête de message ne
    doit jamais se retrouver dans le texte d'un autre."""
    from whatsapp_analysis.fils import lire_corpus

    f = tmp_path / "chat.txt"
    f.write_text(
        "".join(
            f"{marque}[12/03/2026 10:0{i}:00] Auteur{i}: message {i}\n"
            for i, marque in enumerate("‎‏‪⁦﻿")
        ),
        encoding="utf-8",
    )
    msgs = list(lire_corpus(f))
    assert len(msgs) == 5
    assert all("Auteur" not in m.texte for m in msgs)

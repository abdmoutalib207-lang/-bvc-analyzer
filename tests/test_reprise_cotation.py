#!/usr/bin/env python3
"""Une reprise de cotation se constate, et elle change plus qu'un drapeau.

CE QUI S'EST PASSÉ LE 16/09/2026
────────────────────────────────
Minière Touissit a repris sa cotation après deux mois de suspension pour OPA.
Le bulletin de l'opérateur — « Indices du mercredi 16 septembre 2026 », sha256
55f7c079… — la cote à **2 438,00, +9,97 %, 1 titre échangé à 15:30:00**. Les
bulletins des 14 et 15/09 la donnaient encore entièrement à zéro.

Le terminal, lui, affichait toujours **4 350 DH** — la clôture du 16 juillet —
avec l'étiquette SUSPENDU. Le registre des suspensions est écrit à la main :
rien ne pouvait le lever sans qu'un humain l'écrive.

TROIS MÉCANISMES CROYAIENT ENCORE LE TITRE SUSPENDU, ET CHACUN A NUI
────────────────────────────────────────────────────────────────────
1. **Le cours était figé.** Le moteur ramenait le prix à la dernière cotation
   d'avant la suspension et écrasait celui que la source servait.

2. **Le contrôle de capitalisation que j'avais posé le matin même a refusé une
   valeur JUSTE.** Il comparait la capitalisation servie — 3 727 MDHS — à
   `prix × actions sourcées` et trouvait 7 313. Il a remplacé la première par
   la seconde. Or 3 727 000 000 ÷ 1 681 233 actions = **2 216,83 DH**, soit
   exactement la référence que le bulletin implique (2 438 ÷ 1,0997 = 2 216,97).
   La capitalisation servie était bonne ; c'était NOTRE cours qui était périmé.

   ⚠️ Un contrôle qui s'appuie sur une valeur périmée est pire que pas de
   contrôle : il remplace du juste par du faux, et il le fait avec autorité.

3. **Le moteur a publié ACHETER ★★ avec une confiance de 5 sur 5.** Une fois le
   cours corrigé à 2 438, les indicateurs restaient ceux d'avant : MA20 à
   4 624, MA50 à 4 769. Un cours très au-dessous de ses moyennes se lit
   « survendu », donc « acheter » — sur un titre qui venait de changer de
   régime de prix, avec UN titre échangé.

   Le garde-fou existant ne pouvait pas le voir : `neutraliser_si_isin_suspect`
   cherche un facteur 3 entre le prix et la MA20, et l'écart n'était que de
   1,65. Le facteur 3 attrape une identité croisée ; il n'attrape pas un
   changement de référence.

⚠️ CE N'EST PAS UN SPLIT. L'opérateur a remis la référence à 2 217 lors de la
reprise. La série historique ne doit PAS être ajustée : les cours d'avant sont
ce qu'ils étaient.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from conftest import chemin_data_json  # noqa: E402


@pytest.fixture(scope="module")
def moteur():
    spec = importlib.util.spec_from_file_location("ud_rep", RACINE / "update_data.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["ud_rep"] = m
    spec.loader.exec_module(m)
    return m


# ── Le registre ──────────────────────────────────────────────────────────────

def test_la_reprise_de_cmt_est_inscrite_et_sourcee():
    """Une reprise se constate sur une pièce, elle ne se décrète pas.

    ⚠️ La même exigence que pour une correction de série : la date seule ne
    vaut rien si l'on ne peut pas dire d'où elle vient.
    """
    from bvc_config import SUSPENSIONS
    cmt = SUSPENSIONS["CMT"][0]
    assert cmt["reprise"] == "2026-09-16", (
        f"reprise inscrite au {cmt.get('reprise')}, le bulletin dit le 16/09")
    assert cmt.get("reprise_source"), "la reprise n'est adossée à aucune pièce"
    assert "bulletin" in cmt["reprise_source"].lower()
    assert cmt.get("cours_de_reprise") == 2438.0


def test_le_resolveur_suit_la_reprise():
    from bvc_config import est_suspendu
    assert est_suspendu("CMT", "2026-09-15") is not None, "suspendue la veille"
    assert est_suspendu("CMT", "2026-09-16") is None, "elle cote depuis le 16"
    assert est_suspendu("CMT", "2026-10-01") is None


# ── Les indicateurs d'avant ne décrivent plus le titre ────────────────────────

class _Serie:
    """Un substitut minimal du cache de chandelles : il ne porte que `d`."""
    def __init__(self, dates):
        self.d = dates

    def __getitem__(self, cle):
        assert cle == "d"
        return self.d


def test_les_indicateurs_sont_neutralises_tant_que_la_serie_est_courte(moteur):
    """Vingt séances : la plus longue des fenêtres courtes (MA20), qui couvre
    le RSI de 14."""
    avant = ["2026-07-%02d" % j for j in range(1, 17)]
    for n_apres, attendu in ((1, 1), (5, 5), (19, 19), (20, None), (40, None)):
        serie = _Serie(avant + ["2026-09-%02d" % (16 + i) for i in range(n_apres)])
        assert moteur.reprise_trop_recente("CMT", serie) == attendu, (
            f"{n_apres} séances depuis la reprise → {attendu} attendu")


def test_un_titre_sans_reprise_n_est_jamais_neutralise(moteur):
    """Le contrôle ne doit toucher que les titres qui ont repris.

    Sans cette borne, il neutraliserait toute la cote — c'est le genre de
    garde-fou qui, mal borné, casse plus qu'il ne protège.
    """
    serie = _Serie(["2026-09-%02d" % j for j in range(1, 17)])
    assert moteur.reprise_trop_recente("ADH", serie) is None
    assert moteur.reprise_trop_recente("INCONNU", serie) is None


def test_sans_serie_un_titre_qui_a_repris_reste_neutralise(moteur):
    """⚠️ ÉCRIT APRÈS QUE LE TEST A CORRIGÉ MON ATTENTE, pas l'inverse.

    J'avais d'abord exigé que l'absence de série rende « rien à signaler ».
    C'est faux : un titre qui a repris et dont on n'a AUCUNE chandelle n'a, à
    plus forte raison, aucune séance depuis la reprise. Ne rien neutraliser
    reviendrait à publier des indicateurs venus d'ailleurs.

    « Je ne sais pas » se traite comme « pas assez », jamais comme « tout va
    bien ».
    """
    assert moteur.reprise_trop_recente("CMT", None) == 0


# ── Ce que le fichier publié doit montrer ─────────────────────────────────────

@pytest.fixture(scope="module")
def cmt_publie():
    d = json.loads(chemin_data_json().read_text(encoding="utf-8"))
    return next((t for t in d["tickers"] if t["symbol"] == "CMT"), None)


def test_cmt_n_est_plus_donnee_pour_suspendue(cmt_publie):
    if cmt_publie is None:
        pytest.skip("CMT absente du fichier")
    m = cmt_publie.get("_meta") or {}
    if m.get("prix_asof", "") < "2026-09-16":
        pytest.skip("fichier antérieur à la reprise")
    assert m.get("suspendu") is False, "le terminal la dit encore suspendue"
    assert cmt_publie["price"] > 0


def test_aucun_signal_n_est_emis_sur_des_indicateurs_neutralises():
    """⚠️ LA RÈGLE QUI COMPTE, et elle vaut pour tous les titres.

    Un titre dont le RSI et les moyennes sont absents ne peut pas porter de
    recommandation : il n'y a rien pour la fonder. C'est ce qui manquait le
    16/09, quand CMT est sortie avec ACHETER ★★ et cinq sur cinq de confiance.
    """
    d = json.loads(chemin_data_json().read_text(encoding="utf-8"))
    RECOMMANDATIONS = {"ACHAT FORT", "ACHAT", "ACHETER", "ÉVITER", "ÉVITER FORT"}
    fautifs = []
    for t in d["tickers"]:
        sig = (t.get("sig") or "").replace("★", "").strip()
        if sig not in RECOMMANDATIONS:
            continue
        if t.get("rsi") is None and t.get("ma20") is None and t.get("ma50") is None:
            fautifs.append(f"{t['symbol']} : « {sig} » sans aucun indicateur")
    assert not fautifs, "\n  ".join(["recommandation sans fondement :"] + fautifs)


def test_la_capitalisation_n_est_plus_arbitree_sur_un_prix_perime(moteur):
    """⚠️ LA CORRECTION DE MA PROPRE FAUTE DU 16/09.

    Le contrôle posé le matin a refusé la capitalisation JUSTE de CMT parce
    qu'il la comparait à un cours figé depuis deux mois. Un prix qui ne vient
    pas d'une cotation de la séance n'arbitre rien.
    """
    moteur.FAITS_DATA = {"CMT": {"exercice": 2025, "faits": {
        "nombre_actions_au_rapport": {"valeur": 1_681_233, "page": 57}}}}

    # Le cas exact du 16/09 : cours figé à 4 350, capitalisation servie 3 727.
    for src in ("derniere_cotation_avant_suspension", "candles", "static",
                "historical", "data_json_precedent", "idbourse_perime"):
        cap, prov = moteur._capitalisation("CMT", 4350.0, 3727, src)
        assert (cap, prov) == (3727, "servie"), (
            f"un prix de provenance « {src} » a servi d'arbitre : {cap} ({prov})")

    # Avec un cours réellement coté, l'arbitrage reprend ses droits.
    cap, prov = moteur._capitalisation("CMT", 4350.0, 3727, "cdg")
    assert prov == "calculee_apres_refus"

# ── La variation du jour de la reprise ───────────────────────────────────────

def test_la_reference_de_reprise_vient_du_registre_et_pas_d_ailleurs(moteur):
    """⚠️ LE 0,00 % QUE R9 INTERDIT.

    Le 16/09, le terminal a publié CMT « inchangé » un jour où elle avait fait
    +9,97 %. Personne n'avait écrit ce zéro : il est le résidu du garde-fou
    R10. Le moteur comparait 2 438 aux 4 350 diffusés pendant la suspension,
    trouvait −43,95 %, jugeait — à raison — qu'aucun titre ne bouge de 44 % en
    une séance, et rabotait à zéro.

    Les deux raisonnements sont justes séparément et faux ensemble : l'écart
    n'était pas une erreur de source, c'était un CHANGEMENT DE RÉFÉRENCE décidé
    par l'opérateur. R10 parle de variations de cours ; elle ne dit rien d'une
    référence remise à neuf.
    """
    # ⚠️ 2 217 EXACTEMENT, ET C'EST UN CHIFFRE LU, PAS DÉDUIT. Cette valeur
    # était 2216.97, obtenue en divisant le cours de reprise par sa variation.
    # La décision AMMC DO/EM/010/2026 du 15/09 fixe le prix de l'offre à
    # 2 217 MAD. La variation publiée est la même dans les deux cas ; le statut
    # du nombre, non — d'où l'exigence de la pièce ci-dessous.
    assert moteur.reference_de_reprise("CMT", "2026-09-16") == 2217.0
    # Ni la veille, ni le lendemain : la référence ne vaut que ce jour-là.
    assert moteur.reference_de_reprise("CMT", "2026-09-15") is None
    assert moteur.reference_de_reprise("CMT", "2026-09-17") is None
    # Et jamais pour un titre qui n'a pas repris.
    assert moteur.reference_de_reprise("ADH", "2026-09-16") is None
    assert moteur.reference_de_reprise("INCONNU", "2026-09-16") is None


def test_la_reference_est_adossee_a_une_piece_du_regulateur(moteur):
    """Une référence sans pièce est une supposition, quel que soit son auteur.

    ⚠️ Même exigence que pour la date de reprise et pour toute correction de
    série : on doit pouvoir dire D'OÙ vient le nombre, et le lecteur doit
    pouvoir aller le vérifier. Un chiffre juste dont on ne sait pas l'origine
    redevient faux le jour où quelqu'un le conteste.
    """
    from bvc_config import SUSPENSIONS
    p = SUSPENSIONS["CMT"][0]
    src = (p.get("reference_source") or "").lower()
    assert "ammc" in src, "la référence ne cite pas le régulateur"
    assert "do/em/010/2026" in src, "la décision n'est pas identifiée"
    piece = RACINE / (p.get("reference_piece") or "")
    assert p.get("reference_piece"), "aucune pièce jointe à la référence"
    assert p.get("reference_piece_sha256"), (
        "la pièce n'est pas empreintée — un PDF remplacé passerait inaperçu")
    if piece.exists():
        import hashlib
        vu = hashlib.sha256(piece.read_bytes()).hexdigest()
        assert vu == p["reference_piece_sha256"], (
            f"la pièce archivée n'est plus celle qui a été citée : {vu[:16]}…")


def test_la_reference_redonne_le_chiffre_du_bulletin(moteur):
    """La vérification qui ne passe pas par notre propre formule.

    ⚠️ On ne réutilise pas la fonction testée pour écrire l'attendu. Le
    bulletin publie deux nombres indépendants — 2 438,00 et +9,97 % — et leur
    quotient doit redonner la référence inscrite au registre. Si le registre
    était faux, ce calcul ne tomberait pas juste.
    """
    from bvc_config import SUSPENSIONS
    p = SUSPENSIONS["CMT"][0]
    implicite = p["cours_de_reprise"] / (1 + 9.97 / 100)
    assert abs(implicite - p["reference_impliquee"]) < 0.5, (
        f"le bulletin implique {implicite:.2f}, le registre dit "
        f"{p['reference_impliquee']}")


def test_le_garde_fou_des_dix_pour_cent_reste_entier(moteur):
    """⚠️ LE REVERS, sans lequel on aurait ouvert une porte au lieu d'en fermer
    une. Hors du jour d'une reprise inscrite, R10 doit continuer de raboter.
    """
    s = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert "elif abs(chg) > 10:" in s, (
        "le plafond ±10 % n'est plus la branche par défaut — une variation "
        "aberrante de la source passerait telle quelle")
    assert "_ref_reprise = reference_de_reprise(ticker, prix_asof" in s, (
        "la référence de reprise n'est plus consultée avant le rabotage")


def test_la_variation_publiee_de_cmt_n_est_pas_un_zero_non_verifie(cmt_publie):
    """Ce que le lecteur doit voir le jour de la reprise."""
    if cmt_publie is None:
        pytest.skip("CMT absente du fichier")
    m = cmt_publie.get("_meta") or {}
    if m.get("prix_asof") != "2026-09-16":
        pytest.skip("le fichier ne porte pas la séance de la reprise")
    assert abs(cmt_publie.get("chg", 0) - 9.97) < 0.05, (
        f"variation publiée {cmt_publie.get('chg')} % — le bulletin dit +9,97 %")


def test_le_dernier_ecrivain_de_la_variation_connait_la_reprise(moteur):
    """⚠️ IL A FALLU DEUX TENTATIVES, ET LA PREMIÈRE AVAIT L'AIR DE MARCHER.

    J'ai d'abord posé la règle à côté du plafond ±10 %. Le journal affichait
    bien « +9,97 % »… et le fichier publiait toujours 0,00 %. `chg` est
    recalculé une dernière fois, plus bas, par `recalculer_variation()` — qui
    repartait des chandelles, retrouvait −43,95 % et rabotait.

    Une règle posée ailleurs que chez le dernier écrivain ne tient pas. Ce test
    interroge donc la fonction qui décide vraiment.
    """
    import pandas as pd
    candles = pd.DataFrame({"d": ["2026-07-15", "2026-07-16"],
                            "c": [4501.0, 4350.0]})

    # Le jour de la reprise : la base est la référence du registre.
    assert moteur.recalculer_variation("CMT", 2438.0, 0.0, candles,
                                       "2026-09-16",
                                       asof_prix="2026-09-16") == 9.97

    # Un autre jour : la clôture précédente reprend ses droits, et le plafond
    # R10 raisonne de nouveau sur un écart réel.
    assert moteur.recalculer_variation("CMT", 2438.0, 0.0, candles,
                                       "2026-09-17",
                                       asof_prix="2026-09-17") == 0.0

    # ⚠️ ATTENTE CORRIGÉE, PAS CODE CORRIGÉ. J'avais écrit `== 0.0` ici en
    # pensant « rien de spécial ». C'est faux : un titre ordinaire suit le
    # chemin ordinaire, donc 4 400 contre une clôture de 4 350 fait +1,15 %.
    # Attendre zéro aurait exigé du code qu'il cesse de faire son travail —
    # c'est la deuxième fois dans ce lot que le test se trompe avant le code.
    assert moteur.recalculer_variation("ADH", 4400.0, 0.0, candles,
                                       "2026-09-16",
                                       asof_prix="2026-09-16") == 1.15

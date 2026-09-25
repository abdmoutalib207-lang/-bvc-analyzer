#!/usr/bin/env python3
"""Une variation sans son volume ne dit pas grand-chose.

⚠️ CE QUI MANQUAIT, ET DEPUIS TOUJOURS
──────────────────────────────────────
Le classement affichait la variation de chaque titre sans jamais dire **sur
combien d'échanges** elle s'était faite. Un titre à +3 % sur quarante titres
échangés et un titre à +3 % sur quarante mille ne décrivent pas la même
chose : le premier est une transaction, le second est un marché.

Et l'en-tête affichait la variation de l'indice sans son volume global.
181 M DH et 400 M DH ne décrivent pas la même séance, à variation identique.

⚠️ DEUX UNITÉS, ET L'UNE N'EST PAS L'AUTRE
Un NOMBRE DE TITRES et un MONTANT EN DIRHAMS ne se comparent pas d'un titre à
l'autre : dix titres de Minière Touissit valent 39 230 DH, dix d'Addoha en
valent 336. Les deux sont publiés, jamais confondus.

⚠️ LE MONTANT RÉEL EXISTAIT ET N'ÉTAIT PAS LU
Le fournisseur sert `Volumes` — la contrepartie en dirhams de la séance. Le
projet ne lisait que `QteEchangee`, la quantité, et approchait le montant par
`volume × clôture`. Chaque transaction se faisant à SON prix, l'approximation
dérive dans les deux sens. Mesuré sur la séance du 25/09 :

    TGCC   58,64 M approchés   contre 58,48 M réels   (+0,161 M)
    MSA     8,79 M approchés   contre  8,85 M réels   (−0,059 M)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

ECRAN = (RACINE / "index.html").read_text(encoding="utf-8")


# ── ⚠️ La condition de rapprochement, et elle est le cœur du sujet ─────────

def test_le_montant_suit_la_source_du_prix_publie():
    """⚠️ Le montant ne vaut que pour LA ligne dont le prix a été retenu.

    La chaîne de repli (R3) peut publier une chandelle ou la table figée
    pendant que `live_prices` garde encore une ligne CDG : y accoler son
    montant afficherait les échanges d'un jour à côté du cours d'un autre.
    """
    from update_data import _echange_rapprochable
    ligne = {"echange_dh": 58_480_000.0, "seuil_bas": 640.0, "seuil_haut": 700.0}

    # prix publié par CDG, même séance → le montant est rapprochable
    assert _echange_rapprochable(ligne, "cdg", "2026-09-25", "2026-09-25") == (
        58_480_000.0, 640.0, 700.0)

    # prix publié depuis les chandelles → la ligne CDG ne le décrit pas
    assert _echange_rapprochable(ligne, "candles", "2026-09-25", "2026-09-25") == (
        None, None, None)

    # prix publié par la table figée → idem
    assert _echange_rapprochable(ligne, "static", "2026-09-25", "2026-09-25") == (
        None, None, None)


def test_le_montant_suit_la_SEANCE_du_prix_publie():
    """⚠️ Une ligne CDG plus ANCIENNE que le prix publié décrit une autre
    séance. C'est le cas exact du 28/08, où la source a reculé d'un jour."""
    from update_data import _echange_rapprochable
    ligne = {"echange_dh": 1_000_000.0}
    assert _echange_rapprochable(ligne, "cdg", "2026-09-25", "2026-09-24") == (
        None, None, None)
    assert _echange_rapprochable(ligne, "cdg", "", "2026-09-25") == (
        None, None, None)


def test_non_rapprochable_rend_None_et_jamais_zero():
    """⚠️ Un montant NUL est une séance SANS ÉCHANGE — une information réelle,
    et tout à fait différente de « on ne sait pas ». Les confondre ferait
    passer un titre non rapproché pour un titre mort."""
    from update_data import _echange_rapprochable
    m, b, h = _echange_rapprochable({}, "candles", "2026-09-25", "2026-09-25")
    assert m is None and b is None and h is None


def test_un_champ_ABSENT_sur_une_ligne_rapprochable_reste_None():
    """⚠️ LE TROU QU'UNE MUTATION A RÉVÉLÉ, et le test manquait.

    Le cas précédent couvre la ligne NON rapprochable. Celui-ci couvre la
    ligne rapprochable dont le champ est simplement ABSENT — une réponse du
    fournisseur amputée, ce qui arrive.

    Rendre 0 y ferait passer « la source ne l'a pas donné » pour « zéro
    dirham échangé ». Le titre s'afficherait comme mort alors qu'il a
    peut-être été le plus actif de la séance.

    ⚠️ Écrire `l.get("echange_dh") or 0` suffit à produire ce défaut, et la
    suite restait verte avant ce test.
    """
    from update_data import _echange_rapprochable
    # ligne CDG de la bonne séance, mais sans le champ
    m, b, h = _echange_rapprochable(
        {"vol": 1234}, "cdg", "2026-09-25", "2026-09-25")
    assert m is None, "un champ absent est devenu un montant nul"
    assert b is None and h is None

    # et un zéro RÉELLEMENT servi doit rester zéro : c'est une séance sans
    # échange, pas une absence.
    m0, _, _ = _echange_rapprochable(
        {"echange_dh": 0.0}, "cdg", "2026-09-25", "2026-09-25")
    assert m0 == 0.0, "un zéro servi par la source a été effacé"


def test_la_liste_des_sources_est_nommee_et_non_deduite():
    """⚠️ IDBourse sert la capitalisation mais PAS la contrepartie en dirhams,
    et les chandelles n'ont jamais eu ces champs. Élargir à « toute source
    vivante » ferait publier des `None` là où on croit avoir un montant."""
    from update_data import SOURCES_MONTANT
    assert set(SOURCES_MONTANT) == {"cdg", "bmce"}


# ── ⚠️ Le volume global de l'indice ────────────────────────────────────────

def test_le_flux_publie_le_volume_global():
    """⚠️ Il était collecté par `marche_history` depuis le 24/09 et le bloc
    `masi` n'en portait AUCUN champ."""
    f = RACINE / "data.json"
    if not f.exists():
        pytest.skip("data.json absent de ce clone")
    m = json.loads(f.read_text(encoding="utf-8")).get("masi") or {}
    assert m.get("volume_mad") is not None, (
        "l'indice est publié sans son volume — la variation ne dit pas sur "
        "combien d'échanges elle s'est faite")
    assert m["volume_mad"] > 0


def test_les_trois_grandeurs_du_volume_sont_distinctes():
    """⚠️ Montant, quantité et nombre d'opérations ne disent pas la même
    chose. 2 293 transactions pour 568 414 titres n'est pas une séance de
    cinquante blocs, et seul leur rapport le dit."""
    f = RACINE / "data.json"
    if not f.exists():
        pytest.skip("data.json absent de ce clone")
    m = json.loads(f.read_text(encoding="utf-8")).get("masi") or {}
    for champ in ("volume_mad", "titres_echanges", "transactions"):
        assert champ in m, f"`{champ}` manque au bloc masi"
    # ⚠️ Contrôle de cohérence : la taille moyenne d'une transaction doit être
    # un nombre de titres plausible. Un rapport absurde signalerait que deux
    # champs ont été échangés.
    if m.get("transactions"):
        taille = m["titres_echanges"] / m["transactions"]
        assert 1 <= taille <= 100_000, (
            f"taille moyenne d'une transaction aberrante : {taille:.0f} titres")


# ── ⚠️ L'affichage ─────────────────────────────────────────────────────────

def test_le_classement_porte_une_colonne_volume():
    """Une colonne absente ne se remarque pas — c'est bien le problème."""
    i = ECRAN.find("const HEADS=")
    entetes = ECRAN[i:ECRAN.find("]", i)]
    assert '"VOLUME"' in entetes, "le classement n'a pas de colonne volume"


def test_la_cellule_affiche_les_deux_unites():
    """⚠️ Le nombre de titres en premier, le montant dessous QUAND la source
    le donne. Publier l'un sans l'autre laisserait comparer des quantités
    entre titres de prix très différents."""
    i = ECRAN.find('{(()=>{const v=r.vol,dh=r.echange_dh;')
    assert i > 0, "la cellule de volume ne lit pas les deux champs"
    bloc = ECRAN[i:i + 1200]
    assert "M DH" in bloc and "k DH" in bloc, (
        "le montant n'est pas mis en forme selon son ordre de grandeur")


def test_les_champs_traversent_la_fusion():
    """⚠️ TROISIÈME FOIS AUJOURD'HUI. L'énumération de la fusion avait déjà
    perdu `rang_secteur`, et `meta()` cinq champs de `_meta`. Un champ publié
    par le moteur et absent de cette liste n'atteint jamais l'écran."""
    i = ECRAN.find("d.tickers.forEach(t=>{m[t.symbol]={")
    fusion = ECRAN[i:ECRAN.find("};});", i)]
    for champ in ("echange_dh", "seuil_bas", "seuil_haut"):
        assert f"{champ}:t.{champ}" in fusion, (
            f"`{champ}` n'est pas recopié par la fusion — il n'atteindra "
            f"jamais l'écran")


def test_l_en_tete_affiche_le_volume_global():
    assert "masi.volume_mad" in ECRAN, (
        "le volume global de la séance n'est pas affiché")
    i = ECRAN.find("masi.volume_mad!=null&&")
    assert i > 0
    bloc = ECRAN[i:i + 1400]
    assert "masi.transactions" in bloc, (
        "le nombre de transactions n'accompagne pas le montant — sans lui, "
        "on ne distingue pas un marché d'une poignée de blocs")

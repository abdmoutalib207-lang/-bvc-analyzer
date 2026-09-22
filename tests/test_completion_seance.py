#!/usr/bin/env python3
"""Une séance figée en vol se complète ; elle ne s'écrase pas.

⚠️ CE QUI EST ARRIVÉ LE 21/09/2026
──────────────────────────────────
Le moteur écrit la bougie du jour dès le premier run et la RAFRAÎCHIT ensuite.
Le 21/09, le dernier run réussi date de **10h44** — en pleine séance — et tous
ceux d'après la clôture ont échoué aux contrôles bloquants. Les bougies sont
restées figées en vol.

Mesuré sur les 60 titres comparables au bulletin CDG de clôture :

    l'ouverture n'est JAMAIS en écart  ·  le volume l'est TOUJOURS
    les extrêmes seulement là où la séance a débordé après la capture

Exemple : BCP publiait `c=247,0 v=1 337` quand la clôture réelle valait
`c=248,0 qte=469 537`. Le volume capturé représentait 0,3 % du volume réel.

⚠️ LA LIGNE QUE CE FICHIER DÉFEND
─────────────────────────────────
Ce n'est pas une source qui en contredit une autre : c'est la même séance vue
à deux instants. On a donc le droit de la compléter — **à condition que la
bougie officielle ENVELOPPE la capture**. Si le haut recule, si le bas remonte,
si le volume décroît ou si l'ouverture change, les deux bougies se
contredisent réellement et l'écrasement reste refusé.

La clôture, elle, bouge librement : c'est la seule valeur qu'une capture de
10h44 ne pouvait pas connaître, et c'est précisément ce qu'on vient chercher.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline.import_cdg_session import completion  # noqa: E402


def _b(d="2026-09-21", o=100.0, h=105.0, l=95.0, c=100.0, v=1000):
    return {"d": d, "o": o, "h": h, "l": l, "c": c, "v": v}


# ── Ce que la complétion autorise ───────────────────────────────────────────

def test_la_cloture_peut_monter_ou_descendre():
    """C'est la valeur qu'on vient chercher : elle n'est bornée d'aucun côté."""
    capturee = _b(c=100.0)
    assert completion(capturee, _b(c=104.0, v=5000)) is True
    assert completion(capturee, _b(c=96.0, v=5000)) is True


def test_les_extremes_peuvent_s_etendre():
    capturee = _b(h=105.0, l=95.0)
    assert completion(capturee, _b(h=110.0, l=90.0, v=5000)) is True


def test_le_volume_peut_croitre_fortement():
    """BCP : 1 337 titres capturés, 469 537 à la clôture."""
    assert completion(_b(v=1337), _b(v=469537)) is True


def test_une_bougie_identique_est_une_completion_triviale():
    assert completion(_b(), _b()) is True


# ── Ce qu'elle refuse — et c'est tout l'intérêt ─────────────────────────────

def test_un_haut_qui_recule_est_refuse():
    """Une séance ne se rétracte pas : deux sources se contredisent."""
    assert completion(_b(h=105.0), _b(h=104.0, v=5000)) is False


def test_un_bas_qui_remonte_est_refuse():
    assert completion(_b(l=95.0), _b(l=96.0, v=5000)) is False


def test_un_volume_qui_decroit_est_refuse():
    """⚠️ Le volume est le témoin le plus sûr : il ne fait que s'accumuler."""
    assert completion(_b(v=5000), _b(v=4999)) is False


def test_une_ouverture_differente_est_refusee():
    """L'ouverture est fixée au premier échange. Si elle change, ce n'est pas
    la même séance — ou l'une des deux sources se trompe de titre."""
    assert completion(_b(o=100.0), _b(o=100.5, v=5000)) is False


def test_une_date_differente_est_refusee():
    assert completion(_b(d="2026-09-21"), _b(d="2026-09-18", v=5000)) is False


@pytest.mark.parametrize("vide", [None, {}])
def test_une_bougie_absente_n_est_jamais_une_completion(vide):
    assert completion(vide, _b()) is False
    assert completion(_b(), vide) is False


def test_une_bougie_malformee_est_refusee_sans_lever():
    """Un champ manquant ou illisible ne doit pas faire tomber l'import :
    il doit simplement interdire la complétion."""
    assert completion({"d": "2026-09-21", "o": 100.0}, _b()) is False
    assert completion(_b(), {"d": "2026-09-21", "o": "abc", "h": 1,
                             "l": 1, "c": 1, "v": 1}) is False


# ── La propriété, indépendante de toute valeur écrite en dur ────────────────

@pytest.mark.parametrize("champ,sens", [("h", -1), ("l", +1), ("v", -1)])
def test_tout_recul_d_une_borne_interdit_la_completion(champ, sens):
    """Propriété : quelle que soit la bougie, faire reculer une borne dans le
    sens impossible suffit à refuser. C'est ce qui empêche la complétion de
    devenir un écrasement déguisé."""
    capturee = _b(h=105.0, l=95.0, v=1000)
    officielle = _b(h=110.0, l=90.0, v=5000)
    officielle[champ] = capturee[champ] + sens * (1 if champ == "v" else 0.01)
    assert completion(capturee, officielle) is False


# ── La condition que j'avais manquée, et qu'un test existant a établie ──────

def test_une_cloture_qui_bouge_a_volume_constant_est_refusee():
    """⚠️ CETTE CONDITION MANQUAIT À MA PREMIÈRE VERSION.

    Une clôture ne se déplace que lorsqu'un échange a lieu, et un échange fait
    croître le volume. Une clôture différente avec un volume identique ne
    décrit donc pas la même séance vue plus tard : les deux relevés se
    contredisent.

    Cas exact qui l'a établi (`test_import_cdg_18_septembre.py`) : ADI, bougie
    sur disque `c=378 v=10`, bulletin `c=377 v=10`. Ma règle l'acceptait comme
    une complétion — à tort.
    """
    capturee = {"d": "2026-09-18", "o": 400, "h": 400, "l": 376, "c": 378, "v": 10}
    officielle = {"d": "2026-09-18", "o": 400, "h": 400, "l": 376, "c": 377, "v": 10}
    assert completion(capturee, officielle) is False


def test_la_meme_cloture_a_volume_constant_reste_acceptee():
    """Contre-épreuve : sans changement de clôture, un volume identique ne
    prouve aucune contradiction — la bougie est simplement inchangée."""
    b = {"d": "2026-09-18", "o": 400, "h": 400, "l": 376, "c": 377, "v": 10}
    assert completion(b, dict(b)) is True


def test_une_cloture_qui_bouge_avec_le_volume_reste_une_completion():
    capturee = {"d": "2026-09-21", "o": 248.9, "h": 248.9, "l": 240.0,
                "c": 247.0, "v": 1337}
    officielle = {"d": "2026-09-21", "o": 248.9, "h": 248.9, "l": 240.0,
                  "c": 248.0, "v": 469537}
    assert completion(capturee, officielle) is True

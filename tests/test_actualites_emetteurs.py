#!/usr/bin/env python3
"""L'onglet Actualités était presque à l'arrêt : 60 titres sur 80 n'affichaient rien.

⚠️ CE QUI ÉTAIT MESURÉ LE 22/09
───────────────────────────────
`TickerNews` renvoie `null` quand aucun article ne porte le ticker. Or le flux
ne rattachait que 41 articles sur 300, couvrant **20 titres sur 80**. La fiche
des soixante autres ne montrait rien du tout.

Et ce n'était PAS un défaut de rattachement. Les articles « bvc » non rattachés
étaient la météo, les élections, Tanjazz, le Bitcoin, les BRICS — ils ne
parlent d'aucune société cotée. Le canal AMMC, lui, marchait parfaitement :
11 rattachés sur 14, et les 3 restants — OCP, Crédit Agricole du Maroc — ne
sont pas cotés à la BVC, donc correctement non rattachés.

Le problème était le VOLUME du seul canal qui publie de l'information
d'émetteur :

    on ne lisait qu'UNE page d'un index paginé par dix
    et la fenêtre de sept jours jetait ce qu'on aurait pu en tirer

    7 jours, 1 page     16 dépôts   12 rattachés   12 titres
    30 jours, 5 pages   50 dépôts   37 rattachés   28 titres

⚠️ UN DÉPÔT RÉGLEMENTAIRE NE VIEILLIT PAS COMME UNE DÉPÊCHE. Sept jours est
juste pour un commentaire de marché ; c'est faux pour des résultats
semestriels, qui restent le dernier mot connu sur l'émetteur jusqu'au trimestre
suivant. Les garder n'est pas servir du périmé, c'est être complet.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import fetch_news as fn  # noqa: E402


class _Reponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def _index(urls):
    """Un index AMMC minimal, au format EXACT que `parse_ammc` sait lire.

    ⚠️ Écrit d'après le parseur, pas d'après une idée du format : ma première
    version employait un `<span class="date">` et un titre nu, et n'en tirait
    rien. Le parseur exige `views-field-title`, un `<time datetime=...>` et un
    lien HTTPS vers un PDF sur ammc.ma.
    """
    lignes = "".join(
        f'<li class="actualites-row">'
        f'<div class="views-field-title"><span>{titre}</span></div>'
        f'<time datetime="{date}T09:00:00+00:00"></time>'
        f'<a href="https://www.ammc.ma{u}.pdf">lire</a>'
        f'</li>'
        for u, titre, date in urls)
    return f"<ul>{lignes}</ul>"


# ── La pagination ──────────────────────────────────────────────────────────

def test_les_pages_suivantes_sont_lues():
    """⚠️ LE DÉFAUT CENTRAL : on ne lisait qu'une page d'un index paginé."""
    pages = {
        fn.AMMC_URL: _index([("/a1", "Alpha - Résultats", "2026-09-18"),
                             ("/a2", "Beta - Résultats", "2026-09-18")]),
        f"{fn.AMMC_URL}?page=1": _index([("/b1", "Gamma - Résultats", "2026-09-12")]),
        f"{fn.AMMC_URL}?page=2": _index([("/c1", "Delta - Résultats", "2026-09-05")]),
    }
    vus = []

    def get(url):
        vus.append(url)
        return _Reponse(pages.get(url, _index([])))

    arts = fn._collecter_ammc("2026-09-22T12:00:00+00:00", pages=5, get=get)
    assert len(vus) >= 3, "les pages suivantes n'ont pas été demandées"
    assert {a["url"].rsplit("/", 1)[-1].removesuffix(".pdf") for a in arts} == {"a1", "a2", "b1", "c1"}


def test_on_s_arrete_des_qu_une_page_n_apporte_rien():
    """Une pagination qui se répète ne doit pas nous faire tourner en rond."""
    memes = _index([("/x", "Alpha - Résultats", "2026-09-18")])
    appels = []

    def get(url):
        appels.append(url)
        return _Reponse(memes)

    arts = fn._collecter_ammc("2026-09-22T12:00:00+00:00", pages=5, get=get)
    assert len(arts) == 1, "un même dépôt a été compté plusieurs fois"
    assert len(appels) == 2, "l'arrêt n'a pas eu lieu à la première répétition"


def test_une_page_en_echec_n_annule_pas_les_precedentes():
    """Mieux vaut quatre pages que rien."""
    def get(url):
        if url == fn.AMMC_URL:
            return _Reponse(_index([("/ok", "Alpha - Résultats", "2026-09-18")]))
        raise RuntimeError("réseau indisponible")

    arts = fn._collecter_ammc("2026-09-22T12:00:00+00:00", pages=5, get=get)
    assert len(arts) == 1


def test_la_deduplication_porte_sur_l_url_pas_sur_le_rang():
    """Deux pages qui se recouvrent partiellement ne créent pas de doublon."""
    p0 = _index([("/a", "Alpha - Résultats", "2026-09-18"),
                 ("/b", "Beta - Résultats", "2026-09-17")])
    p1 = _index([("/b", "Beta - Résultats", "2026-09-17"),
                 ("/c", "Gamma - Résultats", "2026-09-16")])
    suite = iter([p0, p1, _index([])])
    arts = fn._collecter_ammc("2026-09-22T12:00:00+00:00", pages=3,
                              get=lambda u: _Reponse(next(suite)))
    urls = [a["url"].rsplit("/", 1)[-1].removesuffix(".pdf") for a in arts]
    assert sorted(urls) == ["a", "b", "c"], urls


# ── La rétention différenciée ──────────────────────────────────────────────

def test_un_depot_reglementaire_vit_plus_longtemps_qu_une_depeche():
    """⚠️ LA SECONDE MOITIÉ DU CORRECTIF. Paginer sans allonger la fenêtre ne
    servait à rien : les dépôts des pages 2 à 5 datent de plus de sept jours et
    étaient jetés aussitôt récupérés."""
    assert fn.DOCUMENTS_DAYS > fn.ARCHIVE_DAYS
    assert fn.DOCUMENTS_DAYS == 30, (
        "30 jours capturent tout ce que l'index publie — son historique "
        "s'arrête trois semaines en arrière. Au-delà, on prétendrait une "
        "profondeur que la source n'offre pas.")


def test_les_places_reservees_suffisent_aux_depots_recuperes():
    """Trente places pour cinquante dépôts en aurait évincé vingt — donc perdu
    des titres, exactement ce qu'on vient chercher."""
    assert fn.DOCUMENTS_RESERVES >= 50
    assert fn.DOCUMENTS_RESERVES <= fn.MAX_ARTICLES


def test_les_deux_bornes_sont_posees_aux_deux_endroits():
    """⚠️ L'archive et la coupe finale doivent employer LA MÊME règle. Si la
    relecture rejetait ce que l'écriture accepte, les dépôts disparaîtraient au
    premier run suivant leur septième jour et la fenêtre de trente jours
    n'existerait que sur le papier."""
    source = Path(fn.__file__).read_text(encoding="utf-8")
    assert source.count("DOCUMENTS_DAYS") >= 3, (
        "la borne des documents doit servir à la déclaration, à l'archive "
        "et à la coupe finale")


# ── L'épreuve sur le flux publié ───────────────────────────────────────────

def test_les_depots_du_regulateur_sont_rattaches_a_leur_emetteur():
    """Le canal AMMC est le seul nativement lié à une société. S'il cessait de
    rattacher, l'onglet retomberait à l'arrêt sans que rien d'autre bouge.

    ⚠️ Le seuil n'est pas 100 % : OCP et Crédit Agricole du Maroc déposent à
    l'AMMC sans être cotés à la BVC. Ne pas les rattacher est CORRECT.
    """
    import json
    chemin = RACINE / "news.json"
    if not chemin.exists():
        pytest.skip("news.json absent de ce clone")
    arts = json.loads(chemin.read_text(encoding="utf-8")).get("articles") or []
    depots = [a for a in arts if a.get("source_type") == "regulator_index"]
    if not depots:
        pytest.skip("aucun dépôt réglementaire dans cette fenêtre")
    rattaches = [a for a in depots if a.get("tickers")]
    assert len(rattaches) / len(depots) >= 0.6, (
        f"seulement {len(rattaches)}/{len(depots)} dépôts rattachés — le canal "
        f"qui porte l'actualité d'émetteur ne relie plus rien")

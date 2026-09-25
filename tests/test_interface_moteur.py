#!/usr/bin/env python3
"""Ce que le moteur calcule doit se voir — sinon il ne sert à personne.

⚠️ LE DÉFAUT QUE CES TESTS EMPÊCHENT DE REVENIR
───────────────────────────────────────────────
Au 25/09/2026, quatre blocs étaient calculés à chaque run et **invisibles à
l'écran** : le rang sectoriel, le montant échangé, la cohérence du flux et la
largeur de marché. Le moteur les publiait dans `data.json`, le terminal ne les
lisait pas.

C'est exactement le reproche qu'une lecture extérieure faisait au score
composite : les notes par pilier existaient dans le flux depuis des mois sans
jamais être montrées. Le même défaut s'est reproduit quatre fois en deux jours,
à mesure que le moteur gagnait des mesures.

⚠️ CE N'EST PAS UNE QUESTION D'ESTHÉTIQUE
Deux de ces blocs **justifient une décision du moteur** :

  · le montant échangé explique pourquoi la confiance est plafonnée à 2 sur
    27 titres — un plafond qu'on ne peut pas vérifier ne se discute pas ;
  · le rang sectoriel répond à « un P/B de 2,16 ne veut rien dire seul », et
    sans lui le chiffre nu laisse le lecteur faire une comparaison que
    personne ne fait de tête sur quatre-vingts titres.

Un moteur qui décide sans montrer sur quoi il décide demande qu'on lui fasse
confiance. Ce projet fait l'inverse.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

ECRAN = (RACINE / "index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def flux():
    f = RACINE / "data.json"
    if not f.exists():
        pytest.skip("data.json absent de ce clone")
    return json.loads(f.read_text(encoding="utf-8"))


# ── ⚠️ Ce que le moteur calcule, l'écran le lit ────────────────────────────

@pytest.mark.parametrize("champ,pourquoi", [
    ("echange_median_dh", "c'est ce qui plafonne la confiance de 27 titres"),
    ("rang_secteur", "un ratio nu ne se compare pas d'un secteur à l'autre"),
    ("reprise_recente", "sinon un titre repris affiche « Données insuffisantes »"),
    ("fond_age_jours", "la moitié du poids de la note vient de chiffres de juin"),
])
def test_le_terminal_lit_ce_que_le_moteur_publie(champ, pourquoi):
    assert champ in ECRAN, f"`{champ}` est calculé mais invisible — {pourquoi}"


def test_la_largeur_de_marche_est_affichee():
    """⚠️ Le 24/09, le MASI perdait 0,95 % et DEUX TITRES SUR TROIS
    reculaient — 16 hausses contre 42 baisses. La variation seule ne le dit
    pas : un indice peut monter porté par trois grosses capitalisations."""
    assert "masi.hausses" in ECRAN and "masi.baisses" in ECRAN, (
        "la largeur de marché est collectée mais n'apparaît pas dans l'en-tête")


# ── Le flux porte bien ce que l'écran attend ───────────────────────────────

def test_le_flux_publie_la_largeur(flux):
    m = flux.get("masi") or {}
    assert m.get("hausses") is not None, "l'en-tête afficherait du vide"
    assert m.get("baisses") is not None
    assert (m.get("largeur") or {}).get("ratio") is not None


def test_le_flux_publie_le_montant_echange(flux):
    t = flux.get("tickers") or []
    avec = [x for x in t if (x.get("_meta") or {}).get("echange_median_dh") is not None]
    assert len(avec) >= len(t) * 0.8, (
        f"{len(avec)}/{len(t)} titres seulement portent leur montant échangé")


def test_le_flux_publie_un_rang_sectoriel_utile(flux):
    """⚠️ Pas pour tous : les secteurs de moins de quatre comparables n'en ont
    pas, et c'est voulu — un « rang 1 sur 1 » n'informe de rien."""
    t = flux.get("tickers") or []
    avec = [x for x in t if x.get("rang_secteur")]
    assert len(avec) >= 30, (
        f"seulement {len(avec)} titres situés dans leur secteur — la table "
        f"COMPANY_SECTORS est-elle intacte ?")


# ── ⚠️ Ce que l'affichage ne doit pas faire ────────────────────────────────

def test_le_rang_n_est_pas_affiche_sans_pairs():
    """Le composant doit rendre `null` quand le titre n'a pas de rang, et non
    un « — » qui ressemblerait à une donnée manquante alors que c'est une
    mesure volontairement absente."""
    i = ECRAN.find("r.rang_secteur")
    assert i > 0
    bloc = ECRAN[i:i + 300]
    assert "if(!e) return null" in bloc, (
        "un titre sans comparables afficherait un rang vide")


def test_le_plafond_de_liquidite_est_annonce_a_l_ecran():
    """⚠️ Le chiffre seul ne suffit pas : il faut dire ce qu'il entraîne. Un
    lecteur qui voit « 6 309 DH » sans explication ne fait pas le lien avec la
    confiance de 2 sur 5 qui s'affiche ailleurs."""
    assert "confiance plafonnée" in ECRAN, (
        "le montant échangé est affiché sans dire qu'il plafonne la confiance")


def test_l_ecart_au_secteur_porte_son_sens():
    """Pour le PER et le P/B, au-dessus de la médiane signifie PLUS CHER ; pour
    le dividende, c'est l'inverse. Une couleur unique pour les trois dirait le
    contraire de la vérité une fois sur trois."""
    i = ECRAN.find("r.rang_secteur")
    bloc = ECRAN[i:i + 600]
    assert 'ratio==="div"' in bloc, (
        "le sens de lecture du dividende n'est pas distingué de celui du PER")

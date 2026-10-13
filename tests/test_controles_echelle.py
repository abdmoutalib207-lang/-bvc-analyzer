#!/usr/bin/env python3
"""Contre-épreuves des contrôles d'ÉCHELLE relatifs (voir `_echelle.py`).

⚠️ POURQUOI CE FICHIER
──────────────────────
Le 11/10/2026, les seuils de prix absolus de la famille « données publiées »
(`l52w > 250`, `ma200 > 300`, `l52w > 500`, `h52w < 2500`, `l/o < 200`,
`l52w > 1000`…) ont été remplacés par des contrôles RELATIFS. Un contrôle qu'on
vient de réécrire peut avoir perdu sa dent sans que rien ne le dise. Ce fichier
la prouve, dans les DEUX sens, sur les vraies séries du dépôt — jamais écrites :
toutes les mutations se font sur des copies en mémoire.

    NÉGATIF  le défaut d'origine, réinjecté, est toujours attrapé
             (Sothema ÷23, Mutandis dans Marsa Maroc, Stokvis dans Sonasid,
             Minière Touissit dans Ciments du Maroc, le 490 de la table statique)
    POSITIF  une chute RÉELLE de 30 % — et de 55 %, qui passe sous les anciens
             seuils — ou une hausse réelle de 30 à 60 % NE fait JAMAIS échouer

Les contre-épreuves appellent les MÊMES fonctions que les tests réécrits : si
l'une s'émousse, l'autre le dit.

⚠️ PORTÉE : ces épreuves prouvent la détection des contaminations HISTORIQUES
réinjectées et des ruptures dont le facteur dépasse facteur/2 — pas de toutes
les erreurs d'échelle possibles. `test_limite_un_saut_de_100_a_200_n_est_pas_rejete`
documente un contre-exemple.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

import _echelle as E  # noqa: E402

# (ticker, extremum du cache que le défaut contaminait, ancienne valeur publiée fausse)
CAS = [
    ("SOT", "l52w", 65.99),     # moitié de la fenêtre à l'échelle ÷23
    ("MSA", "l52w", 225.0),     # clôture de Mutandis du 26/05
    ("SNA", "l52w", 67.08),     # plus-bas de Stokvis du 11/09
    ("CIM", "h52w", 5940.0),    # plus-haut de Minière Touissit
    ("STK", "h52w", 490.0),     # table statique
]


def _doc(t):
    return json.loads((RACINE / "datasets" / "corrections_acceptees" / f"{t}.json")
                      .read_text(encoding="utf-8"))


def _contamine(t, bougies):
    """Réinjecte, sur une copie, le défaut D'ORIGINE du titre."""
    out = [dict(b) for b in bougies]
    par_date = {b["d"]: b for b in out}
    if t == "SOT":                                   # double ajustement ≈ ÷23
        return E.diviser(out, len(out) - 250, len(out) - 60, 23.03)
    if t == "MSA":                                   # cours de Mutandis, lot réceptionné
        for l in _doc("MSA")["lignes"]:
            par_date[l["d"]].update(l["remplace"])
    elif t == "SNA":                                 # ouverture et plus-bas de Stokvis
        for d in ("2026-06-25", "2026-06-26", "2026-06-29", "2026-09-10", "2026-09-11"):
            par_date[d].update({"o": 67.08, "l": 67.08})
    elif t == "CIM":                                 # les vraies clôtures de CMT, mêmes dates
        cmt = {b["d"]: b for b in E.charger_bougies("CMT")}
        for d in sorted(par_date):
            if "2026-05-11" <= d <= "2026-06-09" and d in cmt:
                par_date[d].update({k: cmt[d][k] for k in ("o", "h", "l", "c")})
    elif t == "STK":                                 # 490 de static_fallback.json
        for b in out[-100:-97]:
            b.update({"o": 490.0, "h": 490.0, "l": 490.0, "c": 490.0})
    return out


# ── NÉGATIF : le défaut d'origine est toujours attrapé ─────────────────────

@pytest.mark.parametrize("t,nom,_", CAS)
def test_negatif_le_reliquat_reinjecte_dans_la_serie_est_attrape(t, nom, _):
    bougies = E.charger_bougies(t)
    facteur = E.facteur_d_echelle(t)
    assert E.hors_echelle(bougies, facteur) == [], "base déjà polluée"
    sale = _contamine(t, bougies)
    assert sale != bougies
    assert E.hors_echelle(sale, facteur), (
        f"{t} : le reliquat réinjecté n'est plus vu par le contrôle de série")


@pytest.mark.parametrize("t,nom,_", CAS)
def test_negatif_le_cache_recalcule_sur_la_serie_polluee_est_attrape(t, nom, _):
    """⚠️ Le cas où un test par RECALCUL seul serait aveugle : le cache est
    recalculé sur la série polluée, donc cohérent avec elle. Seul le critère
    d'échelle (extremum atteint par le tronçon continu du cours publié) le voit."""
    bougies = E.charger_bougies(t)
    facteur = E.facteur_d_echelle(t)
    sale = _contamine(t, bougies)
    cache = E.cache_recalcule(sale)
    assert E.defauts_extreme(nom, cache, sale, facteur), (
        f"{t} : {nom} = {cache[nom]} tiré d'une série polluée passe le contrôle")


@pytest.mark.parametrize("t,nom,faux", CAS)
def test_negatif_l_ancienne_valeur_publiee_fausse_est_attrapee(t, nom, faux):
    """La valeur réellement servie le jour du défaut, sur la série saine."""
    bougies = E.charger_bougies(t)
    facteur = E.facteur_d_echelle(t)
    cache = dict(E.charger_cache(t), **{nom: faux})
    defauts = E.defauts_extreme(nom, cache, bougies, facteur)
    assert defauts, f"{t} : {nom} = {faux} passerait désormais le contrôle"


def test_negatif_sothema_ma200_a_la_moitie_du_cours_est_attrapee():
    bougies = E.charger_bougies("SOT")
    cache = dict(E.charger_cache("SOT"), ma200=164.94)
    assert E.defauts_moyenne(cache, bougies), "la MA200 de 164,94 passerait"
    assert E.defauts_moyenne(E.charger_cache("SOT"), bougies) == []


def test_negatif_une_bougie_qui_melange_deux_echelles_est_attrapee():
    """La forme qu'avait SOT au 05/05 : plus-haut de 1 700 (ancienne échelle),
    clôture de 369 (nouvelle). Aucune rupture de clôture, pourtant défaut."""
    bougies = E.charger_bougies("SOT")
    sale = [dict(b) for b in bougies]
    sale[-30].update({"o": 1700.0, "h": 1700.0, "l": 369.0, "c": sale[-30]["c"]})
    assert E.hors_echelle(sale, E.facteur_d_echelle("SOT")) == [sale[-30]["d"]]


# ── POSITIF : une vraie baisse, une vraie hausse, ne font jamais échouer ───

def _verifier_sain(t, serie):
    facteur = E.facteur_d_echelle(t)
    cache = E.cache_recalcule(serie)
    assert E.hors_echelle(serie, facteur) == []
    assert E.defauts_extreme("l52w", cache, serie, facteur) == []
    assert E.defauts_extreme("h52w", cache, serie, facteur) == []
    assert E.defauts_moyenne(cache, serie) == []
    return cache


@pytest.mark.parametrize("pct", [0.7, 0.45])
@pytest.mark.parametrize("t,nom,_", CAS)
def test_positif_une_chute_reelle_ne_fait_jamais_echouer(t, nom, _, pct):
    """−30 % puis −55 %, par séances de −9 % (R10 respecté). Sous les anciens
    seuils absolus (250, 500, 1 000, 150, 200) la série de −55 % aurait fait
    échouer le test ; elle ne produit aucune rupture, donc aucun défaut."""
    bougies = E.charger_bougies(t)
    assert _verifier_sain(t, bougies) is not None
    # ⚠️ 13/10/2026 : la cible est arrondie au centime, la borne doit l'être
    # aussi. STK clôturant à 48,99 donnait 22,05 contre 22,0477 attendus —
    # un écart d'arrondi, pas un défaut, qui bloquait la garde de publication.
    cible = round(bougies[-1]["c"] * pct, 2)
    chute = E.prolonger(bougies, cible)
    assert len(chute) > len(bougies)
    cache = _verifier_sain(t, chute)
    assert cache["l52w"] <= cible + 1e-9


def test_positif_les_anciens_seuils_absolus_auraient_echoue_sur_cette_chute():
    """La preuve que le remplacement n'est pas cosmétique : sur une chute de
    55 %, chaque ancien seuil rougit, le contrôle relatif non."""
    ancien = {"SOT": ("l52w", lambda v: v > 250), "MSA": ("l52w", lambda v: v > 500),
              "SNA": ("l52w", lambda v: v > 1000)}
    for t, (nom, ancien_ok) in ancien.items():
        bougies = E.charger_bougies(t)
        chute = E.prolonger(bougies, round(bougies[-1]["c"] * 0.45, 2))
        cache = E.cache_recalcule(chute)
        assert not ancien_ok(cache[nom]), f"{t} : l'ancien seuil aurait tenu"
        assert E.defauts_extreme(nom, cache, chute, E.facteur_d_echelle(t)) == []


@pytest.mark.parametrize("t,facteur_hausse", [("CIM", 1.3), ("STK", 1.6)])
def test_positif_une_hausse_reelle_au_dela_des_anciens_plafonds_passe(t, facteur_hausse):
    """h52w de CIM au-dessus de 2 500 (ancien plafond) et de STK au-dessus de
    200 : une vraie hausse continue ne doit rien faire échouer."""
    bougies = E.charger_bougies(t)
    h = E.cache_recalcule(bougies)["h52w"]
    hausse = E.prolonger(bougies, round(h * facteur_hausse, 2))
    cache = _verifier_sain(t, hausse)
    assert cache["h52w"] >= h * facteur_hausse * 0.9999
    assert cache["h52w"] > {"CIM": 2500, "STK": 200}[t], "ne dépasse pas l'ancien plafond"


# ── Les briques ────────────────────────────────────────────────────────────

def test_une_limite_basse_reelle_de_10_pour_cent_n_est_pas_une_rupture():
    """−10,00 % est la limite réglementaire (R10), pas un défaut. Le bug du
    premier jet : la borne symétrique en rapport (1/1,10) marquait comme
    rupture les limites-bas réelles de SOT, MSA, CIM et STK."""
    a = {"d": "2026-10-05", "c": 100.0}
    assert not E.est_rupture(a, {"d": "2026-10-06", "c": 90.0})
    assert not E.est_rupture(a, {"d": "2026-10-06", "c": 110.0})
    assert E.est_rupture(a, {"d": "2026-10-06", "c": 88.0})
    assert E.est_rupture(a, {"d": "2026-10-06", "c": 112.0})


def test_un_trou_dans_la_serie_elargit_la_borne():
    """Trois séances absentes : −27 % devient possible sans que rien soit faux."""
    a = {"d": "2026-10-05", "c": 100.0}      # lundi
    assert not E.est_rupture(a, {"d": "2026-10-08", "c": 73.0})   # jeudi : 3 séances
    assert E.est_rupture(a, {"d": "2026-10-06", "c": 73.0})       # lendemain


def test_le_facteur_vient_des_registres():
    assert E.facteur_d_echelle("SOT") == 5.0            # SPLITS
    assert 3 < E.facteur_d_echelle("MSA") < 4            # lot réceptionné
    assert E.facteur_d_echelle("SNA") == 28.0            # Stokvis / Sonasid


# ── La limite, écrite plutôt que tue ───────────────────────────────────────

def test_limite_un_saut_de_100_a_200_n_est_pas_rejete():
    """⚠️ CONTRE-EXEMPLE DOCUMENTÉ. Une série qui passe brutalement de 100 à 200
    (rupture de facteur 2) n'est PAS rejetée par `hors_echelle(..., 28)` : le
    facteur 2 est sous le seuil facteur/2 = 14. Ces contrôles attrapent un
    reliquat dont le facteur est grand devant le seuil, pas toute erreur
    d'échelle. Si ce test échoue un jour, c'est que le contrôle a gagné en
    sensibilité : mettre le test à jour et le dire, pas le supprimer."""
    from datetime import date, timedelta
    d, serie = date(2026, 1, 5), []
    for i in range(200):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        c = 100.0 if i < 100 else 200.0
        serie.append({"d": d.isoformat(), "o": c, "h": c, "l": c, "c": c, "v": 1})
        d += timedelta(days=1)
    assert any(E.est_rupture(a, b) for a, b in zip(serie, serie[1:])), "la rupture existe"
    assert E.hors_echelle(serie, 28.0) == []           # ... et pourtant non rejetée
    assert E.hors_echelle(serie, 3.0) != []            # un facteur déclaré plus petit la voit


# ── Volumes : saut d'échelle, pas niveau (ADI) ─────────────────────────────

def _volumes_synthetiques(n=320, v0=20_000, cours=400.0):
    """Série déterministe : volumes autour de v0 (±30 %), cours constant."""
    from datetime import date, timedelta
    d, out = date(2025, 1, 6), []
    for i in range(n):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        v = int(v0 * (0.7 + 0.6 * ((i * 37) % 11) / 10))
        out.append({"d": d.isoformat(), "o": cours, "h": cours, "l": cours, "c": cours, "v": v})
        d += timedelta(days=1)
    return out


def test_volume_negatif_un_montant_en_dirhams_est_attrape():
    """Le défaut d'origine d'ADI : un montant en dirhams pris pour des titres,
    soit les volumes multipliés par le cours."""
    assert E.defauts_volume(_volumes_synthetiques()) == []
    sale = _volumes_synthetiques()
    for b in sale[-60:]:
        b["v"] = int(b["v"] * b["c"])
    assert E.defauts_volume(sale), "un montant en dirhams passerait"
    inverse = _volumes_synthetiques()
    for b in inverse[-60:]:
        b["v"] = max(1, int(b["v"] / b["c"]))
    assert E.defauts_volume(inverse), "des titres pris pour un montant (÷cours) passeraient"


@pytest.mark.parametrize("coef", [3, 10, 30])
def test_volume_positif_une_hausse_durable_et_reelle_des_echanges_passe(coef):
    """Les échanges s'envolent pour de bon (×3, ×10, ×30 sur 60 séances) : ni
    un pic, ni un changement d'unité. Avec un seuil fixe à 100 000, ×10 aurait
    bloqué la publication."""
    haute = _volumes_synthetiques()
    for b in haute[-60:]:
        b["v"] = b["v"] * coef
    assert E.defauts_volume(haute) == []
    if coef >= 10:
        # au-dessus de l'ancien seuil fixe de 100 000 : il aurait bloqué
        assert statistics.median(b["v"] for b in haute[-60:]) > 100_000


def test_volume_positif_un_pic_isole_passe():
    pic = _volumes_synthetiques()
    pic[-3]["v"] *= 500
    assert E.defauts_volume(pic) == []


def test_volume_reel_d_adi_est_sans_saut_d_echelle():
    assert E.defauts_volume(E.charger_bougies("ADI")) == []

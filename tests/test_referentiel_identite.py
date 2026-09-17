#!/usr/bin/env python3
"""L'identité d'une valeur ne se discute pas : elle se recoupe.

POURQUOI CE FICHIER EXISTE
──────────────────────────
Trois confusions d'identité en deux jours, toutes coûteuses :

  · `MANUAL_MAP["MRL"] = "SODEP"` — Maroc Leasing a reçu l'historique de
    Sodep-Marsa Maroc. 22 séances entre 800 et 869 DH sur un titre qui cote 367.
  · ATL a reçu 7 séances d'Auto Hall — 66 à 69 DH sur un titre qui cote 130.
  · Marsa Maroc étiquetée « Agro » et BMCI « Agro » dans la table du frontend.

Le 17/09/2026, Abd Moutalib a fourni le relevé complet de la cote : 77 sociétés
avec leur code BVC, leur ISIN, leur dénomination et leur secteur. Il est archivé
dans `datasets/referentiel/` et ce fichier le rend OPPOSABLE.

⚠️ CE QUE LE RELEVÉ A ÉTABLI, ET QUI N'ÉTAIT PAS ACQUIS
───────────────────────────────────────────────────────
    ISIN confrontés à notre table    77 sur 77 concordants, ZÉRO divergence
    ISIN confirmés par Maroclear     75 sur 77 (dépositaire central)
    cours du 16/09 vs nos chandelles 65 comparaisons, zéro écart
    capitalisations                  1 seule au-delà de 10 % (STR)

Autrement dit : nos ISIN et nos codes étaient JUSTES. Ce qui était faux, c'était
une entrée d'une table de NOMS et des secteurs écrits trois fois de trois façons.

⚠️ ET CE RELEVÉ N'EST PAS L'AUTORITÉ SUR LES DÉNOMINATIONS
──────────────────────────────────────────────────────────
Ses libellés sont des noms d'affichage, tronqués. L'export de l'opérateur
lui-même écrit « MUTANDIS SCA » et « TOTALENERGIES MARKETING MAROC » là où le
relevé dit « Mutandis » et « TotalEnergies Maroc ». On ne recopie donc pas ses
noms : on garde les nôtres, plus complets, et on vérifie seulement qu'aucun ne
désigne une AUTRE société.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
REF = RACINE / "datasets" / "referentiel" / "cote_bvc.json"


@pytest.fixture(scope="module")
def ref():
    d = json.loads(REF.read_text(encoding="utf-8"))
    return {v["ticker"]: v for v in d["valeurs"].values() if v.get("ticker")}


def test_le_referentiel_est_adosse_a_sa_piece():
    """Un référentiel sans pièce est une opinion."""
    import hashlib
    d = json.loads(REF.read_text(encoding="utf-8"))
    src = REF.parent / d["_fichier"]
    assert src.exists(), f"la pièce {d['_fichier']} a disparu"
    vu = hashlib.sha256(src.read_bytes()).hexdigest()
    assert vu == d["_sha256"], (
        f"la pièce archivée n'est plus celle qui a été relevée : {vu[:16]}…")
    assert d["valeurs"], "référentiel vide"


def test_chaque_isin_concorde_avec_le_referentiel(ref):
    """⚠️ LA RÈGLE QUI REND R2 VÉRIFIABLE.

    « JAMAIS supprimer ou modifier le ISIN_MAP sans accord explicite » protège
    la table d'une modification étourdie. Elle ne dit pas si son contenu est
    juste. Ce test le dit, et il le redira à chaque livraison.
    """
    from bvc_config import ISIN_MAP
    fautifs = []
    for t, v in sorted(ref.items()):
        notre = ISIN_MAP.get(t)
        if notre is None:
            fautifs.append(f"{t} : absent d'ISIN_MAP (relevé : {v['isin']})")
        elif notre.strip() != v["isin"]:
            fautifs.append(f"{t} : {notre} ≠ {v['isin']} ({v['nom_bvc']})")
    assert not fautifs, "ISIN divergents du relevé :\n  " + "\n  ".join(fautifs)


def test_chaque_code_bvc_concorde_avec_le_referentiel(ref):
    """Le code officiel est ce par quoi toutes les sources nous parlent.

    ⚠️ C'est là que se logent les pièges du marché marocain : `SNA` désigne
    STOKVIS chez l'opérateur et SONASID chez nous, `SID` désigne Sonasid. Une
    inversion et deux sociétés échangent leurs cours.
    """
    from bvc_config import IDB_TICKER_MAP
    d = json.loads(REF.read_text(encoding="utf-8"))
    codes = {v["ticker"]: c for c, v in d["valeurs"].items() if v.get("ticker")}
    fautifs = [f"{t} : nous disons {IDB_TICKER_MAP.get(t, t)}, le relevé dit {c}"
               for t, c in sorted(codes.items())
               if IDB_TICKER_MAP.get(t, t) != c]
    assert not fautifs, "codes BVC divergents :\n  " + "\n  ".join(fautifs)


def test_aucun_code_bvc_ne_sert_deux_tickers(ref):
    """Deux de nos tickers sur un même code, c'est une collision garantie."""
    from bvc_config import IDB_TICKER_MAP, TICKERS_ALL
    vus = {}
    for t in TICKERS_ALL:
        vus.setdefault(IDB_TICKER_MAP.get(t, t), []).append(t)
    doubles = {c: ts for c, ts in vus.items() if len(ts) > 1}
    assert not doubles, f"codes partagés : {doubles}"


def test_aucune_denomination_ne_designe_une_autre_societe(ref):
    """⚠️ ON NE COMPARE PAS LES LIBELLÉS, ON VÉRIFIE QU'ILS SE RECOUVRENT.

    Le relevé tronque : « Mutandis » pour MUTANDIS SCA. Exiger l'égalité
    ferait rougir trente et un titres sains. Ce qui doit être interdit, c'est
    qu'un libellé désigne une AUTRE société — « Marsa Maroc » sous le ticker de
    Maroc Leasing.

    Le test : les deux libellés doivent partager au moins un mot significatif,
    ou l'un contenir l'autre. C'est lâche exprès — il n'attrape que le vol
    d'identité, pas la mise en forme.
    """
    from bvc_config import COMPANY_NAMES
    import unicodedata

    def mots(s):
        s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode()
        return {m for m in re.split(r"[^A-Za-z0-9]+", s.upper()) if len(m) > 2}

    # ⚠️ Mots qui ne distinguent rien : les partager ne prouve aucune parenté.
    VIDES = {"SOCIETE", "GROUP", "GROUPE", "MAROC", "MAROCAINE", "BANK", "BANQUE",
             "SA", "SCA", "HOLDING", "CAPITAL", "DES", "DU", "DE", "LA", "LE"}
    fautifs = []
    for t, v in sorted(ref.items()):
        a, b = COMPANY_NAMES.get(t, ""), v["nom_bvc"]
        if not a:
            fautifs.append(f"{t} : aucune dénomination chez nous")
            continue
        na, nb = mots(a) - VIDES, mots(b) - VIDES
        if na & nb:
            continue
        ca = re.sub(r"[^A-Z0-9]", "", a.upper())
        cb = re.sub(r"[^A-Z0-9]", "", b.upper())
        if ca in cb or cb in ca:
            continue
        fautifs.append(f"{t} : nous « {a} », le relevé « {b} »")
    assert not fautifs, ("dénominations sans rapport avec le relevé :\n  "
                         + "\n  ".join(fautifs))


def test_le_secteur_est_celui_du_releve(ref):
    """Trois taxonomies coexistaient et se contredisaient sur 55 titres."""
    from bvc_config import COMPANY_SECTORS
    fautifs = [f"{t} : « {COMPANY_SECTORS.get(t)} » ≠ « {v['secteur']} »"
               for t, v in sorted(ref.items())
               if COMPANY_SECTORS.get(t) != v["secteur"]]
    assert not fautifs, "secteurs divergents :\n  " + "\n  ".join(fautifs)


def test_un_seul_vocabulaire_de_secteurs():
    """⚠️ `fondamentaux.json` portait 45 libellés libres — « Mines -
    Plomb/Argent/Zinc », « Fintech / Paiements SaaS ». Un secteur écrit de
    quarante-cinq façons n'est pas un classement."""
    from bvc_config import COMPANY_SECTORS
    voc = set(COMPANY_SECTORS.values())
    f = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))
    hors = sorted({v["secteur"] for t, v in f.items()
                   if isinstance(v, dict) and v.get("secteur")
                   and v["secteur"] not in voc})
    assert not hors, f"secteurs hors vocabulaire dans fondamentaux.json : {hors}"


def test_le_frontend_ne_contredit_pas_le_referentiel():
    """⚠️ LA TABLE FIGÉE DU FRONTEND EST UN TROISIÈME JEU DE DONNÉES.

    Elle portait Marsa Maroc en « Agro » — un opérateur portuaire — et BMCI,
    une banque, en « Agro » également. Elle ne sert qu'en dernier recours, ce
    qui la rend d'autant plus dangereuse : on ne la lit jamais.
    """
    from bvc_config import COMPANY_NAMES, COMPANY_SECTORS
    s = (RACINE / "index.html").read_text(encoding="utf-8")
    motif = re.compile(r'\{symbol:"([A-Z0-9]{2,5})"\s*,\s*name:"([^"]*)"\s*,\s*sector:"([^"]*)"')
    lignes = motif.findall(s)
    assert len(lignes) > 40, f"table figée introuvable ({len(lignes)} lignes)"
    fautifs = []
    for t, nom, sec in lignes:
        if t in COMPANY_NAMES and nom != COMPANY_NAMES[t]:
            fautifs.append(f"{t} : nom « {nom} » ≠ « {COMPANY_NAMES[t]} »")
        if t in COMPANY_SECTORS and sec != COMPANY_SECTORS[t]:
            fautifs.append(f"{t} : secteur « {sec} » ≠ « {COMPANY_SECTORS[t]} »")
    assert not fautifs, ("la table figée contredit bvc_config :\n  "
                         + "\n  ".join(fautifs[:12]))


def test_le_secteur_n_entre_dans_aucun_score():
    """⚠️ CE QUI REND LA CORRECTION DES SECTEURS SÛRE AU REGARD DE R8.

    Une seule exception, et elle est bornée : `fond_score` neutralise le ratio
    dette nette / EBITDA quand il vaut zéro dans un secteur où il n'a pas de
    sens. La liste doit donc parler le vocabulaire courant, sans quoi elle
    protège des secteurs qui n'existent plus.
    """
    s = (RACINE / "pipeline" / "smart_money" / "fond_score.py").read_text(encoding="utf-8")
    from bvc_config import COMPANY_SECTORS
    voc = set(COMPANY_SECTORS.values())
    m = re.search(r'_SANS_OBJET\s*=\s*\(([^)]*)\)', s)
    assert m, "_SANS_OBJET introuvable"
    cites = re.findall(r'"([^"]+)"', m.group(1))
    morts = [c for c in cites if c not in voc]
    assert not morts, (
        f"_SANS_OBJET nomme des secteurs qui n'existent plus : {morts}")

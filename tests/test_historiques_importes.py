#!/usr/bin/env python3
"""Un historique importé doit être celui de l'opérateur, date pour date.

CE QUE CES CINQ EXPORTS ONT APPRIS (16/09/2026)
───────────────────────────────────────────────
Abd Moutalib a fourni les exports 3 ans de casablanca-bourse.com pour AKD, TQA,
HAL, MUT et TMA — cinq des trente et un titres qui n'avaient qu'un trimestre
d'historique. En les recoupant avec ce que nous avions déjà, deux défauts sont
apparus, et aucun des deux n'était soupçonné.

1. NOS COURS ÉTAIENT DES COURS DE MILIEU DE SÉANCE, pas des clôtures.
   Sur 120 séances en désaccord avec l'opérateur, **109 (91 %) tombaient DANS
   la fourchette haut-bas du jour**. Ce ne sont pas de fausses séances : c'est
   la trace des jours où le run de 15h45 n'a pas eu lieu et où le cours retenu
   venait d'un passage de mi-journée. Les 11 restants sont nos valeurs figées
   (TQA bloquée à 1 750 trois séances de suite, TMA à 1 504).

2. UNE SÉANCE FANTÔME LE 30 JUILLET, jour de la Fête du Trône.
   L'export de l'opérateur liste TOUTES les séances réelles — Dari Couspate y
   figure 629 fois sans le moindre échange — et omet exactement les jours
   fériés : 30/07, 14/08, 20/08, 21/08, 01/05, 11/01. Le 30/07/2026 n'existe
   pas. Nous en avions une bougie.

⚠️ ET `(7, 30)` EST DANS `JOURS_FERIES_FIXES` DEPUIS LE DÉBUT. La liste existe,
rien ne la confronte aux chandelles écrites. `purger_seance_fantome` juge sur
une signature statistique — 95 % de clôtures identiques — et seules 26 des 72
bougies du 30/07 recopiaient la veille : le seuil n'a pas été atteint. Un
garde-fou écrit mais pas branché sur le calendrier qu'il possède.

⚠️ SOIXANTE-SEPT AUTRES TITRES PORTENT ENCORE CETTE BOUGIE. Les purger touche
67 séries et sort du périmètre de cet import ; c'est une décision à prendre,
inscrite dans `.claude/memory/EN_COURS.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent
XLSX = RACINE / "data" / "historique"
CANDLES = RACINE / "pipeline" / "candles"

# ⚠️ CES CINQ-LÀ ET PAS TOUTE LA COTE. Leur série vient en entier de l'export de
# l'opérateur, et rien ne la réécrit ensuite. Les autres porteurs d'export ont
# des corrections réceptionnées qui PRIMENT sur le fichier (SOT, MSA) : leur
# exiger l'égalité avec l'XLSX ferait échouer le contrôle là où le dépôt a
# raison.
IMPORTES = ["AKD", "FNB", "HAL", "MGL", "MRL", "MUT", "PPM", "TMA", "TQA", "WAF"]


def _export(ticker: str) -> dict:
    df = pd.read_excel(XLSX / f"{ticker}.xlsx")
    df["d"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return {r["d"]: r for _, r in df.iterrows()}


def _serie(ticker: str) -> list:
    return json.loads((CANDLES / f"{ticker}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("ticker", IMPORTES)
def test_la_serie_est_celle_de_l_operateur(ticker):
    """Même dates, mêmes clôtures. C'est tout ce qu'un import doit garantir."""
    op, s = _export(ticker), _serie(ticker)

    # ⚠️ L'EXPORT COUVRE UNE PÉRIODE, IL N'INTERDIT PAS L'AVENIR.
    #
    # Écrit `[b["d"] for b in s] == sorted(op)`, ce test exigeait que la série
    # publiée soit EXACTEMENT l'export — donc que ces cinq titres ne cotent
    # plus jamais. Il a bloqué la publication du 17/09 à 10h11, séance ouverte,
    # dès que le moteur a ajouté la bougie du jour.
    #
    # ⚠️ C'EST LA MÊME FAUTE QUE J'AVAIS CORRIGÉE SUR CMT L'AVANT-VEILLE, en
    # écrivant noir sur blanc qu'« un test qui exige que la série s'arrête à
    # une date n'énonce plus une règle : il interdit au titre de coter ». Je
    # l'ai refaite deux jours plus tard, sur cinq titres à la fois.
    #
    # La règle : sur la période que l'export couvre, la série publiée est
    # l'export, date pour date et clôture pour clôture. Après, elle est libre.
    fin = max(op)
    couvert = [b for b in s if b["d"] <= fin]
    assert [b["d"] for b in couvert] == sorted(op), (
        f"{ticker} : sur la période de l'export ({min(op)} → {fin}), les dates "
        f"publiées ne sont pas celles de l'export")
    ecarts = [f"{b['d']} : {b['c']} ≠ {op[b['d']]['close']}"
              for b in couvert if abs(b["c"] - float(op[b["d"]]["close"])) > 0.011]
    assert not ecarts, f"{ticker} : {len(ecarts)} clôtures divergentes {ecarts[:4]}"


@pytest.mark.parametrize("ticker", IMPORTES)
def test_aucune_bougie_un_jour_ferie(ticker):
    """⚠️ LA RÈGLE QUE LE 30/07 A RÉVÉLÉE, et qui ne coûte rien à vérifier.

    Le calendrier des fériés à date fixe est dans `bvc_config`. Une bougie
    tombant sur l'un d'eux est fabriquée : la Bourse n'a pas ouvert.

    Ce contrôle ne remplace pas `purger_seance_fantome`, qui attrape les fériés
    lunaires en lisant les données. Il attrape ce que celui-ci laisse passer :
    un férié de date fixe où les cours diffèrent assez pour que la signature
    statistique ne se déclenche pas.
    """
    import sys
    sys.path.insert(0, str(RACINE))
    from bvc_config import JOURS_FERIES_FIXES
    fautives = [b["d"] for b in _serie(ticker)
                if (int(b["d"][5:7]), int(b["d"][8:10])) in JOURS_FERIES_FIXES]
    assert not fautives, (
        f"{ticker} : bougie(s) un jour férié déclaré — {fautives[:5]}")


@pytest.mark.parametrize("ticker", IMPORTES)
def test_le_volume_est_un_nombre_de_titres_pas_un_montant(ticker):
    """⚠️ L'EXPORT PORTE DEUX COLONNES DE VOLUME, ET LE CHARGEUR PREND LA
    PREMIÈRE QUI CONTIENT « vol ».

    `Volume (MAD)` est un montant en dirhams, `Titres Échangés` un nombre de
    titres. Le premier entrerait comme second et gonflerait l'OBV de plusieurs
    ordres de grandeur — invisible à l'écran, ruineux pour l'indicateur.

    Le juge est arithmétique : `volume × cours` est un montant échangé. S'il
    dépassait la capitalisation du titre chaque jour, c'est que le volume est
    déjà un montant.
    """
    s = _serie(ticker)
    import sys
    sys.path.insert(0, str(RACINE))
    d = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    cap = next((t.get("cap") for t in d["tickers"] if t["symbol"] == ticker), None)
    if not cap:
        pytest.skip(f"{ticker} sans capitalisation publiée")
    aberrants = [b["d"] for b in s if b["v"] * b["c"] > cap * 1e6]
    assert not aberrants, (
        f"{ticker} : {len(aberrants)} séances où volume × cours dépasse la "
        f"capitalisation — le volume est un montant, pas un nombre de titres "
        f"{aberrants[:4]}")


@pytest.mark.parametrize("ticker", IMPORTES)
def test_la_serie_couvre_bien_trois_ans(ticker):
    """Le but de l'import : sortir du trimestre d'historique."""
    s = _serie(ticker)
    assert len(s) >= 700, f"{ticker} : {len(s)} séances, l'import n'a pas pris"
    assert s[0]["d"] <= "2023-10-01", f"{ticker} commence au {s[0]['d']}"


@pytest.mark.parametrize("ticker", IMPORTES)
def test_la_serie_reste_dans_les_bornes_du_marche(ticker):
    """R10 : aucun instrument ne varie de plus de ±10 % en une séance.

    ⚠️ Marge à 11 % : les clôtures sont arrondies au centime et deux arrondis
    de part et d'autre peuvent faire franchir le seuil exact sans qu'aucune
    règle ait été violée.
    """
    s = _serie(ticker)
    ruptures = [(s[i]["d"], s[i - 1]["c"], s[i]["c"]) for i in range(1, len(s))
                if s[i - 1]["c"] and abs(s[i]["c"] / s[i - 1]["c"] - 1) > 0.11]
    assert not ruptures, f"{ticker} : {len(ruptures)} variations hors bornes {ruptures[:3]}"

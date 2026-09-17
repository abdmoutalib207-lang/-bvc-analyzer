#!/usr/bin/env python3
"""Un historique rapatrié par NOM doit prouver qu'il est bien le nôtre.

CE QUI ÉTAIT PUBLIÉ LE 17/09/2026 AU MATIN
──────────────────────────────────────────
    ATL — AtlantaSanad, qui cote ≈130 DH
          7 séances du 08 au 16/06 aux cours d'Auto Hall : 66 à 69 DH.
          Les 7 clôtures égalent au centime celles de HAL les mêmes jours.

    MRL — Maroc Leasing, qui cote ≈367 DH
          22 séances du 25/05 au 29/06 aux cours de Marsa Maroc : 800 à 869 DH.
          14 d'entre elles égalent au centime celles de MSA.
          Puis 25 séances à 235,00 et 350,25 — volume nul, jamais échangées.

Sur 67 bougies, Maroc Leasing en avait DIX qui correspondaient à des échanges
réels de Maroc Leasing.

LE MÉCANISME, ÉTABLI ET NON SUPPOSÉ
───────────────────────────────────
`collect_history_bvcscrap.py` identifie les sociétés par NOM et demande au
fournisseur tout ce qui suit la dernière date connue. Pour ATL, l'export XLSX
s'arrête au 05/06 — et la contamination commence au 08/06, séance suivante. Pour
MRL, sans export, la date de départ vaut « aujourd'hui moins 31 jours », ce qui
place le début au 25/05. **La contamination commence exactement là où s'arrête
la source fiable.**

Pour MRL la cause est écrite dans le code lui-même :

    "MRL": "SODEP",   # SODEP = ancien nom BVCscrap pour Marsa Maroc (MRL)

MRL est Maroc Leasing. Sodep-Marsa Maroc est MSA. Le commentaire confond les deux.

⚠️ ET LA TABLE DES NOMS N'EST PAS CHEZ NOUS. BVCscrap résout le libellé côté
fournisseur, qui répond 403 depuis des semaines. Nous ne pouvons donc ni lire ni
auditer l'appariement : la seule défense possible est de juger le RÉSULTAT.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))
sys.path.insert(0, str(RACINE))
CANDLES = RACINE / "pipeline" / "candles"


def _serie(t):
    return json.loads((CANDLES / f"{t}.json").read_text(encoding="utf-8"))


# ── La règle générale, sur toute la cote ────────────────────────────────────

def test_aucun_titre_ne_porte_les_cours_d_un_autre():
    """⚠️ LA SIGNATURE EXACTE D'UNE CONTAMINATION D'IDENTITÉ — ET RIEN D'AUTRE.

    Il a fallu trois versions pour cerner la règle, et les deux premières
    accusaient des innocents :

    · « trois clôtures identiques » accusait ADI et M2M sur trois égalités
      espacées de DIX-NEUF MOIS. Deux titres finissent toujours par se croiser
      au même prix.

    · « trois clôtures identiques D'AFFILÉE » accusait AFI et RISMA, qui
      cotaient tous deux 350,00 pendant trois séances — un prix rond, avec des
      volumes sans rapport (37 334 contre 30 246). Une coïncidence reste une
      coïncidence même trois jours de suite.

    Ce qui distingue le vol, c'est que la série ATTERRIT sur l'autre titre : le
    cours saute au-delà du plafond réglementaire pour rejoindre un niveau qui
    n'est pas le sien, y reste, puis revient. ATL est passé de 132,00 à 68,99
    (−48 %) pour sept séances, puis est remonté à 130,15. AFI, lui, est arrivé
    à 350 en cotant normalement.

    ⚠️ R10 N'EST PAS UNE LOI DE LA BANDE, C'EST UN CONTRÔLE DE NOTRE QUALITÉ.
    L'export de l'opérateur porte lui-même un −14,3 % sur Crédit Eqdom le
    11/02/2025, après plusieurs séances sans échange réel. Un test qui
    refuserait toute variation supérieure à 10 % refuserait les données de la
    Bourse elle-même. C'est la CONJONCTION — saut hors plafond ET atterrissage
    sur un autre émetteur — qui accuse.
    """
    import statistics
    series = {}
    for f in CANDLES.glob("*.json"):
        try:
            series[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
    parjour = {}
    for t, s_ in series.items():
        for b in s_:
            parjour.setdefault(b["d"], {})[t] = b["c"]

    # ⚠️ TGC est l'ancien ticker de TGCC — même émetteur, même ISIN
    # (MA0000012528). Leurs séries DOIVENT coïncider.
    ALIAS = {frozenset(("TGC", "TGCC"))}

    fautifs = []
    for t, s_ in sorted(series.items()):
        n = len(s_)
        i = 0
        while i < n:
            # Sur quelle(s) autre(s) série(s) cette bougie tombe-t-elle ?
            def jumeaux(k):
                d = s_[k]["d"]
                return {u for u, v in parjour.get(d, {}).items()
                        if u != t and frozenset((u, t)) not in ALIAS
                        and abs(v - s_[k]["c"]) < 1e-9}
            comp = jumeaux(i)
            if not comp:
                i += 1
                continue
            j_ = i + 1
            while j_ < n and (comp & jumeaux(j_)):
                comp &= jumeaux(j_)
                j_ += 1
            longueur = j_ - i
            if longueur >= 3:
                # ⚠️ LA PLAGE EST-ELLE AU NIVEAU DE PRIX DU TITRE, OU DE L'AUTRE ?
                # C'est la seule question qui sépare le vol de la coïncidence.
                # AFI et RISMA ont tous deux coté 350,00 trois séances : chacun
                # à SON niveau. ATL à 67 et MRL à 850 étaient au niveau de
                # l'autre — un cours ne quitte pas son ordre de grandeur.
                dehors = [b["c"] for k, b in enumerate(s_)
                          if not (i <= k < j_) and b["c"]]
                if dehors:
                    ref = statistics.median(dehors)
                    dedans = statistics.median(s_[k]["c"] for k in range(i, j_))
                    # ⚠️ LE RAPPORT DOIT ÊTRE SYMÉTRIQUE. Écrit `dedans/ref - 1`,
                    # il donnait −48 % pour ATL (67 contre 130) et passait sous
                    # un seuil de 50 % — le titre échappait au contrôle de deux
                    # points. Une division par deux est aussi suspecte qu'un
                    # doublement : c'est le rapport des niveaux qui compte, pas
                    # le sens.
                    ecart = max(dedans / ref, ref / dedans) - 1 if dedans else 99
                    if ref and ecart > 0.5:
                        fautifs.append(
                            f"{t} {s_[i]['d']} → {s_[j_ - 1]['d']} : "
                            f"{longueur} séances à {dedans:.0f} DH aux cours de "
                            f"{sorted(comp)[0]}, alors que {t} cote {ref:.0f}")
            i = j_
    assert not fautifs, ("des titres portent l'historique d'un autre émetteur :\n  "
                         + "\n  ".join(fautifs))


# ── Les retraits réceptionnés ───────────────────────────────────────────────

@pytest.mark.parametrize("ticker,n", [("ATL", 7), ("MRL", 47)])
def test_les_seances_retirees_le_sont_bien(ticker, n):
    """Ce que l'instruction dit retirer ne doit plus être servi."""
    import seances_retirees as R
    doc = R.charger(ticker)
    assert doc and len(doc["lignes"]) == n
    dates = {b["d"] for b in _serie(ticker)}
    restantes = [l["d"] for l in doc["lignes"] if l["d"] in dates]
    assert not restantes, f"{ticker} : {len(restantes)} séances retirées sont revenues"


def test_un_retrait_refuse_si_la_bougie_a_change(tmp_path, monkeypatch):
    """⚠️ LE CONTRÔLE QUI FAIT LA DIFFÉRENCE ENTRE UNE INSTRUCTION ET UNE ARME.

    Une liste de dates à supprimer s'appliquerait à n'importe quoi. Une
    instruction qui porte la bougie exacte s'arrête dès que le terrain a bougé.
    """
    import seances_retirees as R
    doc = {"ticker": "ZZZ", "lignes": [
        {"d": "2026-06-08",
         "retiree": {"o": 1, "h": 1, "l": 1, "c": 68.99, "v": 5062},
         "motif": "essai"}]}
    (tmp_path / "ZZZ.json").write_text(json.dumps(doc), encoding="utf-8")

    # La bougie sur disque n'est PAS celle décrite.
    bougies = [{"d": "2026-06-08", "o": 1, "h": 1, "l": 1, "c": 132.0, "v": 5062}]
    out, rap = R.appliquer("ZZZ", bougies, dossier=tmp_path)
    assert rap["retirees"] == 0 and len(rap["refus"]) == 1
    assert out == bougies, "la bougie a été retirée malgré le refus"

    # Et quand elle correspond, le retrait a lieu.
    bougies[0]["c"] = 68.99
    out, rap = R.appliquer("ZZZ", bougies, dossier=tmp_path)
    assert rap["retirees"] == 1 and out == []


def test_une_instruction_au_mauvais_ticker_est_refusee(tmp_path):
    import seances_retirees as R
    (tmp_path / "ZZZ.json").write_text(
        json.dumps({"ticker": "AAA", "lignes": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        R.charger("ZZZ", dossier=tmp_path)


# ── La garde d'identité sur l'import ────────────────────────────────────────

def _df(dates, closes):
    import pandas as pd
    return pd.DataFrame({"date": [pd.Timestamp(d) for d in dates], "close": closes})


def test_une_extension_qui_ne_se_raccorde_pas_est_refusee():
    """Le cas ATL : 132,00 la veille, 68,99 le lendemain. −48 % : impossible."""
    import collect_history_bvcscrap as C
    ok, motif = C.extension_credible(
        "ATL", _df(["2026-06-08"], [68.99]), 132.0, {})
    assert not ok and "±10" in motif


def test_une_extension_qui_est_l_historique_d_un_autre_est_refusee():
    """Le cas MRL : aucun cours connu, donc le raccord ne dit rien. C'est la
    collision qui tranche."""
    import collect_history_bvcscrap as C
    msa = {"2026-05-25": 851.0, "2026-05-26": 822.6, "2026-06-01": 839.0}
    ok, motif = C.extension_credible(
        "MRL", _df(list(msa), list(msa.values())), None, {"MSA": msa})
    assert not ok and "MSA" in motif


def test_une_extension_legitime_passe():
    """⚠️ CONTRE-ÉPREUVE. Une garde qui refuserait tout arrêterait la collecte."""
    import collect_history_bvcscrap as C
    autre = {"2026-06-08": 851.0, "2026-06-09": 822.6, "2026-06-10": 839.0}
    ok, motif = C.extension_credible(
        "ATL", _df(["2026-06-08", "2026-06-09"], [131.0, 129.5]), 132.0,
        {"MSA": autre})
    assert ok, motif


def test_deux_egalites_ne_suffisent_pas_a_accuser():
    """Le seuil est à trois, et il doit le rester : le balayage du 17/09 a
    relevé des égalités isolées entre titres sans aucun rapport."""
    import collect_history_bvcscrap as C
    autre = {"2026-06-08": 131.0, "2026-06-09": 129.5, "2026-06-10": 999.0}
    ok, _ = C.extension_credible(
        "ATL", _df(["2026-06-08", "2026-06-09", "2026-06-10"],
                   [131.0, 129.5, 128.0]), 132.0, {"XXX": autre})
    assert ok


# ── L'identité fausse est retirée du code ───────────────────────────────────

def test_maroc_leasing_n_est_plus_associe_a_marsa_maroc():
    import collect_history_bvcscrap as C
    from bvc_config import COMPANY_NAMES
    assert C.MANUAL_MAP.get("MRL") != "SODEP"
    assert "marsa" not in (C.MANUAL_MAP.get("MRL") or "").lower()
    assert COMPANY_NAMES["MRL"] == "Maroc Leasing"
    assert C.MANUAL_MAP.get("MSA") == "Marsa Maroc"


def test_un_refus_de_correction_empeche_l_ecriture():
    """Le même défaut que `generate_candles.py` portait le 16/09, corrigé là et
    pas ici — jusqu'à aujourd'hui."""
    s = (RACINE / "pipeline" / "collect_history_bvcscrap.py").read_text(encoding="utf-8")
    assert 'rapport.get("refus")' in s, "le KeyError('refus') peut revenir"
    i_refus, i_ecrit = s.index("if _refus:"), s.rindex("save_candle_file(ticker, df")
    assert i_refus < i_ecrit, "la garde est posée après l'écriture qu'elle doit empêcher"

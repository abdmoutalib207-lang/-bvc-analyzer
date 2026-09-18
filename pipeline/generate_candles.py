#!/usr/bin/env python3
"""
BVC Candle Generator — pipeline/generate_candles.py
Convertit data/historique/*.xlsx → pipeline/candles/{sym}.json
Format: [{d:"YYYY-MM-DD", o:float, h:float, l:float, c:float, v:int}]
"""
import sys, os, json, logging
from pathlib import Path
from datetime import datetime, timedelta, timezone, date as _date

try:
    import pandas as pd, numpy as np, requests
except ImportError as _e:
    sys.exit(f"Dépendance manquante : {_e}\nInstalle : pip install -r requirements_pipeline.txt")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("CandleGen")

ROOT        = Path(__file__).parent.parent
XLSX_DIR    = ROOT / "data" / "historique"
CANDLES_DIR = Path(__file__).parent / "candles"
MED_BASE    = "https://www.medias24.com/bourse/api_bourse.php"
HEADERS     = {"User-Agent":"Mozilla/5.0","Accept-Language":"fr-FR,fr;q=0.9"}
TIMEOUT     = 15

XLSX_ALIAS = {"TGC": "TGCC"}

sys.path.insert(0, str(Path(__file__).parent))
from candle_write_policy import appliquer_corrections_avant_ecriture  # noqa: E402

SERIES_ACCEPTEES = ROOT / "datasets" / "series_acceptees"


def serie_acceptee(ticker: str, dossier: Path | None = None) -> bool:
    """Ce titre porte-t-il une série RÉCEPTIONNÉE ?

    ⚠️ Même garde que dans `collect_history_bvcscrap.py`, et pour la même
    raison : trois programmes écrivent dans `pipeline/candles/`, en protéger
    un seul ne protège rien. Celui-ci fusionne l'export XLSX avec l'existant —
    il n'écraserait pas la série entière, mais il peut réintroduire des
    séances que la série réceptionnée a délibérément écartées.

    La règle est celle du dossier : `datasets/series_acceptees/` INSTRUIT.
    Un import ne discute pas une instruction.
    """
    return ((dossier or SERIES_ACCEPTEES) / f"{ticker}.json").exists()


def _reimposer(ticker, candles):
    """Réimpose les séances corrigées avant d'écrire.

    ⚠️ CE QUI EST ARRIVÉ LE 15/09/2026, ET CE QUE J'AVAIS MAL FAIT.
    La couche `corrections_acceptees` avait été branchée dans
    `collect_history_bvcscrap.py` — et là seulement. J'avais pourtant écrit, en
    posant la garde des séries réceptionnées : « trois programmes écrivent dans
    pipeline/candles/, en protéger un seul ne protège rien ». Je ne l'ai pas
    appliqué à la couche de corrections.

    Résultat, mesuré : les 486 séances de Sothema ramenées à la bonne échelle à
    20h27 ont été réécrites à l'ancienne par ce programme-ci quelques minutes
    plus tard. Le même défaut que CMT le 14/09, par l'autre porte.
    """
    out, rapport = appliquer_corrections_avant_ecriture(ticker, candles)
    if rapport["corrections"]:
        log.warning(f"  {ticker}: {rapport['corrections']} séance(s) corrigée(s) "
                    f"réimposée(s) avant écriture")

    # ⚠️ `refus` EST ABSENT QUAND AUCUN LOT N'EXISTE, ET C'EST LE CAS ORDINAIRE.
    # `appliquer()` renvoie alors {ticker, corrections, _lecture} — sans clé
    # `refus`. L'indexer levait KeyError('refus'), l'exception remontait dans le
    # `except Exception` de l'appelant, et le titre sortait sur « ✗ SRM: 'refus' »
    # SANS que ses chandelles soient écrites. Soixante et un titres sur
    # soixante-treize étaient dans ce cas le 16/09 : le message avait l'air d'un
    # refus motivé, c'était un plantage.
    refus = rapport.get("refus", [])
    for r in refus:
        log.warning(f"     refus {r['seance']} : {r['motif']}")
    return out, refus

try:
    sys.path.insert(0, str(ROOT))
    from bvc_config import ISIN_MAP, TICKERS_ALL, adjust_splits
except Exception:
    ISIN_MAP = {}
    TICKERS_ALL = []
    def adjust_splits(ticker, candles, date_key="d"):  # no-op si config absente
        return candles


_TZ_CA = timezone(timedelta(hours=1))   # Africa/Casablanca (UTC+1 stable)

def _is_trading_day(d: str) -> bool:
    try:
        dt = _date.fromisoformat(d)
        return dt.weekday() < 5  # lun=0 … ven=4
    except Exception:
        return True

def _med_history(isin: str, days: int = 400) -> pd.DataFrame:
    to  = datetime.now(_TZ_CA)
    frm = to - timedelta(days=days + 30)
    try:
        r = requests.get(MED_BASE, params={
            "method": "getPriceHistory",
            "ISIN":   isin,
            "from":   frm.strftime("%Y-%m-%d"),
            "to":     to.strftime("%Y-%m-%d"),
            "format": "json"
        }, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200 or len(r.text) < 20:
            return pd.DataFrame()
        recs = r.json().get("result", [])
        if not isinstance(recs, list) or len(recs) < 5:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

    rows = []
    for rec in recs:
        try:
            raw = rec.get("date","")
            if "/" in raw:
                d, m, y = raw.split("/")
                dt = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
            else:
                dt = raw[:10]
            c = float(rec.get("value") or 0)
            if c <= 0:
                continue
            rows.append({
                "d": dt,
                "c": round(c, 2),
                "h": round(float(rec.get("max")    or c), 2),
                "l": round(float(rec.get("min")    or c), 2),
                "v": int(float(rec.get("volume")   or 0)),
            })
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values("d").reset_index(drop=True)
    df = df[df["d"].apply(_is_trading_day)].reset_index(drop=True)
    df["o"] = df["c"].shift(1).fillna(df["c"]).round(2)
    df["o"] = df[["o", "l"]].max(axis=1).round(2)
    df["o"] = df[["o", "h"]].min(axis=1).round(2)
    return df


def _xlsx_to_candles(path: Path) -> list:
    df = pd.read_excel(path)
    df.columns = [c.lower().strip() for c in df.columns]
    if "date" not in df.columns:
        return []
    df["d"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["c"] = pd.to_numeric(df.get("close", df.get("clôture", 0)), errors="coerce").fillna(0)
    df["h"] = pd.to_numeric(df.get("high",  df.get("haut",    df["c"])), errors="coerce").fillna(df["c"])
    df["l"] = pd.to_numeric(df.get("low",   df.get("bas",     df["c"])), errors="coerce").fillna(df["c"])
    df["v"] = pd.to_numeric(df.get("volume",df.get("vol",     0)),       errors="coerce").fillna(0).astype(int)
    df["o"] = pd.to_numeric(df.get("open",  df.get("ouvert",  df["c"])), errors="coerce").fillna(df["c"])
    df = df[df["c"] > 0].sort_values("d").reset_index(drop=True)
    return [
        {"d": row["d"], "o": round(float(row["o"]),2),
         "h": round(float(row["h"]),2), "l": round(float(row["l"]),2),
         "c": round(float(row["c"]),2), "v": int(row["v"])}
        for _, row in df.iterrows()
    ]


def _merge_candles(existing: list, new_candles: list) -> list:
    combined = {c["d"]: c for c in existing}
    combined.update({c["d"]: c for c in new_candles})
    return sorted(combined.values(), key=lambda x: x["d"])


def generate_from_xlsx() -> dict:
    CANDLES_DIR.mkdir(exist_ok=True)
    results = {}

    for xlsx in sorted(XLSX_DIR.glob("*.xlsx")):
        ticker = XLSX_ALIAS.get(xlsx.stem.upper(), xlsx.stem.upper())
        if serie_acceptee(ticker):
            log.warning(f"  {ticker}: série réceptionnée — XLSX non fusionné")
            continue
        try:
            # XLSX = source brute (cours non ajustés) → ajustement split avant
            # fusion avec l'existant, qui est déjà ajusté.
            candles = adjust_splits(ticker, _xlsx_to_candles(xlsx))
            if not candles:
                log.warning(f"  {ticker}: XLSX vide")
                continue

            out = CANDLES_DIR / f"{ticker}.json"
            if out.exists():
                try:
                    existing = json.loads(out.read_text())
                    candles  = _merge_candles(existing, candles)
                except Exception:
                    pass

            candles, refus = _reimposer(ticker, candles)

            # ⚠️ UN REFUS INTERDIT D'ÉCRIRE. Il ne se journalise pas pour
            # mémoire : il arrête le geste.
            #
            # Le 16/09 à 19h21, ce programme a refusé les 191 corrections
            # réceptionnées de Sothema — « l'état actuel n'est ni l'ancien ni le
            # corrigé » — puis a écrit sa propre série par-dessus. Les 220
            # ruptures de l'ancienne échelle sont revenues, et la publication
            # s'est bloquée. Le contrôle avait vu juste ; personne ne l'écoutait.
            #
            # « Conservez les données et indicateurs antérieurs valides lorsqu'un
            # nouvel import est refusé. » Ce qui est déjà sur le disque a été
            # réceptionné ; ce qui arrive ne l'a pas été.
            if refus:
                log.error(f"  ✗ {ticker}: {len(refus)} correction(s) réceptionnée(s) "
                          f"refusée(s) — fichier CONSERVÉ, rien n'est écrit")
                continue

            out.write_text(json.dumps(candles, separators=(",",":")))
            log.info(f"  ✓ {ticker}: {len(candles)} bougies (XLSX)")
            results[ticker] = len(candles)
        except Exception as e:
            log.warning(f"  ✗ {ticker}: {e}")

    return results


def generate_from_med24(skip_existing_tickers: set = None, days: int = 400) -> dict:
    """Enrichit les candles depuis Médias24.
    skip_existing_tickers : sautés seulement si leurs candles sont fraîches (< 10 jours).
    Les candles XLSX vieilles (> 10 jours) sont enrichies automatiquement.
    """
    import time
    CANDLES_DIR.mkdir(exist_ok=True)
    if skip_existing_tickers is None:
        skip_existing_tickers = set()
    today = datetime.now(_TZ_CA).date().isoformat()
    results = {}

    for ticker in TICKERS_ALL:
        canon = ticker
        out   = CANDLES_DIR / f"{canon}.json"

        if serie_acceptee(canon):
            log.warning(f"  {canon}: série réceptionnée — Médias24 non fusionné")
            continue

        # Skip seulement si les candles existantes sont récentes (< 10 jours)
        if out.exists() and canon in skip_existing_tickers:
            try:
                _existing = json.loads(out.read_text())
                if _existing:
                    last = _existing[-1].get("d", "")
                    age  = (_date.fromisoformat(today) - _date.fromisoformat(last)).days
                    if age < 10:
                        log.info(f"  → {ticker}: candles fraîches ({last}), skip Médias24")
                        continue
                    log.info(f"  → {ticker}: candles vieilles de {age}j ({last}), enrichissement...")
            except Exception:
                pass

        isin = ISIN_MAP.get(ticker)
        if not isin:
            log.warning(f"  ✗ {ticker}: ISIN inconnu — skip")
            continue

        try:
            df = _med_history(isin, days=days)
            if df.empty or len(df) < 5:
                log.warning(f"  ✗ {ticker}: Médias24 vide ({len(df)} points)")
                time.sleep(0.3)
                continue

            candles = adjust_splits(ticker, [
                {"d": row["d"], "o": float(row["o"]), "h": float(row["h"]),
                 "l": float(row["l"]), "c": float(row["c"]),   "v": int(row["v"])}
                for _, row in df.iterrows()
            ])

            out = CANDLES_DIR / f"{ticker}.json"
            if out.exists():
                try:
                    existing = json.loads(out.read_text())
                    candles  = _merge_candles(existing, candles)
                except Exception:
                    pass

            candles, refus = _reimposer(ticker, candles)

            # ⚠️ UN REFUS INTERDIT D'ÉCRIRE. Il ne se journalise pas pour
            # mémoire : il arrête le geste.
            #
            # Le 16/09 à 19h21, ce programme a refusé les 191 corrections
            # réceptionnées de Sothema — « l'état actuel n'est ni l'ancien ni le
            # corrigé » — puis a écrit sa propre série par-dessus. Les 220
            # ruptures de l'ancienne échelle sont revenues, et la publication
            # s'est bloquée. Le contrôle avait vu juste ; personne ne l'écoutait.
            #
            # « Conservez les données et indicateurs antérieurs valides lorsqu'un
            # nouvel import est refusé. » Ce qui est déjà sur le disque a été
            # réceptionné ; ce qui arrive ne l'a pas été.
            if refus:
                log.error(f"  ✗ {ticker}: {len(refus)} correction(s) réceptionnée(s) "
                          f"refusée(s) — fichier CONSERVÉ, rien n'est écrit")
                continue

            out.write_text(json.dumps(candles, separators=(",",":")))
            log.info(f"  ✓ {ticker}: {len(candles)} bougies (Médias24)")
            results[ticker] = len(candles)
            time.sleep(0.4)
        except Exception as e:
            log.warning(f"  ✗ {ticker}: {e}")
            time.sleep(0.3)

    return results


def run(xlsx_only: bool = False):
    log.info("═" * 60)
    log.info("BVC Candle Generator")
    log.info("═" * 60)

    log.info("\n[1/2] Génération depuis XLSX historique...")
    xlsx_results = generate_from_xlsx()
    log.info(f"  → {len(xlsx_results)} fichiers générés depuis XLSX")

    if xlsx_only:
        log.info("\nMode xlsx_only — fin.")
        return

    xlsx_tickers = set(xlsx_results.keys())
    log.info(f"\n[2/2] Récupération Médias24 pour les tickers sans XLSX ({len(TICKERS_ALL)-len(xlsx_tickers)} tickers)...")
    med24_results = generate_from_med24(skip_existing_tickers=xlsx_tickers)
    log.info(f"  → {len(med24_results)} fichiers générés depuis Médias24")

    total = len(xlsx_results) + len(med24_results)
    log.info(f"\n✅ Total: {total} fichiers candles générés dans pipeline/candles/")

    # Les sources datent parfois leurs cours d'un jour où la Bourse n'a pas
    # ouvert : le 14/08 (férié), Médias24 a rediffusé la clôture du 13 sous la
    # date du 14, et 43 fichiers ont pris une bougie fantôme. Le contrôle ne
    # peut se faire qu'ici, une fois tous les titres écrits : c'est à l'échelle
    # du marché que la rediffusion se voit, jamais titre par titre.
    try:
        from seance import (purger_seance_fantome, reparer_ohlc,
                            purger_suspensions, purger_seances_annulees)
    except ImportError:
        from pipeline.seance import (purger_seance_fantome, reparer_ohlc,
                                     purger_seances_annulees)

    # ⚠️ LA PURGE DÉCLARÉE PASSE EN PREMIER. Une séance annulée par l'opérateur
    # ne se devine pas : ses cours étaient authentiques. Si on la laissait, les
    # contrôles statistiques qui suivent raisonneraient sur un jour qui n'existe
    # plus.
    _da, _na, _ta = purger_seances_annulees()
    if _na:
        log.warning(f"   Séance(s) ANNULÉE(S) {', '.join(_da)} : {_na} bougies "
                    f"retirées de {len(_ta)} fichiers")

    _date_fantome, _n = purger_seance_fantome()
    if _date_fantome:
        log.warning(f"   Séance {_date_fantome} purgée : {_n} bougies retirées")
    _no, _fo = reparer_ohlc()
    _ns, _fs = purger_suspensions()
    if _ns:
        print(f"  Suspensions : {_ns} bougie(s) retirée(s) de {_fs} fichier(s)")
    if _no:
        log.warning(f"   OHLC : {_no} bougies élargies sur {_fo} tickers")

    all_results = {**xlsx_results, **med24_results}
    log.info(f"   Tickers couverts: {', '.join(sorted(all_results.keys()))}")
    missing = [t for t in TICKERS_ALL if t not in all_results]
    if missing:
        log.warning(f"   Tickers sans candles: {', '.join(missing)}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--xlsx-only", action="store_true", help="Ne générer que depuis les XLSX")
    args = p.parse_args()
    run(xlsx_only=args.xlsx_only)

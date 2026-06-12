#!/usr/bin/env python3
"""
sync_sentiment.py — Resynchronise SENTIMENT depuis les CSV NLP (whatsapp_analysis/output/)
Usage : python sync_sentiment.py [--dry-run]

Lit :
  whatsapp_analysis/output/stock_scores.csv    → smart, hype, mentions, classification
  whatsapp_analysis/output/final_rankings.csv  → alpha, win (p_outperform_1m), biais

Met à jour le bloc SENTIMENT dans update_data.py.
"""
import csv, sys, re
from pathlib import Path

ROOT         = Path(__file__).parent
SCORES_CSV   = ROOT / "whatsapp_analysis" / "output" / "stock_scores.csv"
RANKINGS_CSV = ROOT / "whatsapp_analysis" / "output" / "final_rankings.csv"
TARGET       = ROOT / "update_data.py"
DRY_RUN      = "--dry-run" in sys.argv


def _f(v, default=0.0):
    try: return float(v)
    except: return default


def load_scores():
    rows = {}
    with open(SCORES_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = r["ticker"].strip()
            if not t:
                continue
            rows[t] = {
                "smart":    round(_f(r.get("sm_weighted_sentiment", 0)), 3),
                "hype":     round(min(1.0, _f(r.get("conviction_score", 0))), 2),
                "mentions": int(_f(r.get("total_mentions", 0))),
                "classification": r.get("classification", "Neutre").strip(),
            }
    return rows


def load_rankings():
    rows = {}
    with open(RANKINGS_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = r["ticker"].strip()
            if not t:
                continue
            sig = r.get("signal", "NEUTRE").strip().upper()
            biais = "ACHAT" if sig in ("ACHAT", "ACHAT_FORT") else "NÉGATIF" if "VENTE" in sig else "NEUTRE"
            rows[t] = {
                "alpha": round(_f(r.get("alpha_12m", 0)), 1),
                "win":   round(_f(r.get("p_outperform_1m", 0.5)), 2),
                "biais": biais,
            }
    return rows


def build_sentiment(scores, rankings):
    tickers = sorted(set(list(scores.keys()) + list(rankings.keys())))
    entries = []
    for t in tickers:
        s = scores.get(t, {})
        r = rankings.get(t, {})
        smart     = s.get("smart", 0.0)
        hype      = s.get("hype",  0.5)
        mentions  = s.get("mentions", 0)
        classif   = s.get("classification", "Neutre")
        alpha     = r.get("alpha", 0.0)
        win       = r.get("win",   0.5)
        biais     = r.get("biais", "NEUTRE")
        # Contrarian : communauté haussière mais smart money négatif
        contrarian = (biais == "ACHAT" and smart < -0.15) or classif == "Controversé"
        entry = (
            f'    "{t}": {{"smart":{smart},"hype":{hype},"alpha":{alpha},'
            f'"win":{win},"mentions":{mentions},"biais":"{biais}","contrarian":{contrarian}}},'
        )
        entries.append(entry)
    return "SENTIMENT = {\n" + "\n".join(entries) + "\n}"


def update_file(new_block: str):
    content = TARGET.read_text(encoding="utf-8")
    lines   = content.split("\n")
    try:
        start = next(i for i, l in enumerate(lines) if l.startswith("SENTIMENT = {"))
        end   = next(i for i, l in enumerate(lines[start + 1:], start + 1) if l.strip() == "}")
    except StopIteration:
        print("❌ Impossible de localiser le bloc SENTIMENT dans update_data.py")
        sys.exit(1)
    new_lines = lines[:start] + new_block.split("\n") + lines[end + 1:]
    TARGET.write_text("\n".join(new_lines), encoding="utf-8")


TOTAL_MSGS = 896_907  # messages WhatsApp bruts (corpus complet, fixe)


def compute_meta(scores):
    """Calcule les stats du corpus depuis les CSV."""
    import datetime
    with open(SCORES_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    total_signals = sum(
        int(float(r.get("signal_ACHAT_FORT", 0) or 0)) +
        int(float(r.get("signal_ACHETER", 0) or 0)) +
        int(float(r.get("signal_RENFORCEMENT", 0) or 0)) +
        int(float(r.get("signal_VENTE", 0) or 0)) +
        int(float(r.get("signal_PANIQUE", 0) or 0)) +
        int(float(r.get("signal_EUPHORIE", 0) or 0))
        for r in rows
    )
    dates_first = [r["first_mention"][:10] for r in rows if r.get("first_mention", "").strip()]
    dates_last  = [r["last_mention"][:10]  for r in rows if r.get("last_mention",  "").strip()]
    years = 6
    if dates_first and dates_last:
        d1 = datetime.date.fromisoformat(min(dates_first))
        d2 = datetime.date.fromisoformat(max(dates_last))
        years = max(6, round((d2 - d1).days / 365, 1))
    return {
        "msgs":    f"{TOTAL_MSGS:,}".replace(",", " "),
        "signals": f"{total_signals:,}".replace(",", " "),
        "years":   int(years),
        "tickers": len(scores),
    }


def update_meta_in_index(meta: dict):
    """Met à jour le bloc META dans index.html."""
    idx = ROOT / "index.html"
    if not idx.exists():
        return
    content = idx.read_text(encoding="utf-8")
    new_block = (
        f'// ── MÉTADONNÉES CORPUS (synchronisé depuis whatsapp_analysis/output/) ────────\n'
        f'const META = {{\n'
        f'  msgs:    "{meta["msgs"]}",   // mentions boursières\n'
        f'  years:   {meta["years"]},           // années de données\n'
        f'  signals: "{meta["signals"]}",    // tous types de signaux\n'
        f'  tickers: {meta["tickers"]},          // tickers avec activité NLP\n'
        f'}};'
    )
    content = re.sub(
        r'// ── MÉTADONNÉES CORPUS.*?const META\s*=\s*\{[^}]+\};',
        new_block, content, flags=re.DOTALL
    )
    idx.write_text(content, encoding="utf-8")
    print(f"   index.html META mis à jour : {meta}")


def main():
    scores   = load_scores()
    rankings = load_rankings()
    new_block = build_sentiment(scores, rankings)
    meta      = compute_meta(scores)

    n = new_block.count('"smart"')
    print(f"{'[DRY RUN] ' if DRY_RUN else ''}SENTIMENT reconstruit — {n} tickers")
    print(f"  META: {meta}")

    if DRY_RUN:
        print("\n--- Aperçu (10 premières entrées) ---")
        for line in new_block.split("\n")[1:11]:
            print(line)
        return

    update_file(new_block)
    update_meta_in_index(meta)
    print(f"✅ update_data.py + index.html mis à jour")
    print("   Relance update_data.py ou le workflow BVC Data Update pour appliquer.")


if __name__ == "__main__":
    main()

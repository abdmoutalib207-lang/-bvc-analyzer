#!/usr/bin/env python3
"""Applique le correctif séance annulée sur la branche de travail.

Script temporaire et déterministe : chaque remplacement exige exactement un
bloc source connu. Il n'est pas destiné à rester dans main.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: bloc attendu {count} fois au lieu de 1")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"OK {path}")


replace_once(
    "pipeline/seance.py",
    '''def derniere_seance_connue(candles_dir=None):
    """Date de la séance la plus récente présente dans les chandelles.

    Sert de repère quand la source est muette : sans elle, rien ne permet de
    contredire une charge utile qui se date elle-même du jour. Renvoie une
    chaîne « AAAA-MM-JJ », ou "" si aucune chandelle n'est lisible.
    """
    d = Path(candles_dir) if candles_dir else CANDLES_DIR
    if not d.exists():
        return ""
    dernieres = []
    for f in d.glob("*.json"):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(s, list) and s:
            dernieres.append(s[-1].get("d") or "")
    return max(dernieres) if dernieres else ""
''',
    '''def derniere_seance_connue(candles_dir=None, avant=None):
    """Date de la séance la plus récente présente dans les chandelles.

    `avant` est une borne EXCLUSIVE ``AAAA-MM-JJ``. Elle est indispensable
    quand on traite après coup une séance annulée D : une chandelle réelle de
    D+1 peut déjà exister, mais aucun repli de D n'a le droit de voyager vers
    D ou vers le futur. Sans borne, le cycle 16 valide → 17 annulé → 18 réel
    ramenait à tort la référence du 17 sur le 18.

    Sans borne, conserve le comportement historique : dernière séance connue.
    Renvoie une chaîne « AAAA-MM-JJ », ou "" si aucune chandelle n'est lisible.
    """
    d = Path(candles_dir) if candles_dir else CANDLES_DIR
    if not d.exists():
        return ""
    borne = str(avant or "")[:10]
    dernieres = []
    for f in d.glob("*.json"):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(s, list) or not s:
            continue
        dates = [str(b.get("d") or "")[:10] for b in s]
        dates = [jour for jour in dates if jour and (not borne or jour < borne)]
        if dates:
            dernieres.append(max(dates))
    return max(dernieres) if dernieres else ""
''')

replace_once(
    "update_data.py",
    '            nouvelle = derniere_seance_connue() or ""\n',
    '            nouvelle = derniere_seance_connue(avant=str(idb_asof)[:10]) or ""\n')

replace_once(
    "update_data.py",
    '''            restantes = [str(v.get("asof") or "")[:10] for v in live_prices.values()]
            restantes = [d for d in restantes if d and not seance_annulee(d)]
            nouvelle = max(restantes) if restantes else ""
''',
    '''            borne = str(idb_asof or "")[:10]
            restantes = [str(v.get("asof") or "")[:10] for v in live_prices.values()]
            restantes = [d for d in restantes
                          if d and d < borne and not seance_annulee(d)]
            nouvelle = max(restantes) if restantes else ""
''')

replace_once(
    "update_data.py",
    '''    if precedent and not seance_annulee(str(precedent.get("asof") or "")[:10]):
''',
    '''    date_precedent = str(precedent.get("asof") or "")[:10]
    if (precedent and date_precedent and date_precedent < annulee
            and not seance_annulee(date_precedent)):
''')

replace_once(
    "update_data.py",
    '        masi["chg"] = precedent.get("change_pct")\n',
    '        masi["chg"] = None\n')

replace_once(
    "update_data.py",
    '    valides = sorted(d for d in seances if not seance_annulee(d))\n',
    '    valides = sorted(d for d in seances if d < annulee and not seance_annulee(d))\n')

replace_once(
    ".github/workflows/update_bvc.yml",
    '''      # ── 3b. CONTRÔLES BLOQUANTS — avant toute publication ──
''',
    '''      # ── 3a. SYNCHRONISER LE CACHE DÉRIVÉ ────────────────────
      # `update_data.py` peut ajouter/remplacer la bougie du jour. Le cache
      # `historical_data.json` doit alors décrire exactement la même série
      # AVANT que la garde bloquante ne compare cache et chandelles.
      - name: Synchroniser le cache historique des chandelles modifiées
        if: steps.gate.outputs.run == 'true' && github.event.inputs.dry_run != 'true'
        run: |
          TICKERS=$(git diff --name-only -- 'pipeline/candles/*.json' \\
            | sed -n 's#^pipeline/candles/\\(.*\\)\\.json$#\\1#p' \\
            | sort -u | tr '\\n' ' ')
          if [ -z "$TICKERS" ]; then
            echo "Aucune chandelle modifiée — cache inchangé"
            exit 0
          fi
          echo "Recalcul cache complet pour: $TICKERS"
          python pipeline/recalculer_cache.py --complet $TICKERS --ecrire

      # ── 3b. CONTRÔLES BLOQUANTS — avant toute publication ──
''')

replace_once(
    ".github/workflows/update_bvc.yml",
    '''            git add data.json
            if [ -d pipeline/candles ] && [ "$(ls pipeline/candles/*.json 2>/dev/null | wc -l)" -gt 0 ]; then
''',
    '''            git add data.json
            if [ -f pipeline/historical_data.json ]; then
              git add pipeline/historical_data.json
            fi
            if [ -d pipeline/candles ] && [ "$(ls pipeline/candles/*.json 2>/dev/null | wc -l)" -gt 0 ]; then
''')

print("Correctif déterministe appliqué.")

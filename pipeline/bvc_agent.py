#!/usr/bin/env python3
"""
BVC Terminal AI Agent
Agent IA autonome et auto-réparateur pour l'analyse de la Bourse de Casablanca.

Usage:
    python pipeline/bvc_agent.py
    python pipeline/bvc_agent.py "/analysis IAM"
    python pipeline/bvc_agent.py "/websearch résultats BCP 2026"
    python pipeline/bvc_agent.py "/repair"
    python pipeline/bvc_agent.py --verbose "/memory list"

Variables d'environnement:
    ANTHROPIC_API_KEY  — Clé API Anthropic (requis)

Slash commands:
    /websearch  <query>           Recherche web (actualités, cours BVC)
    /fetch      <target>          Données BVC locales (ticker, news, index)
    /code       <description>     Écrire et exécuter du code Python
    /repair     [composant]       Diagnostiquer et réparer le pipeline
    /analysis   <ticker>          Analyse technique + fondamentale
    /file       <path>            Lire/lister des fichiers du projet
    /memory     <action> [key]    Mémoire persistante de l'agent
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ─── Chemins ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
PIPELINE = Path(__file__).parent
MEMORY_PATH = PIPELINE / "agent_memory.json"

MODEL = "claude-opus-4-8"
MAX_TOKENS = 8192
MAX_ITERATIONS = 12

# ─── Schémas des outils ───────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "websearch",
        "description": (
            "Recherche web pour actualités financières BVC, cours, rapports d'entreprises, "
            "communiqués AMMC. Retourne titres, sources et extraits."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Requête (ex: 'BCP résultats S1 2026', 'MASI cours aujourd\\'hui')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Résultats voulus (1-10, défaut: 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_bvc",
        "description": (
            "Lit les données BVC stockées localement: cours, fondamentaux, "
            "historique de prix (candles), actualités, BPA."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": (
                        "Cible: ticker BVC en majuscules (IAM, ATW, BCP, SMI, MNG…), "
                        "'news', 'index', 'fondamentaux', 'bpa', 'all_tickers'"
                    )
                }
            },
            "required": ["target"]
        }
    },
    {
        "name": "execute_python",
        "description": (
            "Exécute du code Python en sandbox local. "
            "Pour calculs, statistiques, analyses de données. Timeout max 30s."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Code Python à exécuter"},
                "timeout": {
                    "type": "integer",
                    "description": "Timeout en secondes (max 30, défaut: 15)",
                    "default": 15
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "repair_pipeline",
        "description": (
            "Diagnostique et répare le pipeline BVC: valide les JSON, vérifie la syntaxe Python, "
            "teste la fraîcheur des données, inspecte les workflows GitHub Actions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "component": {
                    "type": "string",
                    "enum": ["all", "news", "data", "candles", "workflows", "dependencies"],
                    "description": "Composant à inspecter (défaut: all)"
                },
                "fix": {
                    "type": "boolean",
                    "description": "Appliquer corrections automatiques (défaut: false = diagnostique seul)"
                }
            }
        }
    },
    {
        "name": "analyze_ticker",
        "description": (
            "Analyse complète d'un titre BVC: technique (RSI, moyennes mobiles, plages 52 sem.), "
            "fondamentaux (PER, BPA, dividendes, ROE, croissance), actualités récentes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Symbole BVC en majuscules (IAM, ATW, BCP, SMI, MNG, HPS…)"
                },
                "mode": {
                    "type": "string",
                    "enum": ["technical", "fundamental", "news", "full"],
                    "description": "Type d'analyse (défaut: full)"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "file_ops",
        "description": "Lit, écrit ou liste les fichiers du projet BVC.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "list"],
                    "description": "Action à effectuer"
                },
                "path": {
                    "type": "string",
                    "description": (
                        "Chemin relatif depuis la racine du projet "
                        "(ex: 'news.json', 'pipeline/fetch_news.py', 'pipeline/candles/')"
                    )
                },
                "content": {
                    "type": "string",
                    "description": "Contenu à écrire (requis pour action=write)"
                }
            },
            "required": ["action", "path"]
        }
    },
    {
        "name": "memory_ops",
        "description": (
            "Mémoire persistante de l'agent: stocker et retrouver incidents, "
            "solutions, analyses historiques, notes de trading."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get", "set", "list", "delete", "search"],
                    "description": "Action mémoire"
                },
                "key": {
                    "type": "string",
                    "description": "Clé (ex: 'incidents/rss_403', 'analyses/IAM', 'solutions/news_stale')"
                },
                "value": {
                    "description": "Valeur à stocker (pour action=set)"
                },
                "query": {
                    "type": "string",
                    "description": "Texte à rechercher dans les mémos (pour action=search)"
                }
            },
            "required": ["action"]
        }
    }
]

SYSTEM_PROMPT = """Tu es l'Agent IA du Terminal BVC — assistant autonome et auto-réparateur spécialisé dans l'analyse de la Bourse de Casablanca (BVC/MASI).

## Identité
- **Nom**: Agent BVC
- **Spécialité**: Analyse financière marocaine, Bourse de Casablanca
- **Style**: Expert, précis, proactif, réponses structurées et concises

## Outils disponibles
1. **websearch** — Recherche web (actualités BVC, communiqués AMMC, résultats entreprises)
2. **fetch_bvc** — Données locales (cours, fondamentaux, actualités, historique candles)
3. **execute_python** — Exécution de code Python pour calculs et analyses
4. **repair_pipeline** — Diagnostic et réparation automatique du pipeline de données
5. **analyze_ticker** — Analyse technique + fondamentale d'un titre BVC
6. **file_ops** — Lecture/écriture des fichiers du projet
7. **memory_ops** — Mémoire persistante (incidents, solutions, analyses passées)

## Slash Commands
Quand tu reçois une commande /cmd, utilise l'outil correspondant directement:
- `/websearch <query>` → `websearch`
- `/fetch <target>` → `fetch_bvc`
- `/code <description>` → `execute_python` (génère et exécute le code)
- `/repair [composant]` → `repair_pipeline`
- `/analysis <ticker>` → `analyze_ticker`
- `/file <path>` → `file_ops` (read par défaut)
- `/memory <action> [key]` → `memory_ops`

## Règles de comportement
- Utilise les outils **immédiatement** sans demander de confirmation sauf si l'action est destructive
- **Mémorise** automatiquement les incidents importants et leurs solutions
- Si un outil retourne une erreur, diagnostique et tente une approche alternative
- Formatte les nombres: DH pour les valeurs en dirhams, % pour les pourcentages
- Timestamps en UTC ou heure Casablanca (UTC+1 hiver / UTC+0 été)
- Emojis sobres: ✅ succès ⚠️ avertissement ❌ erreur 📊 analyse 🔍 recherche 🔧 repair

## Contexte BVC
- Place: Casablanca Stock Exchange (BVC), Maroc
- Indice: MASI (Moroccan All Shares Index)
- Régulateur: AMMC (Autorité Marocaine du Marché des Capitaux)
- Monnaie: Dirham marocain (DH / MAD)
- Horaires: 9h30-15h30 Casablanca (UTC+1 hiver)"""


# ─── Implémentation des outils ────────────────────────────────────────────────

def _safe_path(path: str) -> Path:
    """Résout un chemin relatif et refuse les traversées hors du projet."""
    p = (ROOT / path).resolve()
    if not str(p).startswith(str(ROOT.resolve())):
        raise ValueError(f"Chemin refusé (hors projet): {path}")
    return p


def tool_websearch(query: str, max_results: int = 5) -> str:
    try:
        import requests

        headers = {"User-Agent": "Mozilla/5.0 (compatible; BVCAgent/1.0; +https://github.com)"}
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers=headers,
            timeout=10
        )
        resp.raise_for_status()

        # Extraction légère des résultats via regex
        import re
        titles = re.findall(r'class="result__a"[^>]*>([^<]+)</a>', resp.text)
        urls = re.findall(r'class="result__url"[^>]*>([^<]+)<', resp.text)

        results = list(zip(titles, urls))[:max_results]
        if not results:
            return f"Aucun résultat web pour: {query}"

        lines = [f"🔍 Résultats web pour: **{query}**\n"]
        for i, (title, url) in enumerate(results, 1):
            lines.append(f"{i}. **{title.strip()}** — {url.strip()}")
        return "\n".join(lines)

    except Exception as e:
        return (
            f"⚠️ Recherche web indisponible dans cet environnement: {e}\n"
            "Note: Le réseau est restreint ici — la recherche fonctionne dans GitHub Actions."
        )


def tool_fetch_bvc(target: str) -> str:
    target = target.strip().upper()

    if target == "NEWS":
        p = ROOT / "news.json"
        if not p.exists():
            return "❌ news.json introuvable"
        data = json.loads(p.read_text(encoding="utf-8"))
        articles = data.get("articles", [])[:10]
        lines = [f"📰 Actualités BVC — {data.get('count', len(articles))} articles (màj: {data.get('updated','?')})\n"]
        for a in articles:
            tickers = ", ".join(a.get("tickers", [])) or "—"
            sent = "✅" if a.get("sentiment") == "POSITIF" else ("❌" if a.get("sentiment") == "NEGATIF" else "◦")
            lines.append(f"{sent} [{a.get('source','?')}] **{a.get('title','?')}** ({tickers})")
        return "\n".join(lines)

    if target in ("FONDAMENTAUX", "FUNDAMENTALS"):
        p = ROOT / "fondamentaux.json"
        if not p.exists():
            return "❌ fondamentaux.json introuvable"
        data = json.loads(p.read_text(encoding="utf-8"))
        lines = [f"📊 Fondamentaux — {len(data)} tickers\n"]
        for ticker, f in list(data.items())[:25]:
            lines.append(
                f"- **{ticker}** | PER={f.get('per','?')}x fwd={f.get('forward_per','?')}x "
                f"| Div={f.get('div_yield','?')}% | {f.get('secteur','')}"
            )
        return "\n".join(lines)

    if target == "BPA":
        p = ROOT / "bpa.json"
        if not p.exists():
            return "❌ bpa.json introuvable"
        data = json.loads(p.read_text(encoding="utf-8"))
        lines = [f"💰 BPA & Dividendes — {len(data)} tickers\n"]
        for ticker, b in list(data.items())[:25]:
            lines.append(
                f"- **{ticker}**: BPA={b.get('bpa','?')} DH | "
                f"Div={b.get('div_dh','?')} DH | ROE={b.get('roe','?')}%"
            )
        return "\n".join(lines)

    if target == "ALL_TICKERS":
        for fname in ("financial_data.json", "data.json"):
            p = ROOT / fname
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                tickers = sorted(data.keys()) if isinstance(data, dict) else []
                return f"📋 {len(tickers)} tickers: {', '.join(tickers)}"
        return "❌ financial_data.json et data.json introuvables"

    if target in ("INDEX", "MASI"):
        for fname in ("financial_data.json", "data.json"):
            p = ROOT / fname
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "index" in data:
                    return f"📈 MASI:\n{json.dumps(data['index'], ensure_ascii=False, indent=2)}"
                return f"Données disponibles: {len(data)} tickers"
        return "❌ Données de marché introuvables"

    # Ticker individuel
    ticker = target
    sections = []

    candle_p = PIPELINE / "candles" / f"{ticker}.json"
    if candle_p.exists():
        candles = json.loads(candle_p.read_text(encoding="utf-8"))
        if isinstance(candles, list) and candles:
            last = candles[-1]
            prev = candles[-2] if len(candles) > 1 else last
            lc, pc = last.get("close", 0), prev.get("close", 0)
            chg = ((lc - pc) / pc * 100) if pc else 0
            sections.append(f"📈 **{ticker}** — {lc:.2f} DH ({chg:+.2f}%)")
            sections.append(
                f"   Open: {last.get('open','?')} | High: {last.get('high','?')} | "
                f"Low: {last.get('low','?')} | Vol: {last.get('volume','?')}"
            )
            sections.append(f"   Date: {last.get('date','?')} | {len(candles)} séances")

    fond_p = ROOT / "fondamentaux.json"
    if fond_p.exists():
        fond_data = json.loads(fond_p.read_text(encoding="utf-8"))
        if ticker in fond_data:
            f = fond_data[ticker]
            sections.append(f"\n📊 Fondamentaux:")
            sections.append(f"   Secteur: {f.get('secteur','?')}")
            sections.append(
                f"   PER: {f.get('per','?')}x | PER fwd: {f.get('forward_per','?')}x | "
                f"ROIC: {f.get('roic','?')}%"
            )
            sections.append(
                f"   Croissance CA: {f.get('croissance_ca','?')}% | BPA: {f.get('croissance_bpa','?')}%"
            )
            sections.append(
                f"   Div yield: {f.get('div_yield','?')}% | DPS 2026: {f.get('dps_2026','?')} DH"
            )
            sections.append(f"   Momentum: {f.get('momentum_fondamental','?')}")
            if f.get("catalyseur"):
                sections.append(f"   Catalyseur: {f['catalyseur']}")

    bpa_p = ROOT / "bpa.json"
    if bpa_p.exists():
        bpa_data = json.loads(bpa_p.read_text(encoding="utf-8"))
        if ticker in bpa_data:
            b = bpa_data[ticker]
            sections.append(f"\n💰 BPA & Dividendes:")
            sections.append(
                f"   BPA FY2025: {b.get('bpa','?')} DH | "
                f"Div: {b.get('div_dh','?')} DH | ROE: {b.get('roe','?')}%"
            )
            if b.get("note"):
                sections.append(f"   Note: {b['note']}")

    news_p = ROOT / "news.json"
    if news_p.exists():
        news_data = json.loads(news_p.read_text(encoding="utf-8"))
        related = [a for a in news_data.get("articles", []) if ticker in a.get("tickers", [])][:5]
        if related:
            sections.append(f"\n📰 Actualités ({len(related)}):")
            for a in related:
                sent = "✅" if a.get("sentiment") == "POSITIF" else ("❌" if a.get("sentiment") == "NEGATIF" else "◦")
                sections.append(f"   {sent} {a.get('title','?')} [{a.get('source','?')}] ({a.get('date','?')[:10]})")

    if not sections:
        return f"❌ Aucune donnée pour **{ticker}**. Symboles valides: IAM, ATW, BCP, SMI, MNG, HPS…"

    return "\n".join(sections)


def tool_execute_python(code: str, timeout: int = 15) -> str:
    timeout = min(max(int(timeout), 1), 30)

    dangerous = ["os.system(", "subprocess.run(", "subprocess.Popen(",
                 "__import__('os').system", "open('/etc", "open('/proc",
                 "socket.connect(", "urllib.request.urlopen("]
    for d in dangerous:
        if d in code:
            return f"❌ Code refusé: opération interdite ({d})"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(f"import sys\nsys.path.insert(0, {repr(str(ROOT))})\n")
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(ROOT)
        )
        stdout = result.stdout[:4000]
        stderr = result.stderr[:1500]

        if result.returncode == 0:
            return f"✅ Succès\n\n{stdout}" if stdout else "✅ Succès (aucune sortie)"
        else:
            return f"❌ Erreur (code {result.returncode})\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
    except subprocess.TimeoutExpired:
        return f"⏱️ Timeout après {timeout}s"
    except Exception as e:
        return f"❌ Erreur d'exécution: {e}"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def tool_repair_pipeline(component: str = "all", fix: bool = False) -> str:
    component = (component or "all").lower()
    lines = [f"🔧 Diagnostic pipeline BVC — {component}\n"]

    def check_json(path: Path, label: str):
        if not path.exists():
            lines.append(f"❌ {label}: fichier manquant")
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            size = path.stat().st_size
            lines.append(f"✅ {label}: JSON valide ({size/1024:.1f} Ko)")
            if isinstance(data, dict) and "updated" in data:
                lines.append(f"   Dernière màj: {data['updated']}")
        except json.JSONDecodeError as e:
            lines.append(f"❌ {label}: JSON invalide — {e}")

    def check_py(path: Path, label: str):
        if not path.exists():
            lines.append(f"❌ {label}: fichier manquant")
            return
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            capture_output=True, text=True
        )
        if r.returncode == 0:
            lines.append(f"✅ {label}: syntaxe OK")
        else:
            lines.append(f"❌ {label}: syntaxe erreur — {r.stderr[:150]}")

    if component in ("all", "news"):
        lines.append("### News")
        check_json(ROOT / "news.json", "news.json")
        check_py(PIPELINE / "fetch_news.py", "fetch_news.py")
        news_p = ROOT / "news.json"
        if news_p.exists():
            try:
                data = json.loads(news_p.read_text(encoding="utf-8"))
                updated = data.get("updated", "")
                if updated:
                    dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                    icon = "✅" if age_h < 2 else "⚠️"
                    lines.append(f"{icon} Ancienneté: {age_h:.1f}h")
            except Exception:
                pass

    if component in ("all", "data"):
        lines.append("\n### Financial Data")
        for fname in ("financial_data.json", "data.json", "fondamentaux.json", "bpa.json"):
            check_json(ROOT / fname, fname)
        check_py(PIPELINE / "collect_financial_data.py", "collect_financial_data.py")

    if component in ("all", "candles"):
        lines.append("\n### Candles")
        candles_dir = PIPELINE / "candles"
        if candles_dir.exists():
            files = list(candles_dir.glob("*.json"))
            valid = sum(1 for f in files if _try_json(f))
            lines.append(f"✅ {valid}/{len(files)} fichiers candles valides")
        else:
            lines.append("❌ pipeline/candles/ manquant")
        check_py(PIPELINE / "generate_candles.py", "generate_candles.py")

    if component in ("all", "workflows"):
        lines.append("\n### GitHub Actions")
        wf_dir = ROOT / ".github" / "workflows"
        if wf_dir.exists():
            for wf in sorted(wf_dir.glob("*.yml")):
                lines.append(f"✅ {wf.name} ({wf.stat().st_size} o)")
        else:
            lines.append("❌ .github/workflows/ manquant")

    if component in ("all", "dependencies"):
        lines.append("\n### Dépendances")
        req_p = ROOT / "requirements.txt"
        if req_p.exists():
            reqs = [l.strip() for l in req_p.read_text().splitlines() if l.strip() and not l.startswith("#")]
            lines.append(f"📦 {len(reqs)} packages dans requirements.txt")
            has_anthropic = any("anthropic" in r for r in reqs)
            lines.append(
                "✅ anthropic SDK présent" if has_anthropic
                else "⚠️ anthropic manquant dans requirements.txt — Agent IA inactif en CI"
            )

    if fix:
        lines.append("\n### Mode fix")
        lines.append("ℹ️ Les corrections sont appliquées au prochain run CI/pipeline")

    return "\n".join(lines)


def _try_json(path: Path) -> bool:
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True
    except Exception:
        return False


def tool_analyze_ticker(ticker: str, mode: str = "full") -> str:
    ticker = ticker.strip().upper()
    mode = (mode or "full").lower()
    out = [f"# Analyse {ticker} — {mode.upper()}", f"_{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n"]

    # ── Technique ──
    if mode in ("technical", "full"):
        candle_p = PIPELINE / "candles" / f"{ticker}.json"
        if candle_p.exists():
            candles = json.loads(candle_p.read_text(encoding="utf-8"))
            if isinstance(candles, list) and len(candles) > 0:
                closes = [c.get("close", 0) for c in candles if c.get("close")]
                volumes = [c.get("volume", 0) for c in candles if c.get("volume")]
                lc = closes[-1] if closes else 0
                pc = closes[-2] if len(closes) > 1 else lc
                chg = ((lc - pc) / pc * 100) if pc else 0

                out.append("## 📈 Technique")
                out.append(f"- Cours: **{lc:.2f} DH** ({chg:+.2f}% J-1) | {len(candles)} séances")

                if len(closes) >= 20:
                    ma20 = sum(closes[-20:]) / 20
                    out.append(f"- MM20: {ma20:.2f} DH ({'▲ au-dessus' if lc > ma20 else '▼ en-dessous'})")
                if len(closes) >= 50:
                    ma50 = sum(closes[-50:]) / 50
                    out.append(f"- MM50: {ma50:.2f} DH")

                n52 = min(252, len(closes))
                hi52, lo52 = max(closes[-n52:]), min(closes[-n52:])
                out.append(f"- Plage 52sem: {lo52:.2f} — {hi52:.2f} DH | Distance sommet: {((lc - hi52)/hi52*100):+.1f}%")

                if len(closes) >= 15:
                    gains = [max(closes[i] - closes[i-1], 0) for i in range(-14, 0)]
                    losses = [max(closes[i-1] - closes[i], 0) for i in range(-14, 0)]
                    ag, al = sum(gains) / 14, sum(losses) / 14
                    if al > 0:
                        rsi = 100 - 100 / (1 + ag / al)
                        sig = "⚠️ Suracheté" if rsi > 70 else ("⚠️ Survendu" if rsi < 30 else "✅ Neutre")
                        out.append(f"- RSI(14): **{rsi:.1f}** {sig}")

                if volumes:
                    avg_vol = sum(volumes[-20:]) / min(20, len(volumes))
                    out.append(f"- Volume: {volumes[-1]:,.0f} (moy 20j: {avg_vol:,.0f})")
        else:
            out.append("## 📈 Technique\n_Aucune donnée de cours disponible_")

    # ── Fondamentaux ──
    if mode in ("fundamental", "full"):
        fond_p = ROOT / "fondamentaux.json"
        bpa_p = ROOT / "bpa.json"
        fond_found = False

        if fond_p.exists():
            fond_data = json.loads(fond_p.read_text(encoding="utf-8"))
            if ticker in fond_data:
                fond_found = True
                f = fond_data[ticker]
                out.append("\n## 📊 Fondamentaux")
                out.append(f"- Secteur: **{f.get('secteur','?')}**")
                out.append(f"- PER: {f.get('per','?')}x | PER fwd: {f.get('forward_per','?')}x")
                out.append(f"- Croissance CA: {f.get('croissance_ca','?')}% | BPA: {f.get('croissance_bpa','?')}%")
                out.append(f"- ROIC: {f.get('roic','?')}% | WACC: {f.get('wacc','?')}% | Marge nette: {f.get('marge_nette','?')}%")
                out.append(f"- Div yield: {f.get('div_yield','?')}% | DPS 2026: {f.get('dps_2026','?')} DH")
                out.append(f"- Momentum: **{f.get('momentum_fondamental','?')}**")
                if f.get("catalyseur"):
                    out.append(f"- Catalyseur: {f['catalyseur']}")
                if f.get("risque"):
                    out.append(f"- Risque: {f['risque']}")

        if bpa_p.exists():
            bpa_data = json.loads(bpa_p.read_text(encoding="utf-8"))
            if ticker in bpa_data:
                fond_found = True
                b = bpa_data[ticker]
                out.append("\n## 💰 BPA & Dividendes")
                out.append(f"- BPA FY2025: **{b.get('bpa','?')} DH/action**")
                out.append(f"- Dividende: {b.get('div_dh','?')} DH | ROE: {b.get('roe','?')}% | Marge nette: {b.get('marge_nette','?')}%")
                if b.get("note"):
                    out.append(f"- Note: _{b['note']}_")

        if not fond_found:
            out.append("\n## 📊 Fondamentaux\n_Aucune donnée fondamentale disponible_")

    # ── Actualités ──
    if mode in ("news", "full"):
        news_p = ROOT / "news.json"
        if news_p.exists():
            news_data = json.loads(news_p.read_text(encoding="utf-8"))
            related = [a for a in news_data.get("articles", []) if ticker in a.get("tickers", [])]
            out.append(f"\n## 📰 Actualités récentes ({len(related)})")
            if related:
                for a in related[:8]:
                    sent = "✅" if a.get("sentiment") == "POSITIF" else ("❌" if a.get("sentiment") == "NEGATIF" else "◦")
                    out.append(f"- {sent} **{a.get('title','?')}**")
                    out.append(f"  [{a.get('source','?')}] — {a.get('date','?')[:10]}")
            else:
                out.append(f"_Aucune actualité récente pour {ticker} dans l'archive_")

    return "\n".join(out)


def tool_file_ops(action: str, path: str, content: str | None = None) -> str:
    try:
        p = _safe_path(path)
    except ValueError as e:
        return f"❌ {e}"

    if action == "list":
        target = p if p.is_dir() else p.parent
        if not target.exists():
            return f"❌ Répertoire introuvable: {path}"
        files = sorted(target.iterdir())
        lines = [f"📁 {target.relative_to(ROOT)}/\n"]
        for f in files:
            icon = "📁" if f.is_dir() else "📄"
            size = f" ({f.stat().st_size/1024:.1f} Ko)" if f.is_file() else ""
            lines.append(f"  {icon} {f.name}{size}")
        return "\n".join(lines)

    if action == "read":
        if not p.exists():
            return f"❌ Fichier introuvable: {path}"
        size = p.stat().st_size
        if size > 100_000:
            return f"⚠️ Fichier trop grand ({size/1024:.0f} Ko) — spécifiez une section"
        text = p.read_text(encoding="utf-8", errors="replace")
        ext = p.suffix.lstrip(".")
        return f"📄 **{path}** ({size} o)\n\n```{ext}\n{text[:8000]}\n```"

    if action == "write":
        if content is None:
            return "❌ content requis pour action=write"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"✅ Fichier écrit: {path} ({len(content)} caractères)"

    return f"❌ Action inconnue: {action}"


def tool_memory_ops(
    action: str,
    key: str | None = None,
    value: Any = None,
    query: str | None = None
) -> str:
    def load() -> dict:
        if MEMORY_PATH.exists():
            try:
                return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"entries": {}, "_meta": {"created": datetime.now(timezone.utc).isoformat()}}

    def save(mem: dict):
        mem.setdefault("_meta", {})["updated"] = datetime.now(timezone.utc).isoformat()
        MEMORY_PATH.write_text(json.dumps(mem, ensure_ascii=False, indent=2), encoding="utf-8")

    if action == "list":
        mem = load()
        entries = mem.get("entries", {})
        if not entries:
            return "📋 Mémoire vide"
        lines = [f"📋 Mémoire agent ({len(entries)} entrées)\n"]
        for k, v in sorted(entries.items()):
            preview = json.dumps(v, ensure_ascii=False)[:80] if not isinstance(v, str) else v[:80]
            lines.append(f"- **{k}**: {preview}")
        return "\n".join(lines)

    if action == "get":
        if not key:
            return "❌ key requis pour action=get"
        mem = load()
        val = mem.get("entries", {}).get(key)
        if val is None:
            return f"❌ Clé introuvable: {key}"
        return f"📋 **{key}**\n\n{json.dumps(val, ensure_ascii=False, indent=2)}"

    if action == "set":
        if not key:
            return "❌ key requis pour action=set"
        mem = load()
        mem.setdefault("entries", {})[key] = {
            "value": value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        save(mem)
        return f"✅ Mémorisé: **{key}**"

    if action == "delete":
        if not key:
            return "❌ key requis pour action=delete"
        mem = load()
        if key in mem.get("entries", {}):
            del mem["entries"][key]
            save(mem)
            return f"✅ Supprimé: {key}"
        return f"❌ Clé introuvable: {key}"

    if action == "search":
        if not query:
            return "❌ query requis pour action=search"
        mem = load()
        q = query.lower()
        found = [k for k, v in mem.get("entries", {}).items() if q in (k + json.dumps(v)).lower()]
        if not found:
            return f"🔍 Aucun résultat pour: {query}"
        lines = [f"🔍 {len(found)} résultats pour '{query}'\n"]
        lines.extend(f"- {k}" for k in found)
        return "\n".join(lines)

    return f"❌ Action inconnue: {action}"


# ─── Routeur d'outils ─────────────────────────────────────────────────────────

def execute_tool(name: str, inputs: dict) -> str:
    try:
        if name == "websearch":
            return tool_websearch(inputs["query"], inputs.get("max_results", 5))
        if name == "fetch_bvc":
            return tool_fetch_bvc(inputs["target"])
        if name == "execute_python":
            return tool_execute_python(inputs["code"], inputs.get("timeout", 15))
        if name == "repair_pipeline":
            return tool_repair_pipeline(inputs.get("component", "all"), inputs.get("fix", False))
        if name == "analyze_ticker":
            return tool_analyze_ticker(inputs["ticker"], inputs.get("mode", "full"))
        if name == "file_ops":
            return tool_file_ops(inputs["action"], inputs["path"], inputs.get("content"))
        if name == "memory_ops":
            return tool_memory_ops(
                inputs["action"],
                inputs.get("key"),
                inputs.get("value"),
                inputs.get("query")
            )
        return f"❌ Outil inconnu: {name}"
    except KeyError as e:
        return f"❌ Paramètre manquant pour {name}: {e}"
    except Exception as e:
        return f"❌ Erreur outil {name}: {type(e).__name__}: {e}"


# ─── Parsing des slash commands ───────────────────────────────────────────────

def parse_slash(text: str) -> str:
    """Convertit une /commande en message naturel pour Claude."""
    t = text.strip()
    cmd_map = {
        "/websearch": lambda a: f"Effectue une recherche web pour: {a}",
        "/fetch":     lambda a: f"Récupère les données BVC pour: {a}",
        "/code":      lambda a: f"Écris et exécute un script Python pour: {a}",
        "/repair":    lambda a: f"Diagnostique et répare le pipeline BVC{' (' + a + ')' if a else ''}",
        "/analysis":  lambda a: f"Effectue une analyse complète de {a}",
        "/file":      lambda a: f"Affiche le contenu du fichier: {a}",
        "/memory":    lambda a: f"Opération mémoire: {a}",
    }
    for cmd, formatter in cmd_map.items():
        if t.lower().startswith(cmd):
            args = t[len(cmd):].strip()
            return formatter(args)
    return t


# ─── Boucle agentique ─────────────────────────────────────────────────────────

def run_agent(user_input: str, verbose: bool = False) -> str:
    try:
        import anthropic
    except ImportError:
        return (
            "❌ SDK Anthropic non installé.\n"
            "  pip install anthropic\n"
            "  export ANTHROPIC_API_KEY=sk-ant-..."
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return (
            "❌ ANTHROPIC_API_KEY non défini.\n"
            "  export ANTHROPIC_API_KEY=sk-ant-..."
        )

    client = anthropic.Anthropic(api_key=api_key)
    message = parse_slash(user_input)
    messages: list[dict] = [{"role": "user", "content": message}]

    if verbose:
        print(f"🤖 Agent BVC | {MODEL}")
        print(f"📥 {message[:120]}{'…' if len(message) > 120 else ''}\n")

    for iteration in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if verbose and iteration == 0:
            n_thinking = sum(1 for b in response.content if b.type == "thinking")
            if n_thinking:
                print(f"💭 {n_thinking} bloc(s) de réflexion\n")

        if response.stop_reason == "end_turn":
            return "\n".join(b.text for b in response.content if b.type == "text")

        if response.stop_reason == "pause_turn":
            messages = [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response.content},
            ]
            continue

        tool_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_blocks:
            return "\n".join(b.text for b in response.content if b.type == "text")

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tb in tool_blocks:
            if verbose:
                print(f"🔧 {tb.name}({json.dumps(tb.input, ensure_ascii=False)[:80]})")
            result = execute_tool(tb.name, tb.input)
            if verbose:
                print(f"   → {result[:120]}{'…' if len(result) > 120 else ''}\n")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tb.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})

    return "⚠️ Limite d'itérations atteinte — résultat potentiellement incomplet."


# ─── CLI ──────────────────────────────────────────────────────────────────────

BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║           🏦  BVC Terminal AI Agent — Casablanca Stock           ║
║  /websearch  /fetch  /code  /repair  /analysis  /file  /memory  ║
╚══════════════════════════════════════════════════════════════════╝"""


def interactive_mode():
    print(BANNER)
    print("\nMode interactif — 'quit' pour quitter\n")
    while True:
        try:
            raw = input("BVC> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Au revoir!")
            break
        if not raw:
            continue
        if raw.lower() in ("quit", "exit", "q"):
            print("👋 Au revoir!")
            break
        print("\n⏳ Traitement…\n")
        print(run_agent(raw, verbose=True))
        print()


def main():
    args = sys.argv[1:]
    verbose = "--verbose" in args or "-v" in args
    args = [a for a in args if a not in ("--verbose", "-v")]

    if not args:
        interactive_mode()
        return

    user_input = " ".join(args)
    result = run_agent(user_input, verbose=verbose)
    print(result)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Enrichissement déterministe du flux commun BVC Analyzer / Radar BVC.

Le collecteur reste responsable de la collecte, du rattachement aux tickers et
du premier sentiment lexical. Ce passage ajoute ce qui manquait pour une veille
financière exploitable : importance, type d'événement, horizon et qualité de la
source. Il travaille sur news.json, donc le terminal, Radar BVC et le relais
Telegram reçoivent exactement la même qualification.

Aucun LLM et aucun accès réseau : même entrée => même sortie. Les champs source
sont conservés. Le sentiment n'est corrigé que lorsqu'un vocabulaire financier
fort donne un signal nettement plus clair que le premier passage.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEWS = ROOT / "news.json"

OFFICIAL = {
    "AMMC", "BVC Officiel", "Bank Al-Maghrib", "HCP", "MAP",
}
TRUSTED = {
    "Medias24", "L'Économiste", "BourseNews", "Finances News",
    "Reuters Maroc", "Financial Afrik", "Agence Ecofin Maroc", "Le Matin",
    "Les Inspirations Éco", "LeBrief", "Telquel Éco", "Jeune Afrique",
}

EVENTS = [
    ("operation_capital", re.compile(
        r"\b(opa|opv|ipo|augmentation de capital|division du nominal|split|"
        r"fusion|acquisition|cession|offre publique|rachat d.actions?)\b", re.I)),
    ("resultats", re.compile(
        r"\b(résultats?|résultat net|rnpg|chiffre d.affaires|ebitda|ebe|"
        r"bénéfice|profit|perte|marge|publication semestrielle|publication annuelle)\b", re.I)),
    ("dividende", re.compile(r"\b(dividende|coupon|détachement|distribution)\b", re.I)),
    ("contrat", re.compile(
        r"\b(remporte|adjudication|appel d.offres|contrat|marché public|commande|partenariat)\b", re.I)),
    ("reglementaire", re.compile(
        r"\b(ammc|visa|agrément|sanction|suspension de cotation|reprise de cotation|"
        r"communiqué financier|franchissement de seuil)\b", re.I)),
    ("macro", re.compile(
        r"\b(bank al.?maghrib|taux directeur|inflation|pib|hcp|déficit budgétaire|"
        r"balance commerciale|dirham|réserve de change|chômage)\b", re.I)),
    ("marche", re.compile(
        r"\b(masi|msi ?20|bourse de casablanca|cotation|séance|volume|capitalisation|clôture)\b", re.I)),
    ("commodites", re.compile(
        r"\b(or|argent|cuivre|cobalt|pétrole|brent|gaz naturel|charbon|phosphate)\b", re.I)),
    ("geopolitique", re.compile(
        r"\b(guerre|conflit|sanctions internationales|cessez-le-feu|iran|ukraine|"
        r"proche-orient|mer rouge)\b", re.I)),
]

POS = re.compile(
    r"\b(hausse|progression|croissance|accélération|record|gagne|remporte|"
    r"amélioration|rebond|reprise|excédent|bénéfice|profit|surperformance|"
    r"relèvement|dividende en hausse)\b", re.I)
NEG = re.compile(
    r"\b(baisse|recul|chute|perte|déficit|ralentissement|dégradation|"
    r"avertissement|profit warning|sanction|suspension|effondrement|"
    r"sous-performance|réduction du dividende)\b", re.I)

EVENT_WEIGHT = {
    "operation_capital": 34,
    "resultats": 30,
    "dividende": 27,
    "reglementaire": 27,
    "contrat": 23,
    "macro": 18,
    "marche": 13,
    "commodites": 12,
    "geopolitique": 10,
    "autre": 4,
}


def _event(text: str, category: str) -> str:
    for name, rx in EVENTS:
        if rx.search(text):
            return name
    if category == "geopolitique":
        return "geopolitique"
    if category == "commodites":
        return "commodites"
    if category == "macro":
        return "macro"
    return "autre"


def _source_tier(source: str) -> str:
    if source in OFFICIAL:
        return "A"
    if source in TRUSTED:
        return "B"
    return "C"


def _horizon(event: str) -> str:
    if event in {"operation_capital", "resultats", "dividende", "reglementaire"}:
        return "IMMEDIAT"
    if event in {"contrat", "macro", "marche", "commodites"}:
        return "COURT_TERME"
    return "CONTEXTE"


def _strong_sentiment(text: str) -> tuple[str, int]:
    pos = len({m.group(0).lower() for m in POS.finditer(text)})
    neg = len({m.group(0).lower() for m in NEG.finditer(text)})
    delta = pos - neg
    if delta >= 2:
        return "POSITIF", abs(delta)
    if delta <= -2:
        return "NEGATIF", abs(delta)
    return "NEUTRE", abs(delta)


def enrich_article(article: dict) -> dict:
    a = dict(article)
    title = str(a.get("title") or "")
    summary = str(a.get("summary") or a.get("description") or "")
    text = f"{title} {summary}"
    tickers = list(a.get("tickers") or [])
    event = _event(text, str(a.get("category") or ""))
    tier = _source_tier(str(a.get("source") or ""))

    score = EVENT_WEIGHT[event]
    score += {"A": 25, "B": 15, "C": 7}[tier]
    if tickers:
        score += 22
    if len(tickers) > 1:
        score += min(8, (len(tickers) - 1) * 2)
    if a.get("scope") == "MAROC":
        score += 6
    score = max(0, min(100, score))

    old_sent = str(a.get("sentiment") or "NEUTRE")
    strong, strength = _strong_sentiment(text)
    # Très conservateur : on ne touche au sentiment publié que si le second
    # lexique trouve au moins deux signaux concordants. L'ancien reste auditable.
    new_sent = old_sent
    if strong != "NEUTRE" and strength >= 2:
        if old_sent == "NEUTRE" or strong == old_sent or strength >= 3:
            new_sent = strong

    a["sentiment_lexical"] = old_sent
    a["sentiment"] = new_sent
    a["event_type"] = event
    a["source_tier"] = tier
    a["importance"] = score
    a["material"] = score >= 65
    a["horizon"] = _horizon(event)
    return a


def enrich_payload(payload: dict) -> dict:
    out = dict(payload)
    articles = [enrich_article(a) for a in (payload.get("articles") or [])]
    out["articles"] = articles
    out["count"] = len(articles)
    out["enrichment"] = {
        "version": 1,
        "methode": "deterministe",
        "champs": ["event_type", "source_tier", "importance", "material", "horizon"],
        "material_count": sum(1 for a in articles if a["material"]),
        "ticker_tagged_count": sum(1 for a in articles if a.get("tickers")),
    }
    return out


def main() -> int:
    if not NEWS.exists():
        raise SystemExit("news.json introuvable")
    payload = json.loads(NEWS.read_text(encoding="utf-8"))
    enriched = enrich_payload(payload)
    NEWS.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    e = enriched["enrichment"]
    print(
        f"News enrichies: {enriched['count']} · matérielles {e['material_count']} · "
        f"rattachées ticker {e['ticker_tagged_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

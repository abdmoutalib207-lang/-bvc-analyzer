#!/usr/bin/env python3
"""
Score fondamental v5.3 — composante 47% du score global
Calculé depuis fondamentaux.json (ROIC, PER, croissance, bilan)

Composantes [0-10]:
  Qualité       40%  Spread ROIC-WACC
  Croissance    30%  BPA (60%) + CA (40%) composite
  Valorisation  20%  Forward PER vs marché BVC
  Bilan         10%  Dette/EBITDA + cash conversion

Modificateurs: momentum, rerating, cycle_commodities
"""
import json
from pathlib import Path

_FOND_PATH = Path(__file__).parent.parent.parent / "fondamentaux.json"
_cache: dict = {}


def _load() -> dict:
    global _cache
    if not _cache:
        try:
            _cache = json.loads(_FOND_PATH.read_text(encoding="utf-8"))
        except Exception:
            _cache = {}
    return _cache


def reload():
    """Force le rechargement de fondamentaux.json (utile en CI)."""
    global _cache
    _cache = {}
    return _load()


def compute_fond_score(sym: str, fondamentaux: dict = None) -> float:
    """
    Retourne le score fondamental [0-10].
    fondamentaux: dict optionnel — si None, chargé depuis fondamentaux.json.
    Retourne 5.0 si le ticker est absent du fichier.
    """
    data = fondamentaux if fondamentaux is not None else _load()
    f = data.get(sym, {})
    if not f:
        return 5.0

    # QUALITÉ (40%) — spread ROIC-WACC : capacité à créer de la valeur
    roic   = float(f.get("roic") or 10)
    wacc   = float(f.get("wacc") or 10)
    spread = roic - wacc
    if   spread >= 15: q = 9.5
    elif spread >= 10: q = 8.5
    elif spread >= 5:  q = 7.0
    elif spread >= 2:  q = 6.0
    elif spread >= 0:  q = 5.0
    elif spread >= -3: q = 3.5
    else:              q = 2.0

    # CROISSANCE (30%) — BPA 60% + CA 40%
    cbpa   = float(f.get("croissance_bpa") or 0)
    cca    = float(f.get("croissance_ca")  or 0)
    growth = cbpa * 0.6 + cca * 0.4
    if   growth >= 100: g = 10.0
    elif growth >= 50:  g = 9.0
    elif growth >= 25:  g = 7.5
    elif growth >= 10:  g = 6.5
    elif growth >= 5:   g = 5.5
    elif growth >= 0:   g = 4.5
    elif growth >= -10: g = 3.0
    else:               g = 1.5

    # VALORISATION (20%) — Forward PER vs marché BVC (médiane ≈ 17-20x)
    fper = float(f.get("forward_per") or 15)
    if   fper <= 0:  v = 5.0   # aberrant → neutre
    elif fper <= 8:  v = 9.5   # très décoté
    elif fper <= 12: v = 8.5   # décoté
    elif fper <= 17: v = 7.0   # juste valeur
    elif fper <= 25: v = 5.5   # légèrement premium
    elif fper <= 35: v = 4.0   # premium
    elif fper <= 50: v = 2.5   # très premium
    else:            v = 1.5   # spéculatif

    # BILAN (10%) — dette/EBITDA + cash conversion
    #
    # ⚠️ `X or défaut` prend UNE VALEUR pour UNE ABSENCE quand cette valeur
    # vaut zéro. Défaut réel, signalé par l'audit externe du 09/09/2026.
    #
    # ⚠️ MAIS LE CORRECTIF NAÏF ÉTAIT FAUX, et l'auditeur l'avait pressenti en
    # écrivant qu'« une dette nette nulle ne signifie pas automatiquement le
    # meilleur bilan possible ». Mesuré le 10/09 : `fondamentaux.json` compte
    # HUIT zéros exacts — six banques, un assureur, un agroalimentaire. Pour un
    # établissement financier, le ratio dette nette / EBITDA n'a pas de sens :
    # ce zéro est un REMPLISSAGE, pas une mesure. Traiter ces zéros comme un
    # bilan sain relevait 19 titres de +0,08 sur la foi d'un blanc.
    #
    # Le fichier ne permet PAS de distinguer « mesuré à zéro » de « sans
    # objet » — les deux s'écrivent 0.0. Tant que la donnée ne porte pas cette
    # distinction, on ne l'invente pas : le zéro n'est retenu comme mesure que
    # là où le ratio a un sens, et les secteurs financiers gardent le
    # comportement antérieur. C'est une limite de la DONNÉE, consignée comme
    # telle plutôt que masquée par une hypothèse.
    # Relevé le 10/09 : les huit zéros sont ATW, BCP, BOA, CDM, CFGB, CIH
    # (« Banque »), WAF (« Assurance ») et CSR (« Agroalimentaire - Sucre »).
    # Seul ce dernier est une société industrielle, pour qui le ratio a un
    # sens — son zéro est donc retenu comme mesure, avec la réserve qu'aucune
    # source primaire ne l'a confirmé à ce jour.
    _SANS_OBJET = ("Banque", "Assurance", "Société de financement", "Leasing")
    _dne = f.get("dette_nette_ebitda")
    _sect = f.get("secteur") or ""
    if _dne == 0 and any(_sect.startswith(s) for s in _SANS_OBJET):
        _dne = None                      # sans objet : on ne conclut rien
    dne = float(_dne) if _dne is not None else 1.0
    _cc = f.get("cash_conversion")
    cc  = float(_cc) if _cc is not None else 70
    if   dne < 0:   bs = 9.0   # trésorerie nette positive
    elif dne < 0.5: bs = 8.5
    elif dne < 1.5: bs = 7.0
    elif dne < 2.5: bs = 5.5
    elif dne < 3.5: bs = 4.0
    elif dne < 5.0: bs = 2.5
    else:           bs = 1.5
    if cc >= 85:    bs = min(10.0, bs + 0.5)
    elif cc < 40:   bs = max(0.0,  bs - 0.5)

    # Score composite
    fond = q * 0.40 + g * 0.30 + v * 0.20 + bs * 0.10

    # Modificateurs
    mom = str(f.get("momentum_fondamental") or "").lower()
    if "très positif" in mom or "tres positif" in mom:
        fond += 0.5
    elif "positif" in mom:
        fond += 0.25
    elif "négatif" in mom or "negatif" in mom:
        fond -= 0.5

    if f.get("rerating"):
        fond += 0.3

    cyc = str(f.get("cycle_commodities") or "").lower()
    if cyc == "bullish":
        fond += 0.2
    elif cyc == "bearish":
        fond -= 0.2

    return round(min(max(fond, 0.0), 10.0), 2)


def score_all(fondamentaux: dict = None) -> dict:
    """Retourne {sym: fond_score} pour tous les tickers dans fondamentaux.json."""
    data = fondamentaux if fondamentaux is not None else _load()
    return {sym: compute_fond_score(sym, data) for sym in data}

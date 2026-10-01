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


# ⚠️ LES RATIOS CALCULÉS SUR COMPTES PUBLIÉS PRIMENT — 01/10/2026, décision
# d'Abd Moutalib (R8), après mesure. Au 01/10 : 79 ratios calculés sur 31
# titres hors MSA (ROIC, dette nette / EBITDA, conversion de trésorerie) ; la
# note fondamentale bouge sur 28, et 10 titres changent de palier sur les
# notes publiées le jour même (9 vers le bas, SNA vers le haut). Principe posé par lui : « rectifier les anciens calculs faux grâce
# aux publications, et continuer la chronologie avec les nouvelles ». Dès
# qu'un ratio est calculé dans `ratios_publies` (pipeline/ratios_financiers.py,
# chaque fait avec sa page), la note le lit à la place de la valeur saisie ;
# les prochains ratios calculés s'appliqueront donc d'eux-mêmes.
# La valeur saisie reste dans le fichier, intacte : elle n'est plus lue que
# faute de ratio calculé.
# ⚠️ Pas de backtest possible : les ratios calculés n'existent que depuis le
# 29/09/2026. Le remplacement rend la note plus honnête, il ne prouve pas
# qu'elle prédit mieux.
RATIOS_EN_VERIFICATION = {
    # Un titre ici garde ses valeurs saisies, avec le motif, jusqu'au recoupement.
    "MSA": "ROIC calculé de 47,6 % contre 17 saisi — capital investi d'un "
           "concessionnaire portuaire à recouper avant bascule (01/10/2026)",
}


def _publie(f: dict, sym: str, cle: str):
    """Le ratio calculé sur comptes publiés, ou None. Seule une valeur
    numérique compte : « sans objet » n'est pas une mesure."""
    if sym in RATIOS_EN_VERIFICATION:
        return None
    x = (f.get("ratios_publies") or {}).get(cle)
    v = x.get("valeur") if isinstance(x, dict) else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def ratio_effectif(f: dict | None, sym: str, cle: str) -> dict | None:
    """LA valeur d'un ratio que tout le moteur doit lire — note, alertes,
    écran. {"valeur", "origine", "date"} ou None. Fonction pure.

    ⚠️ POURQUOI UNE SEULE PORTE — 01/10/2026. Le jour où la note est passée
    aux ratios calculés, les alertes sont restées sur la saisie : ADI
    affichait « dette critique 5,5× l'EBITDA » pendant que sa note lisait
    2,26× (audit externe du 01/10). Deux lectures d'un même ratio finissent
    toujours par diverger ; il n'y en a plus qu'une.
    """
    f = f or {}
    v = _publie(f, sym, cle)
    if v is not None:
        x = f["ratios_publies"][cle]
        return {"valeur": v, "origine": "comptes publiés", "date": x.get("date"),
                "formule": x.get("formule")}
    s = f.get(cle)
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return {"valeur": float(s), "origine": "saisie", "date": f.get("date_maj"),
                "source": f.get("source")}
    return None


def compute_fond_score(sym: str, fondamentaux: dict = None,
                       per_publie: float | None = None) -> float:
    """
    Retourne le score fondamental [0-10].
    fondamentaux: dict optionnel — si None, chargé depuis fondamentaux.json.
    per_publie: PER sur douze mois glissants calculé sur les comptes publiés
        (cours du jour ÷ BPA 12 mois). Prime sur `forward_per` quand il existe.
    Retourne 5.0 si le ticker est absent du fichier.
    """
    data = fondamentaux if fondamentaux is not None else _load()
    f = data.get(sym, {})
    if not f:
        return 5.0

    # QUALITÉ (40%) — spread ROIC-WACC : capacité à créer de la valeur
    _r     = ratio_effectif(f, sym, "roic") or {}
    # ⚠️ Une saisie à 0 retombe sur 10 (`or 10`), comportement antérieur gardé.
    roic   = _r["valeur"] if _r.get("origine") == "comptes publiés" else float(f.get("roic") or 10)
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
    # ⚠️ LE PER PUBLIÉ PRIME SUR LE « FORWARD » SAISI — 01/10/2026, décision
    # d'Abd Moutalib (R8), après mesure. `forward_per` est une saisie de mai,
    # sans méthode : 12,5 pour ADI quand ses comptes donnent 19,4 et DATA+
    # 18,6 ; 1 634,59 pour RDS. Audit externe de la fiche ADI du 01/10. Sur
    # 37 titres, 16 s'écartaient de plus de 30 % de l'estimation DATA+.
    # Mesure au 01/10 (notes de 14h56) : 63 titres sur 76 ont un PER sur
    # douze mois publié ; 38 notes bougent, 9 paliers changent. Trois options
    # mesurées (PER publié, DATA+ 2026e, valorisation neutralisée) ; celle-ci
    # retenue parce qu'elle ne lit que des faits sourcés.
    # ⚠️ C'est un PER RÉALISÉ, pas prévisionnel : la grille de seuils
    # (8 / 12 / 17 / 25 / 35 / 50) n'a pas été recalibrée. Un titre en perte
    # n'a pas de PER (`_per` rend None) et garde la saisie.
    fper = (float(per_publie) if isinstance(per_publie, (int, float)) and per_publie > 0
            else float(f.get("forward_per") or 15))
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
    # ⚠️ LE VOCABULAIRE DES SECTEURS A CHANGÉ LE 17/09/2026, ET CETTE LISTE EN
    # DÉPEND. Elle citait « Société de financement » et « Leasing », deux
    # libellés de l'ancienne taxonomie maison qui n'existent plus : le
    # référentiel de la cote dit « Finance ». Une liste qui nomme des secteurs
    # disparus ne protège plus personne — elle attend qu'une société de
    # financement affiche une dette nette nulle pour se tromper en silence.
    #
    # ⚠️ Vérifié avant la bascule : sur les huit titres à dette nette nulle
    # (ATW, BCP, BOA, CDM, CFGB, CIH, WAF, CSR), AUCUN ne change de traitement,
    # et aucun titre au secteur « Finance » n'a de dette nette nulle. Aucune
    # note ne bouge (R8).
    _SANS_OBJET = ("Banque", "Assurance", "Finance")
    _dne = (ratio_effectif(f, sym, "dette_nette_ebitda") or {}).get("valeur")
    _sect = f.get("secteur") or ""
    if _dne == 0 and any(_sect.startswith(s) for s in _SANS_OBJET):
        _dne = None                      # sans objet : on ne conclut rien
    dne = float(_dne) if _dne is not None else 1.0
    _cc = (ratio_effectif(f, sym, "cash_conversion") or {}).get("valeur")
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

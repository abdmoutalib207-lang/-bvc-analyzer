#!/usr/bin/env python3
"""Sentiment d'actualité par émetteur — l'entrée manquante du pilier NLP.

⚠️ CE QU'IL FAUT SAVOIR AVANT DE LIRE LE CODE
─────────────────────────────────────────────
Le pilier NLP pèse 28 % du score v5.3 et n'en explique en pratique que 2,6 % :
son entrée est une table de sentiment ÉCRITE EN DUR dans `update_data.py`,
couvrant 34 titres sur 80, d'écart-type 0,078 contre 1,1 pour les deux autres
piliers. Quarante-neuf titres y sont strictement neutres.

Ce module apporte une seconde entrée : le sentiment des articles rattachés à
l'émetteur. Il ne change AUCUNE pondération — R8 reste intact. Il remplit une
entrée creuse, il ne redistribue pas les poids.

⚠️ CE QUE LE FLUX PERMET AUJOURD'HUI, ET CE QU'IL NE PERMET PAS
───────────────────────────────────────────────────────────────
Mesuré le 22/09 sur 300 articles :

    rattachés à un titre                    72
    dont PORTANT un sentiment                8   sur 6 titres
    dépôts AMMC rattachés                   37   sentiment NEUTRE par
                                                 construction

Les dépôts réglementaires sont la meilleure matière — ils nomment l'émetteur et
font foi — mais `annotate_provenance()` leur impose `sentiment = "NEUTRE"`,
parce que nous lisons l'INDEX et jamais le PDF (`document_content_verified` est
faux). Nous savons que Sonasid a publié ses résultats ; nous ne savons pas
s'ils sont bons. C'est une limite honnête, et elle borne ce module.

Le signal disponible vient donc de la presse : « Sonasid : hausse de 72 % du
RNPG », « Vicenne : bénéfice en hausse de 15 % ». Ces titres-là sont justes.
Ils sont seulement peu nombreux.

⚠️ DEUX GARDE-FOUS, ET AUCUN N'EST DÉCORATIF
────────────────────────────────────────────
1. **Un seuil de preuve.** Une seule manchette ne déplace pas un score. Il en
   faut au moins deux, d'articles distincts. Sans ce seuil, un titre gagnerait
   un demi-point parce qu'un journal a écrit « hausse » une fois.

2. **Une influence bornée.** La contribution est plafonnée à ±0,10 sur
   `smart`, soit ±0,5 point sur dix au pilier, soit ±0,14 sur le score final.
   C'est l'ordre de grandeur de ce que la table existante produit déjà
   (amplitude −0,36 à +0,085). Sans ce plafond, une entrée neuve écraserait
   l'ancienne et changerait DE FAIT le poids du pilier — ce que R8 interdit
   sans backtesting.

⚠️ ET UN BIAIS QU'IL FAUT DIRE. Sur le relevé du 22/09, les huit articles
porteurs de sentiment sont TOUS positifs. Le flux entier compte 36 positifs
pour 18 négatifs. Le lexique attrape mieux la bonne nouvelle que la mauvaise,
qu'un communiqué réglementaire formule sobrement. Le seuil et le plafond
limitent le dégât ; ils ne le suppriment pas. À surveiller quand la couverture
grandira.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
NEWS = RACINE / "news.json"

# Nombre minimal d'articles PORTEURS DE SENTIMENT pour qu'un titre bouge.
# Deux, parce qu'une seule manchette n'est pas une information : c'est une
# formulation. Le projet emploie déjà ce raisonnement pour le corpus WhatsApp,
# où le score de confiance exige « plus de 10 mentions ».
MIN_ARTICLES = 2

# Plafond de la contribution sur `smart`, dans les unités de `smart` ([-1,+1]).
# ±0,10 place la contribution dans l'ordre de grandeur de la table existante
# (−0,36 à +0,085) sans pouvoir la dominer.
PLAFOND = 0.10

# Au-delà, un article ne décrit plus la situation courante de l'émetteur.
# Trente jours : la même fenêtre que celle des dépôts réglementaires, pour ne
# pas faire cohabiter deux notions de fraîcheur dans le même produit.
FENETRE_JOURS = 30

# Poids d'un article selon son importance (0–100), posée par `enrich_news`.
# Un article matériel compte double d'un entrefilet ; aucun ne compte zéro,
# sinon le seuil de preuve deviendrait illusoire.
def _poids_article(article: dict) -> float:
    importance = article.get("importance")
    if not isinstance(importance, (int, float)):
        return 1.0
    return 1.0 + max(0.0, min(1.0, importance / 100.0))


def sentiment_par_titre(articles: list, maintenant: datetime | None = None) -> dict:
    """Renvoie {ticker: {"sent", "n", "positifs", "negatifs"}}.

    Fonction pure : elle ne lit ni disque ni réseau. `sent` est dans [-1, +1]
    AVANT plafonnement — le plafond s'applique à la contribution, pas à la
    mesure, pour que le relevé publié dise la vérité sur ce qu'on a observé.

    Seuls les articles PORTEURS d'un sentiment comptent. Un article neutre
    n'est pas une demi-voix : il n'en est pas une.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    limite = (maintenant - timedelta(days=FENETRE_JOURS)).isoformat()
    par: dict[str, dict] = {}
    for a in articles or []:
        # ⚠️ Un flux venu du réseau peut contenir n'importe quoi. Le moteur ne
        # doit pas tomber sur une ligne malformée : elle est ignorée, et les
        # autres comptent normalement.
        if not isinstance(a, dict):
            continue
        sens = a.get("sentiment")
        if sens not in ("POSITIF", "NEGATIF"):
            continue
        if str(a.get("date") or "") < limite:
            continue
        poids = _poids_article(a)
        for t in (a.get("tickers") or []):
            e = par.setdefault(t, {"pour": 0.0, "total": 0.0, "n": 0,
                                   "positifs": 0, "negatifs": 0})
            e["pour"] += poids if sens == "POSITIF" else -poids
            e["total"] += poids
            e["n"] += 1
            e["positifs" if sens == "POSITIF" else "negatifs"] += 1
    return {
        t: {"sent": round(e["pour"] / e["total"], 4) if e["total"] else 0.0,
            "n": e["n"], "positifs": e["positifs"], "negatifs": e["negatifs"]}
        for t, e in par.items()
    }


def contribution(mesure: dict | None) -> float:
    """La part que ce sentiment a le droit d'ajouter à `smart`.

    ⚠️ Zéro tant que le seuil de preuve n'est pas atteint. Renvoyer une
    fraction « proportionnelle à la confiance » reviendrait à agir sur une
    seule manchette en prétendant ne pas le faire.
    """
    if not mesure or mesure.get("n", 0) < MIN_ARTICLES:
        return 0.0
    return max(-PLAFOND, min(PLAFOND, float(mesure.get("sent") or 0.0) * PLAFOND))


def charger(chemin: Path | None = None) -> dict:
    """Le relevé par titre depuis `news.json`, ou {} si le fichier manque.

    ⚠️ Un flux absent ou illisible ne doit jamais faire tomber le moteur : le
    pilier NLP retombe alors sur sa seule table, exactement comme avant.
    """
    f = chemin or NEWS
    try:
        articles = json.loads(f.read_text(encoding="utf-8")).get("articles") or []
    except (OSError, json.JSONDecodeError, AttributeError):
        return {}
    return sentiment_par_titre(articles)


def main() -> int:
    mesures = charger()
    retenus = {t: m for t, m in mesures.items() if m["n"] >= MIN_ARTICLES}
    print(json.dumps({
        "titres_avec_sentiment": len(mesures),
        "titres_au_dessus_du_seuil": len(retenus),
        "seuil": MIN_ARTICLES,
        "plafond_sur_smart": PLAFOND,
        "detail": {t: {**m, "contribution": round(contribution(m), 4)}
                   for t, m in sorted(mesures.items())},
        "_lecture": (f"seuls les {len(retenus)} titres au-dessus du seuil "
                     f"reçoivent une contribution ; les autres restent à zéro"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

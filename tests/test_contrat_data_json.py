"""Le contrat entre le moteur et le frontend — le test le plus rentable.

Le 29/06/2026, `to_legacy_format()` a cessé d'émettre trois champs : `delta`,
`vol` et `win` (le pipeline écrivait `volume` et `win_rate`). `mergeLive` a
écrasé les valeurs statiques avec `undefined`, et le terminal a planté sur un
`.toFixed()` — **écran blanc en production, sans aucun signal préalable**.

Ce fichier fige le contrat. Si un champ disparaît, l'intégration continue vire
au rouge avant que quiconque ouvre la page.

⚠️ Un champ ajouté ne casse rien et ne doit pas faire échouer le test : le
contrat porte sur ce qui doit être PRÉSENT, pas sur l'absence de nouveautés.
"""

import pytest

# Champs que le frontend lit sans garde et qui, absents, cassent le rendu ou
# affichent « — » à la place d'une valeur. Ne retirer une entrée qu'après avoir
# vérifié dans index.html que plus rien ne la lit.
CHAMPS_OBLIGATOIRES = {
    # identité
    "symbol", "name", "sector", "code_bvc",
    # cotation
    "price", "chg", "vol", "open", "close", "cap",
    # scores et signaux
    "bvc", "v53", "sig", "sigBvc", "score_tech", "nlp", "delta", "poids",
    # fondamentaux
    "pe", "pb", "div", "bpa", "upside",
    # technique
    "rsi", "ma20", "ma50", "ma200", "macd", "macd_signal", "macd_hist",
    "bb_upper", "bb_mid", "bb_lower", "stoch_k", "stoch_d", "obv", "adx",
    "h52w", "l52w", "h90", "l90",
    # corpus et smart money
    "bull", "bear", "base", "win", "alpha",
    # présentation
    "setup", "biais", "conv", "flags", "warn", "warnMsg", "bonus",
    # provenance
    "_meta",
}

CHAMPS_META = {"source_prix", "source_fond", "prix_asof", "stale",
               "confidence", "n_candles", "generated_at"}

NUMERIQUES = {"price", "chg", "vol", "bvc", "v53", "score_tech", "nlp",
              "rsi", "ma20", "ma50", "ma200", "upside"}


def test_aucun_champ_obligatoire_ne_manque(titres):
    manques = {}
    for sym, t in titres.items():
        absents = CHAMPS_OBLIGATOIRES - set(t)
        if absents:
            manques[sym] = sorted(absents)
    assert not manques, f"champs disparus du contrat : {manques}"


def test_bloc_meta_complet(titres):
    """Sans `_meta`, le frontend suppose `stale: true` et `confidence: 0`."""
    manques = {}
    for sym, t in titres.items():
        absents = CHAMPS_META - set(t.get("_meta") or {})
        if absents:
            manques[sym] = sorted(absents)
    assert not manques, f"blocs _meta incomplets : {manques}"


@pytest.mark.parametrize("champ", sorted(NUMERIQUES))
def test_champs_numeriques_sont_des_nombres(titres, champ):
    """Une chaîne là où le frontend attend un nombre casse `.toFixed()`."""
    faux = {s: repr(t[champ]) for s, t in titres.items()
            if t.get(champ) is not None and not isinstance(t[champ], (int, float))}
    assert not faux, f"champ `{champ}` non numérique : {faux}"


def test_signaux_dans_le_vocabulaire_connu(titres):
    """Un signal inconnu ne serait pas stylé par le frontend."""
    # ⚠️ Vocabulaire relevé dans `update_data.py`, PAS dans la documentation :
    # le CLAUDE.md n'annonce que ACHETER / SURVEILLER / ÉVITER, alors que le
    # moteur émet aussi ATTENDRE, ÉVITER FORT et ACHAT FORT. Écrire ce test a
    # révélé l'écart. Les étoiles portent l'intensité et sont retirées avant
    # comparaison ; `EVITER` sans accent existe côté `sigBvc`.
    connus = {"ACHAT FORT", "ACHAT", "ACHETER", "SURVEILLER", "ATTENDRE",
              "ÉVITER", "ÉVITER FORT", "EVITER", "NEUTRE",
              "Données insuffisantes"}
    vus = set()
    for t in titres.values():
        for cle in ("sig", "sigBvc"):
            v = (t.get(cle) or "").replace("★", "").strip()
            if v:
                vus.add(v)
    assert vus <= connus, f"signaux hors vocabulaire : {vus - connus}"


def test_symbole_coherent_avec_la_cle(titres):
    incoherents = {k: t.get("symbol") for k, t in titres.items()
                   if t.get("symbol") != k}
    assert not incoherents, f"symboles incohérents : {incoherents}"


def test_pas_de_signal_sans_confiance(titres):
    """Anti-pattern : « signal sans confidence ».

    Sous `confidence <= 1`, le terminal doit afficher « Données insuffisantes »
    plutôt qu'un signal. Un score calculé sur données périmées ou entièrement
    issues d'un repli est trompeur.
    """
    fautifs = {}
    for sym, t in titres.items():
        conf = (t.get("_meta") or {}).get("confidence")
        sig = (t.get("sig") or "").replace("★", "").strip()
        if conf is not None and conf <= 1 and sig in {"ACHETER", "ÉVITER", "EVITER"}:
            fautifs[sym] = f"confiance={conf} mais signal={sig}"
    assert not fautifs, f"signaux tranchés sur données insuffisantes : {fautifs}"

#!/usr/bin/env python3
"""Les niveaux d'un titre — en distinguant ce qui est un FAIT d'une CONVENTION.

⚠️ CE QUI SÉPARE CE MODULE D'UN COMMENTAIRE TECHNIQUE ORDINAIRE
───────────────────────────────────────────────────────────────
Un briefing extérieur lu le 25/09/2026 écrit : « SGTM — 620 = pivot ; reprise
635-645 = pullback digéré ; cassure franche de 620 = risque de prolongation ».
Les chiffres sont peut-être justes. **Rien ne dit d'où ils viennent.**

Un lecteur ne peut ni les reproduire, ni les contester, ni savoir lesquels sont
calculés et lesquels sont estimés. Ce module publie donc chaque niveau **avec
sa méthode**, et les range en deux familles qui ne s'arbitrent pas ensemble :

  **FAITS**       ce que le marché a réellement fait, ou ce que la règle
                  interdit de dépasser. Vérifiable, non discutable.
                  · plafond et plancher réglementaires (±10 %, R10)
                  · plus-haut et plus-bas réellement atteints (52 s., 90 j.)
                  · moyennes mobiles, calculées sur des clôtures réelles

  **CONVENTIONS** de l'arithmétique sur la dernière séance. Utile, largement
                  employé, et **ce n'est pas une mesure du marché**.
                  · points pivots et leurs supports/résistances

⚠️ LE PLAFOND RÉGLEMENTAIRE EST LE NIVEAU LE PLUS SÛR DE TOUS, et personne ne
le publie comme tel. La BVC interdit à un cours de varier de plus de ±10 % en
une séance (R10). Le prix de demain est donc **borné par la loi**, pas par une
opinion. Sur Minière Touissit, qui a touché ce plafond cinq séances d'affilée,
c'est le seul niveau qui ait décrit la réalité.

⚠️ CE MODULE N'ENTRE DANS AUCUN SCORE (R8). C'est une lecture posée à côté du
chiffre. L'y faire entrer déplacerait la note de tous les titres, ce qui exige
un backtesting et un accord explicite.

⚠️ IL NE DIT PAS QUOI FAIRE. « Zone de défense », « ne pas poursuivre à
l'ouverture », « aucun renforcement » sont des conseils de position. Ce module
publie des nombres et leur méthode ; ce que le lecteur en fait lui appartient.
"""

from __future__ import annotations

# La limite réglementaire de variation d'un instrument, en pourcentage.
# ⚠️ Elle porte sur les INSTRUMENTS, jamais sur l'indice (R10).
LIMITE_PCT = 10.0

# En deçà, une moyenne mobile n'est pas calculable sur des clôtures réelles et
# ne doit pas être publiée comme un niveau.
MIN_SEANCES_MM = {"ma20": 20, "ma50": 50, "ma200": 200}


def _n(v):
    """Un nombre strictement positif, ou None."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f > 0 else None


def bornes_reglementaires(cloture) -> dict | None:
    """Le plafond et le plancher de la PROCHAINE séance. Un FAIT, pas un avis.

    ⚠️ C'est le seul niveau de ce module qu'aucune opinion ne peut déplacer :
    la BVC refuse un cours au-delà de ±10 % de la référence (R10). Il borne le
    possible, il ne prédit rien.

    ⚠️ Il se calcule sur la clôture publiée, qui sert de référence à la séance
    suivante. Le jour d'une reprise de cotation après OPA, l'autorité fixe une
    référence NEUVE et ce calcul ne s'applique pas — cas d'école documenté
    dans `docs/CAS_ECOLE_OPA_ET_REPRISE_DE_COTATION.md` (R11).
    """
    c = _n(cloture)
    if c is None:
        return None
    return {
        "plancher": round(c * (1 - LIMITE_PCT / 100), 2),
        "plafond": round(c * (1 + LIMITE_PCT / 100), 2),
        "_methode": (f"±{LIMITE_PCT:.0f} % de la clôture de référence — limite "
                     f"réglementaire de la Bourse de Casablanca (R10). Borne "
                     f"le possible, ne prédit rien."),
    }


def pivots(bougie: dict) -> dict | None:
    """Les points pivots de la dernière séance. Une CONVENTION, pas une mesure.

    ⚠️ Formule classique, écrite ici pour qu'elle soit reproductible :

        P  = (plus_haut + plus_bas + clôture) / 3
        R1 = 2P − plus_bas        S1 = 2P − plus_haut
        R2 = P + (plus_haut − plus_bas)
        S2 = P − (plus_haut − plus_bas)

    C'est de l'arithmétique sur une seule séance. Elle ne devient un « niveau »
    que parce que beaucoup d'intervenants la calculent — ce qui est une raison
    de la publier, et non une preuve qu'elle décrit quoi que ce soit.

    ⚠️ Rendu `None` si l'OHLC est incomplet ou incohérent. Une séance réparée
    porte `o = h = l = c` : les pivots s'y réduisent à la clôture et
    n'apprennent rien. Ce cas est signalé plutôt que publié en silence.
    """
    if not isinstance(bougie, dict):
        return None
    h, b, c = _n(bougie.get("h")), _n(bougie.get("l")), _n(bougie.get("c"))
    if None in (h, b, c) or h < b:
        return None
    if h == b:
        # ⚠️ Amplitude nulle : séance réparée, ou titre n'ayant pas coté.
        return None
    p = (h + b + c) / 3
    a = h - b
    return {
        "pivot": round(p, 2),
        "r1": round(2 * p - b, 2), "s1": round(2 * p - h, 2),
        "r2": round(p + a, 2), "s2": round(p - a, 2),
        "_seance": bougie.get("d"),
        "_methode": ("points pivots classiques sur la séance du "
                     f"{bougie.get('d')} : P=(H+B+C)/3, R1=2P−B, S1=2P−H, "
                     "R2=P+(H−B), S2=P−(H−B). ⚠️ CONVENTION arithmétique, "
                     "pas une mesure du marché."),
    }


def extremes(ticker: dict) -> dict | None:
    """Les extrêmes réellement atteints. Des FAITS.

    ⚠️ Publiés avec la distance au cours, parce que « 804 » ne dit rien seul
    quand le titre vaut 680 : c'est « 18 % au-dessus » qui informe.
    """
    p = _n(ticker.get("price"))
    if p is None:
        return None
    out = {}
    for cle, nom in (("h52w", "plus_haut_52s"), ("l52w", "plus_bas_52s"),
                     ("h90", "plus_haut_90j"), ("l90", "plus_bas_90j")):
        v = _n(ticker.get(cle))
        if v is not None:
            out[nom] = {"niveau": round(v, 2),
                        "distance_pct": round((v / p - 1) * 100, 2)}
    if not out:
        return None
    out["_methode"] = ("extrêmes RÉELLEMENT atteints sur la fenêtre, lus dans "
                       "les chandelles. La distance est exprimée depuis le "
                       "cours publié.")
    return out


def moyennes(ticker: dict) -> dict | None:
    """Les moyennes mobiles comme niveaux dynamiques. Des FAITS calculés.

    ⚠️ Une moyenne n'est publiée que si la fenêtre est réellement disponible.
    `n_candles` porte la longueur de la série SOURCE, pas la liste tronquée —
    piège déjà rencontré le 14/08.
    """
    p = _n(ticker.get("price"))
    n = (ticker.get("_meta") or {}).get("n_candles") or 0
    if p is None:
        return None
    out = {}
    for cle, mini in MIN_SEANCES_MM.items():
        v = _n(ticker.get(cle))
        if v is None or n < mini:
            continue
        out[cle] = {"niveau": round(v, 2),
                    "distance_pct": round((v / p - 1) * 100, 2),
                    "position": "au-dessus" if p > v else "en dessous"}
    if not out:
        return None
    out["_methode"] = ("moyennes arithmétiques des N dernières clôtures, "
                       "séance du jour incluse — convention publiée dans "
                       "`_conventions`. Absente tant que N séances ne sont "
                       "pas disponibles.")
    return out


def composer(ticker: dict, bougie: dict | None = None) -> dict | None:
    """Tous les niveaux d'un titre, rangés par nature. Fonction pure.

    ⚠️ LES DEUX FAMILLES SONT SÉPARÉES DANS LA SORTIE, pas mélangées. Un
    lecteur doit pouvoir voir d'un coup d'œil ce qui est établi et ce qui est
    conventionnel — les confondre dans une même liste, c'est les confondre
    tout court.
    """
    if not isinstance(ticker, dict):
        return None
    faits, conventions = {}, {}

    b = bornes_reglementaires(ticker.get("price"))
    if b:
        faits["bornes_seance"] = b
    e = extremes(ticker)
    if e:
        faits["extremes"] = e
    m = moyennes(ticker)
    if m:
        faits["moyennes"] = m

    pv = pivots(bougie or {})
    if pv:
        conventions["pivots"] = pv

    if not faits and not conventions:
        return None
    out = {}
    if faits:
        out["faits"] = faits
    if conventions:
        out["conventions"] = conventions
    out["_lecture"] = (
        "« faits » : ce que le marché a fait, ou ce que la règle interdit de "
        "dépasser. « conventions » : de l'arithmétique largement employée, qui "
        "ne mesure rien par elle-même. Aucun de ces niveaux n'entre dans le "
        "score (R8), et aucun ne dit quoi faire.")
    return out

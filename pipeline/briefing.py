#!/usr/bin/env python3
"""La lecture de la séance : des constats chiffrés, jamais une explication.

⚠️ LA RÈGLE QUI TIENT TOUT CE FICHIER
─────────────────────────────────────
**Ce module CONSTATE. Il n'EXPLIQUE pas.**

« Le marché a reculé parce que le scrutin a porté le PAM en tête » est une
phrase qu'aucune donnée de ce dépôt ne permet d'écrire. Nous mesurons des
cours et des volumes ; nous ne mesurons pas des causes. Un briefing qui pose
une cause invente le seul élément que son lecteur ne peut pas vérifier — et
c'est précisément celui sur lequel il fondera sa décision.

Chaque constat produit ici porte **le nombre qui l'établit**. Un constat sans
son nombre est une opinion, et une opinion habillée en bulletin quotidien est
pire qu'un bulletin absent.

⚠️ CE QUE CE MODULE APPORTE, QUE LE BULLETIN N'AVAIT PAS
Le bulletin listait déjà l'indice, les extrêmes et les signaux. Il ne disait
pas **ce que la séance a été**. Or la variation de l'indice, seule, se trompe
régulièrement de sens :

    24/09/2026 — le MASI perd 0,95 %, et 16 valeurs montent contre 42 qui
    baissent. Deux titres sur trois reculent : c'est une séance de repli
    large, pas le repli de quelques grosses capitalisations.

L'inverse existe aussi, et c'est le cas dangereux : un indice qui monte porté
par trois poids lourds pendant que le marché recule. Un lecteur qui n'a que la
variation conclut faux.

⚠️ IL NE CALCULE AUCUN SCORE ET N'ENTRE PAS DANS LA NOTE (R8)
C'est une couche de LECTURE posée à côté du flux publié. L'y faire entrer
déplacerait la note de tous les titres, ce qui exige un backtesting et un
accord explicite.

⚠️ IL NE LIT AUCUNE SOURCE
Il prend `data.json` tel qu'il est publié. S'il manque une donnée, il le DIT
au lieu de la combler : « non mesurable » est un résultat, pas un échec.
"""

from __future__ import annotations

# ── Les seuils, et la raison de chacun ─────────────────────────────────────
#
# ⚠️ Aucun n'est un chiffre rond choisi pour sa forme. Chacun sépare deux
# lectures différentes de la séance, et est justifié ici.

# Au-delà, la largeur contredit l'indice : l'indice et le marché ne disent plus
# la même chose. Deux tiers d'un côté, c'est le point où « quelques valeurs »
# devient « le marché ».
SEUIL_LARGEUR = 0.33

# Un volume qui dépasse de tant de fois sa propre médiane 20 séances n'est plus
# une variation d'activité : c'est un événement sur le titre. Trois fois est le
# seuil au-delà duquel la médiane ne peut plus s'expliquer par sa dispersion
# ordinaire.
FACTEUR_VOLUME = 3.0

# En deçà, le terminal lui-même grise le signal. Le relayer dans un briefing,
# où le lecteur ne voit pas l'indicateur, le présenterait comme plus sûr.
CONFIANCE_MIN = 3

# Un extrême annuel n'est retenu que si la série couvre réellement l'année.
# 200 séances valent environ dix mois de cotation.
MIN_SEANCES_52W = 200


def _fr(x, d=2):
    """Un nombre à la française : virgule décimale, espace pour les milliers.

    ⚠️ Le reste du bulletin écrit « -0,95 % ». Un « -0.95 % » au milieu se
    lit comme une donnée venue d'ailleurs — et la première chose qu'un lecteur
    fait d'un chiffre qui dénote, c'est s'en méfier.
    """
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def _pluriel(n, singulier, pluriel=None):
    """« 1 valeur », « 2 valeurs » — jamais « 1 valeur(s) ».

    Une parenthèse de pluriel dans un bulletin quotidien signale que personne
    n'a relu la phrase.
    """
    return f"{n} {singulier if abs(n) == 1 else (pluriel or singulier + 's')}"


def _n(v):
    """Un nombre, ou None. `None` = « le flux ne l'a pas donné »."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None          # NaN écarté


def largeur(masi: dict) -> dict | None:
    """Ce que la largeur dit de la séance, ou None si elle manque.

    ⚠️ Les inchangés comptent au dénominateur. Un marché où rien ne bouge
    n'est pas un marché haussier, et les exclure gonflerait le ratio des
    séances calmes — exactement celles où l'on se trompe le plus.
    """
    h, b = _n(masi.get("hausses")), _n(masi.get("baisses"))
    i = _n(masi.get("inchanges")) or 0
    if h is None or b is None:
        return None
    total = h + b + i
    if total <= 0:
        return None
    return {"hausses": int(h), "baisses": int(b), "inchanges": int(i),
            "total": int(total), "ratio": round((h - b) / total, 4)}


def accord_indice_marche(masi: dict) -> dict | None:
    """L'indice et la largeur racontent-ils la même séance ?

    ⚠️ LE CAS QUI JUSTIFIE CE CONSTAT est le désaccord : un indice qui monte
    pendant que la majorité des valeurs baisse. Il est pondéré par les
    capitalisations, donc trois poids lourds suffisent à le porter. Le lecteur
    qui n'a que la variation conclut alors l'inverse de ce qui s'est passé.
    """
    lg = largeur(masi)
    chg = _n(masi.get("change_pct"))
    if not lg or chg is None:
        return None

    if lg["ratio"] >= SEUIL_LARGEUR:
        sens_marche = "hausse"
    elif lg["ratio"] <= -SEUIL_LARGEUR:
        sens_marche = "baisse"
    else:
        sens_marche = "partage"

    sens_indice = "hausse" if chg > 0 else "baisse" if chg < 0 else "stable"
    accord = (sens_marche == sens_indice) or sens_marche == "partage"

    return {"sens_indice": sens_indice, "sens_marche": sens_marche,
            "accord": accord, **lg, "change_pct": round(chg, 2)}


def volumes_inhabituels(titres: list, seance: str) -> list:
    """Les titres dont l'activité du jour sort de leur propre ordinaire.

    ⚠️ COMPARÉ À SOI-MÊME, JAMAIS AU MARCHÉ. Mille titres échangés est
    considérable pour Zellidja et négligeable pour Attijariwafa. Le seul
    repère qui vaille est la médiane du titre sur vingt séances.

    ⚠️ Un titre sans médiane connue est ÉCARTÉ, pas traité comme calme : on
    ne sait pas, et le dire coûte moins cher que de l'affirmer.
    """
    out = []
    for x in titres or []:
        m = x.get("_meta") or {}
        if str(m.get("prix_asof") or "") != seance:
            continue
        v, med = _n(x.get("vol")), _n(m.get("vol_median20"))
        if v is None or med is None or med <= 0:
            continue
        f = v / med
        if f >= FACTEUR_VOLUME:
            out.append({"symbol": x.get("symbol"), "name": x.get("name"),
                        "volume": int(v), "median20": int(med),
                        "facteur": round(f, 1), "chg": _n(x.get("chg"))})
    return sorted(out, key=lambda z: -z["facteur"])


def extremes_annuels(titres: list, seance: str) -> dict:
    """Les titres au plus haut ou au plus bas de douze mois.

    ⚠️ Seulement si la série couvre réellement l'année. Un titre introduit il
    y a deux mois est à son « plus haut annuel » par construction : l'annoncer
    serait un artefact de la longueur de sa série, pas un fait de marché.
    """
    hauts, bas = [], []
    for x in titres or []:
        m = x.get("_meta") or {}
        if str(m.get("prix_asof") or "") != seance:
            continue
        if (_n(m.get("n_candles")) or 0) < MIN_SEANCES_52W:
            continue
        p, h, b = _n(x.get("price")), _n(x.get("h52w")), _n(x.get("l52w"))
        if p is None:
            continue
        e = {"symbol": x.get("symbol"), "name": x.get("name"),
             "price": round(p, 2), "chg": _n(x.get("chg"))}
        if h is not None and p >= h:
            hauts.append(e)
        elif b is not None and p <= b:
            bas.append(e)
    return {"plus_hauts": hauts, "plus_bas": bas}


def concentration(titres: list, seance: str) -> dict | None:
    """Quelle part de l'activité tient dans les cinq titres les plus actifs ?

    ⚠️ EN DIRHAMS, jamais en titres. Dix titres de Minière Touissit valent
    35 670 DH, dix d'Addoha en valent 370 : une concentration mesurée en
    nombre de titres désignerait systématiquement les valeurs bon marché.

    Une séance très concentrée n'est pas une séance de marché : c'est une
    poignée de transactions. Le dire change la lecture de tout le reste.
    """
    montants = []
    for x in titres or []:
        if str((x.get("_meta") or {}).get("prix_asof") or "") != seance:
            continue
        v, p = _n(x.get("vol")), _n(x.get("price"))
        if v is None or p is None or v <= 0:
            continue
        montants.append((x.get("symbol"), v * p))
    if len(montants) < 5:
        return None
    montants.sort(key=lambda z: -z[1])
    total = sum(m for _, m in montants)
    if total <= 0:
        return None
    top5 = montants[:5]
    return {"part_top5": round(sum(m for _, m in top5) / total, 4),
            "total_dh": round(total),
            "titres": [{"symbol": s, "montant_dh": round(m)} for s, m in top5],
            "n_titres_actifs": len(montants)}


def composer(data: dict) -> dict:
    """Le briefing complet, sous forme de constats. Fonction pure.

    Chaque entrée de `constats` porte son nombre. Aucune n'affirme de cause.
    """
    titres = data.get("tickers") or []
    masi = data.get("masi") or {}
    seance = max((str((x.get("_meta") or {}).get("prix_asof") or "")
                  for x in titres), default="")

    b = {
        "seance": seance,
        "accord": accord_indice_marche(masi),
        "concentration": concentration(titres, seance),
        "volumes": volumes_inhabituels(titres, seance),
        "extremes": extremes_annuels(titres, seance),
        "ytd_pct": _n(masi.get("ytd_pct")),
        "constats": [],
        "non_mesurable": [],
    }

    a = b["accord"]
    if a is None:
        b["non_mesurable"].append(
            "la largeur de marché — l'indice n'a pas livré le nombre de "
            "valeurs en hausse et en baisse")
    elif not a["accord"]:
        # ⚠️ LE CONSTAT QUI JUSTIFIE TOUT LE MODULE.
        b["constats"].append(
            f"L'indice et le marché ne disent pas la même chose : le MASI est "
            f"en {a['sens_indice']} de {_fr(abs(a['change_pct']))} % alors que "
            f"{a['baisses'] if a['sens_marche']=='baisse' else a['hausses']} "
            f"valeurs sur {a['total']} vont dans l'autre sens. L'indice est "
            f"pondéré par les capitalisations : quelques poids lourds "
            f"suffisent à le porter.")
    else:
        b["constats"].append(
            f"Séance de {a['sens_marche']} large : {a['hausses']} valeurs en "
            f"hausse contre {a['baisses']} en baisse sur {a['total']} traitées, "
            f"pour un indice à {_fr(a['change_pct'])} %."
            if a["sens_marche"] != "partage" else
            f"Marché partagé : {a['hausses']} hausses contre {a['baisses']} "
            f"baisses sur {a['total']} valeurs, indice à "
            f"{_fr(a['change_pct'])} %.")

    c = b["concentration"]
    if c and c["part_top5"] >= 0.50:
        b["constats"].append(
            f"L'activité est concentrée : les cinq titres les plus échangés "
            f"portent {c['part_top5']*100:.0f} % des "
            f"{_fr(c['total_dh']/1e6, 1)} M DH traités sur "
            f"{c['n_titres_actifs']} valeurs actives.")

    if b["volumes"]:
        v = b["volumes"][0]
        # ⚠️ Le séparateur de milliers s'applique aux NOMBRES seuls. Un
        # `.replace(",", " ")` sur la phrase entière mangeait aussi sa
        # ponctuation — « sur vingt séances  soit 106.6× ».
        vol = f"{v['volume']:,}".replace(",", " ")
        med = f"{v['median20']:,}".replace(",", " ")
        b["constats"].append(
            f"Activité inhabituelle sur {v['symbol']} : {vol} titres échangés "
            f"contre une médiane de {med} sur vingt séances, soit "
            f"{_fr(v['facteur'], 1)}×.")

    e = b["extremes"]
    if e["plus_hauts"]:
        b["constats"].append(
            f"{_pluriel(len(e['plus_hauts']), 'valeur')} au plus haut de "
            f"douze mois : "
            f"{', '.join(x['symbol'] for x in e['plus_hauts'][:6])}.")
    if e["plus_bas"]:
        b["constats"].append(
            f"{_pluriel(len(e['plus_bas']), 'valeur')} au plus bas de "
            f"douze mois : "
            f"{', '.join(x['symbol'] for x in e['plus_bas'][:6])}.")

    if b["ytd_pct"] is not None:
        b["constats"].append(
            f"Depuis le 1er janvier, l'indice est à "
            f"{_fr(b['ytd_pct'])} %.")
    else:
        b["non_mesurable"].append(
            "la performance annuelle de l'indice — la source ne l'a pas servie")

    # ⚠️ CE QUE CE BRIEFING NE SAIT PAS, ÉNONCÉ DANS LE BRIEFING LUI-MÊME.
    # Une limite écrite dans la documentation n'est pas lue ; écrite dans le
    # produit, elle l'est.
    b["non_mesurable"].append(
        "POURQUOI la séance a été ce qu'elle a été — ce bulletin mesure des "
        "cours et des volumes, il ne mesure pas de causes")

    return b


def texte(b: dict) -> str:
    """Le briefing en clair, pour le corps du bulletin."""
    L = ["LECTURE DE LA SÉANCE"]
    for c in b.get("constats") or []:
        L.append(f"   · {c}")
    if not (b.get("constats")):
        L.append("   · Rien de mesurable à signaler sur cette séance.")
    nm = b.get("non_mesurable") or []
    if nm:
        L.append("")
        L.append("   Ce que cette lecture ne dit pas :")
        for x in nm:
            L.append(f"     — {x}.")
    return "\n".join(L)

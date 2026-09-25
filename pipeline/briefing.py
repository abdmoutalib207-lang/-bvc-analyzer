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

# ⚠️ IL N'Y A PAS DE SEUIL D'IMPORTANCE ICI, ET C'EST DÉLIBÉRÉ.
#
# Une première version en portait un, fixé à 65 après mesure de la
# distribution (médiane 37, quartile supérieur 61, maximum 87). Vérification
# faite, `enrich_news.py:192` calcule déjà `material = score >= 65` : les deux
# désignaient EXACTEMENT les mêmes 73 articles sur 300.
#
# C'était une seconde définition du mot « important », posée à côté de celle
# du collecteur. Deux définitions qui concordent aujourd'hui divergeront le
# jour où l'une des deux bougera, et personne ne saura laquelle fait foi.
#
# Le briefing lit donc `material` et ne le recalcule pas. Si le collecteur
# change son seuil, le briefing suit — c'est le comportement voulu.
# Un test vérifie que ce fichier ne réintroduit pas de seuil à lui.

# Au-delà, l'article n'est plus une actualité de la séance : il décrit un état
# antérieur. Deux jours couvrent le week-end, donc le lundi matin le briefing
# reprend bien ce qui a été publié samedi et dimanche.
FENETRE_NEWS_JOURS = 3


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


def actualites(articles: list, seance: str, jours=FENETRE_NEWS_JOURS) -> dict:
    """Ce qui a été PUBLIÉ autour de la séance. Fonction pure.

    ⚠️ LA DISTINCTION QUI AUTORISE CE BLOC DANS UN MODULE QUI REFUSE LES CAUSES
    « Cosumar publie un résultat net en baisse » est un fait **sur une
    publication** : daté, attribué, et le lecteur peut ouvrir le lien.
    « Le marché a baissé à cause de Cosumar » est une cause, et rien ici ne
    l'établit.

    Le briefing porte le premier et jamais le second. C'est ce qui le sépare
    d'un récit : il dit ce qui a été publié, il ne dit pas ce que ça a produit.

    ⚠️ ON NE REPUBLIE PAS LES ARTICLES. Titre, source, date et lien — rien de
    plus. Le champ `rights` vaut « unknown » sur les 300 articles collectés :
    tant que les conditions de reprise ne sont pas établies, citer le titre et
    renvoyer à la source est la seule forme sûre. C'est aussi la plus utile :
    le lecteur va lire l'original.

    ⚠️ LA SÉLECTION EST CELLE DU COLLECTEUR, PAS LA NÔTRE. On retient les
    articles qu'il a marqués `material`. Le relevé du 25/09 donne 73 articles
    sur 300, tous rattachés à une société cotée — mais on n'en déduit pas que
    ce sera toujours le cas : les articles sans ticker sont rangés à part
    plutôt qu'écartés, et cette liste est vide aujourd'hui sans être morte.
    """
    from datetime import date, timedelta
    try:
        fin = date.fromisoformat(seance[:10])
    except (TypeError, ValueError):
        return {"titres": [], "autres": [], "fenetre": None}
    debut = fin - timedelta(days=max(0, jours - 1))

    retenus = []
    for x in articles or []:
        d = str(x.get("date") or "")[:10]
        if not d:
            continue
        try:
            j = date.fromisoformat(d)
        except ValueError:
            continue
        if not (debut <= j <= fin):
            continue
        # ⚠️ Le drapeau du COLLECTEUR, jamais un seuil recalculé ici.
        if not x.get("material"):
            continue
        retenus.append({
            "titre": x.get("title"),
            "source": x.get("publisher") or x.get("source"),
            "url": x.get("url"),
            "date": d,
            "importance": int(_n(x.get("importance")) or 0),
            "tickers": list(x.get("tickers") or []),
            "type": x.get("event_type"),
            # ⚠️ S1 = source officielle (AMMC, société, Bourse). S2 = presse.
            # La distinction se voit à l'écran : un communiqué déposé au
            # régulateur et un article de presse n'engagent pas la même chose.
            "officielle": x.get("source_tier") == "S1",
        })

    retenus.sort(key=lambda z: (-z["importance"], z["date"]))
    return {
        "fenetre": {"du": debut.isoformat(), "au": fin.isoformat()},
        "titres": [x for x in retenus if x["tickers"]],
        # ⚠️ Vide au 25/09 — les 73 articles matériels portent tous un ticker.
        # Conservée quand même : le collecteur peut marquer `material` un
        # article qu'il n'a pas su rattacher, et le jeter en silence serait
        # perdre précisément celui qu'on n'attendait pas.
        "autres": [x for x in retenus if not x["tickers"]],
    }


def charger_articles(chemin=None) -> list:
    """Les articles publiés, ou une liste vide. Ne lève jamais.

    ⚠️ Un briefing sans actualités reste utile — la lecture de la séance ne
    dépend pas d'elles. L'inverse n'est pas vrai : un briefing absent ne sert
    personne. La collecte d'actualités ne doit donc jamais pouvoir l'empêcher.
    """
    from pathlib import Path
    p = Path(chemin) if chemin else (
        Path(__file__).resolve().parent.parent / "news.json")
    try:
        d = __import__("json").loads(p.read_text(encoding="utf-8"))
        return d.get("articles") or [] if isinstance(d, dict) else []
    except Exception:                                     # noqa: BLE001
        return []


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
        # ⚠️ Ce qui a été PUBLIÉ, jamais ce que ça aurait causé.
        "actualites": actualites(charger_articles(), seance),
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


def ecrire(b: dict, chemin=None) -> str:
    """Publie le briefing dans un fichier que le terminal peut lire.

    ⚠️ POURQUOI UN FICHIER, ET PAS UN BOUTON QUI COLLECTE.
    Le terminal est un site statique servi par GitHub Pages : pas de serveur,
    pas d'étape de build. Un bouton ne peut RIEN collecter — il ne sait que
    lire un fichier déjà publié, comme `index.html` le fait déjà pour
    `news.json`. C'est la même limite qui a rendu les proxys CORS inutilisables
    le 25/08/2026.

    **Le workflow collecte, le bouton affiche.**

    ⚠️ POURQUOI LE BRIEFING DU MATIN SE GÉNÈRE LE SOIR.
    Le produit est J+1 : le briefing porte sur la séance CLOSE de la veille.
    Produit au run de 18h, il est disponible toute la nuit et à 8h sans
    qu'aucune tâche n'ait à se déclencher le matin. Cela le rend indépendant
    du cron matinal — qui est, au 25/09, le premier risque du produit et un
    chantier encore ouvert. Promettre « à 8h » en s'appuyant sur un
    déclencheur non fiable, c'était promettre ce qu'on ne tient pas.
    """
    import json
    from pathlib import Path
    p = Path(chemin) if chemin else (
        Path(__file__).resolve().parent.parent / "briefing.json")
    p.write_text(json.dumps(b, ensure_ascii=False, separators=(",", ":")),
                 encoding="utf-8")
    return str(p)


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

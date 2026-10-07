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

# ⚠️ LE SEUIL DE LA LIMITE SE LIT DANS LES DONNÉES, IL N'EST PAS CHOISI.
# Relevé sur les 79 séries de chandelles au 25/09/2026, variations d'une
# séance à l'autre en valeur absolue :
#
#     8,5 % :   7      9,5 % :  12
#     8,9 % :  13      9,8 % :  16
#     9,1 % :  17      9,9 % :  52   ← le saut
#     9,4 % :   9     10,0 % : 286   ← la limite réglementaire (R10)
#
# En dessous de 9,8 % les effectifs sont uniformes, autour de dix. À 9,9 % ils
# triplent, à 10,0 % ils sont dix-huit fois plus nombreux. Couper à 9,9 %
# sépare donc une séance ordinaire d'une séance BLOQUÉE PAR LA RÈGLE.
#
# L'arrondi au pas de cotation explique pourquoi la limite s'observe à 9,97
# ou 9,99 % plutôt qu'à 10,00 % exactement.
SEUIL_LIMITE = 9.9

# En deçà, ce n'est pas une série : un titre touche la limite un jour sur
# quinze environ, deux jours d'affilée arrive par hasard. Trois, non.
MIN_SEANCES_LIMITE = 3


def _fr(x, d=2):
    """Un nombre à la française : virgule décimale, espace pour les milliers.

    ⚠️ Le reste du bulletin écrit « -0,95 % ». Un « -0.95 % » au milieu se
    lit comme une donnée venue d'ailleurs — et la première chose qu'un lecteur
    fait d'un chiffre qui dénote, c'est s'en méfier.
    """
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


_RANGS = ("", "première", "deuxième", "troisième", "quatrième", "cinquième",
          "sixième", "septième", "huitième", "neuvième", "dixième")


def _rang(n):
    """« cinquième » plutôt que « 5 ». Au-delà de dix, on repasse au chiffre —
    « quinzième séance consécutive » est plus lourd que « 15e »."""
    return _RANGS[n] if 0 < n < len(_RANGS) else f"{n}e"


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


def reellement_cote(x: dict, seance: str) -> bool:
    """Le titre a-t-il réellement coté dans la séance du briefing ?

    ⚠️ LE DÉFAUT QUE CE FILTRE CORRIGE — briefing de clôture du 29/09/2026.
    Il listait en « activité inhabituelle » DAR (20 titres contre une médiane
    de 1), M2M et MGL, qui n'avaient PAS coté : BMCE rediffusait leur dernière
    transaction en la datant du jour (famille 24 d'ERRORS.md). Leur
    `prix_asof` valait bien la séance — c'est la source qui mentait sur la
    date — mais le moteur les avait marqués `stale`.

    La date seule ne suffit donc pas. Un titre n'est retenu que si son cours
    est daté de la séance ET que le moteur ne le déclare pas périmé.
    """
    m = x.get("_meta") or {}
    return str(m.get("prix_asof") or "") == seance and m.get("stale") is not True


def volumes_inhabituels(titres: list, seance: str) -> list:
    """Les titres dont l'activité du jour sort de leur propre ordinaire.

    ⚠️ COMPARÉ À SOI-MÊME, JAMAIS AU MARCHÉ. Mille titres échangés est
    considérable pour Zellidja et négligeable pour Attijariwafa. Le seul
    repère qui vaille est la médiane du titre sur vingt séances.

    ⚠️ Un titre sans médiane connue est ÉCARTÉ, pas traité comme calme : on
    ne sait pas, et le dire coûte moins cher que de l'affirmer.

    ⚠️ Seuls les titres RÉELLEMENT cotés — voir `reellement_cote`.
    """
    out = []
    for x in titres or []:
        m = x.get("_meta") or {}
        if not reellement_cote(x, seance):
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
        # ⚠️ Un cours rediffusé n'est pas un extrême atteint dans la séance.
        if not reellement_cote(x, seance):
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

    ⚠️ LE MONTANT RÉEL D'ABORD, L'APPROXIMATION SEULEMENT À DÉFAUT — corrigé
    le 29/09/2026 après recoupement au bulletin officiel.

    Ce calcul reposait entièrement sur `volume × clôture`, faute de mieux.
    Depuis le 25/09 le moteur collecte `echange_dh`, la contrepartie réelle
    servie par l'opérateur. Le briefing annonçait donc **636,8 M DH** de
    séance là où l'opérateur en publie **642,9 M** — six millions d'écart,
    parce que chaque transaction se fait à SON prix et non à la clôture.

    ⚠️ Mélanger les deux est sans risque, et c'est vérifié : sur la séance du
    28/09, les seize titres sans montant réel ont TOUS un volume nul. Leur
    contribution est la même dans les deux méthodes — zéro. Un titre qui a
    échangé sans que le montant soit rapprochable retombe sur l'approximation
    plutôt que de disparaître du total.

    ⚠️ Contrôle qui vaut preuve : la somme des montants réels par titre égale
    **exactement** le volume global servi par l'indice — 642 888 993,45 DH au
    28/09. Deux chemins indépendants, un seul chiffre.
    """
    montants = []
    approches = 0
    for x in titres or []:
        if str((x.get("_meta") or {}).get("prix_asof") or "") != seance:
            continue
        reel = _n(x.get("echange_dh"))
        if reel is not None and reel > 0:
            montants.append((x.get("symbol"), reel))
            continue
        v, p = _n(x.get("vol")), _n(x.get("price"))
        if v is None or p is None or v <= 0:
            continue
        montants.append((x.get("symbol"), v * p))
        approches += 1
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
            "n_titres_actifs": len(montants),
            # ⚠️ Combien de lignes reposent encore sur `volume × clôture`.
            # Zéro veut dire que le total est celui de l'opérateur, au centime.
            "lignes_approchees": approches}


def series_a_la_limite(series: dict, seance: str) -> list:
    """Les titres bloqués par la limite de ±10 % plusieurs séances de suite.

    ⚠️ LE FAIT QUE CE CONSTAT A RÉVÉLÉ. Minière Touissit a repris sa cotation
    le 16/09/2026 à 2 438 DH après OPA, puis a touché le plafond SIX SÉANCES
    CONSÉCUTIVES : 2 681, 2 949, 3 243, 3 567, 3 923. Chacune à +9,97 ou
    +9,99 %, c'est-à-dire au maximum que la règle autorise.

    Un titre au plafond n'a pas fini de monter : il a fini la séance. Le
    marché n'a simplement pas eu le droit d'aller plus loin. C'est un fait
    mesurable et il change la lecture d'une variation — « +9,98 % » et
    « +9,98 % pour la sixième fois d'affilée » ne disent pas la même chose.

    ⚠️ AUCUNE CAUSE N'EST AVANCÉE. Que la référence fixée à la reprise ait
    été trop basse est une interprétation ; que le titre ait touché la limite
    six fois est un décompte.

    ⚠️ Le sens est exigé identique sur toute la série. Un titre au plafond
    puis au plancher n'est pas dans une série : c'est de la volatilité, et
    les additionner masquerait la différence.
    """
    out = []
    for sym, serie in (series or {}).items():
        s = [(d, c) for d, c in serie if d <= seance]
        if len(s) < MIN_SEANCES_LIMITE + 1:
            continue
        n, sens = 0, None
        for i in range(len(s) - 1, 0, -1):
            avant, apres = s[i - 1][1], s[i][1]
            if not avant:
                break
            v = (apres / avant - 1) * 100
            # ⚠️ Au-delà de 10,5 %, ce n'est plus la limite : c'est une
            # opération sur titres ou une donnée fausse (R10/R11). On arrête
            # la série plutôt que de compter un décrochage comme un plafond.
            if abs(v) < SEUIL_LIMITE or abs(v) > 10.5:
                break
            d = "hausse" if v > 0 else "baisse"
            if sens is None:
                sens = d
            elif d != sens:
                break
            n += 1
        if n >= MIN_SEANCES_LIMITE:
            out.append({"symbol": sym, "seances": n, "sens": sens,
                        "depuis": s[-n - 1][1], "cloture": s[-1][1]})
    return sorted(out, key=lambda z: -z["seances"])


def series_chandelles(dossier=None) -> dict:
    """{ticker: [(date, clôture)]} — lecture seule, ne lève jamais."""
    from pathlib import Path
    import json as _json
    d = Path(dossier) if dossier else (
        Path(__file__).resolve().parent.parent / "pipeline" / "candles")
    out = {}
    try:
        fichiers = sorted(d.glob("*.json"))
    except OSError:
        return {}
    for f in fichiers:
        try:
            s = _json.loads(f.read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError, ValueError):
            continue
        if not isinstance(s, list):
            continue
        serie = [(str(b.get("d"))[:10], float(b["c"])) for b in s
                 if b.get("c") and b.get("d") and float(b["c"]) > 0]
        if serie:
            out[f.stem] = sorted(serie)
    return out


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


# ── Le briefing de clôture enrichi — ajouté le 30/09/2026 ──────────────────
#
# Un briefing rédigé par un autre assistant pour la séance du 29/09 donnait la
# trajectoire de l'indice, la comparaison avec la veille, les publications du
# jour, les secteurs, les matières premières et des « niveaux ». Ce qui suit
# reprend CHACUN de ces points EN MESURÉ : source nommée, date portée, méthode
# dite. Rien n'y est probabilisé ni conseillé, et aucune cause n'est avancée.

# Profondeur des extrêmes récents. ⚠️ Le nombre est DIT dans chaque phrase
# (« plus haut des 20 dernières séances ») : un niveau dont on tait la fenêtre
# ne se vérifie pas.
N_SEANCES_NIVEAUX = 20
# Les titres dont on publie les niveaux : ceux qui concentrent l'activité.
TOP_NIVEAUX = 5
# Nombre de secteurs cités en tête et en queue dans la phrase de synthèse.
N_SECTEURS_PHRASE = 3


def _date_fr(iso: str) -> str:
    """« 2026-09-29 » → « 29/09 »."""
    return f"{iso[8:10]}/{iso[5:7]}" if iso and len(iso) >= 10 else str(iso)


def _signe(x, d=2):
    return ("+" if x > 0 else "") + _fr(x, d)


def phrase_trajectoire(t: dict | None) -> str | None:
    """La séance de l'indice en une phrase. Fonction pure.

    ⚠️ CHAQUE MOT DÉCRIT UNE COMPARAISON DE NOMBRES, et rien d'autre :
      · « gain d'ouverture conservé » veut dire ouverture > veille ET
        clôture ≥ ouverture ;
      · « partiellement rendu » : veille < clôture < ouverture ;
      · « effacé » : clôture ≤ veille alors que l'ouverture était au-dessus.
    Symétrique pour une ouverture en baisse. Aucune de ces phrases ne dit
    POURQUOI : elles disent dans quel ordre les nombres se sont rangés.
    """
    if not t:
        return None
    v, o, h, b, c = (t["veille"], t["ouverture"], t["plus_haut"],
                     t["plus_bas"], t["cloture"])
    # ⚠️ « Première valeur calculée », pas « ouverture » tout court : le champ
    # `CoursOuverture` de CDG vaut la veille, et la valeur retenue est le
    # premier point de la série après 09:30 (voir `seance_marche.trajectoire`).
    P = [f"MASI : première valeur calculée {_fr(o)} ({t['heure_ouverture']}), plus haut "
         f"{_fr(h)}" + (f" ({t['heure_plus_haut']})" if t.get("heure_plus_haut") else "")
         + f", plus bas {_fr(b)}"
         + (f" ({t['heure_plus_bas']})" if t.get("heure_plus_bas") else "")
         + f", clôture {_fr(c)} pour une veille à {_fr(v)}."]
    # ⚠️ Mesuré le 30/09 à 13h15 : la série s'arrêtait à 12:59:59 alors que
    # la synthèse était plus récente. Si elle ne rejoint pas la clôture, les
    # heures des extrêmes ne couvrent que la partie de séance qu'elle porte.
    if t.get("serie_rejoint_cloture") is False and t.get("serie_jusqu_a"):
        P.append(f"(La série intrajournalière s'arrête à {t['serie_jusqu_a']} ; "
                 f"clôture et extrêmes viennent de la synthèse CDG.)")
    if o > v:
        if c >= o:
            P.append("Le gain d'ouverture a été conservé jusqu'à la clôture.")
        elif c > v:
            P.append("Le gain d'ouverture a été partiellement rendu : la "
                     "clôture reste au-dessus de la veille mais sous "
                     "l'ouverture.")
        else:
            P.append("Le gain d'ouverture a été effacé : la clôture est au "
                     "niveau de la veille ou en dessous.")
    elif o < v:
        if c <= o:
            P.append("La baisse d'ouverture s'est prolongée jusqu'à la clôture.")
        elif c < v:
            P.append("La baisse d'ouverture a été partiellement reprise : la "
                     "clôture reste sous la veille mais au-dessus de "
                     "l'ouverture.")
        else:
            P.append("La baisse d'ouverture a été effacée : la clôture est au "
                     "niveau de la veille ou au-dessus.")
    if b >= v:
        P.append("L'indice n'est pas descendu sous la clôture de la veille de "
                 "toute la séance.")
    elif h <= v:
        P.append("L'indice n'est pas remonté au-dessus de la clôture de la "
                 "veille de toute la séance.")
    if h > b:
        pos = (c - b) / (h - b)
        P.append(f"La clôture se situe à {pos*100:.0f} % de l'amplitude de "
                 f"séance ({_fr(h - b)} points) en partant du plus bas.")
    return " ".join(P)


def comparaison_veille(historique: dict, seance: str) -> dict | None:
    """La séance et celle qui la précède, lues dans `marche_history.json`.

    ⚠️ La « veille » est la SÉANCE précédente enregistrée, pas le jour
    calendaire précédent : le lundi se compare au vendredi.
    """
    jour = (historique or {}).get(seance)
    if not jour:
        return None
    avant = sorted(k for k in historique if k < seance)
    if not avant:
        return None
    d_veille = avant[-1]
    veille = historique[d_veille]

    def sel(e):
        return {k: e.get(k) for k in ("cours", "variation_pct", "volume_mad",
                                      "hausses", "baisses", "inchanges",
                                      "valeurs_traitees", "transactions")}
    j, p = sel(jour), sel(veille)
    ecart = None
    if _n(j["volume_mad"]) and _n(p["volume_mad"]):
        ecart = round((j["volume_mad"] / p["volume_mad"] - 1) * 100, 1)
    return {"seance": seance, "seance_veille": d_veille, "jour": j,
            "veille": p, "ecart_volume_pct": ecart,
            "source": "CDG Capital Bourse — INDICE-SYNTHESE, via "
                      "pipeline/marche_history.json"}


def phrase_veille(c: dict | None) -> str | None:
    if not c:
        return None
    j, p = c["jour"], c["veille"]
    P = [f"Par rapport à la séance du {_date_fr(c['seance_veille'])} :"]
    if _n(j["variation_pct"]) is not None and _n(p["variation_pct"]) is not None:
        P.append(f"indice à {_signe(j['variation_pct'])} % après "
                 f"{_signe(p['variation_pct'])} %,")
    if c["ecart_volume_pct"] is not None:
        P.append(f"volume global {_fr(j['volume_mad']/1e6, 1)} M DH contre "
                 f"{_fr(p['volume_mad']/1e6, 1)} M DH "
                 f"({_signe(c['ecart_volume_pct'], 1)} %),")
    if None not in (j["hausses"], j["baisses"], p["hausses"], p["baisses"]):
        P.append(f"{j['hausses']} hausses et {j['baisses']} baisses contre "
                 f"{p['hausses']} et {p['baisses']}.")
    if len(P) == 1:
        return None
    s = " ".join(P)
    return s[:-1] + "." if s.endswith(",") else s


def depots_du_jour(entrees: list, seance: str, resoudre=None) -> dict:
    """Les dépôts de résultats publiés à l'AMMC le jour de la séance.

    ⚠️ LA DATE EST CELLE DE LA LISTE DU RÉGULATEUR, qui ne dit pas l'heure.
    Un dépôt du 29/09 peut avoir été publié après la clôture : le briefing
    dit « publié le 29/09 », jamais « avant » ou « pendant » la séance.

    ⚠️ Le filtre « résultats » et la résolution des émetteurs sont ceux de
    `depots_ammc.py`, pas une seconde définition : deux définitions
    finiraient par diverger (même raison que pour `material`).
    """
    from pipeline.depots_ammc import _RESULTATS, emetteur
    if resoudre is None:
        from pipeline.depots_ammc import resoudre_emetteur as resoudre
    cotes, autres = [], []
    for e in entrees or []:
        if e.get("date") != seance or not _RESULTATS.search(e.get("titre") or ""):
            continue
        nom = emetteur(e["titre"])
        t = resoudre(nom)
        x = {"emetteur": nom, "titre": e["titre"], "url": e.get("url"),
             "date": e["date"], "ticker": t}
        (cotes if t else autres).append(x)
    cotes.sort(key=lambda z: z["ticker"])
    return {"seance": seance, "titres": cotes, "autres_emetteurs": autres,
            "source": "AMMC — liste des communiqués des émetteurs"}


def _extremes_fenetre(bougies: list, seance: str, n: int):
    """Plus haut et plus bas des `n` dernières bougies jusqu'à la séance."""
    s = sorted((b for b in bougies or [] if str(b.get("d"))[:10] <= seance
                and _n(b.get("h")) and _n(b.get("l"))), key=lambda b: b["d"])[-n:]
    if not s:
        return None
    # ⚠️ Au plus haut ex æquo, la date la plus RÉCENTE est retenue ; au plus
    # bas ex æquo, la plus récente aussi — c'est la dernière fois que le
    # niveau a été touché, l'information la plus utile au lecteur.
    h = max(reversed(s), key=lambda b: b["h"])
    lo = min(reversed(s), key=lambda b: b["l"])
    return {"n": len(s), "du": s[0]["d"][:10], "au": s[-1]["d"][:10],
            "plus_haut": h["h"], "date_plus_haut": h["d"][:10],
            "plus_bas": lo["l"], "date_plus_bas": lo["d"][:10]}


def _plus_actifs(titres: list, seance: str, top: int) -> list:
    """[(montant_dh, titre)] des titres réellement cotés, du plus échangé au
    moins échangé. Montant réel d'abord, volume × clôture à défaut."""
    actifs = []
    for x in titres or []:
        if not reellement_cote(x, seance):
            continue
        m = _n(x.get("echange_dh"))
        if not m:
            v, p = _n(x.get("vol")), _n(x.get("price"))
            m = v * p if v and p else None
        if m:
            actifs.append((m, x))
    actifs.sort(key=lambda z: -z[0])
    return actifs[:top]


def niveaux_titres(titres: list, seance: str, bougies: dict,
                   n: int = N_SEANCES_NIVEAUX, top: int = TOP_NIVEAUX) -> list:
    """Les extrêmes récents des titres qui concentrent l'activité.

    ⚠️ CE NE SONT PAS DES « SUPPORTS ». Un plus bas des 20 dernières séances
    est un fait vérifiable ; qu'il « tienne » demain est une opinion. Chaque
    niveau porte sa fenêtre et sa date, et rien ne dit ce qu'il faut en faire.

    ⚠️ Seuls les titres réellement cotés dans la séance, classés par montant
    échangé réel (`echange_dh`), à défaut volume × clôture — même règle que
    `concentration`.
    """
    out = []
    for m, x in _plus_actifs(titres, seance, top):
        sym = x.get("symbol")
        serie = (bougies or {}).get(sym) or []
        jour = next((b for b in serie if str(b.get("d"))[:10] == seance), None)
        e = {"symbol": sym, "name": x.get("name"), "montant_dh": round(m),
             "cloture": _n(x.get("price")),
             "seance_haut": _n(jour.get("h")) if jour else None,
             "seance_bas": _n(jour.get("l")) if jour else None,
             "fenetre": _extremes_fenetre(serie, seance, n)}
        out.append(e)
    return out


def niveaux_masi(historique: dict, clotures: dict, seance: str,
                 n: int = N_SEANCES_NIVEAUX, seances_cotees=None) -> dict | None:
    """Les extrêmes de l'indice : séance, n dernières CLÔTURES, année.

    ⚠️ Sur n séances, ce sont des CLÔTURES (`masi_history.json` n'en garde
    pas d'autres), et le libellé le dit : « plus haute clôture ». Les
    extrêmes de séance et d'année sont ceux que CDG sert.
    """
    jour = (historique or {}).get(seance) or {}
    # ⚠️ LA FENÊTRE EST DÉFINIE PAR LES SÉANCES COTÉES, PAS PAR LA SÉRIE DE
    # L'INDICE — mesuré le 30/09 : les 20 dernières clôtures de
    # `masi_history.json` couvraient du 17/08 au 29/09, soit 27 séances cotées.
    # Appeler cela « les 20 dernières séances » aurait été faux. Quand les
    # séances cotées sont connues (dates des chandelles des titres), la
    # fenêtre est celle des n dernières d'entre elles, et l'on dit combien de
    # clôtures de l'indice y sont réellement enregistrées.
    fenetre = None
    if seances_cotees:
        fenetre = sorted(d for d in seances_cotees if d <= seance)[-n:]
    if fenetre:
        s = sorted((d, c) for d, c in (clotures or {}).items()
                   if fenetre[0] <= d <= seance and _n(c))
    else:
        s = sorted((d, c) for d, c in (clotures or {}).items()
                   if d <= seance and _n(c))[-n:]
    if not jour and not s:
        return None
    out = {"seance": seance,
           "seance_haut": _n(jour.get("plus_haut")),
           "seance_bas": _n(jour.get("plus_bas")),
           "annee_haut": _n(jour.get("plus_haut_annee")),
           "annee_bas": _n(jour.get("plus_bas_annee")),
           "clotures": None}
    if s:
        h = max(reversed(s), key=lambda z: z[1])
        lo = min(reversed(s), key=lambda z: z[1])
        out["clotures"] = {
            # `n_seances` : la fenêtre en séances cotées ; `n` : les clôtures
            # de l'indice réellement enregistrées dans cette fenêtre.
            "n_seances": len(fenetre) if fenetre else None,
            "n": len(s), "du": fenetre[0] if fenetre else s[0][0], "au": seance,
            "plus_haute": h[1], "date_plus_haute": h[0],
            "plus_basse": lo[1], "date_plus_basse": lo[0]}
    return out


def phrase_niveaux_masi(nv: dict | None) -> str | None:
    """Les extrêmes de l'indice, chacun nommé par ce qu'il est."""
    if not nv:
        return None
    P = []
    if nv.get("seance_haut") and nv.get("seance_bas"):
        P.append(f"plus haut de séance {_fr(nv['seance_haut'])}, plus bas "
                 f"{_fr(nv['seance_bas'])}")
    c = nv.get("clotures")
    if c:
        if c.get("n_seances"):
            fen = (f"{c['n_seances']} dernières séances (du {_date_fr(c['du'])} "
                   f"au {_date_fr(c['au'])})")
            if c["n"] < c["n_seances"]:
                # ⚠️ Dit dans la phrase : un extrême tiré d'une série
                # trouée peut manquer le vrai extrême de la période.
                fen += (f", sur les {c['n']} clôtures de l'indice enregistrées "
                        f"dans cette fenêtre")
        else:
            fen = (f"{c['n']} dernières clôtures enregistrées (du "
                   f"{_date_fr(c['du'])} au {_date_fr(c['au'])})")
        P.append(f"sur les {fen}, plus haute clôture {_fr(c['plus_haute'])} "
                 f"({_date_fr(c['date_plus_haute'])}), plus basse clôture "
                 f"{_fr(c['plus_basse'])} ({_date_fr(c['date_plus_basse'])})")
    if nv.get("annee_haut") and nv.get("annee_bas"):
        P.append(f"sur l'année, plus haut {_fr(nv['annee_haut'])} et plus bas "
                 f"{_fr(nv['annee_bas'])} (servis par CDG)")
    return ("Niveaux mesurés du MASI : " + " ; ".join(P) + ".") if P else None


def phrase_niveaux_titres(lst: list) -> str | None:
    """Une ligne : les extrêmes récents des titres les plus échangés."""
    morceaux, fen = [], None
    for x in lst or []:
        f = x.get("fenetre")
        if not f:
            continue
        fen = fen or f
        s = x["symbol"]
        if x.get("seance_bas") and x.get("seance_haut"):
            s += f" séance {_fr(x['seance_bas'])}–{_fr(x['seance_haut'])},"
        s += (f" plus bas {_fr(f['plus_bas'])} ({_date_fr(f['date_plus_bas'])}),"
              f" plus haut {_fr(f['plus_haut'])} ({_date_fr(f['date_plus_haut'])})")
        morceaux.append(s)
    if not morceaux:
        return None
    return (f"Titres les plus échangés — extrêmes des {fen['n']} dernières "
            f"séances (du {_date_fr(fen['du'])} au {_date_fr(fen['au'])}) : "
            + " ; ".join(morceaux) + ".")


def phrase_secteurs(sect: list, k: int = N_SECTEURS_PHRASE) -> str | None:
    if not sect or len(sect) < 2 * k:
        return None

    def f(x):
        return f"{x['libelle'].capitalize()} {_signe(x['variation_pct'])} %"
    hausse = sum(1 for x in sect if x["variation_pct"] > 0)
    baisse = sum(1 for x in sect if x["variation_pct"] < 0)
    return (f"Indices sectoriels ({len(sect)} servis par CDG) : {hausse} en "
            f"hausse, {baisse} en baisse. En tête : "
            f"{', '.join(f(x) for x in sect[:k])}. En queue : "
            f"{', '.join(f(x) for x in sect[-k:][::-1])}.")


def lire_bougies(symboles, dossier=None) -> dict:
    """{ticker: bougies} pour les seuls titres demandés. Ne lève jamais."""
    import json as _json
    from pathlib import Path
    d = Path(dossier) if dossier else (
        Path(__file__).resolve().parent.parent / "pipeline" / "candles")
    out = {}
    for s in symboles or []:
        try:
            v = _json.loads((d / f"{s}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(v, list):
            out[s] = v
    return out


def charger_contexte(racine=None) -> dict:
    """Les fichiers que lit l'enrichissement de clôture. Ne lève jamais.

    ⚠️ Chacun peut manquer : le briefing dit alors ce qu'il ne sait pas, au
    lieu de ne pas s'écrire.
    """
    import json as _json
    from pathlib import Path
    r = Path(racine) if racine else Path(__file__).resolve().parent.parent

    def lire(chemin, cle):
        try:
            return _json.loads((r / chemin).read_text(encoding="utf-8")).get(cle) or {}
        except (OSError, ValueError, AttributeError):
            return {}
    return {"marche": lire("pipeline/marche_history.json", "seances"),
            "masi": lire("pipeline/masi_history.json", "seances"),
            "depots": lire("pipeline/depots_ammc.json", "entrees") or [],
            "seance_marche": lire("pipeline/seance_marche.json", "seances"),
            "resultats_s1": lire("datasets/resultats_s1_2026.json", "titres"),
            "dossier_bougies": str(r / "pipeline" / "candles")}


# ⚠️ « À SURVEILLER AUJOURD'HUI » — 30/09/2026, demande d'Abd Moutalib.
# Une liste courte, en tête, qui répond à la question du lecteur à 8h :
# « qu'est-ce que je regarde aujourd'hui ? ».
#
# ⚠️ DES CRITÈRES, PAS DES POIDS. Une proposition extérieure classait les
# titres par une note additionnant des points arbitraires (+15 pour une
# actualité, ×2 par point de variation…). Mesurée sur la séance du 29/09 : les
# huit premiers avaient tous une publication, HPS (−0,02 %) et DTT (0,00 %) en
# tête, et AUCUNE des six plus fortes variations du jour n'y figurait. Ici, un
# titre entre s'il remplit au moins un critère MESURÉ, et la ligne dit lequel.
# Rang : nombre de critères remplis, puis montant échangé — rien à inventer.
N_A_SURVEILLER = 8
N_VARIATIONS = 3


def _chiffres_publies(r: dict | None) -> dict | None:
    """Les chiffres lus dans le dépôt (datasets/resultats_s1_2026.json), et
    leurs variations — calculées ici pour que la rédaction n'ait jamais à les
    calculer elle-même (01/10/2026)."""
    if not r:
        return None
    out = {k: r.get(k) for k in ("rnpg_s1_2026", "rnpg_s1_2025", "ca_s1_2026",
                                  "ca_s1_2025", "ca_libelle", "url")}
    for nom, a, b in (("var_ca_pct", "ca_s1_2026", "ca_s1_2025"),
                      ("var_rnpg_pct", "rnpg_s1_2026", "rnpg_s1_2025")):
        x, y = _n(r.get(a)), _n(r.get(b))
        # ⚠️ Une variation rapportée à une base nulle ou négative n'a pas de sens.
        out[nom] = round((x / y - 1) * 100, 1) if x is not None and y and y > 0 else None
    return out


def a_surveiller(b: dict, titres: list, seance: str, n=N_A_SURVEILLER,
                 resultats: dict | None = None) -> dict:
    """Les titres à regarder, chacun avec les critères qu'il remplit. Pure.

    Deux familles, parce que le lecteur se pose deux questions :
      · A BOUGÉ — volume hors de son ordinaire, extrême de douze mois, cours
        au seuil réglementaire de ±10 %, parmi les plus fortes variations ;
        seulement pour un titre RÉELLEMENT coté (`reellement_cote`) ;
      · A PUBLIÉ — résultats déposés à l'AMMC le jour de la séance. Un titre
        qui n'a pas coté y entre quand même : c'est précisément l'information
        que le marché n'a pas encore intégrée.
    """
    par = {x.get("symbol"): x for x in titres or [] if x.get("symbol")}
    crit: dict = {}

    def ajouter(sym, code, texte, **extra):
        crit.setdefault(sym, []).append({"code": code, "texte": texte, **extra})

    for v in b.get("volumes") or []:
        ajouter(v["symbol"], "volume",
                f"volume {_fr(v['facteur'], 1)} fois sa médiane de 20 séances")
    ex = b.get("extremes") or {}
    for e in ex.get("plus_hauts") or []:
        ajouter(e["symbol"], "extreme", "au plus haut de douze mois")
    for e in ex.get("plus_bas") or []:
        ajouter(e["symbol"], "extreme", "au plus bas de douze mois")
    cotes = [x for x in par.values() if reellement_cote(x, seance)]
    # ⚠️ LE SEUIL N'EST PAS ±10 % POUR TOUS. Relevé du 29/09 : OUL et REB
    # sont bornés à ±6 % de leur référence, IAM à ±10 %. Écrire « 10 % » en
    # dur a d'abord affiché OUL (+5,96 %) « au seuil de +10 % ». L'écart se
    # calcule donc sur les seuils que CDG publie pour CE titre.
    for x in cotes:
        p, sh, sb = _n(x.get("price")), _n(x.get("seuil_haut")), _n(x.get("seuil_bas"))
        c = _n(x.get("chg"))
        ref = _n(x.get("reference")) or (p / (1 + c / 100) if p and c is not None else None)
        if p is None or not ref:
            continue
        if sh is not None and p >= sh:
            ajouter(x["symbol"], "seuil",
                    f"au seuil haut de la séance ({_signe((sh / ref - 1) * 100, 0)} %)")
        elif sb is not None and p <= sb:
            ajouter(x["symbol"], "seuil",
                    f"au seuil bas de la séance ({_signe((sb / ref - 1) * 100, 0)} %)")
    avec_chg = [x for x in cotes if _n(x.get("chg"))]
    for sens, lib in ((1, "hausses"), (-1, "baisses")):
        rang = sorted((x for x in avec_chg if sens * _n(x["chg"]) > 0),
                      key=lambda x: -sens * _n(x["chg"]))[:N_VARIATIONS]
        for x in rang:
            ajouter(x["symbol"], "variation",
                    f"parmi les {N_VARIATIONS} plus fortes {lib} de la séance")
    for d in ((b.get("depots") or {}).get("titres") or []):
        ajouter(d["ticker"], "publication",
                f"résultats déposés à l'AMMC le {_date_fr(seance)}", url=d.get("url"))

    lignes = []
    for sym, cs in crit.items():
        x = par.get(sym) or {}
        m = x.get("_meta") or {}
        v, med = _n(x.get("vol")), _n(m.get("vol_median20"))
        lignes.append({
            "volume_rapport": (round(v / med, 2) if reellement_cote(x, seance)
                               and v is not None and med else None),
            "chiffres": (_chiffres_publies((resultats or {}).get(sym))
                         if any(c["code"] == "publication" for c in cs) else None),
            "symbol": sym, "name": x.get("name"),
            "chg": _n(x.get("chg")) if reellement_cote(x, seance) else None,
            "echange_dh": _n(x.get("echange_dh")) if reellement_cote(x, seance) else None,
            "cote": reellement_cote(x, seance),
            "criteres": cs,
        })
    lignes.sort(key=lambda z: (-len(z["criteres"]), -(z["echange_dh"] or 0), z["symbol"]))
    retenus = lignes[:n]
    return {
        "a_publie": [z for z in retenus if any(c["code"] == "publication" for c in z["criteres"])],
        "a_bouge": [z for z in retenus if not any(c["code"] == "publication" for c in z["criteres"])],
        "n_candidats": len(lignes),
        "_regle": ("un titre entre s'il remplit au moins un critère mesuré ; "
                   "rang : nombre de critères, puis montant échangé"),
    }


def enrichir(b: dict, titres: list, contexte: dict) -> dict:
    """Ajoute au briefing les six blocs mesurés, et leurs phrases."""
    seance = b.get("seance") or ""
    ctx = contexte or {}
    sm = (ctx.get("seance_marche") or {}).get(seance) or {}

    b["trajectoire"] = sm.get("trajectoire")
    b["veille"] = comparaison_veille(ctx.get("marche") or {}, seance)
    try:
        b["depots"] = depots_du_jour(ctx.get("depots") or [], seance,
                                     ctx.get("resoudre"))
    except Exception:                                     # noqa: BLE001
        b["depots"] = None
    b["secteurs"] = sm.get("secteurs") or []
    b["matieres"] = sm.get("matieres") or []
    bougies = ctx.get("bougies")
    if bougies is None:
        # ⚠️ On ne lit que les fichiers des titres retenus, pas les 79.
        bougies = lire_bougies([x.get("symbol") for _, x in
                                _plus_actifs(titres, seance, TOP_NIVEAUX)],
                               ctx.get("dossier_bougies"))
    # Les séances réellement cotées, lues dans les chandelles des titres
    # retenus : c'est ce qui révèle les trous de la série de l'indice.
    cotees = {str(x.get("d"))[:10] for serie in bougies.values()
              for x in serie or []} or None
    b["niveaux"] = {"titres": niveaux_titres(titres, seance, bougies),
                    "masi": niveaux_masi(ctx.get("marche") or {},
                                         ctx.get("masi") or {}, seance,
                                         seances_cotees=cotees),
                    "n_seances": N_SEANCES_NIVEAUX}

    # ⚠️ La trajectoire et la comparaison à la veille passent EN TÊTE : elles
    # disent ce que la séance a été, le reste la détaille.
    tete = [p for p in (phrase_trajectoire(b["trajectoire"]),
                        phrase_veille(b["veille"])) if p]
    b["constats"][:0] = tete
    for p in (phrase_niveaux_masi(b["niveaux"]["masi"]),
              phrase_niveaux_titres(b["niveaux"]["titres"])):
        if p:
            b["constats"].append(p)
    if not b["trajectoire"]:
        b["non_mesurable"].append(
            "la trajectoire de l'indice dans la séance — la série "
            "intrajournalière de CDG n'a pas été relevée le jour de la séance, "
            "ou ne portait pas la date de la séance")
    d = b["depots"]
    if d and d["titres"]:
        n = len(d["titres"])
        b["constats"].append(
            f"{_pluriel(n, 'dépôt')} de résultats "
            f"{'publié' if n == 1 else 'publiés'} à l'AMMC le "
            f"{_date_fr(seance)} par {'une société cotée' if n == 1 else 'des sociétés cotées'} : "
            f"{', '.join(x['ticker'] for x in d['titres'])} (liste du "
            f"régulateur, sans heure de publication).")
    ps = phrase_secteurs(b["secteurs"])
    if ps:
        b["constats"].append(ps)
    else:
        b["non_mesurable"].append(
            "les indices sectoriels — non relevés auprès de CDG pour cette "
            "séance")
    if not b["matieres"]:
        b["non_mesurable"].append(
            "les matières premières — non relevées le jour de la séance")
    b["a_surveiller"] = a_surveiller(b, titres, seance,
                                     resultats=ctx.get("resultats_s1"))
    return b


def composer(data: dict, series=None, contexte=None) -> dict:
    """Le briefing complet, sous forme de constats. Fonction pure.

    Chaque entrée de `constats` porte son nombre. Aucune n'affirme de cause.

    `contexte` — les historiques lus par `enrichir` ; lus sur disque par
    `charger_contexte()` quand il est omis. Les tests le passent explicitement.
    """
    titres = data.get("tickers") or []
    masi = data.get("masi") or {}
    seance = max((str((x.get("_meta") or {}).get("prix_asof") or "")
                  for x in titres), default="")

    b = {
        "seance": seance,
        "accord": accord_indice_marche(masi),
        "concentration": concentration(titres, seance),
        # Le volume de l'indice LU PAR CE MÊME RUN : le contrôle « total du
        # briefing = volume de l'opérateur » ne vaut que sur deux chiffres
        # produits ensemble. En CI, data.json est régénéré la nuit et le
        # briefing versionné ne l'est pas : on comparait deux runs (07/10/2026).
        "volume_indice_lu": masi.get("volume_mad"),
        "volumes": volumes_inhabituels(titres, seance),
        "extremes": extremes_annuels(titres, seance),
        "ytd_pct": _n(masi.get("ytd_pct")),
        "constats": [],
        "non_mesurable": [],
        # ⚠️ Ce qui a été PUBLIÉ, jamais ce que ça aurait causé.
        "actualites": actualites(charger_articles(), seance),
        # ⚠️ Les titres bloqués par la limite réglementaire plusieurs séances
        # de suite. Passé `series=` explicitement par les tests pour ne pas
        # relire 79 fichiers à chaque appel.
        "limites": series_a_la_limite(
            series if series is not None else series_chandelles(), seance),
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

    for x in b["limites"]:
        # ⚠️ Un titre au plafond n'a pas fini de monter : il a fini la séance.
        # « +9,98 % » et « +9,98 % pour la sixième fois d'affilée » ne disent
        # pas la même chose, et seul le second le fait comprendre.
        mot = "plafond" if x["sens"] == "hausse" else "plancher"
        # ⚠️ « pour la 5 séances consécutive » — la première version écrivait
        # cela. Un rang s'écrit en toutes lettres, et le compte des séances
        # est celui des VARIATIONS, pas des clôtures : six clôtures font cinq
        # variations, et se tromper d'une unité sur un chiffre affiché suffit
        # à faire douter de tous les autres.
        b["constats"].append(
            f"{x['symbol']} touche le {mot} de variation pour la "
            f"{_rang(x['seances'])} séance consécutive : de "
            f"{_fr(x['depuis'])} à {_fr(x['cloture'])} DH. Le marché n'a pas "
            f"eu le droit d'aller plus loin.")

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

    # ⚠️ L'enrichissement de clôture ne doit jamais empêcher le briefing :
    # un fichier illisible ou un champ inattendu le fait sauter, pas le reste.
    try:
        enrichir(b, titres, contexte if contexte is not None
                 else charger_contexte())
    except Exception as e:                                # noqa: BLE001
        b["non_mesurable"].append(
            f"la lecture détaillée de la séance — erreur à la composition ({e})")

    # ⚠️ CE QUE CE BRIEFING NE SAIT PAS, ÉNONCÉ DANS LE BRIEFING LUI-MÊME.
    # Une limite écrite dans la documentation n'est pas lue ; écrite dans le
    # produit, elle l'est.
    b["non_mesurable"].append(
        "POURQUOI la séance a été ce qu'elle a été — ce bulletin mesure des "
        "cours et des volumes, il ne mesure pas de causes")

    return b


# ── Les trois moments de la journée — ajouté le 29/09/2026 ─────────────────
#
# Demandé par Abd Moutalib : une lecture de MI-JOURNÉE et une de CLÔTURE, à
# côté de la dernière lecture. `briefing.json` est réécrit à chaque passage :
# il ne peut pas servir de trace d'un moment. Chaque moment a donc son fichier,
# écrit seulement quand le passage tombe dans sa fenêtre.
#
# ⚠️ Les heures sont celles des passages déclenchés par cron-job.org
# (9h45 … 15h45, puis 18h45), lues sur l'horloge du REGISTRE `heure_maroc()`.

# Mi-journée : le passage de 12h45 l'écrit, celui de 13h45 le remplace, et plus
# rien ne le touche ensuite. Borne haute à 14h00 pour que la lecture de
# mi-journée reste celle de la MI-journée, et non la dernière avant clôture.
MI_JOURNEE = (1200, 1400)
# Le run qui fixe le cours — même valeur que `porte_rattrapage`. Avant, la
# séance du jour n'est pas close ; après, elle l'est.
CLOTURE_FIXEE = 1545

FICHIERS_MOMENT = {
    "mi_journee": "briefing_mijournee.json",
    "cloture": "briefing_cloture.json",
}


def moment(seance: str, aujourd_hui: str, hhmm: int) -> str | None:
    """« cloture », « mi_journee » ou None. Fonction pure.

    ⚠️ LA CLÔTURE SE RECONNAÎT À LA SÉANCE, PAS SEULEMENT À L'HEURE. Une
    séance ANTÉRIEURE à aujourd'hui est close, quelle que soit l'heure : un
    passage de 9h00, un samedi ou un jour férié relit la dernière séance close
    et peut réécrire sa lecture de clôture — c'est ce qui la rattrape si les
    passages de 15h45 et 18h45 ont tous deux sauté.
    """
    if not seance:
        return None
    if seance < aujourd_hui or hhmm >= CLOTURE_FIXEE:
        return "cloture"
    if seance == aujourd_hui and MI_JOURNEE[0] <= hhmm < MI_JOURNEE[1]:
        return "mi_journee"
    return None


def dater(b: dict, aujourd_hui: str, hhmm: int) -> dict:
    """Pose sur le briefing le moment et l'heure d'écriture.

    ⚠️ UNE LECTURE EN SÉANCE EST PARTIELLE, ET ELLE LE DIT. À 13h45, les
    volumes n'ont couru que quatre heures : les comparer à une médiane de
    séances ENTIÈRES sous-estime l'activité, et la largeur peut encore
    s'inverser. Le lecteur doit le lire dans le briefing, pas le deviner.
    """
    b["moment"] = moment(b.get("seance"), aujourd_hui, hhmm) or "en_seance"
    b["ecrit_a"] = f"{aujourd_hui} {hhmm // 100:02d}:{hhmm % 100:02d}"
    if b.get("seance") == aujourd_hui and hhmm < CLOTURE_FIXEE:
        b.setdefault("non_mesurable", []).insert(
            0, f"la séance entière — lecture prise à {hhmm // 100}h"
               f"{hhmm % 100:02d}, avant la clôture de 15h30 : volumes, largeur "
               f"et variations sont partiels")
    return b


def ecrire_moment(b: dict, racine=None) -> str | None:
    """Recopie le briefing dans le fichier de son moment, s'il en a un."""
    nom = FICHIERS_MOMENT.get(b.get("moment"))
    if not nom:
        return None
    from pathlib import Path
    dossier = Path(racine) if racine else Path(__file__).resolve().parent.parent
    return ecrire(b, dossier / nom)


# ⚠️ L'ARCHIVE DES LECTURES — 30/09/2026, demande d'Abd Moutalib.
# `briefing_mijournee.json` et `briefing_cloture.json` sont remplacés à chaque
# séance : la lecture d'hier disparaissait, et avec elle toute possibilité de
# relire ce que le briefing avait dit. Un fichier par séance, un index pour le
# terminal (un site statique ne sait pas lister un dossier).
ARCHIVE = "briefings"


def archiver(b: dict, aujourd_hui: str, racine=None) -> str | None:
    """Range la lecture dans `briefings/<séance>.json`, sous son moment.

    ⚠️ UNE LECTURE ARCHIVÉE EST FIGÉE APRÈS SA SÉANCE. Le jour même, le
    passage suivant la remplace (13h45 après 12h45, 18h45 après 15h45) : c'est
    la même lecture, mieux informée. Le lendemain, elle ne bouge plus — sauf si
    elle n'existait pas : c'est le rattrapage d'une clôture dont les deux
    passages ont sauté (voir `moment`). Une archive qui se réécrirait après
    coup ne permettrait plus de vérifier ce qui avait été dit.
    """
    import json
    from pathlib import Path
    m, s = b.get("moment"), str(b.get("seance") or "")[:10]
    if m not in FICHIERS_MOMENT or not s:
        return None
    base = Path(racine) if racine else Path(__file__).resolve().parent.parent
    dossier = base / ARCHIVE
    dossier.mkdir(parents=True, exist_ok=True)
    f = dossier / f"{s}.json"
    try:
        doc = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except ValueError:
        doc = {}
    if doc.get(m) is not None and aujourd_hui != s:
        return None
    doc["seance"] = s
    doc[m] = b
    f.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")),
                 encoding="utf-8")
    seances = sorted((x.stem for x in dossier.glob("????-??-??.json")), reverse=True)
    (dossier / "index.json").write_text(
        json.dumps({"seances": seances}, ensure_ascii=False), encoding="utf-8")
    return str(f)


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
    # ⚠️ Les matières premières ne sont pas un constat SUR la séance : elles
    # en sont le contexte, chacune avec l'heure de sa valeur. Aucun lien de
    # cause n'est tiré entre elles et la cote.
    mp = b.get("matieres") or []
    if mp:
        L.append("")
        L.append("   Matières premières (TradingView, contrat le plus proche) :")
        for x in mp:
            v = x.get("variation_pct")
            L.append(f"     {x['nom']} {_fr(x['valeur'], 2)} {x.get('devise') or ''}"
                     + (f" ({_signe(v)} %)" if v is not None else "")
                     + f" — valeur du {x['horodatage_utc'][8:10]}/"
                       f"{x['horodatage_utc'][5:7]} à {x['horodatage_utc'][11:16]} UTC")
    nm = b.get("non_mesurable") or []
    if nm:
        L.append("")
        L.append("   Ce que cette lecture ne dit pas :")
        for x in nm:
            L.append(f"     — {x}.")
    return "\n".join(L)

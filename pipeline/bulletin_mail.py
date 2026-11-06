#!/usr/bin/env python3
"""Compose le bulletin quotidien envoyé par courriel.

Le terminal est un site qu'il faut penser à ouvrir. Le bulletin, lui, vient à
son lecteur — c'est la même donnée, livrée autrement.

⚠️ CE QU'IL NE FAIT PAS. Il ne recalcule rien, n'interroge aucune source, ne
décide de rien. Il lit `data.json` tel qu'il est publié et le met en forme. Si
la collecte a échoué, le bulletin le DIT plutôt que d'enjoliver — un courriel
qui ment est pire qu'un courriel absent, parce qu'on le lit sans vérifier.

⚠️ Le bulletin porte la dernière séance ENREGISTRÉE, pas la date du jour. Le
produit est J+1 : un lundi matin, la dernière séance est celle du vendredi, et
c'est la bonne réponse — pas un retard.

Sortie : (sujet, corps_texte, corps_html), ou un code de sortie non nul si les
données sont trop dégradées pour être envoyées.
"""

import json
import math
import sys
from html import escape
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).parent.parent

# ⚠️ LA LECTURE DE LA SÉANCE MANQUAIT AU COURRIEL RÉEL — constaté le 06/11/2026.
# Le workflow lance `python pipeline/bulletin_mail.py` : `sys.path[0]` vaut alors
# `pipeline/`, et `from pipeline.briefing import …` (comme `from bvc_config
# import …`) levait ModuleNotFoundError — avalé par `_briefing()`, qui ne lève
# jamais. Le courriel partait sans sa lecture de séance pendant que les tests,
# qui importent le module depuis la racine, la voyaient. La racine est donc
# posée ici, une fois ; `tests/test_bulletin.py` lance le script comme le
# workflow le fait.
if str(RACINE.resolve()) not in sys.path:
    sys.path.insert(0, str(RACINE.resolve()))

# ⚠️ LE MAROC N'EST PAS À UTC+1 TOUTE L'ANNÉE — corrigé le 25/09/2026.
# Il est repassé à UTC+0 le 20/09/2026, et le registre `DECALAGES_MAROC` de
# `bvc_config.py` fait foi sur ce point, jamais la base de fuseaux du système :
# elle peut être plus ancienne que le dernier décret, ce qui s'est produit le
# 23/09. Cette constante n'était utilisée nulle part — elle n'a donc rien
# faussé — mais elle affirmait le contraire du registre à qui la lirait.
def tz_casablanca(jour=None):
    """Le fuseau de Casablanca À LA DATE DONNÉE, d'après le registre."""
    from bvc_config import decalage_maroc
    from datetime import date as _date
    return timezone(timedelta(hours=decalage_maroc(jour or _date.today())))
TERMINAL = "https://abdmoutalib207-lang.github.io/-bvc-analyzer/"

# En deçà, la collecte a échoué : on le dit au lieu de publier un bulletin creux.
MIN_TITRES_SEANCE = 40

MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre")

# ── LE SCORE BVC REMPLACE LA NOTE v5.3 — 06/11/2026 ──────────────────────────
# Décision d'Abd Moutalib : « l'ancien scoring doit disparaître ». Le courriel
# ne lit plus `v53` ni `sig` : plus de « notes vertes », plus de note sur 10,
# plus aucun mot d'action. Il présente le Score BVC (`score_bvc`, sur 100), sa
# tranche, et ce que la mesure en a établi.
#
# ⚠️ LES TRANCHES sont celles du backtest (`TRANCHES` de
# pipeline/backtest_score_descriptif.py) et du terminal (`TRANCHES_BVC`) :
# [0, 40) · [40, 60) · [60, 75) · [75, 100]. Recopiées ici parce que le
# courriel tourne sans aucune dépendance installée (le module du backtest
# importe pandas) ; `tests/test_bulletin.py` vérifie que les trois concordent.
TRANCHES_BVC = (("≥ 75", 75), ("60–74", 60), ("40–59", 40), ("< 40", -math.inf))

# ⚠️ Mis en avant : score CALCULÉ, confiance ≥ 2, titre ni suspendu ni
# périmé. C'est la règle de la tuile « Score BVC le plus élevé » du terminal :
# un seul critère sur tous les canaux. Sous 2, le terminal grise le score —
# le relayer par courriel, où l'indicateur ne se voit pas, le présenterait
# comme plus sûr qu'il ne l'est. (L'ancien seuil de 3 portait sur un SIGNAL
# d'achat ; il n'y a plus de signal.)
CONFIANCE_MIN = 2
N_SCORE_BVC = 10

# La mesure citée par le courriel. Rien n'est écrit en dur : chaque chiffre
# est lu dans cet artefact daté, et n'est cité que si sa version de score est
# celle que data.json publie (R12).
MESURE_SCORE_BVC = RACINE / "datasets" / "backtests" / "score_bvc_2026-11-03.json"
_LIBELLES_MESURE = (("< 40", "sous 40"), ("40 – 59", "de 40 à 59"),
                    ("60 – 74", "de 60 à 74"), ("≥ 75", "à 75 et plus"))


def valeur_bvc(x):
    """La valeur publiée du Score BVC, ou None (PARTIEL, NON_CALCULABLE,
    bloc absent, valeur hors [0, 100])."""
    s = x.get("score_bvc")
    if not isinstance(s, dict) or s.get("etat") != "CALCULABLE":
        return None
    v = s.get("valeur")
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v) if 0 <= v <= 100 else None


def tranche_bvc(v):
    """« ≥ 75 », « 60–74 », « 40–59 », « < 40 » — sur la valeur EXACTE (un
    arrondi rangerait 74,5 dans la tranche du dessus)."""
    return next(nom for nom, bas in TRANCHES_BVC if v >= bas)


def mis_en_avant(x):
    """Un titre que le courriel peut citer : voir CONFIANCE_MIN."""
    m = x.get("_meta") or {}
    return (valeur_bvc(x) is not None
            and (m.get("confidence") or 0) >= CONFIANCE_MIN
            and not m.get("suspendu") and not m.get("stale", True))


def _score(v):
    """74.5 → « 74,5 » ; 82.0 → « 82 »."""
    s = f"{v:.1f}".replace(".", ",")
    return s[:-2] if s.endswith(",0") else s


def mesure_score_bvc(chemin=None):
    """Les fréquences mesurées du Score BVC, lues dans l'artefact — ou None.

    Ne lève jamais : un artefact illisible retire le paragraphe, il n'empêche
    pas l'envoi. ⚠️ On ne cite que la mesure SANS rentabilité : c'est la seule
    sans biais d'anticipation (le ROE 2025 n'était pas connu en 2023-2024)."""
    try:
        chemin = Path(chemin) if chemin else MESURE_SCORE_BVC
        d = json.loads(chemin.read_text(encoding="utf-8"))
        r = d["resultats"]["sans_rentabilite"]["score_bvc"]
        sem = r.get("par_semestre") or {}
        tranches = [(lib, r["tranches"][cle]["frequence_surperformance"], r["tranches"][cle]["n"])
                    for cle, lib in _LIBELLES_MESURE]
        return {
            "fichier": f"datasets/backtests/{chemin.name}",
            "version": d["version_score"],
            "n": r["observations_total"],
            "base": r["taux_de_base_global"],
            "du": min((s["du"] for s in sem.values()), default=None),
            "au": max((s["au"] for s in sem.values()), default=None),
            "horizon": d["horizon_seances"],
            "frais": d["frais_aller_retour"],
            "reference": d["reference_principale"],
            "tranches": tranches,
            "significatives": [lib for cle, lib in _LIBELLES_MESURE
                               if r["tranches"][cle].get("ecart_significatif_5pct")],
        }
    except Exception:                                     # noqa: BLE001
        return None


def _pc(f):
    return f"{f * 100:.1f} %".replace(".", ",")


def phrase_mesure(m):
    """La mesure en une phrase, ou une chaîne vide. Même texte pour les deux rendus."""
    if not m:
        return ""
    periode = (f" (dates d'entrée du {_jjmm(m['du'], True)} au {_jjmm(m['au'], True)})"
               if m.get("du") and m.get("au") else "")
    tr = " · ".join(f"{_pc(f)} {lib}" for lib, f, _n in m["tranches"])
    if m["significatives"]:
        lecture = ("écart au taux de base significatif à 5 % pour : "
                   + ", ".join(m["significatives"]) + ".")
    else:
        lecture = ("aucune tranche ne s'en distingue à 5 % : le score décrit la "
                   "situation, il ne distingue pas les gagnants.")
    return (f"Ce que le score a mesuré : sur {_nb(m['n'], 0)} observations{periode}, "
            f"part des cas ayant fait mieux que le {m['reference']} {m['horizon']} séances "
            f"plus tard, frais de {_nb(m['frais'] * 100, 0)} % compris : {tr}, pour "
            f"{_pc(m['base'])} sur l'ensemble — {lecture} Mesure faite sans le facteur "
            f"rentabilité ({m['fichier']}). Une fréquence passée, pas une promesse.")


PHRASE_SCORE = ("Score descriptif sur 100, pas une prévision : il décrit la situation "
                "du titre à la dernière séance (moyennes mobiles, momentum, MACD, "
                "activité, liquidité, rentabilité). La tranche situe le score ; "
                "elle ne dit pas quoi faire.")


def _date_longue(iso):
    """« 2026-09-02 » → « mercredi 2 septembre 2026 »."""
    jours = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
    try:
        d = datetime.strptime(iso[:10], "%Y-%m-%d")
        return f"{jours[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}"
    except Exception:
        return iso or "date inconnue"


def _nb(v, d=2):
    """Formatage à la française : espace fine pour les milliers, virgule décimale."""
    if v is None:
        return "—"
    try:
        s = f"{float(v):,.{d}f}"
        return s.replace(",", " ").replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def _pct(v):
    if v is None:
        return "—"
    try:
        return f"{float(v):+.2f} %".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def _jjmm(iso, annee=False):
    j = str(iso or "")[:10]
    return f"{j[8:10]}/{j[5:7]}" + (f"/{j[:4]}" if annee else "") if len(j) == 10 else ""


def mention_offre(x):
    """La phrase d'une offre publique publiée dans `_meta.offre_publique`, ou
    None. La même que le bandeau du terminal (registre OFFRES_PUBLIQUES,
    29/10/2026) : prix, période, pièces, écart du prix de l'offre au cours
    publié. Factuelle, sans mot d'action.

    ⚠️ Un titre sous offre publique peut figurer parmi les scores les plus
    élevés — CMT, n°1 de la note v5.3 à ~3 800 DH le 28/10, sous une OPA
    obligatoire à 2 217 DH. Le score n'en tient pas compte ; le courriel, lu
    sans le terminal, doit le dire."""
    o = (x.get("_meta") or {}).get("offre_publique")
    if not o:
        return None
    if o.get("phase") == "close":
        periode = f"close le {_jjmm(o['cloture'], True)}, résultats le {_jjmm(o['resultats'], True)}"
    else:
        periode = (("ouverte " if o.get("phase") == "ouverte" else "")
                   + f"du {_jjmm(o['ouverture'])} au {_jjmm(o['cloture'], True)}")
    t = (f"{o['nature']} à {_nb(o['prix'], 0)} DH, {periode} "
         f"(visa AMMC {o['visa']} ; avis de la Bourse {o['avis_bourse']})")
    cours = x.get("price")
    if isinstance(cours, (int, float)) and cours > 0 and o.get("prix"):
        e = (o["prix"] - cours) / cours * 100
        t += f" — écart avec le cours : {'−' if e < 0 else '+'}{abs(e):.1f} %".replace(".", ",")
    return t


def charger(chemin=None):
    d = json.loads((Path(chemin) if chemin else RACINE / "data.json")
                   .read_text(encoding="utf-8"))
    lignes = d.get("tickers") or []
    if isinstance(lignes, dict):
        lignes = list(lignes.values())
    return d, [x for x in lignes if x.get("symbol")]


def analyser(data, titres):
    """Tout ce que le bulletin dira, calculé une fois."""
    masi = data.get("masi") or {}
    seance = max((str((x.get("_meta") or {}).get("prix_asof") or "")
                  for x in titres), default="")

    du_jour = [x for x in titres
               if str((x.get("_meta") or {}).get("prix_asof") or "") == seance]
    cotes = [x for x in du_jour if not (x.get("_meta") or {}).get("stale")]

    hausses = sorted((x for x in cotes if (x.get("chg") or 0) > 0),
                     key=lambda z: -z["chg"])
    baisses = sorted((x for x in cotes if (x.get("chg") or 0) < 0),
                     key=lambda z: z["chg"])

    # ⚠️ LE SCORE BVC, PLUS LA NOTE v5.3 NI SON SIGNAL — 06/11/2026.
    #
    # Ce tri lisait `sig` (« ACHETER… », confiance ≥ 3), classé par `v53` ;
    # avant le 29/09 il lisait `sigBvc`, une table écrite à la main en juin. Il
    # lit désormais le Score BVC publié par le moteur, celui qu'affiche le
    # terminal, selon la même règle que sa tuile d'accueil (`mis_en_avant`).
    # Un test vérifie que modifier `v53`, `sig` ou `sigBvc` ne change plus
    # rien au bulletin.
    notes = [x for x in titres if mis_en_avant(x)]
    score_bvc = sorted(notes, key=lambda z: (-valeur_bvc(z), z["symbol"]))
    repartition = {nom: 0 for nom, _ in TRANCHES_BVC}
    for x in notes:
        repartition[tranche_bvc(valeur_bvc(x))] += 1
    # La mesure n'est citée que si elle porte sur la formule publiée.
    versions = {(x.get("score_bvc") or {}).get("version") for x in titres
                if isinstance(x.get("score_bvc"), dict)}
    mesure = mesure_score_bvc()
    if mesure and mesure["version"] not in versions:
        mesure = None

    return {
        "masi": masi,
        "seance": seance,
        "n_titres": len(titres),
        "n_seance": len(du_jour),
        "cotes": len(cotes),
        # ⚠️ Une valeur qui n'a pas coté sort de `du_jour` : son `prix_asof`
        # reste à la séance précédente. La compter sur le seul écart
        # `du_jour - cotes` en oubliait donc la majorité — 0 affiché pour 21
        # réelles. On compte sur l'univers entier.
        "non_cotes": len(titres) - len(cotes),
        "hausses": hausses,
        "baisses": baisses,
        "score_bvc": score_bvc,
        "repartition": repartition,
        "mesure": mesure,
        # Titres sans Score BVC publié : PARTIEL ou NON_CALCULABLE (cours
        # périmé, suspension, couverture insuffisante).
        "sans_score": [x for x in titres if valeur_bvc(x) is None],
        "insuffisants": [x for x in titres
                         if ((x.get("_meta") or {}).get("confidence") or 0) <= 1],
        "updated": data.get("updated"),
        # ⚠️ La lecture de la séance. Son échec ne doit pas empêcher l'envoi :
        # un bulletin sans lecture reste utile, un bulletin absent ne l'est pas.
        "briefing": _briefing(data),
    }


def _briefing_html(a):
    """La lecture de la séance, mise en forme pour le courriel.

    ⚠️ Les constats et les limites ne portent PAS la même couleur ni le même
    poids : le lecteur doit voir d'un coup d'œil où finit ce qui est mesuré et
    où commence ce qui ne l'est pas. Les confondre typographiquement, c'est
    les confondre tout court.
    """
    from html import escape
    txt = a.get("briefing") or ""
    if not txt:
        return ""
    constats, limites = [], []
    cible = constats
    for ligne in txt.splitlines():
        s = ligne.strip()
        if not s or s == "LECTURE DE LA SÉANCE":
            continue
        if s.startswith("Ce que cette lecture ne dit pas"):
            cible = limites
            continue
        cible.append(s.lstrip("·—- ").strip())
    if not constats and not limites:
        return ""
    puces = "".join(
        f'<li style="margin:0 0 5px">{escape(c)}</li>' for c in constats)
    fin = "".join(
        f'<li style="margin:0 0 3px">{escape(x)}</li>' for x in limites)
    return f"""
  <h2 style="font-size:15px;margin:0 0 4px">Lecture de la séance</h2>
  <p style="font-size:12.5px;color:#6d7887;margin:0 0 8px">
    Des constats chiffrés. Aucune cause n'y est avancée&nbsp;: ce bulletin
    mesure des cours et des volumes.</p>
  <ul style="font-size:13.5px;margin:0 0 10px;padding-left:18px">{puces}</ul>
  {f'''<p style="font-size:12px;color:#6d7887;margin:0 0 4px">
    Ce que cette lecture ne dit pas&nbsp;:</p>
  <ul style="font-size:12px;color:#6d7887;margin:0 0 22px;padding-left:18px">{fin}</ul>'''
     if fin else '<div style="margin-bottom:22px"></div>'}
"""


def largeur_ligne(a):
    """La largeur de marché, en une ligne, pour le texte ET pour le HTML.

    ⚠️ DEUX COMPTES DU MÊME FAIT — corrigé le 25/09/2026.

    L'en-tête comptait les hausses SUR NOTRE UNIVERS (80 titres, dont 13
    n'avaient pas coté ce jour-là) pendant que la lecture de la séance citait
    celui de l'opérateur (68 valeurs traitées). Résultat, dans le même
    courriel : « 14 hausses » quatre lignes au-dessus de « 16 valeurs en
    hausse ». Deux chiffres pour une seule réalité, et rien pour les
    départager — c'est le genre d'écart qui coûte la confiance bien au-delà
    de ce qu'il vaut.

    **La largeur de l'indice appartient à l'opérateur** : c'est lui qui
    définit les valeurs traitées. Notre décompte n'en est qu'une
    reconstitution, sur un univers voisin mais pas identique. On publie donc
    le sien quand il est là, le nôtre seulement à défaut — en disant lequel.

    ⚠️ Une seule fonction pour les deux rendus : corriger la ligne à deux
    endroits, c'est garantir qu'un jour ils divergeront.
    """
    m = a.get("masi") or {}
    if m.get("hausses") is not None and m.get("baisses") is not None:
        return (f"{m['hausses']} hausses · {m['baisses']} baisses · "
                f"{m.get('inchanges') or 0} inchangés "
                f"(sur {m.get('valeurs_traitees') or '?'} valeurs traitées)")
    inchanges = a["cotes"] - len(a["hausses"]) - len(a["baisses"])
    return (f"{len(a['hausses'])} hausses · {len(a['baisses'])} baisses · "
            f"{inchanges} inchangés — décompte sur nos {a['cotes']} titres "
            f"cotés, l'indice n'ayant pas livré sa largeur")


def ligne_retenus():
    return (f"Retenus : score calculé, confiance d'au moins {CONFIANCE_MIN} sur 5, "
            "titre ni suspendu ni périmé.")


def ligne_repartition(a):
    """La répartition par tranche des titres retenus — une fonction pour les
    deux rendus (cf. `largeur_ligne`)."""
    r = a["repartition"]
    return " · ".join(f"{r[nom]} {lib}" for nom, lib in
                      (("≥ 75", "à 75 et plus"), ("60–74", "de 60 à 74"),
                       ("40–59", "de 40 à 59"), ("< 40", "sous 40")))


def ligne_sans_score(a):
    xs = a["sans_score"]
    return (f"{len(xs)} valeur(s) sans Score BVC (cours périmé, suspension ou "
            f"couverture insuffisante) : {', '.join(x['symbol'] for x in xs)}.")


def _briefing(data):
    """La lecture de la séance, ou une chaîne vide. Ne lève jamais."""
    try:
        from pipeline.briefing import composer, texte
        return texte(composer(data))
    except Exception:                                     # noqa: BLE001
        return ""


AVERTISSEMENT = (
    "Information à caractère indicatif, non validée par l'AMMC ni par la Bourse "
    "de Casablanca. Ceci n'est ni un conseil en investissement, ni une offre, ni "
    "une sollicitation. Les cours sont différés et peuvent comporter des erreurs. "
    "Les performances passées ne préjugent pas des performances futures. Vous "
    "restez seul responsable de vos décisions."
)


def texte(a):
    L = []
    add = L.append
    add(f"BULLETIN BVC — séance du {_date_longue(a['seance'])}")
    add("=" * 58)
    add("")
    m = a["masi"]
    add(f"MASI   {_nb(m.get('value'), 2)}   {_pct(m.get('change_pct'))}")
    add(f"       {largeur_ligne(a)}")
    add("")
    if a["hausses"]:
        add("PLUS FORTES HAUSSES")
        for x in a["hausses"][:5]:
            add(f"   {x['symbol']:<6} {(x.get('name') or '')[:26]:<26} "
                f"{_nb(x.get('price'))} DH   {_pct(x.get('chg'))}")
        add("")
    if a["baisses"]:
        add("PLUS FORTES BAISSES")
        for x in a["baisses"][:5]:
            add(f"   {x['symbol']:<6} {(x.get('name') or '')[:26]:<26} "
                f"{_nb(x.get('price'))} DH   {_pct(x.get('chg'))}")
        add("")
    # ⚠️ LA LECTURE DE LA SÉANCE — ajoutée le 25/09/2026.
    #
    # Le bulletin listait l'indice, les extrêmes et les signaux. Il ne disait
    # pas CE QUE LA SÉANCE A ÉTÉ. Or la variation de l'indice, seule, se
    # trompe régulièrement de sens : le MASI est pondéré par les
    # capitalisations, et trois poids lourds suffisent à le porter pendant que
    # la majorité des valeurs recule.
    #
    # ⚠️ Ce bloc CONSTATE, il n'explique jamais. Aucune cause n'y est posée :
    # nous mesurons des cours et des volumes, pas des causes. Voir
    # `pipeline/briefing.py`.
    if a.get("briefing"):
        add(a["briefing"])
        add("")

    sb = a["score_bvc"]
    add(f"SCORE BVC — LES {min(len(sb), N_SCORE_BVC)} PLUS ÉLEVÉS "
        f"(sur {len(sb)} titres notés)")
    add(f"   {PHRASE_SCORE}")
    add(f"   {ligne_retenus()}")
    if sb:
        add(f"   Répartition : {ligne_repartition(a)}")
        for x in sb[:N_SCORE_BVC]:
            v = valeur_bvc(x)
            c = (x.get("_meta") or {}).get("confidence")
            add(f"   {x['symbol']:<6} {(x.get('name') or '')[:26]:<26} "
                f"{_score(v):>4}/100  {tranche_bvc(v):<6} confiance {c}/5")
            if mention_offre(x):
                add(f"          ↳ {mention_offre(x)}")
    else:
        add("   Aucun Score BVC publiable sur cette séance.")
    if phrase_mesure(a.get("mesure")):
        add(f"   {phrase_mesure(a.get('mesure'))}")
    add("")
    add("CE QUE CE BULLETIN NE SAIT PAS")
    add(f"   {a['non_cotes']} valeur(s) n'ont pas coté : leur prix est celui "
        f"de la dernière séance où elles l'ont fait.")
    if a["sans_score"]:
        add(f"   {ligne_sans_score(a)}")
    if a["insuffisants"]:
        add(f"   {len(a['insuffisants'])} valeur(s) sans données suffisantes "
            f"(confiance ≤ 1), score non mis en avant : "
            f"{', '.join(x['symbol'] for x in a['insuffisants'])}.")
    add("")
    add(f"Terminal complet : {TERMINAL}")
    add("")
    add("-" * 58)
    add(AVERTISSEMENT)
    return "\n".join(L)


def html(a):
    m = a["masi"]
    coul = "#1c6b4a" if (m.get("change_pct") or 0) >= 0 else "#a32b21"

    def lignes(xs, n=5):
        out = []
        for x in xs[:n]:
            c = "#1c6b4a" if (x.get("chg") or 0) >= 0 else "#a32b21"
            out.append(
                f'<tr><td style="padding:7px 10px;font-family:monospace;'
                f'font-weight:600">{x["symbol"]}</td>'
                f'<td style="padding:7px 10px;color:#414b58">'
                f'{(x.get("name") or "")[:30]}</td>'
                f'<td style="padding:7px 10px;text-align:right;'
                f'font-family:monospace">{_nb(x.get("price"))}</td>'
                f'<td style="padding:7px 10px;text-align:right;'
                f'font-family:monospace;color:{c};font-weight:600">'
                f'{_pct(x.get("chg"))}</td></tr>')
        return "".join(out)

    scores = "".join(
        f'<tr><td style="padding:7px 10px;font-family:monospace;'
        f'font-weight:600">{x["symbol"]}</td>'
        f'<td style="padding:7px 10px;color:#414b58">'
        f'{escape((x.get("name") or "")[:30], quote=False)}</td>'
        f'<td style="padding:7px 10px;text-align:right;font-family:monospace">'
        f'{_score(valeur_bvc(x))}/100</td>'
        f'<td style="padding:7px 10px;text-align:right;font-family:monospace;'
        f'color:#414b58">{escape(tranche_bvc(valeur_bvc(x)), quote=False)}</td>'
        f'<td style="padding:7px 10px;text-align:right;font-family:monospace;'
        f'color:#6d7887">{(x.get("_meta") or {}).get("confidence")}/5</td></tr>'
        + (f'<tr><td></td><td colspan="4" style="padding:0 10px 9px;font-size:12.5px;'
           f'color:#9a5b00">↳ {escape(mention_offre(x), quote=False)}</td></tr>' if mention_offre(x) else "")
        for x in a["score_bvc"][:N_SCORE_BVC]) or (
        '<tr><td colspan="5" style="padding:12px 10px;color:#6d7887">'
        'Aucun Score BVC publiable sur cette séance.</td></tr>')
    rep = (f'<p style="font-size:12.5px;color:#414b58;margin:0 0 8px">Répartition&nbsp;: '
           f'{escape(ligne_repartition(a), quote=False)}</p>' if a["score_bvc"] else "")
    mes = phrase_mesure(a.get("mesure"))
    mes = (f'<p style="font-size:12px;color:#6d7887;margin:0 0 22px;line-height:1.6">'
           f'{escape(mes, quote=False)}</p>' if mes else '<div style="margin-bottom:22px"></div>')

    ins = ""
    if a["sans_score"]:
        ins += f"<li>{escape(ligne_sans_score(a), quote=False)}</li>"
    if a["insuffisants"]:
        ins += (f"<li>{len(a['insuffisants'])} valeur(s) sans données "
                f"suffisantes (confiance ≤ 1), score non mis en avant : "
                f"{', '.join(x['symbol'] for x in a['insuffisants'])}.</li>")

    th = ('style="padding:8px 10px;text-align:left;font-size:11px;'
          'letter-spacing:.1em;text-transform:uppercase;color:#6d7887;'
          'border-bottom:1px solid #d5dae1"')
    thr = th.replace("text-align:left", "text-align:right")

    return f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',
Roboto,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#161b22;
background:#ffffff;line-height:1.6">

  <p style="font-family:monospace;font-size:11px;letter-spacing:.16em;
     text-transform:uppercase;color:#9a5b00;margin:0 0 6px">Bulletin quotidien</p>
  <h1 style="font-size:22px;margin:0 0 4px;font-weight:700">BVC Analyzer</h1>
  <p style="margin:0 0 22px;color:#414b58">Séance du {_date_longue(a['seance'])}</p>

  <div style="background:#f6f7f9;border-radius:8px;padding:16px 18px;
       margin-bottom:22px">
    <div style="font-size:12px;color:#6d7887;letter-spacing:.08em;
         text-transform:uppercase">MASI</div>
    <div style="font-size:26px;font-weight:700;font-family:monospace;
         margin:2px 0">{_nb(m.get('value'), 2)}
      <span style="font-size:17px;color:{coul}">{_pct(m.get('change_pct'))}</span>
    </div>
    <div style="font-size:13px;color:#414b58">{largeur_ligne(a)}</div>
  </div>

  <h2 style="font-size:15px;margin:0 0 8px">Plus fortes hausses</h2>
  <table style="width:100%;border-collapse:collapse;font-size:14px;
         margin-bottom:22px">
    <tr><th {th}>Valeur</th><th {th}></th><th {thr}>Cours</th>
        <th {thr}>Var.</th></tr>
    {lignes(a['hausses'])}
  </table>

  <h2 style="font-size:15px;margin:0 0 8px">Plus fortes baisses</h2>
  <table style="width:100%;border-collapse:collapse;font-size:14px;
         margin-bottom:22px">
    <tr><th {th}>Valeur</th><th {th}></th><th {thr}>Cours</th>
        <th {thr}>Var.</th></tr>
    {lignes(a['baisses'])}
  </table>

  {_briefing_html(a)}

  <h2 style="font-size:15px;margin:0 0 4px">
    Score BVC — les {min(len(a['score_bvc']), N_SCORE_BVC)} plus élevés
    (sur {len(a['score_bvc'])} titres notés)</h2>
  <p style="font-size:12.5px;color:#6d7887;margin:0 0 4px">{escape(PHRASE_SCORE, quote=False)}</p>
  <p style="font-size:12.5px;color:#6d7887;margin:0 0 8px">{escape(ligne_retenus(), quote=False)}</p>
  {rep}
  <table style="width:100%;border-collapse:collapse;font-size:14px;
         margin-bottom:10px">
    <tr><th {th}>Valeur</th><th {th}></th><th {thr}>Score BVC</th>
        <th {thr}>Tranche</th><th {thr}>Confiance</th></tr>
    {scores}
  </table>
  {mes}

  <div style="background:#f6f7f9;border-left:3px solid #9a5b00;
       border-radius:0 6px 6px 0;padding:14px 16px;margin-bottom:22px">
    <p style="margin:0 0 6px;font-weight:600;font-size:13.5px">
      Ce que ce bulletin ne sait pas</p>
    <ul style="margin:0;padding-left:18px;font-size:13.5px;color:#414b58">
      <li>{a['non_cotes']} valeur(s) n'ont pas coté : leur prix est celui de la
          dernière séance où elles l'ont fait.</li>
      {ins}
    </ul>
  </div>

  <p style="margin:0 0 22px">
    <a href="{TERMINAL}" style="background:#161b22;color:#ffffff;
       text-decoration:none;padding:11px 20px;border-radius:6px;
       display:inline-block;font-size:14px">Ouvrir le terminal</a>
  </p>

  <p style="font-size:11.5px;color:#6d7887;border-top:1px solid #d5dae1;
     padding-top:14px;margin:0;line-height:1.7">{AVERTISSEMENT}</p>
</div>"""


def main():
    try:
        data, titres = charger(sys.argv[1] if len(sys.argv) > 1 else None)
    except Exception as e:
        print(f"data.json illisible : {e}", file=sys.stderr)
        return 1

    a = analyser(data, titres)

    # ⚠️ Refus d'envoi plutôt qu'un bulletin creux. Un courriel qui arrive tous
    # les matins finit par être lu sans vérification : il ne doit jamais porter
    # une séance que la collecte n'a pas réellement établie.
    if a["n_seance"] < MIN_TITRES_SEANCE:
        print(f"Collecte insuffisante : {a['n_seance']} titres à la séance "
              f"{a['seance']} (minimum {MIN_TITRES_SEANCE}) — bulletin NON envoyé.",
              file=sys.stderr)
        return 2

    sujet = (f"BVC — séance du {_date_longue(a['seance'])} · "
             f"MASI {_nb(a['masi'].get('value'), 2)} "
             f"({_pct(a['masi'].get('change_pct'))})")

    sortie = Path("bulletin_out")
    sortie.mkdir(exist_ok=True)
    (sortie / "sujet.txt").write_text(sujet, encoding="utf-8")
    (sortie / "corps.txt").write_text(texte(a), encoding="utf-8")
    (sortie / "corps.html").write_text(html(a), encoding="utf-8")
    print(sujet)
    return 0


if __name__ == "__main__":
    sys.exit(main())

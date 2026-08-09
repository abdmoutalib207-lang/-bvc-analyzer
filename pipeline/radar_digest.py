#!/usr/bin/env python3
"""
Radar BVC — génère un bulletin WhatsApp prêt à publier depuis news.json.

Utilisable immédiatement : le résultat se copie-colle dans la chaîne. WhatsApp
n'expose aucune API publique pour les chaînes, donc la publication reste
manuelle tant qu'on n'est pas passé par l'API Business.

Usage :
    python3 pipeline/radar_digest.py                 # les 6 dernières heures
    python3 pipeline/radar_digest.py --heures 24     # la journée
    python3 pipeline/radar_digest.py --max 8         # limiter le nombre
    python3 pipeline/radar_digest.py --cat bvc       # une seule rubrique

Mise en forme WhatsApp : *gras*, _italique_. Les liens sont laissés bruts,
WhatsApp les rend cliquables et génère l'aperçu.
"""
import json, argparse, re
from datetime import datetime, timezone, timedelta
from pathlib import Path

NEWS = Path(__file__).parent.parent / "news.json"

# Ordre d'affichage : le marché d'abord, le contexte ensuite.
RUBRIQUES = [
    ("bvc",          "🇲🇦 MARCHÉ BVC"),
    ("macro",        "🏛️ MACRO"),
    ("economie",     "📈 ÉCONOMIE"),
    ("commodites",   "🛢️ MATIÈRES PREMIÈRES"),
    ("geopolitique", "🌍 GÉOPOLITIQUE"),
]
SENTIMENT = {"POSITIF": "🟢", "NEGATIF": "🔴"}   # NEUTRE : pas de pastille

# Sujets à écarter du bulletin. Les éditeurs généralistes publient sport,
# culture et société dans le même flux que l'économie ; ces articles héritent
# alors de la catégorie de leur source et se retrouvent en « Marché BVC ».
HORS_SUJET = re.compile(
    r"\b(football|foot|athl[ée]tisme|basket|tennis|handball|olympique|mondiaux|"
    r"CAN\b|s[ée]lection nationale|joueur|entra[îi]neur|club|match|"
    r"cin[ée]ma|festival|film|musique|concert|art\b|exposition|"
    r"m[ée]t[ée]o|canicule|s[ée]isme|accident|fait divers|proc[èe]s|"
    r"pape|religion|ramadan|a[îi]d)\b", re.IGNORECASE)


_CACHE_URL = Path(__file__).parent / ".radar_liens_courts.json"


def raccourcir(url: str) -> str:
    """Raccourcit une URL Google News, sinon renvoie l'URL telle quelle.

    Les liens relayés par Google font jusqu'à 500 caractères et occupent huit
    lignes dans un message WhatsApp. Leur jeton est opaque et la redirection se
    fait côté navigateur : l'adresse d'origine n'est pas récupérable, on passe
    donc par un raccourcisseur.

    Le résultat est mis en cache sur disque — un même article peut apparaître
    dans plusieurs bulletins, inutile de rappeler le service. En cas d'échec
    (service indisponible, quota), on retombe sur l'URL longue : un lien laid
    vaut mieux qu'un lien absent.
    """
    if not url or "news.google.com" not in url:
        return url
    cache = {}
    if _CACHE_URL.exists():
        try:
            cache = json.loads(_CACHE_URL.read_text(encoding="utf-8"))
        except Exception:
            pass
    if url in cache:
        return cache[url]
    try:
        import requests
        from urllib.parse import quote
        r = requests.get("https://tinyurl.com/api-create.php?url=" + quote(url, safe=""),
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        court = r.text.strip()
        if r.ok and court.startswith("http"):
            cache[url] = court
            # bornage : le cache ne doit pas gonfler indéfiniment
            if len(cache) > 800:
                cache = dict(list(cache.items())[-500:])
            _CACHE_URL.write_text(json.dumps(cache), encoding="utf-8")
            return court
    except Exception:
        pass
    return url


def _dt(article):
    """Date de l'article en UTC, ou None si illisible."""
    raw = (article.get("date") or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            d = datetime.strptime(raw[:26] if "+" in raw[19:] else raw[:19], fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def construire(heures=6, maxi=12, rubrique=None):
    data = json.load(open(NEWS, encoding="utf-8"))
    articles = data.get("articles", data if isinstance(data, list) else [])
    limite = datetime.now(timezone.utc) - timedelta(hours=heures)

    recents, vus = [], set()
    for a in articles:
        d = _dt(a)
        if not d or d < limite:
            continue
        titre = (a.get("title") or "").strip()
        cle = re.sub(r"\W+", "", titre.lower())[:60]
        if not titre or cle in vus:          # dédoublonnage : le relais Google
            continue                          # peut répéter un même article
        if not (a.get("url") or "").strip():
            continue                          # sans lien, le lecteur ne peut
                                              # pas vérifier — on écarte
        if HORS_SUJET.search(titre) and not a.get("tickers"):
            continue                          # un article taggué ticker reste
        vus.add(cle)                          # pertinent même s'il parle de sport
        recents.append(a)

    if rubrique:
        recents = [a for a in recents if a.get("category") == rubrique]

    # Sélection par quotas plutôt que par tri global : un simple classement
    # laissait la rubrique « économie », la plus volumineuse, occuper tout le
    # bulletin — champagne et football compris — pendant que la BVC disparaissait.
    QUOTAS = {"bvc": 5, "macro": 2, "commodites": 2, "economie": 3, "geopolitique": 2}

    def rang(a):
        # à l'intérieur d'une rubrique : ticker BVC, puis lien direct (ceux
        # relayés par Google font 300 caractères), puis le plus récent
        direct = "news.google.com" not in (a.get("url") or "")
        d = _dt(a) or datetime.min.replace(tzinfo=timezone.utc)
        return (bool(a.get("tickers")), direct, d)

    if rubrique:
        recents = sorted(recents, key=rang, reverse=True)[:maxi]
    else:
        retenus = []
        for cat, quota in QUOTAS.items():
            lot = sorted((a for a in recents if a.get("category") == cat),
                         key=rang, reverse=True)
            retenus.extend(lot[:quota])
        # complète avec le meilleur du reste si les quotas n'ont pas rempli
        if len(retenus) < maxi:
            reste = [a for a in recents if a not in retenus]
            retenus.extend(sorted(reste, key=rang, reverse=True)[:maxi - len(retenus)])
        recents = retenus[:maxi]

    if not recents:
        return None, 0

    maintenant = datetime.now(timezone.utc) + timedelta(hours=1)   # Casablanca
    out = [f"📡 *RADAR BVC* — {maintenant.strftime('%d/%m/%Y · %H:%M')}",
           f"_Dernières {heures}h · {len(recents)} actualités_", ""]

    for cat, entete in RUBRIQUES:
        lot = [a for a in recents if a.get("category") == cat]
        if not lot:
            continue
        out.append(f"*{entete}*")
        for a in lot:
            puce = SENTIMENT.get(a.get("sentiment"), "•")
            tickers = a.get("tickers") or []
            tag = f" `{' '.join(tickers[:3])}`" if tickers else ""
            out.append(f"{puce} {a['title'].strip()}{tag}")
            out.append(f"   _{a.get('source', '?')}_ — {raccourcir(a.get('url', ''))}")
        out.append("")

    out.append("—")
    out.append("_Information financière, pas un conseil en investissement._")
    return "\n".join(out), len(recents)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Bulletin WhatsApp Radar BVC")
    ap.add_argument("--heures", type=int, default=6, help="fenêtre en heures (défaut 6)")
    ap.add_argument("--max",    type=int, default=12, help="nombre max d'articles")
    ap.add_argument("--cat",    default=None, help="bvc | macro | economie | commodites | geopolitique")
    a = ap.parse_args()

    texte, n = construire(a.heures, a.max, a.cat)
    if not texte:
        print(f"Aucune actualité sur les {a.heures} dernières heures.")
    else:
        print(texte)
        print(f"\n[{n} articles · {len(texte)} caractères]", flush=True)

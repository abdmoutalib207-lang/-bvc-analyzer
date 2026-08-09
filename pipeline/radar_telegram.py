#!/usr/bin/env python3
"""
Radar BVC — relais Telegram.

Pousse les nouvelles actualités vers un bot Telegram privé. Tu reçois une
notification sur ton téléphone, tu copies, tu colles dans la chaîne WhatsApp.

Pourquoi Telegram et pas WhatsApp directement : WhatsApp n'expose aucune API
publique pour les chaînes. Les bibliothèques qui pilotent WhatsApp Web violent
ses conditions d'utilisation et font risquer le bannissement du numéro.
Telegram, lui, offre une API officielle et gratuite. Le relais sert donc de
sonnette : il prévient, l'humain publie.

Le texte envoyé est déjà au format WhatsApp (*gras*, _italique_) et part en
clair, sans parse_mode : les marqueurs restent visibles dans Telegram mais
deviennent du vrai formatage une fois collés dans WhatsApp.

Configuration (variables d'environnement) :
    TELEGRAM_BOT_TOKEN   jeton donné par @BotFather
    TELEGRAM_CHAT_ID     ton identifiant de conversation avec le bot

Usage :
    python3 pipeline/radar_telegram.py --test        # vérifie la connexion
    python3 pipeline/radar_telegram.py               # envoie les nouveautés
    python3 pipeline/radar_telegram.py --dry-run     # affiche sans envoyer
    python3 pipeline/radar_telegram.py --bulletin    # envoie le digest complet
"""
import json, os, sys, argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from radar_digest import construire, HORS_SUJET, _dt   # même logique de tri

RACINE = Path(__file__).parent.parent
NEWS   = RACINE / "news.json"
# Mémoire des articles déjà relayés : sans elle, chaque run renverrait tout.
ETAT   = Path(__file__).parent / ".radar_envoyes.json"
API    = "https://api.telegram.org/bot{token}/{methode}"

# Une alerte sonne sur le téléphone : le seuil doit être exigeant. La
# catégorie ne suffit pas — elle est attribuée par SOURCE, si bien qu'un
# classement d'universités publié par L'Économiste arrive étiqueté « bvc ».
# On exige donc un vocabulaire de marché explicite dans le titre.
import re as _re
MOTS_MARCHE = _re.compile(
    r"\b(bourse|MASI|MSI20|cotation|cot[ée]e?s?|action(s|naire)?|titre[s]?|"
    r"dividende|r[ée]sultat[s]?|b[ée]n[ée]fice|chiffre d'affaires|CA\b|"
    r"augmentation de capital|introduction en bourse|IPO|OPA|OPV|"
    r"split|scission|fusion|acquisition|[ée]mission obligataire|"
    r"AMMC|communiqu[ée]|assembl[ée]e g[ée]n[ée]rale|AGO|AGE\b|"
    r"capitalisation|volume|s[ée]ance|cl[ôo]ture|indice)\b", _re.IGNORECASE)


def merite_alerte(a):
    """Un article taggué ticker passe toujours ; sinon il faut du vocabulaire
    de marché ET la catégorie bvc. Les autres restent dans le bulletin."""
    if a.get("tickers"):
        return True
    titre = (a.get("title") or "")
    return a.get("category") == "bvc" and bool(MOTS_MARCHE.search(titre))


def _charger_etat():
    if ETAT.exists():
        try:
            return set(json.loads(ETAT.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def _sauver_etat(ids):
    # On ne garde que les 500 derniers : l'archive news.json fait 300 articles
    # sur 7 jours, cette marge suffit à ne jamais renvoyer un doublon.
    ETAT.write_text(json.dumps(sorted(ids)[-500:]), encoding="utf-8")


def envoyer(texte, token, chat_id, apercu=False):
    import requests
    r = requests.post(
        API.format(token=token, methode="sendMessage"),
        json={
            "chat_id": chat_id,
            "text": texte,
            # pas de parse_mode : les marqueurs WhatsApp doivent rester bruts
            "disable_web_page_preview": not apercu,
        },
        timeout=20,
    )
    if not r.ok:
        detail = r.json().get("description", r.text[:120]) if r.content else r.status_code
        raise RuntimeError(f"Telegram a refusé l'envoi : {detail}")
    return True


def formater(a):
    """Un article, au format prêt à coller dans WhatsApp."""
    puce = {"POSITIF": "🟢", "NEGATIF": "🔴"}.get(a.get("sentiment"), "•")
    tk = a.get("tickers") or []
    tag = f" `{' '.join(tk[:3])}`" if tk else ""
    return (f"📡 *RADAR BVC*\n\n"
            f"{puce} {a['title'].strip()}{tag}\n"
            f"_{a.get('source', '?')}_\n{a.get('url', '')}\n\n"
            f"—\n_Information financière, pas un conseil en investissement._")


def main():
    ap = argparse.ArgumentParser(description="Relais Telegram Radar BVC")
    ap.add_argument("--test",     action="store_true", help="vérifie la connexion au bot")
    ap.add_argument("--dry-run",  action="store_true", help="affiche sans envoyer")
    ap.add_argument("--bulletin", action="store_true", help="envoie le digest complet")
    ap.add_argument("--heures",   type=int, default=6, help="fenêtre pour --bulletin")
    ap.add_argument("--max",      type=int, default=5, help="max d'alertes par run")
    a = ap.parse_args()

    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not a.dry_run and not (token and chat_id):
        print("❌ TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID doivent être définis.\n"
              "   1. Sur Telegram, écris à @BotFather → /newbot → récupère le jeton\n"
              "   2. Écris un message à ton bot, puis ouvre :\n"
              "      https://api.telegram.org/bot<JETON>/getUpdates\n"
              "      pour lire ton chat_id\n"
              "   3. export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...")
        return 1

    if a.test:
        envoyer("📡 *RADAR BVC*\n\nRelais Telegram opérationnel.\n"
                "Les alertes marché arriveront ici, prêtes à coller dans la chaîne.",
                token, chat_id)
        print("✅ Message de test envoyé.")
        return 0

    if a.bulletin:
        texte, n = construire(a.heures, 12, None)
        if not texte:
            print(f"Aucune actualité sur les {a.heures} dernières heures.")
            return 0
        if a.dry_run:
            print(texte)
        else:
            envoyer(texte, token, chat_id)
        print(f"✅ Bulletin de {n} actualités {'affiché' if a.dry_run else 'envoyé'}.")
        return 0

    # ── alertes individuelles ────────────────────────────────────────
    data = json.loads(NEWS.read_text(encoding="utf-8"))
    articles = data.get("articles", data if isinstance(data, list) else [])
    deja = _charger_etat()
    limite = datetime.now(timezone.utc) - timedelta(hours=24)

    nouveaux = []
    for art in articles:
        aid = art.get("id") or art.get("url", "")
        d = _dt(art)
        titre = (art.get("title") or "").strip()
        if (not aid or aid in deja or not d or d < limite or not titre
                or not (art.get("url") or "").strip()
                or not merite_alerte(art)
                or (HORS_SUJET.search(titre) and not art.get("tickers"))):
            continue
        nouveaux.append(art)

    # Les articles rattachés à un ticker passent devant, puis les plus récents.
    nouveaux.sort(key=lambda x: (bool(x.get("tickers")), _dt(x) or datetime.min.replace(tzinfo=timezone.utc)),
                  reverse=True)
    retenus = nouveaux[:a.max]

    if not retenus:
        print("Aucune nouvelle actualité marché à relayer.")
        return 0

    for art in retenus:
        texte = formater(art)
        if a.dry_run:
            print(texte, "\n" + "═" * 50)
        else:
            envoyer(texte, token, chat_id, apercu=True)
        deja.add(art.get("id") or art.get("url", ""))

    if not a.dry_run:
        _sauver_etat(deja)
    print(f"✅ {len(retenus)} alerte(s) {'affichée(s)' if a.dry_run else 'envoyée(s)'}"
          f" — {len(nouveaux) - len(retenus)} en attente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

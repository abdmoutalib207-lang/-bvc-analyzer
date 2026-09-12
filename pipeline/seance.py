"""Détection des séances fantômes dans les chandelles.

Une séance fantôme est une date pour laquelle nos sources publient des cours
alors que la Bourse n'a pas ouvert. Le cas relevé le 14/08/2026 — férié au
Maroc — est le modèle du genre : IDBourse et Médias24 ont l'une et l'autre
rediffusé la clôture du 13/08 en l'estampillant du 14. Trois écrivains de
chandelles ont suivi (`update_data.py` étape 6c, `generate_candles.py`,
`collect_history_bvcscrap.py`), pour 71 puis 43 bougies dupliquées.

La règle R9 (chg=0 ET vol=0) ne voit rien : les sources rediffusent aussi la
variation de la veille, si bien que 67 titres sur 77 portaient un chg non nul.
Le signal n'existe qu'à l'échelle du marché — une séance réelle ne reproduit
jamais toutes les clôtures au centime près. Mesuré sur les deux cas :
71/71 clôtures identiques le 14/08 (férié), 6/44 le 13/08 (séance cotée).
La marge est telle qu'un seuil à 95 % ne peut pas se tromper de côté.

Aucun calendrier de jours fériés n'est nécessaire : le test se déduit des
données. C'est ce qui le rend fiable — la liste des fériés marocains est
mobile (fêtes religieuses au calendrier lunaire) et nous ne la maintenons pas.

Un balayage après écriture, plutôt qu'une garde chez chaque écrivain : les
sources livrent ticker par ticker et aucune n'a la vue d'ensemble au moment
d'écrire. C'est aussi la seule forme qui répare l'existant.
"""

import json
import logging
from collections import Counter
from pathlib import Path

log = logging.getLogger(__name__)

CANDLES_DIR = Path(__file__).parent / "candles"

# En deçà, l'échantillon ne dit rien : quelques titres illiquides clôturent
# légitimement au même cours deux séances de suite.
MIN_TITRES = 20
SEUIL = 0.95


def purger_seance_fantome(candles_dir=None, dry_run=False):
    """Retire la dernière séance des chandelles si c'est une rediffusion.

    Ne regarde que la séance la plus récente du marché — celle qu'un run vient
    d'écrire. Les séances plus anciennes ne sont pas touchées : les corriger
    demanderait de rejouer tout l'historique, et une erreur ancienne se traite
    au bulletin CDG, pas à l'aveugle.

    Retourne (date_purgée, nombre_de_fichiers) ou (None, 0) si rien à faire.
    """
    d = Path(candles_dir) if candles_dir else CANDLES_DIR
    if not d.exists():
        return None, 0

    series = {}
    for f in d.glob("*.json"):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(s, list) and len(s) >= 2:
            series[f] = s

    if not series:
        return None, 0

    # La séance à examiner est la plus récente du marché, pas celle de chaque
    # titre : un titre peu liquide peut ne pas avoir coté ce jour-là.
    derniere = max(s[-1].get("d", "") for s in series.values())
    if not derniere:
        return None, 0

    concernes = {f: s for f, s in series.items() if s[-1].get("d") == derniere}
    ident = sum(
        1 for s in concernes.values()
        if round(float(s[-1].get("c") or 0), 2) == round(float(s[-2].get("c") or -1), 2)
    )
    total = len(concernes)

    if total < MIN_TITRES or ident / total < SEUIL:
        return None, 0

    veille = Counter(s[-2].get("d") for s in concernes.values()).most_common(1)[0][0]
    log.warning(
        f"Séance fantôme {derniere} : {ident}/{total} clôtures identiques au "
        f"{veille}. Marché fermé (férié ?) — bougies retirées."
        + (" [simulation]" if dry_run else ""))

    if dry_run:
        return derniere, total

    n = 0
    for f, s in concernes.items():
        s.pop()
        f.write_text(json.dumps(s, separators=(",", ":")), encoding="utf-8")
        n += 1
    return derniere, n


def purger_suspensions(candles_dir=None, historique=None, dry_run=False):
    """Retire toute chandelle tombant pendant une suspension de cotation.

    POURQUOI UN BALAYAGE, ET NON UNE GARDE À L'ÉCRITURE
    ───────────────────────────────────────────────────
    L'étape 6c d'`update_data.py` refuse déjà d'écrire pour un titre suspendu.
    Elle ne suffit pas : **trois programmes écrivent des chandelles**, et
    `collect_history_bvcscrap.py` réécrit `historical_data.json` depuis la
    source, sans connaître le registre des suspensions. Vérifié le 10/09/2026 :
    un re-téléchargement ramenait les 28 séances fantômes de CMT que le
    nettoyage manuel de la veille avait retirées.

    C'est exactement le motif du 14/08 — une garde posée chez un seul écrivain
    ne tient qu'un run — et la réponse est la même : un balayage GLOBAL et
    POSTÉRIEUR, que chaque écrivain appelle après avoir écrit. C'est aussi la
    seule forme qui répare l'existant, y compris ce qu'un autre programme vient
    de déposer.

    Signalé par l'audit externe : « le bon contrôle n'est pas *le fichier a été
    corrigé*, c'est *la correction traverse toutes les étapes* ».

    Retourne (nombre_de_bougies_retirées, nombre_de_fichiers_touchés).
    """
    try:
        from bvc_config import SUSPENSIONS
    except ImportError:                                       # pragma: no cover
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from bvc_config import SUSPENSIONS
    if not SUSPENSIONS:
        return 0, 0

    def _fantome(ticker, jour):
        for p in SUSPENSIONS.get(ticker, ()):
            fin = p.get("reprise") or "9999-12-31"
            if p["depuis"] <= jour < fin:
                return True
        return False

    retirees = fichiers = 0

    d = Path(candles_dir) if candles_dir else CANDLES_DIR
    if d.exists():
        for ticker in SUSPENSIONS:
            f = d / f"{ticker}.json"
            if not f.exists():
                continue
            try:
                s = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            garde = [b for b in s if not _fantome(ticker, str(b.get("d", ""))[:10])]
            if len(garde) != len(s):
                retirees += len(s) - len(garde)
                fichiers += 1
                if not dry_run:
                    f.write_text(json.dumps(garde, separators=(",", ":")),
                                 encoding="utf-8")

    h = Path(historique) if historique else CANDLES_DIR.parent / "historical_data.json"
    if h.exists():
        try:
            data = json.loads(h.read_text(encoding="utf-8"))
        except Exception:
            return retirees, fichiers
        touche = False
        for ticker in SUSPENSIONS:
            e = data.get(ticker)
            if not isinstance(e, dict) or "candles" not in e:
                continue
            s = e["candles"]
            garde = [b for b in s if not _fantome(ticker, str(b.get("d", ""))[:10])]
            if len(garde) == len(s):
                continue
            retirees += len(s) - len(garde)
            touche = True
            e["candles"] = garde
            # ⚠️ Les champs DÉRIVÉS doivent suivre, sinon ils décrivent une
            # série qui n'existe plus — piège `n_candles` du 14/08, dans lequel
            # on est retombé le 09/09 (542 annoncées pour 222 réelles).
            if garde:
                e["last_close"] = garde[-1].get("c")
                e["last_date"] = garde[-1].get("d")
            # ⚠️ ON NE TOUCHE PAS À `n_candles`. Il compte la SÉRIE SOURCE, pas
            # la liste stockée — tronquée à 250 points (CLAUDE.md, l. 697). Le
            # 09/09 je l'ai « corrigé » à la longueur de la liste purgée : 222
            # pour une série de 514. C'était le piège du 14/08, dans lequel je
            # suis tombé en croyant le réparer. Ce champ appartient au moteur,
            # qui seul connaît la longueur de la série source ; un balayage
            # postérieur n'a pas cette information et doit s'abstenir.
        if touche:
            fichiers += 1
            if not dry_run:
                h.write_text(json.dumps(data, separators=(",", ":")),
                             encoding="utf-8")

    return retirees, fichiers


def reparer_ohlc(candles_dir=None, dry_run=False):
    """Force l'invariant `l ≤ min(o, c) ≤ max(o, c) ≤ h` sur toutes les bougies.

    POURQUOI
    ────────
    Découvert le 04/09/2026 en recoupant nos chandelles ADI avec la page
    officielle `casablanca-bourse.com/market-data/cours` : les dates et les
    ouvertures concordaient 10/10, mais plusieurs bougies portaient un plus
    haut INFÉRIEUR à leur ouverture. Structurellement impossible.

    Cause : l'étape 6c d'`update_data.py` amorçait `h` et `l` sur la seule
    clôture, puis ne les étendait qu'avec les cours suivants. L'ouverture,
    qui vient d'une autre source, n'entrait jamais dans la fourchette. Dès que
    o ≠ c la bougie naissait fausse — d'où **3 238 bougies sur 32 677 (9,9 %),
    sur 73 tickers**. La source est corrigée ; ceci répare l'existant.

    ⚠️ CE QUE CETTE RÉPARATION N'EST PAS. Elle n'invente aucun extrême et ne
    prétend pas retrouver le vrai plus-haut de la séance. Elle n'écrit que ce
    qui est certain : le titre a coté à `o` et à `c`, donc son plus haut réel
    était au moins `max(o, c)` et son plus bas au plus `min(o, c)`. Les bornes
    obtenues restent des minorants — la vraie amplitude intraday leur est
    supérieure ou égale. C'est le seul élargissement démontrable sans source
    intraday, et il est strictement plus juste que l'état actuel.

    Retourne (bougies_corrigées, fichiers_touchés).
    """
    d = Path(candles_dir) if candles_dir else CANDLES_DIR
    if not d.exists():
        return 0, 0

    total, fichiers = 0, 0
    for f in sorted(d.glob("*.json")):
        try:
            serie = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(serie, list):
            continue

        n = 0
        for bougie in serie:
            o, h, l, c = (bougie.get(k) for k in ("o", "h", "l", "c"))
            if None in (o, h, l, c):
                continue
            try:
                o, h, l, c = float(o), float(h), float(l), float(c)
            except (TypeError, ValueError):
                continue
            haut, bas = round(max(h, o, c), 2), round(min(l, o, c), 2)
            if haut != round(h, 2) or bas != round(l, 2):
                bougie["h"], bougie["l"] = haut, bas
                n += 1

        if n and not dry_run:
            f.write_text(json.dumps(serie, separators=(",", ":")), encoding="utf-8")
        if n:
            total += n
            fichiers += 1

    if total:
        log.warning(
            f"OHLC incohérentes : {total} bougies sur {fichiers} tickers — "
            f"fourchette élargie à [min(o,c), max(o,c)]."
            + (" [simulation]" if dry_run else ""))
    return total, fichiers


def derniere_seance_connue(candles_dir=None):
    """Date de la séance la plus récente présente dans les chandelles.

    Sert de repère quand la source est muette : sans elle, rien ne permet de
    contredire une charge utile qui se date elle-même du jour. Renvoie une
    chaîne « AAAA-MM-JJ », ou "" si aucune chandelle n'est lisible.
    """
    d = Path(candles_dir) if candles_dir else CANDLES_DIR
    if not d.exists():
        return ""
    dernieres = []
    for f in d.glob("*.json"):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(s, list) and s:
            dernieres.append(s[-1].get("d") or "")
    return max(dernieres) if dernieres else ""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="signaler sans modifier les fichiers")
    p.add_argument("--ohlc", action="store_true",
                   help="réparer les fourchettes qui n'englobent pas o/c")
    a = p.parse_args()
    if a.ohlc:
        n, fichiers = reparer_ohlc(dry_run=a.dry_run)
        print(f"{n} bougies corrigées sur {fichiers} tickers"
              if n else "aucune bougie incohérente")
    else:
        date, n = purger_seance_fantome(dry_run=a.dry_run)
        print(f"{n} bougies retirées ({date})" if date else "aucune séance fantôme")

"""Balayage des rapports annuels — le nombre d'actions et le résultat net.

POURQUOI CES DEUX FAITS, ET PAS D'AUTRES
────────────────────────────────────────
Les deux défauts trouvés les 07 et 08/09 sont l'un et l'autre des problèmes de
DÉNOMINATEUR ou d'IDENTITÉ :

- Managem : le BPA valait 234 pour un cours de 1 753, parce que le split 10:1
  du 27/07/2026 avait divisé le cours et pas le bénéfice par action. PER
  affiché 7,5 au lieu de 69.
- Marsa Maroc : le BPA était celui de Mutandis. Maroc Leasing portait la
  description de Marsa Maroc.

Le nombre d'actions et le résultat net part du groupe suffisent à débusquer
les deux, sur toute la cote :

    bpa_publié × nombre_d_actions  ≈  résultat net part du groupe ?

Un rapport de 10 signe un split non répercuté. Un écart sans rapport simple
signe une identité croisée. C'est un contrôle d'ORDRE DE GRANDEUR, pas de
précision comptable — et c'est précisément ce qu'il faut pour trouver des
erreurs d'un facteur 10.

⚠️ CE MODULE NE REMPLACE PAS LA LECTURE. Il signale les titres à ouvrir. Un
fait n'entre dans `faits_financiers.json` qu'avec sa PAGE, relevée à la main.
L'extraction automatique sert à savoir OÙ regarder, pas à publier.

⚠️ LES MISES EN PAGE VARIENT ÉNORMÉMENT d'un émetteur à l'autre. Le taux
d'extraction ne sera jamais de 100 %, et c'est normal. Le rapport final dit
explicitement ce qui n'a pas pu être lu, plutôt que de combler — une absence
se dit, elle ne se comble pas.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

CATALOGUE = Path(__file__).parent / "catalogue_ammc.json"
SORTIE = Path(__file__).parent / "balayage_rfa.json"
CACHE = Path("/tmp/rfa_cache")

UA = "BVC-Analyzer/1.0 (recherche quantitative; contact via le dépôt GitHub)"

# Valeurs nominales autorisées au Maroc. Sert à valider capital ÷ actions.
NOMINALES = (10, 50, 100, 250, 500, 1000)


def _telecharger(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 50_000:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=180) as r:
            data = r.read()
        if len(data) < 50_000 or not data[:5].startswith(b"%PDF"):
            return False
        dest.write_bytes(data)
        return True
    except Exception:
        return False


def _nombre(s: str):
    """« 2 207 858 800,00 » → 2207858800.0. Renvoie None si illisible."""
    s = s.strip().replace(" ", " ").replace(" ", "")
    if s.count(",") == 1 and (len(s.split(",")[1]) <= 2):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
        if s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[1]) == 3):
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


# ⚠️ Un motif trop large avale plusieurs nombres d'affilée. Premier essai le
# 08/09 : sur « Résultat net part du groupe MDH 3 002.0 619.8 2 382.2 384.3% »
# il rendait 3 002 061 982 382 238 — la ligne entière recollée, et le contrôle
# de cohérence aurait crié à l'erreur sur toute la cote. Un nombre s'arrête à
# sa décimale ; les groupes de trois chiffres ne se confondent pas avec le
# nombre suivant. L'ordre des alternatives compte : la forme séparée d'abord.
NB = (r"(\d{1,3}(?:[ \u00a0.]\d{3})+(?:[.,]\d{1,2})?"    # 1 186 467 600,00
      r"|\d+(?:[.,]\d{1,2})?)")                            # 3002.0 · 733956000


def _premier_plausible(ligne: str, etiquette: str, mini: float, maxi: float):
    """Le premier nombre de la ligne, APRÈS l'étiquette, qui tienne dans les
    bornes. Renvoie None si aucun ne convient.

    Prendre le premier nombre rencontré échoue dès qu'un appel de note, un
    numéro de rubrique ou une année s'intercale — et c'est fréquent dans un
    bilan. Balayer et filtrer par l'ordre de grandeur est à la fois plus simple
    et plus sûr que d'essayer d'écrire un motif qui les évite tous.
    """
    m = re.search(etiquette, ligne)
    if not m:
        return None
    for candidat in re.finditer(NB, ligne[m.end():]):
        v = _nombre(candidat.group(1))
        if v is not None and mini <= v <= maxi:
            return v
    return None


def extraire(pages: dict) -> dict:
    """Relève ce qui est trouvable, avec la page. Silence si rien de sûr."""
    res: dict = {}

    for i, t in pages.items():
        for l in t.split("\n"):
            # ── capital social ────────────────────────────────────────────
            # ⚠️ Ne PAS prendre le premier nombre venu. Le 08/09, sur
            # « * Capital social ou personnel (1) 733.956.000,00 », le motif
            # attrapait le « 1 » de l'appel de note et le rejetait ensuite
            # comme hors bornes — le capital de Marsa Maroc était donc déclaré
            # illisible alors qu'il figurait deux mots plus loin. On parcourt
            # désormais TOUS les nombres de la ligne et l'on retient le premier
            # qui tombe dans la fourchette plausible.
            if "capital" in l.lower() and "capital_social" not in res:
                v = _premier_plausible(l, r"[Cc]apital\s+social", 1e6, 5e10)
                if v is not None:
                    res["capital_social"] = {"valeur": v, "page": int(i)}

            # ── nombre d'actions ──────────────────────────────────────────
            if "action" in l.lower() and "nombre_actions" not in res:
                v = _premier_plausible(
                    l, r"[Nn]ombre\s+(?:moyen\s+)?d[e']\s?actions", 1e4, 1e10)
                if v is not None:
                    res["nombre_actions"] = {"valeur": v, "page": int(i)}

            # ── résultat net part du groupe ───────────────────────────────
            # ⚠️ Une ligne de PROSE contient aussi « résultat net part du
            # groupe ». Premier essai le 08/09 : « dépasse les 3 milliards de
            # dirhams » rendait 3, et « il s'est établi à » rendait 2025 —
            # l'année prise pour un montant. Une ligne de TABLEAU porte au
            # moins deux nombres, l'exercice et le précédent ; une phrase n'en
            # porte qu'un. C'est ce qui les sépare, sans dictionnaire.
            if "part du groupe" in l.lower() and "rnpg" not in res:
                m = re.search(r"[Rr]ésultat\s+[Nn]et.{0,40}[Pp]art\s+du\s+[Gg]roupe[^\d\-]{0,40}-?" + NB, l)
                if m and len(re.findall(NB, l)) >= 2:
                    v = _nombre(m.group(1))
                    # ⚠️ Borne haute : aucune société cotée à la BVC ne dégage
                    # 15 milliards de dirhams de résultat net — la plus grosse,
                    # Attijariwafa, tourne autour de 10,6. Au-delà, le nombre
                    # est un artefact de lecture, pas un montant. Sans cette
                    # borne, ATW sortait 6,76 × 10¹⁸ le 08/09. Les unités
                    # varient (MAD, KMAD, MMAD), d'où un plafond large.
                    if (v and abs(v) >= 100 and not (1990 <= v <= 2100)
                            and abs(v) <= 1.5e10):
                        res["rnpg"] = {"valeur": v, "page": int(i), "brut": l.strip()[:110]}

    return res


def deduire_actions(res: dict, actions_marche: float | None) -> dict:
    """Déduit le nombre d'actions du capital social — en tranchant la nominale.

    ⚠️ LA VALEUR NOMINALE NE SE DEVINE PAS. Premier essai le 08/09 : la boucle
    prenait la première nominale qui divisait juste, et 10 divise TOUT. Le
    capital d'Alliances, 2 207 858 800, donnait ainsi 220 785 880 actions au
    lieu de 22 078 588 — un facteur dix, exactement le défaut qu'on traque.

    L'arbitre est le MARCHÉ : `capitalisation ÷ cours` donne le nombre
    d'actions réellement en circulation. On retient la nominale dont le
    quotient s'en approche. C'est le recoupement arithmétique qui avait tranché
    l'ISIN de Maroc Leasing — deux sources peuvent se tromper ensemble, un
    calcul qui boucle, non.

    Sans arbitre, on ne déduit RIEN plutôt que de choisir au hasard.
    """
    if "nombre_actions" in res or "capital_social" not in res:
        return res
    cap = res["capital_social"]["valeur"]
    if not actions_marche:
        res["nombre_actions_indeterminable"] = {
            "capital_social": cap,
            "raison": "valeur nominale inconnue et pas de capitalisation pour trancher",
            "candidats": {str(vn): cap / vn for vn in NOMINALES if (cap / vn).is_integer()},
        }
        return res
    meilleurs = [(abs(cap / vn / actions_marche - 1), vn) for vn in NOMINALES
                 if (cap / vn).is_integer()]
    if not meilleurs:
        return res
    ecart, vn = min(meilleurs)
    if ecart <= 0.05:
        res["nombre_actions"] = {
            "valeur": int(cap / vn), "page": res["capital_social"]["page"],
            "deduit": f"capital ÷ nominale {vn}",
            "arbitre": f"capitalisation ÷ cours = {actions_marche:,.0f} (écart {ecart:.1%})".replace(",", " "),
        }
    else:
        res["nombre_actions_indeterminable"] = {
            "capital_social": cap, "actions_selon_marche": round(actions_marche),
            "raison": f"aucune nominale ne colle au marché (meilleur écart {ecart:.0%})",
        }
    return res


def _pages(chemin: Path) -> dict:
    """Lit le PDF page par page et LIBÈRE chaque page après extraction.

    ⚠️ `pdfplumber` met en cache les objets de chaque page traitée. Sur un
    rapport de 25 Mo comme celui de BMCI, garder les 200 pages en mémoire
    pendant tout le balayage finit par coûter cher — et surtout inutilement,
    puisqu'on ne cherche que deux faits. `page.flush_cache()` rend la mémoire
    dès que le texte est extrait.
    """
    import pdfplumber
    pages = {}
    with pdfplumber.open(chemin) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            pages[str(i)] = page.extract_text() or ""
            page.flush_cache()
    return pages


def _ecrire(resultats: dict, echecs: list) -> None:
    SORTIE.write_text(json.dumps({
        "_quoi": "Relevé automatique sur les rapports annuels AMMC — nombre "
                 "d'actions et résultat net part du groupe.",
        "_avertissement": "⚠️ Signale les titres à OUVRIR. Aucun de ces chiffres "
                          "n'entre dans faits_financiers.json sans une lecture "
                          "à la main et sa page. Les mises en page varient : ce "
                          "qui n'a pas pu être lu est DIT, pas comblé.",
        "_releve_le": time.strftime("%Y-%m-%d"),
        "_echecs": [{"ticker": t, "cause": c} for t, c in echecs],
        "emetteurs": resultats,
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    cat = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    bpa = json.loads((RACINE / "bpa.json").read_text(encoding="utf-8"))
    data = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    prix = {x["symbol"]: x for x in data["tickers"]}
    CACHE.mkdir(exist_ok=True)

    cibles = {t: v for t, v in cat["emetteurs"].items() if v["rapports_annuels"]}

    # ⚠️ REPRISE. Le premier lancement du 08/09 est mort au 10e rapport sur 36
    # et n'avait RIEN écrit : trois quarts d'heure de téléchargement perdus.
    # Un balayage long qui ne sauvegarde qu'à la fin est mal conçu — c'est le
    # même défaut que je relèverais dans le pipeline. La sortie est désormais
    # écrite après CHAQUE émetteur, et une relance reprend où elle s'est
    # arrêtée au lieu de tout refaire.
    resultats, echecs = {}, []
    if SORTIE.exists():
        try:
            deja = json.loads(SORTIE.read_text(encoding="utf-8"))
            resultats = deja.get("emetteurs", {})
            echecs = [(e["ticker"], e["cause"]) for e in deja.get("_echecs", [])]
            print(f"  reprise : {len(resultats)} émetteurs déjà traités")
        except Exception:
            pass
    print(f"  {len(cibles)} émetteurs avec un rapport annuel\n")
    for n, (tic, v) in enumerate(sorted(cibles.items()), 1):
        if tic in resultats:
            continue
        rfa = v["rapports_annuels"][0]
        dest = CACHE / rfa["fichier"]
        if not _telecharger(rfa["url"], dest):
            echecs.append((tic, "téléchargement"))
            print(f"  ✗ {n:>3}/{len(cibles)} {tic:6} téléchargement impossible")
            continue
        try:
            faits = extraire(_pages(dest))
            x = prix.get(tic) or {}
            am = (x.get("cap") * 1e6 / x["price"]
                  if x.get("cap") and x.get("price") else None)
            faits = deduire_actions(faits, am)
        except Exception as e:
            echecs.append((tic, f"lecture : {e}"))
            print(f"  ✗ {n:>3}/{len(cibles)} {tic:6} lecture impossible")
            continue

        ligne = {"exercice": rfa["exercice"], "url": rfa["url"],
                 "fichier": rfa["fichier"], "faits": faits}

        # ⚠️ LE DÉTECTEUR D'OPÉRATION SUR TITRES NON RÉPERCUTÉE.
        # Le rapport dit combien d'actions existaient à sa date ; le marché dit
        # combien il en existe aujourd'hui. Un rapport proche de 10 ou de 0,1
        # signe un split entre les deux — c'est ainsi que Managem se dénonce :
        # 11 864 676 au rapport 2025, 117 231 250 selon la capitalisation.
        na_r = (faits.get("nombre_actions") or {}).get("valeur")
        if na_r and am:
            r = na_r / am
            ligne["actions_rapport_sur_marche"] = round(r, 3)
            if r < 0.5 or r > 2:
                ligne["alerte"] = (
                    f"nombre d'actions du rapport ({na_r:,.0f}) contre le marché "
                    f"({am:,.0f}) — rapport {r:.2f}. Opération sur titres entre "
                    f"la date du rapport et aujourd'hui ?".replace(",", " "))

        # ── le contrôle qui compte ────────────────────────────────────────
        b = (bpa.get(tic) or {}).get("bpa")
        na = (faits.get("nombre_actions") or {}).get("valeur")
        rn = (faits.get("rnpg") or {}).get("valeur")
        if b and na and rn:
            # Le rapport exprime souvent en KMAD ou MMAD : on compare des
            # ORDRES DE GRANDEUR, pas des montants.
            implique = b * na
            ecarts = [abs(implique / (rn * f) - 1) for f in (1, 1e3, 1e6) if rn]
            ligne["coherence"] = {
                "bpa_publie": b, "actions": na, "rnpg_rapport": rn,
                "ecart_min_relatif": round(min(ecarts), 3),
                "facteur_bpa_actions_sur_rnpg": round(implique / rn, 2) if rn else None,
            }
        resultats[tic] = ligne
        _ecrire(resultats, echecs)          # au fil de l'eau, jamais à la fin
        marque = "✓" if faits.get("nombre_actions") else "·"
        print(f"  {marque} {n:>3}/{len(cibles)} {tic:6} "
              f"actions={na or '—'}  rnpg={rn or '—'}")
        time.sleep(0.2)

    _ecrire(resultats, echecs)

    avec = sum(1 for v in resultats.values() if v["faits"].get("nombre_actions"))
    print(f"\n  {avec}/{len(cibles)} avec un nombre d'actions lisible")
    print(f"  {len(echecs)} échecs")
    print(f"  → {SORTIE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

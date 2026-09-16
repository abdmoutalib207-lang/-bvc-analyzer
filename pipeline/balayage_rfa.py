"""Balayage des rapports annuels — actions, résultat net, capitaux propres.

POURQUOI CES FAITS-LÀ, ET PAS D'AUTRES
──────────────────────────────────────
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

LE TROISIÈME FAIT, AJOUTÉ LE 16/09/2026 : LES CAPITAUX PROPRES
──────────────────────────────────────────────────────────────
Noure : « il y'a plein de P/BOOK qui manque ». Mesuré le 16/09 : le moteur en
affiche **4 sur 80**. Ce n'est pas un défaut de calcul. `_pb_sourcé()` demande
`capitaux_propres_part_groupe`, et sur les onze émetteurs archivés dans
`faits_financiers.json` quatre seulement le portent — ADI, CMT, MNG, MSA,
c'est-à-dire exactement les quatre qui affichent un P/BOOK. Les sept autres
avaient été relevés pour le BPA : résultat net et nombre d'actions. La ligne
des fonds propres n'avait jamais été lue.

Le balayage cherche donc aussi cette ligne. Il ne la publie pas : il dit sur
quelle PAGE elle se trouve et ce qu'elle porte, mot pour mot.

⚠️ L'UNITÉ N'EST PAS TRANCHÉE ICI. Les rapports publient en dirhams, en
milliers ou en millions, et rien dans la ligne elle-même ne le dit. Deviner
mettrait un facteur 1 000 dans le P/BOOK sans le moindre bruit. Le balayage
relève les unités MENTIONNÉES sur la page ; c'est la lecture qui tranche.

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

# Ce que le passage cherchait. Incrémenté dès qu'un fait s'ajoute : la
# reprise refait alors les émetteurs relevés par un passage plus ancien.
VERSION_BALAYAGE = 3


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


def _degrouper(jeton: str, maxi: float) -> list[str]:
    """Défait un recollage de colonnes : « 901 142 608 722 030 805 » → deux.

    ⚠️ LE PIÈGE EST INHÉRENT AU TEXTE, pas au motif. Dans un tableau, deux
    montants voisins ne sont séparés que par une espace — la même que celle qui
    sépare les milliers à l'intérieur d'un montant. « 901 142 608 722 030 805 »
    peut donc se lire comme un nombre ou comme deux, et aucune expression
    régulière ne tranchera, parce qu'il n'y a rien à lire pour trancher.

    Mesuré le 16/09 sur le rapport de Minière Touissit : la ligne « Capitaux
    propres (Part du groupe) 901 142 608 722 030 805 » rendait 9×10¹⁷. La borne
    de vraisemblance l'écartait ensuite — le fait était donc déclaré introuvable
    sur un rapport qui le publie noir sur blanc, page 57.

    Ce qui tranche est PHYSIQUE : aucune société de la cote n'a 9×10¹⁷ dirhams
    de fonds propres. On retient donc le plus long préfixe de groupes qui reste
    sous la borne, et l'on relit le reste comme le montant suivant. Chez CMT :
    901 142 608 722 → 9×10¹¹, trop ; 901 142 608 → 9×10⁸, plausible. Reste
    722 030 805, qui est bien la colonne 2024.

    ⚠️ Ce découpage RESTE UNE HYPOTHÈSE DE LECTURE. C'est pourquoi la ligne
    brute est conservée telle quelle dans la sortie : la valeur retenue se
    vérifie sur la page, elle ne se croit pas sur parole.
    """
    v = _nombre(jeton)
    if v is None or v <= maxi:
        return [jeton]
    groupes = re.split(r"[  .]", jeton)
    if len(groupes) < 2:
        return [jeton]
    for k in range(len(groupes) - 1, 0, -1):
        tete = " ".join(groupes[:k])
        vt = _nombre(tete)
        if vt is not None and vt <= maxi:
            return [tete] + _degrouper(" ".join(groupes[k:]), maxi)
    return [jeton]


def _nombres_de_la_ligne(ligne: str, maxi: float) -> list[float]:
    """Tous les montants de la ligne, recollages défaits, bornés par `maxi`."""
    out = []
    for m in re.finditer(NB, ligne):
        for jeton in _degrouper(m.group(1), maxi):
            v = _nombre(jeton)
            if v is not None:
                out.append(v)
    return out


# ⚠️ L'ÉTIQUETTE DES CAPITAUX PROPRES N'EST PAS STANDARDISÉE, et un motif
# rigide en rate la moitié. Relevé le 16/09 sur sept rapports de la cote :
#
#   Addoha    CAPITAUX PROPRES PART DU GROUPE 9.481.694.524 …
#   Akdital   Dont : Capitaux propres part du groupe 2 853 529 135 …
#   Aradei    Capitaux propres part du groupe 5 444 531 …
#   Atlanta   Dont : Capitaux propres part du groupe 2 481 937 …
#   CMGP      TOTAL CAPITAUX PROPRES PART GROUPE 2 788 340 389 …   (pas de « du »)
#   CMT       Capitaux propres (Part du groupe) 901 142 608 …      (parenthèses)
#   Managem   Capitaux propres consolidés Part du Groupe 11 478,0  (mot intercalé)
#
# Un premier motif exigeant « capitaux propres » puis immédiatement « part du
# groupe » en manquait DEUX sur sept — CMGP et Managem — et l'on aurait conclu
# que leur rapport ne publie pas ses fonds propres alors qu'il les publie.
#
# D'où la forme retenue : « capitaux propres », puis n'importe quel qualificatif
# court, puis « groupe ». Ce qui sépare compte plus que ce qui relie, et est
# donc traité à part, par EXCLUSION.
CP_ETIQUETTE = re.compile(
    r"capitaux\s+propres\b(?P<qual>[^\d]{0,32}?)\bgroupe\b"
    r"|capitaux\s+propres\b(?P<qual2>[^\d]{0,40}?)"
    r"attribuables?\s+aux\s+(?:actionnaires|propriétaires)",
    re.IGNORECASE)

# ⚠️ CE QUI DOIT ÊTRE ÉCARTÉ, et pourquoi c'est le point sensible.
# « Capitaux propres D'ENSEMBLE », « ... part des MINORITAIRES », « TOTAL
# capitaux propres » désignent d'autres lignes du même bilan, minoritaires
# inclus ou exclusivement. Les prendre pour la part du groupe SURESTIMERAIT les
# fonds propres et donc SOUS-ESTIMERAIT le P/BOOK : le titre paraîtrait moins
# cher qu'il n'est. C'est le sens d'erreur qu'on a corrigé sur le BPA d'Addoha,
# et celui qui trompe un lecteur dans la direction la plus coûteuse.
#
# Chez Addoha les trois lignes se suivent : 9,48 / 0,93 / 10,41 milliards. Rien
# dans leur forme ne les distingue — seul le qualificatif le fait.
QUALIFICATIFS_EXCLUS = re.compile(
    r"minorit|ensemble|hors\s+groupe|non\s+contrôl|ne\s+donnant\s+pas", re.IGNORECASE)

# Mentions d'unité qu'un rapport porte en tête de tableau ou de colonne. Le
# balayage les RELÈVE, il ne tranche pas : c'est la lecture de la page qui
# tranche. Sans cela un facteur 1 000 entrerait dans le P/BOOK sans bruit.
INDICES_UNITE = (
    (r"\ben\s+milliers\s+de\s+dirhams\b|\bKMAD\b|\bKDH\b|\bK\s?MAD\b", "KMAD"),
    (r"\ben\s+millions\s+de\s+dirhams\b|\bMMAD\b|\bMDH\b|\bM\s?MAD\b", "MMAD"),
    (r"\ben\s+dirhams\b|\bMAD\b(?!\s*000)|\bDH\b", "MAD"),
)


def _unites_de_la_page(texte: str) -> list[str]:
    """Les unités mentionnées sur la page, dans l'ordre où on les rencontre."""
    vus = []
    for motif, nom in INDICES_UNITE:
        if re.search(motif, texte) and nom not in vus:
            vus.append(nom)
    return vus


def extraire(pages: dict) -> dict:
    """Relève ce qui est trouvable, avec la page. Silence si rien de sûr."""
    res: dict = {}

    for i, t in pages.items():
        for l in t.split("\n"):
            # ── capitaux propres part du groupe ───────────────────────────
            # Le fait qui manquait pour calculer le P/BOOK : `_pb_sourcé()`
            # exige `capitaux_propres_part_groupe`, et au 16/09 quatre
            # émetteurs seulement le portaient sur les onze archivés — d'où
            # un P/BOOK affiché sur 4 titres sur 80. Ce balayage n'y remédie
            # pas tout seul : il dit OÙ lire, ligne et page.
            #
            # ⚠️ Deux nombres au moins sur la ligne : un bilan publie
            # l'exercice ET le précédent. Une phrase de prose n'en porte
            # qu'un — c'est ce qui sépare le tableau du commentaire, et c'est
            # le même garde-fou que pour le résultat net.
            if "capitaux propres" in l.lower() and "capitaux_propres_part_groupe" not in res:
                # ⚠️ IGNORECASE n'est pas une commodité. Addoha écrit la ligne
                # en capitales — « CAPITAUX PROPRES PART DU GROUPE
                # 9.481.694.524 9.319.494.058 » — et un motif sensible à la
                # casse l'aurait déclarée introuvable sur un rapport qui la
                # publie noir sur blanc.
                m = CP_ETIQUETTE.search(l)
                # ⚠️ L'exclusion regarde des DEUX CÔTÉS de « groupe ». Minière
                # Touissit écrit, page 59, « Capitaux propres groupe après ret.
                # des minoritaires » : le mot qui disqualifie une ligne peut
                # suivre l'étiquette au lieu de la précéder. On balaie donc
                # jusqu'au premier chiffre — c'est-à-dire tout le libellé, et
                # rien du tableau. Un libellé ambigu est écarté plutôt que
                # deviné : une absence se dit, elle ne se comble pas.
                qual = ""
                if m:
                    qual = (m.group("qual") or m.group("qual2") or "")
                    qual += l[m.start():m.end()]
                    qual += re.split(r"\d", l[m.end():], 1)[0]
                # Borne haute à 2×10¹¹ : les fonds propres d'Attijariwafa, la
                # plus grosse de la cote, avoisinent 60 milliards de dirhams.
                # Au-delà, ce n'est pas un montant, c'est un recollage de
                # colonnes. Les unités varient (MAD, KMAD, MMAD), d'où une
                # fourchette large : elle écarte les artefacts, elle ne tranche
                # pas l'unité.
                nombres = _nombres_de_la_ligne(l, 2e11) if m else []
                if m and not QUALIFICATIFS_EXCLUS.search(qual) and len(nombres) >= 2:
                    # Le premier montant qui SUIT l'étiquette, jamais le premier
                    # de la ligne : « Dont : … » et les appels de note se
                    # placent avant.
                    apres = _nombres_de_la_ligne(l[m.end():], 2e11)
                    v = apres[0] if apres else None
                    # Borne basse à 100 : sous ce seuil on lit un numéro de note
                    # ou un pourcentage, pas des fonds propres.
                    if v and abs(v) >= 100 and not (1990 <= v <= 2100):
                        res["capitaux_propres_part_groupe"] = {
                            "valeur_lue": v,
                            "page": int(i),
                            "brut": l.strip()[:140],
                            "etiquette": l[m.start():m.end()].strip()[:80],
                            # ⚠️ L'ORDRE DES COLONNES N'EST PAS CONSTANT, y
                            # compris À L'INTÉRIEUR D'UN MÊME RAPPORT. Dans
                            # celui d'Addoha, la page 9 porte « Capitaux
                            # propres 10655 10364 » — 2025 puis 2024 — et la
                            # page 26 « 10.363.635.188 10.654.958.878 »,
                            # l'inverse. Retenir « le premier nombre » revient
                            # donc à tirer l'exercice au sort. Tous les nombres
                            # de la ligne sont conservés ; c'est la lecture de
                            # l'en-tête qui dira lequel est l'exercice clos.
                            "nombres_de_la_ligne": nombres[:6],
                            "unites_sur_la_page": _unites_de_la_page(t),
                            "⚠️": "valeur LUE. Ni l'unité ni l'exercice ne sont "
                                  "tranchés ici — à confirmer sur la page avant "
                                  "tout usage.",
                        }

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
                 "d'actions, résultat net part du groupe et capitaux "
                 "propres part du groupe.",
        "_avertissement": "⚠️ Signale les titres à OUVRIR. Aucun de ces chiffres "
                          "n'entre dans faits_financiers.json sans une lecture "
                          "à la main et sa page. Les mises en page varient : ce "
                          "qui n'a pas pu être lu est DIT, pas comblé.",
        "_unite_non_tranchee": "⚠️ `capitaux_propres_part_groupe.valeur_lue` "
                               "est le nombre tel qu'il figure sur la ligne. "
                               "Son UNITÉ (MAD, KMAD, MMAD) n'est PAS tranchée "
                               "ici : `unites_sur_la_page` ne fait que citer ce "
                               "que la page mentionne. Trancher au jugé mettrait "
                               "un facteur 1 000 dans le P/BOOK sans bruit.",
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
        # ⚠️ LA REPRISE DOIT SAVOIR CE QU'ELLE A DÉJÀ CHERCHÉ, pas seulement
        # qui elle a déjà vu. En ajoutant les capitaux propres le 16/09, la
        # reprise « ce ticker est déjà là » aurait sauté les 36 émetteurs et
        # rendu un balayage inchangé — un relevé vide qu'on aurait pris pour
        # « aucun rapport ne publie ses fonds propres ». La version marque ce
        # que le passage cherchait ; un passage plus ancien est refait.
        if resultats.get(tic, {}).get("_version_balayage") == VERSION_BALAYAGE:
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

        ligne = {"_version_balayage": VERSION_BALAYAGE,
                 "exercice": rfa["exercice"], "url": rfa["url"],
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
        cp = (faits.get("capitaux_propres_part_groupe") or {}).get("valeur_lue")
        print(f"  {marque} {n:>3}/{len(cibles)} {tic:6} "
              f"actions={na or '—'}  rnpg={rn or '—'}  cp={cp or '—'}")
        time.sleep(0.2)

    _ecrire(resultats, echecs)

    avec = sum(1 for v in resultats.values() if v["faits"].get("nombre_actions"))
    cp = sum(1 for v in resultats.values()
             if v["faits"].get("capitaux_propres_part_groupe"))
    print(f"\n  {avec}/{len(cibles)} avec un nombre d'actions lisible")
    print(f"  {cp}/{len(cibles)} avec une ligne de capitaux propres part du "
          f"groupe À LIRE (unité non tranchée)")
    print(f"  {len(echecs)} échecs")
    print(f"  → {SORTIE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

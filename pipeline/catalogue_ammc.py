"""Catalogue des publications AMMC — quel émetteur, quel document, quelle URL.

POURQUOI
────────
`fondamentaux.json` porte 77 sociétés saisies à la main depuis une quarantaine
de sources secondaires, toutes datées de juin 2026. Trois vérifications au
document primaire (ADI, MNG, MSA) ont montré des écarts allant du facteur 3 au
facteur 10, et deux identités croisées. Passer l'ensemble de la cote au crible
demande d'abord de savoir OÙ se trouve le rapport de chaque société.

L'AMMC — le régulateur — tient cet index. C'est la source la plus autoritaire
disponible, et la seule qui couvre tous les émetteurs au même endroit.

CE QUE CE MODULE FAIT
─────────────────────
1. Parcourt la liste des émetteurs de l'AMMC (paginée).
2. Apparie chaque émetteur à NOTRE ticker, par le nom.
3. Ouvre la fiche de l'émetteur et relève ses documents PDF.
4. Écrit `pipeline/catalogue_ammc.json`.

⚠️ CE QU'IL NE FAIT PAS : il ne lit aucun chiffre. Il ne fait que localiser
les documents. L'extraction des faits reste une opération séparée, avec sa
page, parce qu'un chiffre sans page ne vaut rien.

⚠️ L'APPARIEMENT PAR LE NOM EST LE POINT FRAGILE. C'est exactement le piège
qui a produit les collisions MSA/Mutandis et MRL/Marsa Maroc. Aucun
appariement n'est retenu sans un score suffisant, et les incertains sont
listés à part pour arbitrage humain plutôt que devinés.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from bvc_config import COMPANY_NAMES, TICKERS_ALL          # noqa: E402

BASE = "https://www.ammc.ma"
LISTE = BASE + "/fr/espace-emetteurs/liste-des-emetteurs"
SORTIE = Path(__file__).parent / "catalogue_ammc.json"

# Politesse : l'AMMC est un service public, pas une API.
PAUSE = 0.4
UA = "BVC-Analyzer/1.0 (recherche quantitative; contact via le dépôt GitHub)"

# En deçà, l'appariement n'est pas assez sûr pour être retenu sans relecture.
SEUIL_APPARIEMENT = 0.62

_VIDE = {"sa", "s.a", "sarl", "group", "groupe", "maroc", "morocco", "du", "de",
         "des", "la", "le", "les", "et", "d", "l", "ex", "compagnie", "societe"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", " ", s.lower())


def _mots(s: str) -> set:
    return {m for m in _norm(s).split() if len(m) > 1 and m not in _VIDE}


def _similarite(a: str, b: str) -> float:
    """Jaccard sur les mots significatifs, bonifié si l'un contient l'autre.

    Volontairement simple et lisible : un appariement qu'on ne sait pas
    expliquer est un appariement qu'on ne peut pas contester.

    ⚠️ LE CONTAINMENT SE MESURE SUR LES MOTS, JAMAIS SUR LES CARACTÈRES.
    Corrigé le 08/09/2026 : la version précédente testait `nb in na` sur les
    chaînes brutes, et « ONE » — l'Office National de l'Électricité — décrochait
    0,80 face à « S.M M-ONE-tique » parce que ses trois lettres se trouvent au
    milieu de « monétique ». S2M s'est ainsi retrouvé apparié à l'ONE, avec
    zéro document. C'est le même défaut que les collisions d'identité du NLP :
    comparer des chaînes sans respecter les frontières de mots.
    """
    ma, mb = _mots(a), _mots(b)
    if not ma or not mb:
        return 0.0
    j = len(ma & mb) / len(ma | mb)
    # Sous-ensemble strict de mots : « MARSA MAROC » ⊂ « SODEP MARSA MAROC ».
    if ma <= mb or mb <= ma:
        j = max(j, 0.80)
    return j


def _get(url: str, essais: int = 3) -> str:
    for i in range(essais):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception:
            if i == essais - 1:
                return ""
            time.sleep(1.5 * (i + 1))
    return ""


def lister_emetteurs(pages_max: int = 20) -> dict:
    """{identifiant AMMC: nom}. S'arrête dès qu'une page n'apporte rien."""
    trouves: dict = {}
    for p in range(pages_max):
        url = LISTE if p == 0 else f"{LISTE}?page={p}"
        s = _get(url)
        if not s:
            break
        avant = len(trouves)
        for ident, nom in re.findall(
                r'href="/fr/espace-emetteurs/liste-des-emetteurs/(\d+)"[^>]*>([^<]{2,90})', s):
            nom = html.unescape(nom).strip()
            if nom:
                trouves.setdefault(ident, nom)
        if len(trouves) == avant:
            break
        time.sleep(PAUSE)
    return trouves


def apparier(emetteurs: dict) -> tuple[dict, list]:
    """Associe nos tickers aux identifiants AMMC. Renvoie (sûrs, incertains).

    ⚠️ Un appariement douteux est PIRE qu'une absence : c'est ainsi que le
    sentiment de Ciments du Maroc s'est retrouvé sur Minière Touissit. Les cas
    limites sortent dans la seconde liste, pour arbitrage humain.
    """
    surs, incertains = {}, []
    for tic in TICKERS_ALL:
        notre = COMPANY_NAMES.get(tic, tic)
        classe = sorted(((_similarite(notre, nom), ident, nom)
                         for ident, nom in emetteurs.items()), reverse=True)
        if not classe:
            continue
        score, ident, nom = classe[0]
        second = classe[1][0] if len(classe) > 1 else 0.0
        if score >= SEUIL_APPARIEMENT and score - second >= 0.08:
            surs[tic] = {"id": ident, "nom_ammc": nom, "nom_projet": notre,
                         "score": round(score, 3)}
        elif score > 0.35:
            incertains.append({"ticker": tic, "nom_projet": notre,
                               "candidats": [{"id": i, "nom": n, "score": round(sc, 3)}
                                             for sc, i, n in classe[:3]]})
    return surs, incertains


def documents(ident: str) -> list:
    """Les PDF publiés par un émetteur, avec leur intitulé et leur date."""
    s = _get(f"{LISTE}/{ident}")
    if not s:
        return []
    vus, docs = set(), []
    for m in re.finditer(r'href="(/sites/default/files/[^"]+\.pdf)"', s, re.I):
        url = m.group(1)
        if url in vus:
            continue
        vus.add(url)
        contexte = s[max(0, m.start() - 700):m.start() + 300]
        titre = ""
        for t in re.findall(r">([^<>]{12,140})<", contexte):
            t = html.unescape(t).strip()
            if t and not t.startswith("http") and "{" not in t:
                titre = t
        date = ""
        d = re.search(r"(\d{2}/\d{2}/\d{4})", contexte)
        if d:
            date = d.group(1)
        docs.append({"url": BASE + url, "titre": titre, "date": date,
                     "fichier": url.rsplit("/", 1)[-1]})
    return docs


# Un rapport annuel pèse au moins ceci. Mesuré le 16/09 sur les 66 rapports
# téléchargés : le plus léger, celui de Rebab Company, fait 1,09 Mo, et la
# médiane dépasse 8 Mo.
#
# ⚠️ CE SEUIL EXISTE À CAUSE D'UN FAUX POSITIF RÉEL. `Auto_Hall_RFA_2025.pdf`
# est bien servi par l'AMMC, en PDF, sous exactement le nom attendu — mais il
# fait 244 ko et UNE page, et c'est le COMMUNIQUÉ qui annonce le rapport :
# « La Société Auto Hall met à la disposition du public son Rapport Financier
# Annuel […] disponible sur le site internet de la société ». Le rapport
# lui-même n'est pas déposé à l'AMMC.
#
# « Servi en PDF » ne veut donc pas dire « c'est le rapport ». Le seuil est
# placé à 600 ko : 2,4 fois le communiqué d'Auto Hall, 1,8 fois moins que le
# plus léger vrai rapport. Aucun des deux côtés n'est serré.
TAILLE_MINIMALE_RAPPORT = 600_000


def _existe(url: str, taille_min: int = 0) -> bool:
    """Le fichier est-il réellement servi ? ⚠️ L'AMMC renvoie une page HTML
    d'erreur en 404 avec un corps de ~105 ko : se fier au seul code HTTP ne
    suffit pas, il faut vérifier le type de contenu — et, pour un rapport
    annuel, la taille."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA}, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status != 200 or "pdf" not in r.headers.get("Content-Type", "").lower():
                return False
            if taille_min:
                taille = int(r.headers.get("Content-Length") or 0)
                return taille >= taille_min
            return True
    except Exception:
        return False


# Les segments qui marquent la FIN du nom de la société dans un nom de fichier :
# période, nature de l'acte, ou millésime. Tout ce qui suit décrit le document,
# pas l'émetteur. Relevé sur les 74 fiches, pas supposé.
_FIN_DU_NOM = re.compile(
    r"^(T[1-4]|S[12]|20\d\d|\d{1,2}|post|avis|ago|age|agm|agoe|rfa|erratum"
    r"|r%C3%A9sultats|resultats|communique|communiqu%C3%A9|cp|pr|fr|maj|cd"
    r"|emission|augmentation|visa|fusion|signature|realisation|revision"
    r"|cloture|convocation|eo|ipo|s%C3%A9ance)$", re.I)


def _bases_possibles(docs: list) -> list:
    """Les noms de société que ces fichiers peuvent porter, du plus long au
    plus court.

    On retire les préfixes `CP_` et `Avis_`, on coupe au premier segment qui
    décrit le document plutôt que l'émetteur, puis on propose aussi les
    troncatures — « CFG_Bank » donne « CFG_Bank » et « CFG », parce que le
    rapport de CFG Bank s'appelle `CFG_RFA_2025.pdf`.

    Les bases les plus fréquentes viennent en premier : c'est presque toujours
    la bonne, et l'ordre limite le nombre d'appels au dépôt.
    """
    from collections import Counter
    compte: Counter = Counter()
    for d in docs:
        f = re.sub(r"\.pdf$", "", d["fichier"], flags=re.I)
        f = re.sub(r"^(CP|Avis)[_ ]", "", f, flags=re.I)
        f = re.sub(r"_\d$", "", f)                    # suffixe _0 / _1 du dépôt
        segments = [s for s in f.split("_") if s]
        garde = []
        for s in segments:
            if _FIN_DU_NOM.match(s):
                break
            garde.append(s)
        while garde:
            compte["_".join(garde)] += 1
            garde = garde[:-1]
    # Un nom d'un seul caractère ou purement numérique ne désigne personne.
    return [b for b, _ in compte.most_common(12)
            if len(b) >= 2 and not b.isdigit()]


def rapports_annuels(docs: list) -> list:
    """Retrouve le RAPPORT ANNUEL, qui n'est PAS listé sur la fiche émetteur.

    ⚠️ Découvert le 08/09/2026 en vérifiant le résultat plutôt que le message
    du script : celui-ci annonçait « 0 RFA » pour Managem, dont je venais de
    télécharger le rapport de 121 pages. La fiche émetteur de l'AMMC ne liste
    que les communiqués et les avis. Le rapport annuel existe bien, sous un
    nom voisin :

        fiche émetteur   Managem_2025.pdf      (communiqué de résultats)
        rapport annuel   Managem_RFA_2025.pdf  (le document de 121 pages)

    On dérive donc le second du premier, et on VÉRIFIE qu'il est servi avant
    de l'inscrire — deviner une URL sans la tester reproduirait exactement le
    travers qu'on cherche à corriger.

    ⚠️ LA PREMIÈRE VERSION NE DÉRIVAIT QUE D'UN SEUL MOTIF, et déclarait donc
    « pas de rapport annuel » pour 38 émetteurs sur 74. Constaté le 16/09 en
    cherchant pourquoi le P/BOOK manquait sur les titres que Noure venait de
    faire passer : huit rapports ont été retrouvés en une passe, dont six de
    ces titres-là.

        Vicenne          Vicenne_RFA_2025.pdf        ← CP_Vicenne_2025.pdf
        Auto Hall        Auto_Hall_RFA_2025.pdf      ← CP_Auto_Hall_RFA_2025.pdf
        Ciments du Maroc Cimar_RFA_2025.pdf          ← CP_Cimar_2025.pdf
        Dari Couspate    Dari_Couspate_RFA_2025.pdf  ← Dari_Couspate_2025_1.pdf
        Stokvis          Stokvis_RFA_2025.pdf        ← CP_Stokvis_post_AGO_…
        CFG Bank         CFG_RFA_2025.pdf            ← CP_CFG_Bank_T2_26.pdf
        Auto Nejma       Auto_Nejma_RFA_2025.pdf     ← CP_Auto_Nejma_2025.pdf
        CIH Bank         CIH_Bank_RFA_2025.pdf       ← CP_CIH_Bank_T2_26.pdf

    Ce que la première version ratait, et qui n'était pas devinable a priori :
    le préfixe `CP_` qu'elle EXCLUAIT alors qu'il suffit de le retirer ; un
    suffixe `_0`/`_1` ajouté par le dépôt ; et le fait que le nom du rapport se
    déduit parfois d'un communiqué trimestriel, pas d'un communiqué annuel.

    CFG Bank montre pourquoi il faut aussi RACCOURCIR la base : ses documents
    disent « CFG_Bank », son rapport s'appelle `CFG_RFA_2025.pdf`.

    ⚠️ La règle n'a pas changé d'un iota : on ESSAIE, et l'on n'inscrit que ce
    qui répond en PDF. Élargir la recherche n'est pas deviner davantage — c'est
    frapper à plus de portes, et n'entrer que par celles qui s'ouvrent.
    """
    # ⚠️ NE PAS SE LIMITER AUX MILLÉSIMES QUI FIGURENT DANS LES NOMS DE
    # FICHIERS. CIH Bank ne publie que des communiqués trimestriels de 2026 :
    # aucun de ses noms ne porte « 2025 », et l'exercice 2025 n'était donc
    # jamais essayé — alors que `CIH_Bank_RFA_2025.pdf` est bien servi. Un
    # rapport annuel porte l'exercice CLOS, c'est-à-dire l'année précédente.
    #
    # ⚠️ Et borner ce qu'on prend pour un millésime. `Communique%20Visa%20CIH%
    # 20AUK%20750.pdf` contient « 2075 » — dans l'échappement d'une espace, pas
    # dans une date. Cet exercice imaginaire devenait le plus récent, et
    # écrasait 2025 dans les deux essais retenus : CIH Bank était déclarée sans
    # rapport annuel alors que le sien est servi. Un exercice clos ne dépasse
    # pas l'année en cours.
    maxi = time.gmtime().tm_year + 1
    vus_annees = {m.group(1) for d in docs
                  for m in [re.search(r"(20\d\d)", d["fichier"])] if m
                  and 2010 <= int(m.group(1)) <= maxi}
    if vus_annees:
        vus_annees.add(str(max(int(a) for a in vus_annees) - 1))
    annees = sorted(vus_annees, reverse=True)[:2] or ["2025"]
    trouves, vus, essais = [], set(), 0
    for base in _bases_possibles(docs):
        for annee in annees:
            for motif in (f"{base}_RFA_{annee}.pdf",
                          f"{base}_RFA_{annee[2:]}.pdf",
                          f"{base}_{annee}_RFA.pdf"):
                url = f"{BASE}/sites/default/files/{motif}"
                if url in vus or essais >= 90:
                    continue
                vus.add(url)
                essais += 1
                time.sleep(PAUSE / 4)
                if _existe(url, TAILLE_MINIMALE_RAPPORT):
                    trouves.append({"url": url, "fichier": motif,
                                    "exercice": int(annee), "derive_de": base,
                                    "verifie": True})
                    break
            if any(t["exercice"] == int(annee) for t in trouves):
                break
    # Un seul rapport par exercice : le premier trouvé fait foi.
    par_exercice = {}
    for t in trouves:
        par_exercice.setdefault(t["exercice"], t)
    return sorted(par_exercice.values(), key=lambda x: -x["exercice"])


def main() -> int:
    print("  Lecture de la liste des émetteurs AMMC…")
    emetteurs = lister_emetteurs()
    print(f"  {len(emetteurs)} émetteurs référencés")

    surs, incertains = apparier(emetteurs)
    print(f"  {len(surs)}/{len(TICKERS_ALL)} de nos tickers appariés avec certitude")
    print(f"  {len(incertains)} incertains, laissés à l'arbitrage\n")

    catalogue = {
        "_source": "AMMC — Autorité Marocaine du Marché des Capitaux",
        "_url": LISTE,
        "_releve_le": time.strftime("%Y-%m-%d"),
        "_avertissement": ("L'appariement se fait par le NOM de la société. "
                           "C'est le point fragile — c'est ainsi que le sentiment "
                           "de Ciments du Maroc s'est retrouvé sur Minière "
                           "Touissit. Les cas douteux sont dans `_incertains`, "
                           "non résolus, plutôt que devinés."),
        "_incertains": incertains,
        "emetteurs": {},
    }

    for n, (tic, info) in enumerate(sorted(surs.items()), 1):
        docs = documents(info["id"])
        annuels = rapports_annuels(docs)
        catalogue["emetteurs"][tic] = {**info, "n_documents": len(docs),
                                       "rapports_annuels": annuels[:5],
                                       "documents": docs[:25]}
        marque = "✓" if annuels else "·"
        print(f"  {marque} {n:>3}/{len(surs)} {tic:6} {info['nom_ammc'][:38]:38} "
              f"{len(docs):>3} doc · {len(annuels)} RFA")
        time.sleep(PAUSE)

    SORTIE.write_text(json.dumps(catalogue, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    avec = sum(1 for v in catalogue["emetteurs"].values() if v["rapports_annuels"])
    print(f"\n  {avec}/{len(surs)} émetteurs avec au moins un rapport annuel")
    print(f"  → {SORTIE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

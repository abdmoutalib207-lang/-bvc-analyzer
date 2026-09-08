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


def _existe(url: str) -> bool:
    """Le fichier est-il réellement servi ? ⚠️ L'AMMC renvoie une page HTML
    d'erreur en 404 avec un corps de ~105 ko : se fier au seul code HTTP ne
    suffit pas, il faut vérifier le type de contenu."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA}, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200 and "pdf" in r.headers.get("Content-Type", "").lower()
    except Exception:
        return False


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
    """
    trouves, vus = [], set()
    for d in docs:
        f = d["fichier"]
        m = re.match(r"^(?!CP_|Avis_)(.+?)_(20\d\d)\.pdf$", f, re.I)
        if not m:
            continue
        base, annee = m.group(1), m.group(2)
        for motif in (f"{base}_RFA_{annee}.pdf", f"{base}_RFA_{annee[2:]}.pdf"):
            url = f"{BASE}/sites/default/files/{motif}"
            if url in vus:
                continue
            vus.add(url)
            if _existe(url):
                trouves.append({"url": url, "fichier": motif, "exercice": int(annee),
                                "derive_de": f, "date_communique": d["date"],
                                "verifie": True})
                break
        time.sleep(PAUSE / 2)
    return sorted(trouves, key=lambda x: -x["exercice"])


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

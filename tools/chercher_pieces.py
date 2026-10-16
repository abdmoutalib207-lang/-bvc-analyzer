#!/usr/bin/env python3
"""Recherche de pièces sources pour les fondamentaux — outil du chercheur de pièces.

Quatre gestes, toujours dans cet ordre, et un contrôle :

    python3 -I tools/chercher_pieces.py telecharger ADI https://www.ammc.ma/.../ADI_RFA_2025.pdf
    python3 -I tools/chercher_pieces.py extraire   datasets/pieces/ADI/ADI_RFA_2025.pdf
    python3 -I tools/chercher_pieces.py chercher   datasets/pieces/ADI/ADI_RFA_2025.pdf [--mots "dette nette" ...]
    python3 -I tools/chercher_pieces.py rendre     datasets/pieces/ADI/ADI_RFA_2025.pdf --pages 17,21
    python3 -I tools/chercher_pieces.py verifier   datasets/releves/ADI.json

⚠️ Un fichier téléchargé est NON FIABLE. Il ne sort jamais de
`datasets/pieces/<TICKER>/`, il n'est jamais exécuté, et l'outil se lance avec
`python3 -I` (mode isolé : ni le répertoire courant ni celui du script ne sont
dans le chemin d'import, un `json.py` déposé là ne serait pas chargé). L'outil
ne lit le fichier qu'à travers pdfplumber (déclaré dans requirements.txt, R4).

L'outil ne décide rien : il télécharge, empreinte, extrait et repère. Le
chiffre retenu, sa page et sa citation sont recopiés À LA MAIN dans le relevé
`datasets/releves/<TICKER>.json`, après lecture de la page entière.

Index : `datasets/pieces/<TICKER>/index.json` garde, pour chaque pièce, l'URL,
l'empreinte sha256, la taille et la date. Les PDF eux-mêmes ne sont pas
commités (`datasets/pieces/.gitignore`) : l'URL et l'empreinte suffisent à
prouver qu'on relit le même document.

Pas d'OCR embarqué : aucun moteur n'est déclaré dans requirements. Une page
sans couche texte est SIGNALÉE par `extraire` ; `rendre` la convertit en PNG
(pdfplumber + Pillow, déclarés) pour une lecture visuelle, et le relevé doit
alors porter « [lu sur image rendue] » dans sa citation.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PIECES = RACINE / "datasets" / "pieces"
RELEVES = RACINE / "datasets" / "releves"

TAILLE_MAX_COMMIT = 5 * 1024 * 1024  # au-delà : URL + empreinte seulement
TAILLE_MAX_TELECHARGEMENT = 80 * 1024 * 1024

MOTS_COMPTABLES = (
    "endettement net", "dette nette", "trésorerie nette", "EBITDA", "EBE",
    "excédent brut d'exploitation", "capitaux propres", "IFRS 16",
    "dettes locatives", "droit d'utilisation", "droits d'usage",
    "mises en équivalence", "gearing", "crédit-bail",
)

CHAMPS_CHIFFRE = ("grandeur", "valeur", "unite", "periode", "perimetre",
                  "source", "page", "citation")
CHAMPS_ESTIMATION = CHAMPS_CHIFFRE + ("auteur", "date_estimation")
CHAMPS_PIECE = ("id", "url", "titre", "rang_methode")


def _sha256(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def _ticker_valide(t: str) -> str:
    if not re.fullmatch(r"[A-Z0-9]{2,6}", t or ""):
        raise SystemExit(f"ticker invalide : {t!r}")
    return t


def _nom_sur(url: str) -> str:
    nom = Path(urllib.parse.urlparse(url).path).name or "piece"
    nom = re.sub(r"[^A-Za-z0-9._-]", "_", urllib.parse.unquote(nom))[:120]
    return nom if "." in nom else nom + ".bin"


def _index(dossier: Path) -> dict:
    p = dossier / "index.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"pieces": []}


def telecharger(ticker: str, url: str, nom: str | None = None) -> dict:
    """Télécharge `url` dans datasets/pieces/<TICKER>/ et l'inscrit à l'index."""
    ticker = _ticker_valide(ticker)
    if urllib.parse.urlparse(url).scheme != "https":
        raise SystemExit("seules les URL https sont acceptées")
    dossier = PIECES / ticker
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / (nom and re.sub(r"[^A-Za-z0-9._-]", "_", nom) or _nom_sur(url))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (BVC Analyzer - chercheur-pieces)"})
    with urllib.request.urlopen(req, timeout=60) as r:  # TLS vérifié : jamais désactivé
        statut = r.status
        type_ = r.headers.get("Content-Type", "")
        donnees = r.read(TAILLE_MAX_TELECHARGEMENT + 1)
    if len(donnees) > TAILLE_MAX_TELECHARGEMENT:
        raise SystemExit("fichier trop gros, abandonné")
    cible.write_bytes(donnees)
    entree = {
        "fichier": cible.name, "url": url, "sha256": _sha256(cible),
        "octets": len(donnees), "http": statut, "content_type": type_,
        "est_pdf": donnees[:5] == b"%PDF-",
        "commitable": len(donnees) <= TAILLE_MAX_COMMIT,
        "telecharge_le": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }
    idx = _index(dossier)
    idx["pieces"] = [p for p in idx["pieces"] if p.get("fichier") != cible.name] + [entree]
    (dossier / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    return entree


def extraire(chemin: Path) -> list[dict]:
    """Texte page par page → <fichier>.pages.json. Signale les pages sans texte."""
    import pdfplumber  # requirements.txt

    pages = []
    with pdfplumber.open(chemin) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            t = page.extract_text() or ""
            pages.append({"page": i, "caracteres": len(t.strip()), "texte": t})
    sortie = chemin.with_suffix(chemin.suffix + ".pages.json")
    sortie.write_text(json.dumps({"fichier": chemin.name, "sha256": _sha256(chemin),
                                  "pages": pages}, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    return pages


def _plat(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.replace("’", "'"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def chercher(chemin: Path, mots=MOTS_COMPTABLES, contexte: int = 90) -> dict:
    """{mot: [{page, extrait}]} — page = rang dans le fichier PDF (1 = première)."""
    pj = chemin.with_suffix(chemin.suffix + ".pages.json")
    pages = json.loads(pj.read_text(encoding="utf-8"))["pages"] if pj.exists() else extraire(chemin)
    res = {}
    for mot in mots:
        m = _plat(mot)
        motif = re.compile(r"\b" + re.escape(m) + r"\b") if len(m) <= 5 else re.compile(re.escape(m))
        trouves = []
        for p in pages:
            plat = _plat(p["texte"])
            for x in motif.finditer(plat):
                a, b = max(0, x.start() - contexte), x.end() + contexte
                trouves.append({"page": p["page"],
                                "extrait": " ".join(p["texte"][a:b].split())})
        res[mot] = trouves
    res["_pages_sans_texte"] = [p["page"] for p in pages if p["caracteres"] < 20]
    return res


def rendre(chemin: Path, pages: list[int], resolution: int = 170) -> list[str]:
    """Rend des pages en PNG (lecture visuelle d'un PDF scanné)."""
    import pdfplumber  # requirements.txt (le rendu passe par Pillow, déclaré)

    sorties = []
    with pdfplumber.open(chemin) as pdf:
        for n in pages:
            out = chemin.parent / f"{chemin.stem}_p{n}.png"
            pdf.pages[n - 1].to_image(resolution=resolution).save(out)
            sorties.append(str(out))
    return sorties


def verifier_releve(releve: dict) -> list[str]:
    """Liste des défauts de format d'un relevé (vide = conforme)."""
    d = []
    for c in ("ticker", "societe", "releve_le", "blocage", "pieces", "chiffres", "estimations"):
        if c not in releve:
            d.append(f"champ racine manquant : {c}")
    ids = set()
    for p in releve.get("pieces", []):
        for c in CHAMPS_PIECE:
            if p.get(c) in (None, ""):
                d.append(f"pièce {p.get('id')} : {c} manquant")
        if not str(p.get("url", "")).startswith("https://"):
            d.append(f"pièce {p.get('id')} : URL non https")
        ids.add(p.get("id"))

    def _un(ch, champs, ou):
        for c in champs:
            if ch.get(c) in (None, ""):
                d.append(f"{ou} {ch.get('grandeur')} : {c} manquant")
        src = str(ch.get("source", ""))
        if not src.startswith("https://"):
            d.append(f"{ou} {ch.get('grandeur')} : source non URL")
        if ch.get("piece") is not None and ch["piece"] not in ids:
            d.append(f"{ou} {ch.get('grandeur')} : pièce {ch['piece']} non listée")
        pg = ch.get("page")
        if not (isinstance(pg, int) and pg > 0) and not (isinstance(pg, str) and pg.strip()):
            d.append(f"{ou} {ch.get('grandeur')} : page invalide")

    for ch in releve.get("chiffres", []):
        _un(ch, CHAMPS_CHIFFRE, "chiffre")
        if ch.get("nature") == "estimation":
            d.append(f"chiffre {ch.get('grandeur')} : une estimation n'entre pas dans « chiffres »")
    for ch in releve.get("estimations", []):
        _un(ch, CHAMPS_ESTIMATION, "estimation")
    return d


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("telecharger"); a.add_argument("ticker"); a.add_argument("url"); a.add_argument("--nom")
    a = sp.add_parser("extraire"); a.add_argument("fichier", type=Path)
    a = sp.add_parser("chercher"); a.add_argument("fichier", type=Path); a.add_argument("--mots", nargs="*")
    a.add_argument("--max", type=int, default=6, help="occurrences affichées par mot")
    a = sp.add_parser("rendre"); a.add_argument("fichier", type=Path); a.add_argument("--pages", required=True)
    a = sp.add_parser("verifier"); a.add_argument("releves", nargs="*", type=Path)
    x = ap.parse_args(argv)

    if x.cmd == "telecharger":
        print(json.dumps(telecharger(x.ticker, x.url, x.nom), ensure_ascii=False, indent=1))
    elif x.cmd == "extraire":
        pages = extraire(x.fichier)
        vides = [p["page"] for p in pages if p["caracteres"] < 20]
        print(f"{len(pages)} pages ; sans texte (OCR ou rendu requis) : {vides or 'aucune'}")
    elif x.cmd == "chercher":
        r = chercher(x.fichier, tuple(x.mots) if x.mots else MOTS_COMPTABLES)
        for mot, occ in r.items():
            if mot.startswith("_"):
                continue
            print(f"## {mot} — {len(occ)} occurrence(s), pages {sorted({o['page'] for o in occ})}")
            for o in occ[: x.max]:
                print(f"  p.{o['page']} … {o['extrait']} …")
        print("pages sans texte :", r["_pages_sans_texte"] or "aucune")
    elif x.cmd == "rendre":
        print("\n".join(rendre(x.fichier, [int(p) for p in x.pages.split(",")])))
    elif x.cmd == "verifier":
        fichiers = x.releves or sorted(RELEVES.glob("*.json"))
        ko = 0
        for f in fichiers:
            defauts = verifier_releve(json.loads(f.read_text(encoding="utf-8")))
            ko += bool(defauts)
            print(f"{f.name}: {'conforme' if not defauts else '; '.join(defauts)}")
        return 1 if ko else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

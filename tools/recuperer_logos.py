#!/usr/bin/env python3
"""Les logos des sociétés, pris sur LEUR site officiel — 30/09/2026.

Demande d'Abd Moutalib : rendre le classement plus vivant, avec des logos en
miniature comme sur les plateformes des sociétés de bourse.

⚠️ D'OÙ VIENT CHAQUE LOGO, ET POURQUOI PAS D'AILLEURS
─────────────────────────────────────────────────────
Un logo est une marque de la société. On le prend chez ELLE, jamais chez un
intermédiaire qui l'héberge (CDG, IDBourse…) : reprendre les fichiers d'un
tiers, c'est utiliser ses ressources sans accord (chantier n° 5, droit des
données).

⚠️ L'ADRESSE DU SITE NE SE DEVINE PAS. Elle est lue dans la fiche société de
CDG Capital Bourse (`VALEURS-INFOS`, champ `SiteInternet`) — la seule chose
qu'on y prend. Un site supposé de mémoire pourrait être celui d'une autre
société : c'est le piège `SNA` Stokvis / Sonasid, par l'image. Quatre titres
sans site déclaré (ZLD, SOT, BAL, REB) n'ont pas de logo : le terminal leur
affiche un monogramme.

⚠️ CHAQUE LOGO EST VÉRIFIÉ À L'ŒIL avant publication (planche contact), et
consigné dans `datasets/logos/registre.json` : site, adresse du fichier,
méthode, date, empreinte. Un logo refusé à la relecture est inscrit dans
`REFUSES` avec sa raison, et n'est pas publié.

    python tools/recuperer_logos.py            # relève, miniaturise, registre
    python tools/recuperer_logos.py --echecs   # ne reprend que les titres sans logo
    python tools/recuperer_logos.py --planche  # planche contact pour relecture
    python tools/recuperer_logos.py --refus    # applique REFUSES sans rien relever

⚠️ Le rendu des logos SVG passe par Playwright (requirements_outils.txt) :
un outil lancé à la main, jamais par un workflow.
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import requests
from PIL import Image, ImageOps

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from bvc_config import IDB_TICKER_MAP, TICKERS_ALL  # noqa: E402

DOSSIER = RACINE / "logos"
REGISTRE = RACINE / "datasets" / "logos" / "registre.json"
CDG_API = "https://www.cdgcapitalbourse.ma/api/"
UA = {"User-Agent": "Mozilla/5.0 (BVC Analyzer; identification des sociétés cotées)"}
COTE = 64          # pixels : affiché en 28 px, net sur écran haute densité
MARGE = 6          # pixels de blanc autour du logo, dans la pastille

# Logos écartés à la relecture visuelle du 30/09/2026 — avec la raison.
# ⚠️ Le site déclaré par CDG est parfois celui du GROUPE, et l'en-tête montre
# alors le logo d'une autre entité, ou celui d'un partenaire.
REFUSES: dict[str, str] = {
    "SMI": "site déclaré = celui du groupe Managem : le logo capturé est celui de Managem",
    "SRM": "site déclaré = groupe Premium : le logo capturé est Hyundai Construction Equipment",
    "DAR": "le logo capturé est celui du SIAM, un salon partenaire affiché sur le site",
    "HAL": "le logo capturé montre les marques distribuées (Case, Valtra, FPT)",
    "MIC": "le logo capturé est Dell EMC, un partenaire",
    "SAF": "le logo capturé est une icône générique d'une banque d'images, pas celui de Sanlam",
    "DTT": "illisible en miniature : texte gris clair sur fond blanc",
    "RIS": "texture sombre de l'en-tête capturée à la place du logo, illisible",
}
FOND_SOMBRE = (26, 37, 64)   # la couleur du terminal, pour les logos blancs


def site_officiel(sym: str) -> str | None:
    """Le site déclaré dans la fiche société de CDG (champ `SiteInternet`)."""
    corps = {"ACTIONS": [{
        "ACTION": {"NAME": "VALEURS-INFOS", "TYPE": "SELECT", "VALUE": "VALEURS-INFOS"},
        "PARAMS": [{"NAME": "Lang_", "TYPE": "S", "VALUE": "fr"},
                   {"NAME": "Espace_", "TYPE": "I", "VALUE": "1"},
                   {"NAME": "Symbol_", "TYPE": "S", "VALUE": IDB_TICKER_MAP.get(sym) or sym}]}]}
    r = requests.post(CDG_API, json=corps, timeout=30, headers={
        **UA, "Content-Type": "application/json",
        "Referer": "https://www.cdgcapitalbourse.ma/Bourse/market",
        "Origin": "https://www.cdgcapitalbourse.ma"})
    d = (r.json()[0]["VALEURS-INFOS"].get("Data") or [{}])[0]
    s = (d.get("SiteInternet") or "").strip()
    if not s:
        return None
    return s if s.startswith("http") else "https://" + s.lstrip("/")


def candidats(page: str, base: str) -> list[tuple[str, str]]:
    """(méthode, url) dans l'ordre de préférence. Fonction pure.

    1. l'image du logo dans la page (attribut contenant « logo ») ;
    2. l'icône haute définition déclarée pour les téléphones ;
    3. les icônes déclarées, les plus grandes d'abord.
    `og:image` est écarté : c'est presque toujours une photo de bannière.
    """
    out = []
    for tag in re.findall(r"<img\b[^>]*>", page, flags=re.I):
        if re.search(r"logo", tag, flags=re.I):
            m = re.search(r'\bsrc\s*=\s*["\']([^"\']+)', tag, flags=re.I)
            if m and not m.group(1).startswith("data:"):
                out.append(("img_logo", urljoin(base, html.unescape(m.group(1)))))
    icones = []
    for tag in re.findall(r"<link\b[^>]*>", page, flags=re.I):
        rel = (re.search(r'\brel\s*=\s*["\']([^"\']+)', tag, flags=re.I) or [None, ""])[1].lower()
        href = re.search(r'\bhref\s*=\s*["\']([^"\']+)', tag, flags=re.I)
        if not href or "icon" not in rel:
            continue
        taille = re.search(r'\bsizes\s*=\s*["\'](\d+)x\d+', tag, flags=re.I)
        icones.append((0 if "apple" in rel else 1, -int(taille.group(1)) if taille else 0,
                       "apple_touch_icon" if "apple" in rel else "icon",
                       urljoin(base, html.unescape(href.group(1)))))
    out += [(m, u) for _, _, m, u in sorted(icones)]
    return out


def miniature(brut: bytes) -> Image.Image | None:
    """Le logo réduit dans un carré blanc de COTE pixels, ou None."""
    try:
        im = Image.open(io.BytesIO(brut))
        im.load()
    except Exception:
        return None
    if min(im.size) < 24:
        return None                       # trop petit pour être lisible
    im = im.convert("RGBA")
    # ⚠️ UN LOGO BLANC SUR FOND BLANC EST INVISIBLE. Beaucoup de sites dessinent
    # leur logo en blanc pour un en-tête sombre : mesuré sur la luminance des
    # seuls pixels opaques, il est alors posé sur le fond du terminal.
    opaques = [px for px in im.getdata() if px[3] > 128]
    clair = bool(opaques) and (sum(0.299 * r + 0.587 * g + 0.114 * b
                                   for r, g, b, _ in opaques) / len(opaques)) > 200
    teinte = FOND_SOMBRE if clair else (255, 255, 255)
    # Rogner autour de la partie OPAQUE (ou non blanche, pour un fond plein).
    boite = im.getchannel("A").point(lambda p: 255 if p > 20 else 0).getbbox()
    if boite and boite != (0, 0, im.width, im.height):
        im = im.crop(boite)
    fond = Image.new("RGBA", im.size, teinte + (255,))
    im = Image.alpha_composite(fond, im).convert("RGB")
    if not clair:
        boite = ImageOps.invert(im.convert("L")).point(lambda p: 255 if p > 12 else 0).getbbox()
        if boite:
            im = im.crop(boite)
    im.thumbnail((COTE - 2 * MARGE, COTE - 2 * MARGE), Image.LANCZOS)
    carre = Image.new("RGB", (COTE, COTE), teinte)
    carre.paste(im, ((COTE - im.width) // 2, (COTE - im.height) // 2))
    return carre


# Éléments candidats pour le logo, rendus par le navigateur. Ordre : ce qui
# se déclare « logo », puis la première image ou le premier SVG de l'en-tête.
SELECTEURS = [
    "[class*='logo' i] img", "[class*='logo' i] svg", "[id*='logo' i] img",
    "[id*='logo' i] svg", "img[src*='logo' i]", "img[alt*='logo' i]",
    "a[class*='brand' i] img", "a[class*='brand' i] svg",
    "header img", "header svg",
]


def relever_rendu(site: str) -> tuple[bytes, str] | None:
    """Le logo tel que le site l'AFFICHE, capturé dans le navigateur.

    Pour les sites dont le logo est un SVG, ou une image injectée par
    JavaScript, que la lecture du HTML brut ne voit pas.

    ⚠️ Le Chromium du conteneur n'a pas d'accès direct au réseau : chacune de
    ses requêtes est servie par `requests`, qui VÉRIFIE les certificats
    (jamais désactivé). Un site au certificat invalide échoue ici aussi.
    """
    from playwright.sync_api import sync_playwright   # outil manuel seulement

    def servir(route):
        req = route.request
        try:
            r = requests.request(req.method, req.url, headers={**UA, "Referer": site},
                                 data=req.post_data_buffer, timeout=20)
            entetes = {k: v for k, v in r.headers.items()
                       if k.lower() not in ("content-encoding", "content-length",
                                            "transfer-encoding", "content-security-policy")}
            route.fulfill(status=r.status_code, headers=entetes, body=r.content)
        except Exception:
            route.abort()

    with sync_playwright() as p:
        # ⚠️ Le Chromium du conteneur, pas celui que Playwright voudrait
        # télécharger : `CHROMIUM` le désigne, `/opt/pw-browsers/chromium` par
        # défaut (environnement Claude Code) ; ailleurs, le navigateur livré.
        import os
        chemin = os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium")
        nav = p.chromium.launch(executable_path=chemin if os.path.exists(chemin) else None)
        page = nav.new_page(viewport={"width": 1366, "height": 900})
        page.route("**/*", servir)
        try:
            page.goto(site, timeout=45000, wait_until="load")
            page.wait_for_timeout(2500)
            for sel in SELECTEURS:
                for el in page.query_selector_all(sel)[:4]:
                    b = el.bounding_box()
                    if not b or b["y"] > 260 or b["width"] < 30 or b["height"] < 14:
                        continue
                    if b["width"] > 600 or b["height"] > 220:
                        continue
                    return el.screenshot(), f"rendu:{sel}"
        finally:
            nav.close()
    return None


def relever(sym: str, site: str) -> dict:
    r = requests.get(site, headers=UA, timeout=25)
    page, base = r.text, r.url
    for methode, url in candidats(page, base):
        if url.lower().split("?")[0].endswith(".svg"):
            continue                      # pas de rastérisation SVG ici
        try:
            f = requests.get(url, headers=UA, timeout=25)
        except Exception:
            continue
        if f.status_code != 200:
            continue
        m = miniature(f.content)
        if m is None:
            continue
        tampon = io.BytesIO()
        m.save(tampon, "PNG", optimize=True)
        octets = tampon.getvalue()
        (DOSSIER / f"{sym}.png").write_bytes(octets)
        return {"site": site, "page_lue": base, "fichier_source": url,
                "methode": methode, "recupere_le": date.today().isoformat(),
                "sha256": hashlib.sha256(octets).hexdigest(), "octets": len(octets)}
    rendu = None
    try:
        rendu = relever_rendu(base)
    except Exception as e:
        return {"site": site, "echec": f"rendu impossible : {type(e).__name__}"}
    if rendu:
        m = miniature(rendu[0])
        if m is not None:
            tampon = io.BytesIO()
            m.save(tampon, "PNG", optimize=True)
            octets = tampon.getvalue()
            (DOSSIER / f"{sym}.png").write_bytes(octets)
            return {"site": site, "page_lue": base, "fichier_source": None,
                    "methode": rendu[1], "recupere_le": date.today().isoformat(),
                    "sha256": hashlib.sha256(octets).hexdigest(), "octets": len(octets)}
    return {"site": site, "echec": "aucun logo repéré dans la page"}


def appliquer_refus(reg: dict) -> None:
    """Retire les logos refusés à la relecture, et dit pourquoi au registre."""
    for sym, raison in REFUSES.items():
        (DOSSIER / f"{sym}.png").unlink(missing_ok=True)
        reg[sym] = {**reg.get(sym, {}), "refuse": raison}
        reg[sym].pop("sha256", None)


def planche(sortie: Path) -> None:
    """Planche contact : chaque miniature avec son ticker, pour relecture."""
    from PIL import ImageDraw
    reg = json.loads(REGISTRE.read_text(encoding="utf-8"))
    syms = [s for s in reg if (DOSSIER / f"{s}.png").exists()]
    col, cel = 8, 96
    img = Image.new("RGB", (col * cel, ((len(syms) + col - 1) // col) * cel), (20, 26, 38))
    d = ImageDraw.Draw(img)
    for i, s in enumerate(syms):
        x, y = (i % col) * cel, (i // col) * cel
        img.paste(Image.open(DOSSIER / f"{s}.png"), (x + 16, y + 6))
        d.text((x + 30, y + 76), s, fill=(230, 230, 230))
    img.save(sortie)


def main() -> int:
    if "--planche" in sys.argv:
        planche(RACINE / "logos_planche.png")
        return 0
    if "--refus" in sys.argv:
        reg = json.loads(REGISTRE.read_text(encoding="utf-8"))
        appliquer_refus(reg)
        REGISTRE.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0
    DOSSIER.mkdir(exist_ok=True)
    reg = {}
    if "--echecs" in sys.argv and REGISTRE.exists():
        reg = json.loads(REGISTRE.read_text(encoding="utf-8"))
    for sym in TICKERS_ALL:
        if reg.get(sym, {}).get("sha256"):
            continue
        try:
            site = site_officiel(sym)
        except Exception as e:
            reg[sym] = {"echec": f"fiche CDG illisible : {e}"}
            continue
        if not site:
            reg[sym] = {"echec": "aucun site déclaré dans la fiche société"}
            continue
        try:
            reg[sym] = relever(sym, site)
        except Exception as e:
            reg[sym] = {"site": site, "echec": f"site injoignable : {type(e).__name__}"}
        time.sleep(0.5)
    appliquer_refus(reg)
    REGISTRE.parent.mkdir(parents=True, exist_ok=True)
    REGISTRE.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = [s for s, v in reg.items() if v.get("sha256")]
    print(f"{len(ok)} logos sur {len(reg)} ; sans logo : "
          f"{', '.join(s for s in reg if s not in ok)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

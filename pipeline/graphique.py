#!/usr/bin/env python3
"""Un graphique qui montre aussi ce qu'il ne sait pas.

CE QUE CE GRAPHIQUE DOIT FAIRE, ET QUE LES NÔTRES NE FAISAIENT PAS
──────────────────────────────────────────────────────────────────
    « Un graphique sur ADH ou CSR avec un indicateur, une période identifiée,
      les données manquantes visibles et un statut de qualité explicite. »

Trois exigences, et la troisième est celle qu'on oublie toujours.

1. **L'axe du temps est un CALENDRIER, pas un compteur de lignes.** Tracer les
   séances à intervalle régulier efface les trous : trois jours d'absence
   ressemblent alors à une séance ordinaire. Ici l'abscisse est la date réelle,
   donc un trou occupe la place qu'il mérite.

2. **Une interruption n'est pas reliée.** Au-delà de `JOURS_AVANT_RUPTURE`
   jours sans séance, le trait s'arrête et reprend de l'autre côté. Relier deux
   points séparés d'un mois dessine une tendance qui n'a jamais existé.

   ⚠️ **UNE COUPURE DU TRAIT N'EST PAS UNE COUPURE DU CALCUL.** Les indicateurs
   travaillent sur les observations REÇUES, dans leur ordre, sans tenir compte
   de l'écart calendaire qui les sépare. Une moyenne sur vingt séances peut
   donc enjamber une interruption que le trait, lui, montre rompue. Le dessin
   dit « il manque des jours ici » ; il ne dit pas « le calcul s'est arrêté ».
   Les deux sont affichés côte à côte pour qu'on ne les confonde pas.

   ⚠️ Le seuil de quatre jours détecte des **écarts calendaires longs**, pas
   toutes les séances manquantes. Une séance absente au milieu d'une semaine
   ordinaire ne crée qu'un écart de deux jours et passe donc inaperçue ici —
   le calendrier officiel des séances nous manque pour faire mieux.

3. **Le statut de qualité est en haut, en grand, pas en note de bas de page.**
   Un résultat exploratoire qu'on ne distingue pas d'un résultat publiable
   finira par être lu comme publiable.

⚠️ AUCUNE DÉPENDANCE EXTERNE. Le SVG est écrit à la main dans un fichier HTML
autonome : pas de CDN, pas de bibliothèque, rien à télécharger. Le fichier
s'ouvre hors ligne et ne parle à personne.

USAGE
    python pipeline/graphique.py --titre ADH --indicateur sma --periode 20 \\
        --depuis 2026-06-01
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))
from fenetre import Verdict, qualifier_fenetre  # noqa: E402
from indicateurs import ema, rsi_wilder, sma  # noqa: E402

LOT1B = RACINE / "datasets" / "lot1b"

# ⚠️ Les OSCILLATEURS ne partagent pas l'échelle des prix. Le RSI varie de 0 à
# 100 ; un titre qui cote 200 DH écraserait sa courbe en bas du cadre, où elle
# se lirait comme un prix. Ils vont dans un panneau séparé, avec leur propre
# graduation — c'est une question d'honnêteté de lecture, pas d'esthétique.
PANNEAU_SEPARE = {"rsi_wilder"}
BORNES_OSCILLATEUR = {"rsi_wilder": (0.0, 100.0, (30.0, 70.0))}

# Au-delà de ce nombre de jours calendaires sans séance, le trait est rompu.
# Quatre jours couvrent un week-end ordinaire plus un férié ; au-delà, il
# manque vraiment quelque chose.
JOURS_AVANT_RUPTURE = 4

L, H = 1120, 560
MG = {"g": 70, "d": 28, "h": 150, "b": 62}

COULEURS = {
    "fond": "#fbfaf7", "cadre": "#e2ded4", "texte": "#2c2a26",
    "discret": "#8a857a", "cours": "#1f4e6b", "indicateur": "#c0632a",
    "manque": "#c8442e", "explo": "#8a5a00", "explo_fond": "#fdf3dc",
    "refus_fond": "#fbe4e0",
}


def calculer(nom: str, valeurs: list, periode: int) -> list:
    return {"sma": sma, "ema": ema, "rsi_wilder": rsi_wilder}[nom](valeurs, periode)


def echelle(vals: list, y_bas: float, y_haut: float):
    """Échelle de valeur → ordonnée SVG.

    ⚠️ `y_bas` est l'ordonnée du BAS du cadre, donc le plus GRAND nombre : en
    SVG l'axe y descend. Une valeur BASSE doit tomber près de `y_bas`, une
    valeur HAUTE près de `y_haut`.

    Une version antérieure écrivait `y_haut - frac × (y_haut − y_bas)`, ce qui
    renvoyait exactement l'inverse : le graphique affichait les prix les plus
    bas EN HAUT du cadre. Le défaut ne s'est vu qu'en regardant l'image — aucun
    test de calcul ne pouvait l'attraper, puisque les nombres étaient justes et
    seule leur mise en place était fausse.
    """
    reels = [v for v in vals if v is not None]
    if not reels:
        return (lambda v: (y_bas + y_haut) / 2), 0.0, 1.0
    lo, hi = min(reels), max(reels)
    if hi == lo:
        hi = lo + 1.0
    marge = (hi - lo) * 0.1
    lo, hi = lo - marge, hi + marge
    return (lambda v: y_bas - (v - lo) / (hi - lo) * (y_bas - y_haut)), lo, hi


def segments(points: list, jours_max: int) -> list:
    """Découpe en traits continus, en coupant sur les vraies interruptions."""
    out, courant = [], []
    for i, p in enumerate(points):
        if p["y"] is None:
            if courant:
                out.append(courant)
            courant = []
            continue
        if courant:
            ecart = (p["jour"] - points[i - 1]["jour"]).days
            if ecart > jours_max or points[i - 1]["y"] is None:
                out.append(courant)
                courant = []
        courant.append(p)
    if courant:
        out.append(courant)
    return out


def construire(titre, nom_ind, periode, obs, q, ind) -> str:
    jours = [date.fromisoformat(o["date"]) for o in obs]
    cours = [o["cloture"] for o in obs]
    j0, j1 = jours[0], jours[-1]
    span = max((j1 - j0).days, 1)

    separe = nom_ind in PANNEAU_SEPARE
    x = lambda d: MG["g"] + (d - j0).days / span * (L - MG["g"] - MG["d"])  # noqa: E731

    bas_graphe = H - MG["b"]
    if separe:
        # Deux cadres : les prix en haut, l'oscillateur en bas, échelles distinctes.
        bas_prix = MG["h"] + (bas_graphe - MG["h"]) * 0.60
        haut_osc = bas_prix + 46
        y_c, lo, hi = echelle(cours, bas_prix, MG["h"])
        omin, omax, reperes = BORNES_OSCILLATEUR[nom_ind]
        y_i = lambda v: bas_graphe - (v - omin) / (omax - omin) * (bas_graphe - haut_osc)  # noqa: E731
    else:
        bas_prix, haut_osc, omin, omax = bas_graphe, 0.0, 0.0, 0.0
        y_c, lo, hi = echelle(cours + [v for v in ind if v is not None],
                              bas_graphe, MG["h"])
        y_i, reperes = y_c, ()

    pc = [{"jour": j, "y": (y_c(c) if c is not None else None), "v": c}
          for j, c in zip(jours, cours)]
    pi = [{"jour": j, "y": (y_i(v) if v is not None else None), "v": v}
          for j, v in zip(jours, ind)]

    def trace(pts, couleur, largeur, tirets=""):
        d = ""
        for seg in segments(pts, JOURS_AVANT_RUPTURE):
            if len(seg) < 2:
                continue
            d += "M" + " L".join(f"{x(p['jour']):.1f},{p['y']:.1f}" for p in seg)
        if not d:
            return ""
        da = f' stroke-dasharray="{tirets}"' if tirets else ""
        return (f'<path d="{d}" fill="none" stroke="{couleur}" '
                f'stroke-width="{largeur}" stroke-linejoin="round"{da}/>')

    # ── interruptions : on les DESSINE, on ne les comble pas ───────────────
    trous = []
    for a, b in zip(jours, jours[1:]):
        if (b - a).days > JOURS_AVANT_RUPTURE:
            trous.append((a, b, (b - a).days))
    bandes = "".join(
        f'<rect x="{x(a):.1f}" y="{MG["h"]}" width="{max(x(b) - x(a), 1.5):.1f}" '
        f'height="{bas_graphe - MG["h"]}" fill="{COULEURS["manque"]}" '
        f'opacity="0.09"/>' for a, b, _ in trous)

    # ── amorce de l'indicateur : la zone où il n'existe pas encore ─────────
    premier = next((i for i, v in enumerate(ind) if v is not None), None)
    amorce = ""
    if premier:
        amorce = (
            f'<rect x="{MG["g"]}" y="{MG["h"]}" '
            f'width="{max(x(jours[premier]) - MG["g"], 0):.1f}" '
            f'height="{bas_graphe - MG["h"]}" fill="{COULEURS["discret"]}" '
            f'opacity="0.07"/>'
            f'<text x="{MG["g"] + 8}" y="{MG["h"] + 20}" font-size="11" '
            f'fill="{COULEURS["discret"]}">fenêtre incomplète — '
            f'{nom_ind} non calculable</text>')

    # ── graduations ────────────────────────────────────────────────────────
    gy = ""
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        yy = y_c(v)
        gy += (f'<line x1="{MG["g"]}" y1="{yy:.1f}" x2="{L - MG["d"]}" '
               f'y2="{yy:.1f}" stroke="{COULEURS["cadre"]}" stroke-width="1"/>'
               f'<text x="{MG["g"] - 10}" y="{yy + 4:.1f}" text-anchor="end" '
               f'font-size="11" fill="{COULEURS["discret"]}">{v:,.1f}</text>')
    gx = ""
    for k in range(5):
        d = j0 + (j1 - j0) * k // 4
        gx += (f'<text x="{x(d):.1f}" y="{H - MG["b"] + 22}" '
               f'text-anchor="middle" font-size="11" '
               f'fill="{COULEURS["discret"]}">{d.strftime("%d/%m/%y")}</text>')

    # ── panneau de l'oscillateur : sa propre graduation, ses repères ──────
    cadre_osc = ""
    if separe:
        cadre_osc = (
            f'<line x1="{MG["g"]}" y1="{haut_osc - 18:.1f}" x2="{L - MG["d"]}" '
            f'y2="{haut_osc - 18:.1f}" stroke="{COULEURS["cadre"]}" '
            f'stroke-width="1"/>'
            f'<text x="{MG["g"]}" y="{haut_osc - 24:.1f}" font-size="11" '
            f'fill="{COULEURS["discret"]}">{nom_ind}({periode}) — échelle propre, '
            f'{omin:.0f} à {omax:.0f}, sans rapport avec les prix ci-dessus</text>')
        for r in reperes:
            cadre_osc += (
                f'<line x1="{MG["g"]}" y1="{y_i(r):.1f}" x2="{L - MG["d"]}" '
                f'y2="{y_i(r):.1f}" stroke="{COULEURS["cadre"]}" '
                f'stroke-width="1" stroke-dasharray="3 4"/>'
                f'<text x="{MG["g"] - 10}" y="{y_i(r) + 4:.1f}" text-anchor="end" '
                f'font-size="10.5" fill="{COULEURS["discret"]}">{r:.0f}</text>')

    pts_c = "".join(
        f'<circle cx="{x(p["jour"]):.1f}" cy="{p["y"]:.1f}" r="1.8" '
        f'fill="{COULEURS["cours"]}" opacity="0.55"/>'
        for p in pc if p["y"] is not None)

    explo = q["verdict"] != Verdict.QUALIFIE.value
    fond_b = COULEURS["explo_fond"] if explo else "#eef4ee"
    bord_b = COULEURS["explo"] if explo else "#3d6b47"
    etiquette = ("RÉSULTAT EXPLORATOIRE — n'alimente ni le signal officiel, "
                 "ni une probabilité, ni une performance validée"
                 if explo else "FENÊTRE QUALIFIÉE pour cet usage")

    calcules = sum(1 for v in ind if v is not None)
    manquants = sum(1 for c in cours if c is None)

    svg = f"""<svg viewBox="0 0 {L} {H}" width="100%" role="img"
     aria-label="{titre} — clôtures et {nom_ind}({periode})">
  <rect width="{L}" height="{H}" fill="{COULEURS['fond']}"/>
  <rect x="14" y="14" width="{L - 28}" height="108" rx="6"
        fill="{fond_b}" stroke="{bord_b}" stroke-width="1.5"/>
  <text x="30" y="44" font-size="20" font-weight="600"
        fill="{COULEURS['texte']}">{titre} · clôtures et {nom_ind}({periode})</text>
  <text x="30" y="68" font-size="12.5" fill="{bord_b}" font-weight="600">{etiquette}</text>
  <text x="30" y="90" font-size="11.5" fill="{COULEURS['discret']}">
    fenêtre {q['debut']} → {q['fin']} · {q['lignes']} séances ·
    {calcules} points d'indicateur · {len(trous)} interruption(s) ·
    {manquants} clôture(s) absente(s)</text>
  <text x="30" y="109" font-size="11.5" fill="{COULEURS['discret']}">
    base de prix : {q.get('_base', '—')} · besoins : {', '.join(q['besoins'])} ·
    verdict : {q['verdict']}</text>
  {gy}{bandes}{amorce}{cadre_osc}
  {trace(pc, COULEURS['cours'], 1.9)}
  {pts_c}
  {trace(pi, COULEURS['indicateur'], 2.4)}
  <line x1="{MG['g']}" y1="{bas_graphe}" x2="{L - MG['d']}" y2="{bas_graphe}"
        stroke="{COULEURS['cadre']}" stroke-width="1.5"/>
  {gx}
  <g transform="translate({MG['g']},{H - 20})" font-size="11.5">
    <line x1="0" y1="-4" x2="26" y2="-4" stroke="{COULEURS['cours']}" stroke-width="1.9"/>
    <text x="34" y="0" fill="{COULEURS['texte']}">clôture</text>
    <line x1="110" y1="-4" x2="136" y2="-4" stroke="{COULEURS['indicateur']}" stroke-width="2.4"/>
    <text x="144" y="0" fill="{COULEURS['texte']}">{nom_ind}({periode})</text>
    <rect x="250" y="-11" width="22" height="11" fill="{COULEURS['manque']}" opacity="0.09"/>
    <text x="280" y="0" fill="{COULEURS['texte']}">écart calendaire — trait rompu, mais le CALCUL enjambe</text>
  </g>
</svg>"""

    lignes_trous = "".join(
        f"<li>{a.strftime('%d/%m/%Y')} → {b.strftime('%d/%m/%Y')} — "
        f"{n} jours calendaires</li>" for a, b, n in trous) or \
        "<li>aucune interruption de plus de "f"{JOURS_AVANT_RUPTURE} jours</li>"

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>{titre} — {nom_ind}({periode})</title>
<style>
 body{{margin:0;padding:24px;background:#f3f1ec;
      font:14px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
      color:#2c2a26}}
 main{{max-width:1180px;margin:0 auto}}
 .carte{{background:#fff;border:1px solid #e2ded4;border-radius:10px;
        padding:18px;margin-bottom:18px}}
 h2{{font-size:15px;margin:0 0 10px;text-transform:uppercase;
    letter-spacing:.06em;color:#6b665c}}
 ul{{margin:0;padding-left:20px}} li{{margin:3px 0}}
 code{{background:#f3f1ec;padding:1px 5px;border-radius:3px;font-size:12.5px}}
 .avert{{background:#fdf3dc;border-left:4px solid #8a5a00;padding:12px 16px;
        border-radius:0 6px 6px 0;margin:0 0 18px}}
 table{{border-collapse:collapse;width:100%;font-size:13px}}
 td,th{{text-align:left;padding:5px 10px;border-bottom:1px solid #eeebe4}}
 th{{color:#6b665c;font-weight:600}}
 @media (max-width:600px){{body{{padding:12px}}}}
</style></head><body><main>
<div class="carte">{svg}</div>
<div class="avert"><strong>{etiquette}</strong><br>{q.get('reserve') or
 'La fenêtre satisfait les conditions déclarées pour cet usage.'}</div>
<div class="carte"><h2>Ce que la fenêtre contient</h2>
<table>
 <tr><th>Période</th><td>{q['debut']} → {q['fin']}</td></tr>
 <tr><th>Séances reçues dans la fenêtre</th><td>{q['lignes']}</td></tr>
 <tr><th>Clôtures absentes parmi les lignes reçues</th><td>{manquants}</td></tr>
 <tr><th>Séances manquantes au calendrier</th><td>non établi — calendrier officiel absent</td></tr>
 <tr><th>Points d'indicateur calculés</th><td>{calcules} sur {q['lignes']}</td></tr>
 <tr><th>Champs requis</th><td>{', '.join(q['besoins'])}</td></tr>
 <tr><th>Base de prix</th><td>{q.get('_base', '—')}</td></tr>
 <tr><th>Base des quantités</th><td>{q.get('_base_qte', '—')}</td></tr>
</table></div>
<div class="carte"><h2>Écarts calendaires</h2>
<ul>{lignes_trous}</ul>
<p style="color:#6b665c;font-size:12.5px;margin:10px 0 0">
⚠️ <strong>Le trait est rompu, le calcul ne l'est pas.</strong> Les indicateurs
travaillent sur les observations reçues, dans leur ordre, sans tenir compte de
l'écart calendaire qui les sépare : une moyenne sur {periode} séances peut
enjamber l'une de ces interruptions. Le dessin signale qu'il manque des jours ;
il ne signale pas un arrêt du calcul.</p>
<p style="color:#6b665c;font-size:12.5px;margin:10px 0 0">
⚠️ Le seuil de {JOURS_AVANT_RUPTURE} jours détecte des <strong>écarts
calendaires longs</strong>, pas toutes les séances manquantes : une séance
absente au milieu d'une semaine ordinaire passe inaperçue. Et nous ne savons
pas si le marché était fermé ou si la collecte a manqué — le calendrier officiel
n'est pas en notre possession.</p></div>
<div class="carte"><h2>Ce que ce graphique ne démontre pas</h2>
<ul>
 <li>Aucune performance, aucun rendement, aucune capacité prédictive.</li>
 <li>Il ne prouve pas que les prix sont exacts — il dit sur quelle base ils
     sont exprimés, et avec quel niveau de preuve.</li>
 <li>L'indicateur est une spécification à tester, pas une formule validée.</li>
 <li>Il ne montre pas les séances manquantes que le calendrier révélerait :
     seuls les écarts de plus de {JOURS_AVANT_RUPTURE} jours sont visibles.</li>
</ul></div>
<p style="color:#8a857a;font-size:12px">
Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')} par
<code>pipeline/graphique.py</code> depuis <code>datasets/lot1b/{titre}.json</code>.
Aucune dépendance externe : SVG écrit à la main, ouvrable hors ligne.</p>
</main></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--titre", default="ADH")
    ap.add_argument("--indicateur", default="sma",
                    choices=["sma", "ema", "rsi_wilder"])
    ap.add_argument("--periode", type=int, default=20)
    ap.add_argument("--depuis", default="")
    ap.add_argument("--jusqu-a", default="")
    ap.add_argument("--sortie", type=Path, default=RACINE / "datasets" / "lot2")
    a = ap.parse_args()

    serie = json.loads((LOT1B / f"{a.titre}.json").read_text(encoding="utf-8"))
    q = qualifier_fenetre(serie["observations"], a.indicateur,
                          a.depuis, a.jusqu_a, periode=a.periode, ticker=a.titre)
    q["_base"] = serie["diagnostic_base_prix"]["niveau"]
    q["_base_qte"] = serie["diagnostic_quantites"]["niveau"]

    obs = [o for o in serie["observations"]
           if (not a.depuis or o["date"] >= a.depuis)
           and (not a.jusqu_a or o["date"] <= a.jusqu_a)]

    if q["verdict"] == Verdict.REFUSE.value:
        print(f"{a.titre} · {a.indicateur} : FENÊTRE REFUSÉE, aucun graphique.")
        for m in q["motifs"]:
            print(f"  ⚠️ {m}")
        raise SystemExit(2)

    ind = calculer(a.indicateur, [o["cloture"] for o in obs], a.periode)
    a.sortie.mkdir(parents=True, exist_ok=True)
    cible = a.sortie / f"{a.titre}_{a.indicateur}_{a.periode}.html"
    cible.write_text(construire(a.titre, a.indicateur, a.periode, obs, q, ind),
                     encoding="utf-8")
    print(f"{a.titre} · {a.indicateur}({a.periode}) · {q['verdict']}")
    print(f"  {q['lignes']} séances, {sum(1 for v in ind if v is not None)} points")
    print(f"→ {cible.relative_to(RACINE)}")


if __name__ == "__main__":
    main()

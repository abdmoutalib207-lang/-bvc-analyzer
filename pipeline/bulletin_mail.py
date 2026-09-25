#!/usr/bin/env python3
"""Compose le bulletin quotidien envoyé par courriel.

Le terminal est un site qu'il faut penser à ouvrir. Le bulletin, lui, vient à
son lecteur — c'est la même donnée, livrée autrement.

⚠️ CE QU'IL NE FAIT PAS. Il ne recalcule rien, n'interroge aucune source, ne
décide de rien. Il lit `data.json` tel qu'il est publié et le met en forme. Si
la collecte a échoué, le bulletin le DIT plutôt que d'enjoliver — un courriel
qui ment est pire qu'un courriel absent, parce qu'on le lit sans vérifier.

⚠️ Le bulletin porte la dernière séance ENREGISTRÉE, pas la date du jour. Le
produit est J+1 : un lundi matin, la dernière séance est celle du vendredi, et
c'est la bonne réponse — pas un retard.

Sortie : (sujet, corps_texte, corps_html), ou un code de sortie non nul si les
données sont trop dégradées pour être envoyées.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).parent.parent

# ⚠️ LE MAROC N'EST PAS À UTC+1 TOUTE L'ANNÉE — corrigé le 25/09/2026.
# Il est repassé à UTC+0 le 20/09/2026, et le registre `DECALAGES_MAROC` de
# `bvc_config.py` fait foi sur ce point, jamais la base de fuseaux du système :
# elle peut être plus ancienne que le dernier décret, ce qui s'est produit le
# 23/09. Cette constante n'était utilisée nulle part — elle n'a donc rien
# faussé — mais elle affirmait le contraire du registre à qui la lirait.
def tz_casablanca(jour=None):
    """Le fuseau de Casablanca À LA DATE DONNÉE, d'après le registre."""
    from bvc_config import decalage_maroc
    from datetime import date as _date
    return timezone(timedelta(hours=decalage_maroc(jour or _date.today())))
TERMINAL = "https://abdmoutalib207-lang.github.io/-bvc-analyzer/"

# En deçà, la collecte a échoué : on le dit au lieu de publier un bulletin creux.
MIN_TITRES_SEANCE = 40

MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre")


def _date_longue(iso):
    """« 2026-09-02 » → « mercredi 2 septembre 2026 »."""
    jours = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
    try:
        d = datetime.strptime(iso[:10], "%Y-%m-%d")
        return f"{jours[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}"
    except Exception:
        return iso or "date inconnue"


def _nb(v, d=2):
    """Formatage à la française : espace fine pour les milliers, virgule décimale."""
    if v is None:
        return "—"
    try:
        s = f"{float(v):,.{d}f}"
        return s.replace(",", " ").replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def _pct(v):
    if v is None:
        return "—"
    try:
        return f"{float(v):+.2f} %".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def charger(chemin=None):
    d = json.loads((Path(chemin) if chemin else RACINE / "data.json")
                   .read_text(encoding="utf-8"))
    lignes = d.get("tickers") or []
    if isinstance(lignes, dict):
        lignes = list(lignes.values())
    return d, [x for x in lignes if x.get("symbol")]


def analyser(data, titres):
    """Tout ce que le bulletin dira, calculé une fois."""
    masi = data.get("masi") or {}
    seance = max((str((x.get("_meta") or {}).get("prix_asof") or "")
                  for x in titres), default="")

    du_jour = [x for x in titres
               if str((x.get("_meta") or {}).get("prix_asof") or "") == seance]
    cotes = [x for x in du_jour if not (x.get("_meta") or {}).get("stale")]

    hausses = sorted((x for x in cotes if (x.get("chg") or 0) > 0),
                     key=lambda z: -z["chg"])
    baisses = sorted((x for x in cotes if (x.get("chg") or 0) < 0),
                     key=lambda z: z["chg"])

    # ⚠️ Un signal n'est retenu qu'à partir d'une confiance de 3. En dessous,
    # le terminal lui-même le grise : le relayer par courriel, où le lecteur ne
    # voit pas l'indicateur, serait le présenter comme plus sûr qu'il ne l'est.
    achats = sorted((x for x in cotes
                     if x.get("sigBvc") == "ACHETER"
                     and ((x.get("_meta") or {}).get("confidence") or 0) >= 3),
                    key=lambda z: -(z.get("v53") or 0))

    return {
        "masi": masi,
        "seance": seance,
        "n_titres": len(titres),
        "n_seance": len(du_jour),
        "cotes": len(cotes),
        # ⚠️ Une valeur qui n'a pas coté sort de `du_jour` : son `prix_asof`
        # reste à la séance précédente. La compter sur le seul écart
        # `du_jour - cotes` en oubliait donc la majorité — 0 affiché pour 21
        # réelles. On compte sur l'univers entier.
        "non_cotes": len(titres) - len(cotes),
        "hausses": hausses,
        "baisses": baisses,
        "achats": achats,
        "insuffisants": [x for x in titres
                         if ((x.get("_meta") or {}).get("confidence") or 0) <= 1],
        "updated": data.get("updated"),
        # ⚠️ La lecture de la séance. Son échec ne doit pas empêcher l'envoi :
        # un bulletin sans lecture reste utile, un bulletin absent ne l'est pas.
        "briefing": _briefing(data),
    }


def _briefing_html(a):
    """La lecture de la séance, mise en forme pour le courriel.

    ⚠️ Les constats et les limites ne portent PAS la même couleur ni le même
    poids : le lecteur doit voir d'un coup d'œil où finit ce qui est mesuré et
    où commence ce qui ne l'est pas. Les confondre typographiquement, c'est
    les confondre tout court.
    """
    from html import escape
    txt = a.get("briefing") or ""
    if not txt:
        return ""
    constats, limites = [], []
    cible = constats
    for ligne in txt.splitlines():
        s = ligne.strip()
        if not s or s == "LECTURE DE LA SÉANCE":
            continue
        if s.startswith("Ce que cette lecture ne dit pas"):
            cible = limites
            continue
        cible.append(s.lstrip("·—- ").strip())
    if not constats and not limites:
        return ""
    puces = "".join(
        f'<li style="margin:0 0 5px">{escape(c)}</li>' for c in constats)
    fin = "".join(
        f'<li style="margin:0 0 3px">{escape(x)}</li>' for x in limites)
    return f"""
  <h2 style="font-size:15px;margin:0 0 4px">Lecture de la séance</h2>
  <p style="font-size:12.5px;color:#6d7887;margin:0 0 8px">
    Des constats chiffrés. Aucune cause n'y est avancée&nbsp;: ce bulletin
    mesure des cours et des volumes.</p>
  <ul style="font-size:13.5px;margin:0 0 10px;padding-left:18px">{puces}</ul>
  {f'''<p style="font-size:12px;color:#6d7887;margin:0 0 4px">
    Ce que cette lecture ne dit pas&nbsp;:</p>
  <ul style="font-size:12px;color:#6d7887;margin:0 0 22px;padding-left:18px">{fin}</ul>'''
     if fin else '<div style="margin-bottom:22px"></div>'}
"""


def largeur_ligne(a):
    """La largeur de marché, en une ligne, pour le texte ET pour le HTML.

    ⚠️ DEUX COMPTES DU MÊME FAIT — corrigé le 25/09/2026.

    L'en-tête comptait les hausses SUR NOTRE UNIVERS (80 titres, dont 13
    n'avaient pas coté ce jour-là) pendant que la lecture de la séance citait
    celui de l'opérateur (68 valeurs traitées). Résultat, dans le même
    courriel : « 14 hausses » quatre lignes au-dessus de « 16 valeurs en
    hausse ». Deux chiffres pour une seule réalité, et rien pour les
    départager — c'est le genre d'écart qui coûte la confiance bien au-delà
    de ce qu'il vaut.

    **La largeur de l'indice appartient à l'opérateur** : c'est lui qui
    définit les valeurs traitées. Notre décompte n'en est qu'une
    reconstitution, sur un univers voisin mais pas identique. On publie donc
    le sien quand il est là, le nôtre seulement à défaut — en disant lequel.

    ⚠️ Une seule fonction pour les deux rendus : corriger la ligne à deux
    endroits, c'est garantir qu'un jour ils divergeront.
    """
    m = a.get("masi") or {}
    if m.get("hausses") is not None and m.get("baisses") is not None:
        return (f"{m['hausses']} hausses · {m['baisses']} baisses · "
                f"{m.get('inchanges') or 0} inchangés "
                f"(sur {m.get('valeurs_traitees') or '?'} valeurs traitées)")
    inchanges = a["cotes"] - len(a["hausses"]) - len(a["baisses"])
    return (f"{len(a['hausses'])} hausses · {len(a['baisses'])} baisses · "
            f"{inchanges} inchangés — décompte sur nos {a['cotes']} titres "
            f"cotés, l'indice n'ayant pas livré sa largeur")


def _briefing(data):
    """La lecture de la séance, ou une chaîne vide. Ne lève jamais."""
    try:
        from pipeline.briefing import composer, texte
        return texte(composer(data))
    except Exception:                                     # noqa: BLE001
        return ""


AVERTISSEMENT = (
    "Information à caractère indicatif, non validée par l'AMMC ni par la Bourse "
    "de Casablanca. Ceci n'est ni un conseil en investissement, ni une offre, ni "
    "une sollicitation. Les cours sont différés et peuvent comporter des erreurs. "
    "Les performances passées ne préjugent pas des performances futures. Vous "
    "restez seul responsable de vos décisions."
)


def texte(a):
    L = []
    add = L.append
    add(f"BULLETIN BVC — séance du {_date_longue(a['seance'])}")
    add("=" * 58)
    add("")
    m = a["masi"]
    add(f"MASI   {_nb(m.get('value'), 2)}   {_pct(m.get('change_pct'))}")
    add(f"       {largeur_ligne(a)}")
    add("")
    if a["hausses"]:
        add("PLUS FORTES HAUSSES")
        for x in a["hausses"][:5]:
            add(f"   {x['symbol']:<6} {(x.get('name') or '')[:26]:<26} "
                f"{_nb(x.get('price'))} DH   {_pct(x.get('chg'))}")
        add("")
    if a["baisses"]:
        add("PLUS FORTES BAISSES")
        for x in a["baisses"][:5]:
            add(f"   {x['symbol']:<6} {(x.get('name') or '')[:26]:<26} "
                f"{_nb(x.get('price'))} DH   {_pct(x.get('chg'))}")
        add("")
    # ⚠️ LA LECTURE DE LA SÉANCE — ajoutée le 25/09/2026.
    #
    # Le bulletin listait l'indice, les extrêmes et les signaux. Il ne disait
    # pas CE QUE LA SÉANCE A ÉTÉ. Or la variation de l'indice, seule, se
    # trompe régulièrement de sens : le MASI est pondéré par les
    # capitalisations, et trois poids lourds suffisent à le porter pendant que
    # la majorité des valeurs recule.
    #
    # ⚠️ Ce bloc CONSTATE, il n'explique jamais. Aucune cause n'y est posée :
    # nous mesurons des cours et des volumes, pas des causes. Voir
    # `pipeline/briefing.py`.
    if a.get("briefing"):
        add(a["briefing"])
        add("")

    add(f"SIGNAUX D'ACHAT ({len(a['achats'])})")
    if a["achats"]:
        add("   Retenus seulement à partir d'une confiance de 3 sur 5.")
        for x in a["achats"][:10]:
            c = (x.get("_meta") or {}).get("confidence")
            add(f"   {x['symbol']:<6} {(x.get('name') or '')[:26]:<26} "
                f"note {_nb(x.get('v53'), 2)}/10   confiance {c}/5")
    else:
        add("   Aucun signal d'achat suffisamment étayé sur cette séance.")
    add("")
    add("CE QUE CE BULLETIN NE SAIT PAS")
    add(f"   {a['non_cotes']} valeur(s) n'ont pas coté : leur prix est celui "
        f"de la dernière séance où elles l'ont fait.")
    if a["insuffisants"]:
        add(f"   {len(a['insuffisants'])} valeur(s) sans données suffisantes, "
            f"aucun signal émis : "
            f"{', '.join(x['symbol'] for x in a['insuffisants'])}.")
    add("")
    add(f"Terminal complet : {TERMINAL}")
    add("")
    add("-" * 58)
    add(AVERTISSEMENT)
    return "\n".join(L)


def html(a):
    m = a["masi"]
    coul = "#1c6b4a" if (m.get("change_pct") or 0) >= 0 else "#a32b21"

    def lignes(xs, n=5):
        out = []
        for x in xs[:n]:
            c = "#1c6b4a" if (x.get("chg") or 0) >= 0 else "#a32b21"
            out.append(
                f'<tr><td style="padding:7px 10px;font-family:monospace;'
                f'font-weight:600">{x["symbol"]}</td>'
                f'<td style="padding:7px 10px;color:#414b58">'
                f'{(x.get("name") or "")[:30]}</td>'
                f'<td style="padding:7px 10px;text-align:right;'
                f'font-family:monospace">{_nb(x.get("price"))}</td>'
                f'<td style="padding:7px 10px;text-align:right;'
                f'font-family:monospace;color:{c};font-weight:600">'
                f'{_pct(x.get("chg"))}</td></tr>')
        return "".join(out)

    achats = "".join(
        f'<tr><td style="padding:7px 10px;font-family:monospace;'
        f'font-weight:600">{x["symbol"]}</td>'
        f'<td style="padding:7px 10px;color:#414b58">'
        f'{(x.get("name") or "")[:30]}</td>'
        f'<td style="padding:7px 10px;text-align:right;font-family:monospace">'
        f'{_nb(x.get("v53"), 2)}/10</td>'
        f'<td style="padding:7px 10px;text-align:right;font-family:monospace;'
        f'color:#6d7887">{(x.get("_meta") or {}).get("confidence")}/5</td></tr>'
        for x in a["achats"][:10]) or (
        '<tr><td colspan="4" style="padding:12px 10px;color:#6d7887">'
        'Aucun signal d\'achat suffisamment étayé sur cette séance.</td></tr>')

    ins = ""
    if a["insuffisants"]:
        ins = (f"<li>{len(a['insuffisants'])} valeur(s) sans données "
               f"suffisantes, aucun signal émis : "
               f"{', '.join(x['symbol'] for x in a['insuffisants'])}.</li>")

    th = ('style="padding:8px 10px;text-align:left;font-size:11px;'
          'letter-spacing:.1em;text-transform:uppercase;color:#6d7887;'
          'border-bottom:1px solid #d5dae1"')
    thr = th.replace("text-align:left", "text-align:right")

    return f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',
Roboto,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#161b22;
background:#ffffff;line-height:1.6">

  <p style="font-family:monospace;font-size:11px;letter-spacing:.16em;
     text-transform:uppercase;color:#9a5b00;margin:0 0 6px">Bulletin quotidien</p>
  <h1 style="font-size:22px;margin:0 0 4px;font-weight:700">BVC Analyzer</h1>
  <p style="margin:0 0 22px;color:#414b58">Séance du {_date_longue(a['seance'])}</p>

  <div style="background:#f6f7f9;border-radius:8px;padding:16px 18px;
       margin-bottom:22px">
    <div style="font-size:12px;color:#6d7887;letter-spacing:.08em;
         text-transform:uppercase">MASI</div>
    <div style="font-size:26px;font-weight:700;font-family:monospace;
         margin:2px 0">{_nb(m.get('value'), 2)}
      <span style="font-size:17px;color:{coul}">{_pct(m.get('change_pct'))}</span>
    </div>
    <div style="font-size:13px;color:#414b58">{largeur_ligne(a)}</div>
  </div>

  <h2 style="font-size:15px;margin:0 0 8px">Plus fortes hausses</h2>
  <table style="width:100%;border-collapse:collapse;font-size:14px;
         margin-bottom:22px">
    <tr><th {th}>Valeur</th><th {th}></th><th {thr}>Cours</th>
        <th {thr}>Var.</th></tr>
    {lignes(a['hausses'])}
  </table>

  <h2 style="font-size:15px;margin:0 0 8px">Plus fortes baisses</h2>
  <table style="width:100%;border-collapse:collapse;font-size:14px;
         margin-bottom:22px">
    <tr><th {th}>Valeur</th><th {th}></th><th {thr}>Cours</th>
        <th {thr}>Var.</th></tr>
    {lignes(a['baisses'])}
  </table>

  {_briefing_html(a)}

  <h2 style="font-size:15px;margin:0 0 4px">
    Signaux d'achat ({len(a['achats'])})</h2>
  <p style="font-size:12.5px;color:#6d7887;margin:0 0 8px">
    Retenus seulement à partir d'une confiance de 3 sur 5.</p>
  <table style="width:100%;border-collapse:collapse;font-size:14px;
         margin-bottom:22px">
    <tr><th {th}>Valeur</th><th {th}></th><th {thr}>Note</th>
        <th {thr}>Confiance</th></tr>
    {achats}
  </table>

  <div style="background:#f6f7f9;border-left:3px solid #9a5b00;
       border-radius:0 6px 6px 0;padding:14px 16px;margin-bottom:22px">
    <p style="margin:0 0 6px;font-weight:600;font-size:13.5px">
      Ce que ce bulletin ne sait pas</p>
    <ul style="margin:0;padding-left:18px;font-size:13.5px;color:#414b58">
      <li>{a['non_cotes']} valeur(s) n'ont pas coté : leur prix est celui de la
          dernière séance où elles l'ont fait.</li>
      {ins}
    </ul>
  </div>

  <p style="margin:0 0 22px">
    <a href="{TERMINAL}" style="background:#161b22;color:#ffffff;
       text-decoration:none;padding:11px 20px;border-radius:6px;
       display:inline-block;font-size:14px">Ouvrir le terminal</a>
  </p>

  <p style="font-size:11.5px;color:#6d7887;border-top:1px solid #d5dae1;
     padding-top:14px;margin:0;line-height:1.7">{AVERTISSEMENT}</p>
</div>"""


def main():
    try:
        data, titres = charger(sys.argv[1] if len(sys.argv) > 1 else None)
    except Exception as e:
        print(f"data.json illisible : {e}", file=sys.stderr)
        return 1

    a = analyser(data, titres)

    # ⚠️ Refus d'envoi plutôt qu'un bulletin creux. Un courriel qui arrive tous
    # les matins finit par être lu sans vérification : il ne doit jamais porter
    # une séance que la collecte n'a pas réellement établie.
    if a["n_seance"] < MIN_TITRES_SEANCE:
        print(f"Collecte insuffisante : {a['n_seance']} titres à la séance "
              f"{a['seance']} (minimum {MIN_TITRES_SEANCE}) — bulletin NON envoyé.",
              file=sys.stderr)
        return 2

    sujet = (f"BVC — séance du {_date_longue(a['seance'])} · "
             f"MASI {_nb(a['masi'].get('value'), 2)} "
             f"({_pct(a['masi'].get('change_pct'))})")

    sortie = Path("bulletin_out")
    sortie.mkdir(exist_ok=True)
    (sortie / "sujet.txt").write_text(sujet, encoding="utf-8")
    (sortie / "corps.txt").write_text(texte(a), encoding="utf-8")
    (sortie / "corps.html").write_text(html(a), encoding="utf-8")
    print(sujet)
    return 0


if __name__ == "__main__":
    sys.exit(main())

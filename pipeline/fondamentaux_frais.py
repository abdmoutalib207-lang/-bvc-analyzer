#!/usr/bin/env python3
"""La société a-t-elle publié des comptes plus récents que les nôtres ?

⚠️ LA QUESTION QUE PERSONNE N'AVAIT POSÉE
─────────────────────────────────────────
Le terminal affiche « fondamentaux · 18/06/2026 (99 j) » et s'arrête là. Un
âge, sans point de comparaison. Quatre-vingt-dix-neuf jours, est-ce grave ?
On ne peut pas le dire — **tant qu'on ignore si la société a publié entre-temps**.

Relevé le 25/09/2026 : **dix-huit sociétés cotées ont déposé leurs comptes du
premier semestre 2026 entre le 7 et le 24 septembre.** Nos chiffres pour ces
mêmes titres datent tous de juin. Et ces dépôts étaient **déjà dans notre
collecte d'actualités depuis des jours**.

La source existait, nous étions à sa porte, personne n'était entré.

⚠️ CE MODULE NE LIT PAS LES CHIFFRES, ET C'EST DÉLIBÉRÉ
Il dit QUE des comptes plus récents existent, QUAND ils ont été déposés et OÙ
les lire. Il ne dit pas ce qu'ils contiennent.

Extraire un bénéfice par action de cent rapports aux mises en page
hétérogènes est un travail distinct, et le faire mal produirait des chiffres
faux là où il n'y en avait aucun — le pire des deux mondes, parce qu'un
lecteur retient le nombre et oublie l'avertissement.

⚠️ CE QU'IL CHANGE QUAND MÊME, ET CE N'EST PAS RIEN
« 99 jours » devient « 99 jours, et la société a publié ses comptes
semestriels il y a deux jours ». Le premier est une information sur nous ; le
second est une information sur ce qu'il faut faire. Avec le lien vers le
dépôt, la mise à jour manuelle cesse d'être une chasse.

⚠️ ON NE RÉINVENTE PAS LA CLASSIFICATION
Un dépôt est retenu sur les deux champs du collecteur : `source_tier == "S1"`
(source officielle — AMMC, société, Bourse) et `event_type == "resultats"`.
Reconstruire ce jugement ici par expressions régulières créerait une seconde
définition de « la société a publié », et deux définitions finissent toujours
par diverger.
"""

from __future__ import annotations

from datetime import date

# ⚠️ Un dépôt antérieur à nos chiffres n'apprend rien : c'est celui dont ils
# sont probablement tirés. Seul un dépôt POSTÉRIEUR signale un retard.
# La marge de un jour absorbe les décalages d'horodatage entre la date de
# dépôt et celle de la saisie.
MARGE_JOURS = 1


def _jour(v) -> date | None:
    """Une date, ou None. Accepte « 2026-09-24 » comme « 2026-09-24T12:03:08Z »."""
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def depots_officiels(articles: list) -> dict:
    """{ticker: {date, titre, url}} — le dépôt de comptes le plus RÉCENT.

    ⚠️ Un émetteur non rattaché à un ticker est ignoré, pas deviné. Relevé du
    25/09 : « Saham Leasing - CP relatif aux résultats du 1er semestre 2026 »
    porte `tickers: []`. Lui attribuer un ticker par ressemblance de nom
    rejouerait le piège d'`IDB_TICKER_MAP`, où le `SNA` du bulletin est
    Stokvis et non Sonasid.
    """
    out: dict[str, dict] = {}
    for x in articles or []:
        if not isinstance(x, dict):
            continue
        # ⚠️ Le jugement du collecteur, pas le nôtre.
        if x.get("source_tier") != "S1" or x.get("event_type") != "resultats":
            continue
        j = _jour(x.get("date"))
        if not j:
            continue
        for t in (x.get("tickers") or []):
            garde = out.get(t)
            if garde and _jour(garde["date"]) >= j:
                continue
            out[t] = {"date": j.isoformat(), "titre": x.get("title"),
                      "url": x.get("url"),
                      "source": x.get("publisher") or x.get("source")}
    return out


def retard(fond_asof, depot: dict | None) -> dict | None:
    """Ce que le dépôt dit de nos chiffres, ou None s'il ne dit rien.

    ⚠️ `fond_asof` absent est un cas RÉEL et distinct : quatre titres — T2S,
    MDP, DLM, DIS — sont absents de `fondamentaux.json` et retombent sur la
    table figée, qui ne porte aucune date. Pour eux, tout dépôt est un retard,
    et son ampleur est inconnue plutôt que nulle.
    """
    if not depot:
        return None
    d = _jour(depot.get("date"))
    if not d:
        return None
    a = _jour(fond_asof)
    if a is None:
        return {**depot, "retard_jours": None,
                "_lecture": ("la société a publié des comptes, et nos chiffres "
                             "ne portent aucune date — impossible de dire "
                             "s'ils en tiennent compte")}
    ecart = (d - a).days
    if ecart <= MARGE_JOURS:
        return None
    return {**depot, "retard_jours": ecart,
            "_lecture": (f"comptes déposés le {d.isoformat()}, "
                         f"nos chiffres datent du {a.isoformat()} — "
                         f"{ecart} jours d'écart")}


def par_ticker(tickers: list, articles: list) -> dict:
    """{ticker: retard} pour les seuls titres en retard. Fonction pure."""
    depots = depots_officiels(articles)
    out = {}
    for x in tickers or []:
        sym = (x or {}).get("symbol")
        if not sym:
            continue
        r = retard(((x.get("_meta") or {}).get("fond_asof")), depots.get(sym))
        if r:
            out[sym] = r
    return out


def resume(retards: dict, tickers: list) -> dict:
    """De quoi écrire une ligne honnête dans le flux."""
    n = len(retards)
    dates = sorted(r["date"] for r in retards.values())
    return {
        "titres_en_retard": n,
        "sur": len(tickers or []),
        "depot_le_plus_ancien": dates[0] if dates else None,
        "depot_le_plus_recent": dates[-1] if dates else None,
        "_lecture": (
            f"{n} société(s) ont déposé des comptes postérieurs à nos "
            f"fondamentaux. Le dépôt dit QUE des chiffres plus récents "
            f"existent et OÙ les lire ; il ne dit pas ce qu'ils contiennent."
            if n else
            "aucune société n'a déposé de comptes postérieurs à nos chiffres"),
    }

#!/usr/bin/env python3
"""Confronte notre historique d'un titre à l'export de l'opérateur.

⚠️ L'IDENTITÉ D'ABORD, LE RAPPROCHEMENT ENSUITE
───────────────────────────────────────────────
Rien n'est comparé tant que l'identité de l'instrument n'est pas établie sur
la ligne du cours. C'est l'ordre qui manquait en juin 2026 : on rapprochait des
séries en supposant qu'elles désignaient la même société, et l'une d'elles
portait les cours d'une autre.

CE QUE CE PROGRAMME ÉTABLIT
───────────────────────────
  · l'identité portée par l'export, constante ou non
  · la période, les colonnes, leurs unités
  · les séances communes, celles qui manquent de chaque côté
  · les écarts de clôture, datés et chiffrés
  · ce que suit notre champ « v » : le MONTANT EN DIRHAMS ou le NOMBRE DE
    TITRES — les deux restent DISTINCTS, aucune conversion n'est appliquée

CE QU'IL N'ÉTABLIT PAS
──────────────────────
⚠️ Il ne dit pas qui a raison. L'export est la publication de l'opérateur ;
c'est la source la plus proche du marché dont nous disposions, ce n'est pas une
preuve d'exactitude. Un écart est un ÉCART, pas une erreur de notre côté tant
que sa cause n'est pas établie.

⚠️ Les corrections proposées vont dans une COUCHE CANDIDATE, jamais dans les
chandelles publiées. Chaque proposition porte son motif et son niveau de
preuve — « établi par la mesure » ou « hypothèse à confirmer ».

    python pipeline/confronter_historique.py MSA MUT --ecrire
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SOURCES = RACINE / "sources"
CANDIDAT = RACINE / "datasets" / "historiques_candidats"

COLS = {
    "ouverture": ("Ouverture", "cours en dirhams"),
    "cloture": ("Dernier Cours", "cours en dirhams"),
    "plus_haut": ("Plus Haut", "cours en dirhams"),
    "plus_bas": ("Plus Bas", "cours en dirhams"),
    "volume_mad": ("Volume (MAD)", "MONTANT échangé, en dirhams"),
    "titres_echanges": ("Titres Échangés", "NOMBRE de titres"),
    "nb_transactions": ("Nb Transactions", "nombre de transactions"),
    "capitalisation": ("Capitalisation", "capitalisation en dirhams"),
}
ABSENCES = {"", "-", "--", "n/a", "N/A", "ND"}


def _nb(brut: str):
    s = (brut or "").strip().replace(" ", "").replace(" ", "")
    if s in ABSENCES:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def lire_export(chemin: Path) -> dict:
    lignes = {}
    with chemin.open(encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        colonnes = lecteur.fieldnames or []
        for r in lecteur:
            brut = (r.get("Séance") or "").strip()
            try:
                j, m, a = brut.split("/")
            except ValueError:
                continue
            lignes[f"{a}-{m}-{j}"] = {k: _nb(r.get(c)) for k, (c, _) in COLS.items()}
    return {"colonnes": colonnes, "seances": lignes}


def ajuster_splits(ticker: str, seances: dict) -> dict:
    """Ramène l'export à NOTRE échelle quand une opération sur titres a eu lieu.

    ⚠️ SANS CELA, MANAGEM SEMBLERAIT CONTAMINÉ. Nos chandelles sont ajustées
    du split 10:1 du 27/07/2026 ; l'export de l'opérateur ne l'est pas. Les
    comparer brutes donnerait un facteur 10 sur trois ans d'historique, qu'un
    lecteur pressé lirait comme « nos cours sont faux ».

    L'ajustement est déclaré dans le rapport : il ne se devine pas.
    """
    from bvc_config import SPLITS
    splits = SPLITS.get(ticker) or []
    if not splits:
        return {"seances": seances, "splits_appliques": []}

    def ratio_mesure(date_effet: str):
        """Le ratio déduit de la CAPITALISATION de l'opérateur, pas de notre table.

        ⚠️ Confronter notre registre à lui-même ne prouverait rien. Le nombre de
        titres se déduit de `capitalisation / cours` : s'il est multiplié par N
        à la date d'effet, le ratio est N. C'est la méthode qui avait tranché
        l'identité de MRL — une arithmétique qui se recoupe, non deux sources
        qui se citent.
        """
        # ⚠️ LES DEUX SÉANCES QUI ENCADRENT, PAS UNE MOYENNE DE TRENTE.
        # Ma première version moyennait trente séances de part et d'autre.
        # Sur Sothema, le nombre de titres avait déjà bougé dans la fenêtre
        # antérieure : la moyenne donnait 7 660 061 et un ratio de 5,0012,
        # alors que les deux lignes qui encadrent la date d'effet donnent
        # 7 661 900 puis 38 309 500 — exactement ×5. Une moyenne lisse ce
        # qu'on cherche précisément à lire : une MARCHE.
        ds = sorted(seances)
        if date_effet not in ds:
            return None
        i = ds.index(date_effet)

        def titres(d):
            v = seances.get(d) or {}
            if not (v.get("capitalisation") and v.get("cloture")):
                return None
            return v["capitalisation"] / v["cloture"]

        def derniere_valeur(indices):
            for j in indices:
                t = titres(ds[j])
                if t is not None:
                    return ds[j], t
            return None, None

        d_av, av = derniere_valeur(range(i - 1, max(-1, i - 11), -1))
        d_ap, ap = derniere_valeur(range(i, min(len(ds), i + 10)))
        if not av or not ap:
            return None
        return {"seance_avant": d_av, "titres_avant": round(av),
                "seance_apres": d_ap, "titres_apres": round(ap),
                "ratio_mesure": round(ap / av, 4),
                "_methode": "les deux séances qui ENCADRENT la date d'effet — "
                            "jamais une moyenne, qui lisserait la marche"}
    out, appliques = {}, []
    for d, v in seances.items():
        w = dict(v)
        for sp in splits:
            if d < sp["date"]:
                for champ in ("ouverture", "cloture", "plus_haut", "plus_bas"):
                    if w.get(champ) is not None:
                        w[champ] = round(w[champ] / sp["ratio"], 2)
                # ⚠️ LES QUANTITÉS NE SONT PAS TOUCHÉES, ET C'EST DÉCLARÉ.
                # Un split multiplie le nombre de titres : 715 titres échangés
                # avant un 10:1 en valent 7 150 sur la base postérieure. Nous
                # ne convertissons pas — nous exposons les DEUX bases, nommées.
                # Diviser les prix en laissant les quantités muettes laisserait
                # croire que tout est sur la même base.
                if w.get("titres_echanges") is not None:
                    w["titres_echanges_base_posterieure"] = round(
                        w["titres_echanges"] * sp["ratio"])
                w["_base_des_quantites"] = "ANTÉRIEURE au split — non convertie"
                w["_base_des_prix"] = f"postérieure au split (÷ {sp['ratio']})"
                appliques.append(sp["date"])
        out[d] = w
    return {"seances": out,
            "splits_appliques": [{"date": sp["date"], "ratio_declare": sp["ratio"],
                                  "verification": ratio_mesure(sp["date"]),
                                  "seances_ajustees": sum(1 for d in seances if d < sp["date"])}
                                 for sp in splits]}


def nos_chandelles(ticker: str, ref: str = "origin/main") -> dict:
    try:
        s = subprocess.check_output(
            ["git", "show", f"{ref}:pipeline/candles/{ticker}.json"],
            text=True, cwd=RACINE, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return {}
    return {b["d"]: b for b in json.loads(s)}


def _unite_du_champ_v(comm, nous, exp) -> dict:
    """Notre « v » suit-il le montant en dirhams, ou le nombre de titres ?

    ⚠️ La réponse N'EST PAS la même d'un titre à l'autre. Mesurée sur ADH et
    CSR, elle donnait le montant en dirhams ; sur MSA, elle donne les titres.
    Aucune conversion n'est donc appliquée nulle part, et les deux colonnes de
    l'export restent séparées.
    """
    mad = titres = base = 0
    for d in comm:
        v = nous[d].get("v")
        e = exp[d]
        if v is None or e["volume_mad"] is None or e["titres_echanges"] is None:
            continue
        base += 1
        if abs(v - e["volume_mad"]) <= max(1.0, 0.01 * e["volume_mad"]):
            mad += 1
        if abs(v - e["titres_echanges"]) <= max(1.0, 0.01 * e["titres_echanges"]):
            titres += 1
    if not base:
        return {"comparables": 0, "_lecture": "aucune séance comparable"}
    return {
        "comparables": base,
        "suit_le_montant_mad": mad, "part_mad": round(100 * mad / base, 1),
        "suit_le_nombre_de_titres": titres, "part_titres": round(100 * titres / base, 1),
        "_lecture": "⚠️ mesure propre à CE titre. Elle ne s'étend à aucun autre : "
                    "la convention du champ varie d'un titre à l'autre et, sur "
                    "un même titre, selon les périodes.",
    }


def confronter(ticker: str, ref: str = "origin/main") -> dict:
    # ── 1. L'IDENTITÉ, AVANT TOUT RAPPROCHEMENT ────────────────────────────
    from identite_source import identite_de_l_export
    from identites import autoriser_ecriture

    fichiers = sorted((SOURCES / ticker).glob("*.csv"))
    if not fichiers:
        return {"ticker": ticker, "erreur": f"aucun export dans sources/{ticker}/"}
    chemin = fichiers[-1]
    lu = identite_de_l_export(chemin)
    if not lu["identite_portee"]:
        return {"ticker": ticker, "identite": lu,
                "_arret": "identité non portée — AUCUN rapprochement n'est fait"}
    aut = autoriser_ecriture(ticker, lu["instrument"])
    if not aut["autorise"]:
        return {"ticker": ticker, "identite": lu, "autorisation": aut,
                "_arret": "l'identité portée ne concorde pas avec notre "
                          "référentiel — AUCUN rapprochement n'est fait"}

    # ── 2. Les deux séries ─────────────────────────────────────────────────
    brut = lire_export(chemin)["seances"]
    aju = ajuster_splits(ticker, brut)
    exp, splits = aju["seances"], aju["splits_appliques"]
    nous = nos_chandelles(ticker, ref)
    comm = sorted(set(exp) & set(nous))
    debut_nous = min(nous) if nous else None

    manquantes_dans_notre_plage = sorted(
        d for d in exp if debut_nous and d >= debut_nous and d not in nous)
    anterieures = sorted(d for d in exp if debut_nous and d < debut_nous)
    # ⚠️ « CHEZ NOUS SEULEMENT » N'EST PAS « FANTÔME ».
    # Une séance que l'export ne couvre pas — parce qu'il commence plus tard —
    # est notre PROFONDEUR, pas une invention. Les mêler sous un seul nombre
    # a produit une colonne « fantôme » annonçant 68 séances pour HPS et MNG
    # là où il y en a une. La qualification était trompeuse même si le
    # générateur, lui, ne proposait plus de les supprimer.
    d1_exp, d2_exp = (min(exp), max(exp)) if exp else (None, None)
    chez_nous_seulement = sorted(set(nous) - set(exp))
    notre_profondeur = [d for d in chez_nous_seulement
                        if d1_exp and (d < d1_exp or d > d2_exp)]
    fantomes = [d for d in chez_nous_seulement
                if d1_exp and d1_exp <= d <= d2_exp]

    # ── 3. Les écarts de clôture ───────────────────────────────────────────
    ecarts = []
    for d in comm:
        a, b = nous[d].get("c"), exp[d]["cloture"]
        if a is None or b is None:
            continue
        if abs(a - b) > 0.005:
            ecarts.append({"seance": d, "notre_cloture": a, "operateur": b,
                           "ecart_pct": round((a - b) / b * 100, 2) if b else None})
    par_mois = {}
    for e in ecarts:
        par_mois[e["seance"][:7]] = par_mois.get(e["seance"][:7], 0) + 1

    # ⚠️ UNE ÉCHELLE SYSTÉMATIQUE N'EST PAS UNE SÉRIE D'ÉCARTS.
    # Si le rapport nous/opérateur est CONSTANT sur une longue période, ce
    # n'est pas du bruit : c'est un facteur appliqué de trop, ou pas appliqué.
    # Le compter comme « 486 écarts » masquerait un défaut unique.
    # ⚠️ PAR SEGMENT. Une opération sur titres coupe l'historique en deux
    # régimes ; mesurer le rapport sur l'ensemble les mélange et n'y voit que
    # du bruit. Les bornes sont les dates d'effet des splits.
    bornes = [sp["date"] for sp in splits]
    segments, deb = [], None
    for fin in bornes + [None]:
        seg = [d for d in comm
               if (deb is None or d >= deb) and (fin is None or d < fin)]
        segments.append((deb or "début", fin or "fin", seg))
        deb = fin
    echelle = []
    for d1, d2, seg in segments:
        rap = [nous[d]["c"] / exp[d]["cloture"] for d in seg
               if nous[d].get("c") and exp[d].get("cloture")]
        if len(rap) < 30:
            continue
        med = statistics.median(rap)
        disp = (max(rap) - min(rap)) / med if med else None
        if med and abs(med - 1) > 0.02 and disp is not None and disp < 0.05:
            echelle.append({
                "de": d1, "a": d2, "seances": len(rap),
                "rapport_median": round(med, 4), "facteur": round(1 / med, 2),
                "dispersion_relative": round(disp, 4),
                "_lecture": "rapport CONSTANT sur ce segment : défaut d'ÉCHELLE "
                            "unique, et non une série d'écarts indépendants. "
                            "Le compter comme N écarts masquerait un seul "
                            "défaut derrière un grand nombre.",
            })
    echelle = echelle or None

    comparables = [d for d in comm
                   if nous[d].get("c") is not None and exp[d]["cloture"] is not None]
    pct = [abs(e["ecart_pct"]) for e in ecarts if e["ecart_pct"] is not None]

    return {
        "_quoi": f"confrontation de notre historique {ticker} à l'export de l'opérateur",
        "ticker": ticker,
        "piece": {
            "fichier": chemin.name,
            "sha256": hashlib.sha256(chemin.read_bytes()).hexdigest(),
            "octets": chemin.stat().st_size,
        },
        "identite": {
            "instrument_porte": lu["instrument"],
            "ticker_porte": lu["ticker_fournisseur"],
            "constante_sur": lu["lignes_de_cours"],
            "autorisation": aut["preuve"],
            "_lecture": "établie AVANT tout rapprochement, sur la ligne du cours",
        },
        "colonnes_et_unites": {k: {"colonne": c, "unite": u} for k, (c, u) in COLS.items()},
        "splits": {
            "appliques_a_l_export": splits,
            "_lecture": "⚠️ Nos chandelles sont ajustées des opérations sur "
                        "titres ; l'export de l'opérateur ne l'est pas. "
                        "L'ajustement est appliqué À L'EXPORT avant la "
                        "comparaison, et déclaré ici. Sans lui, un titre "
                        "ayant subi un split paraîtrait contaminé."
                        if splits else
                        "aucune opération déclarée pour ce titre dans SPLITS",
        },
        "periodes": {
            "export": [min(exp), max(exp)] if exp else [None, None],
            "chez_nous": [debut_nous, max(nous)] if nous else [None, None],
            "seances_export": len(exp), "seances_chez_nous": len(nous),
        },
        "couverture": {
            "communes": len(comm),
            "anterieures_a_notre_historique": len(anterieures),
            "manquantes_dans_notre_plage": manquantes_dans_notre_plage,
            "fantomes": fantomes,
            "notre_profondeur_hors_export": {
                "nombre": len(notre_profondeur),
                "periode": [notre_profondeur[0], notre_profondeur[-1]] if notre_profondeur else None,
                "_lecture": "séances que nous portons HORS de la période couverte "
                            "par l'export. Ce n'est PAS un défaut : l'export "
                            "commence plus tard. Ne jamais les compter comme "
                            "fantômes ni proposer leur suppression.",
            },
            "chez_nous_mais_pas_chez_l_operateur": chez_nous_seulement,
        },
        "clotures": {
            "comparables": len(comparables),
            "identiques": len(comparables) - len(ecarts),
            "divergentes": len(ecarts),
            "part_identiques_pct": round(100 * (len(comparables) - len(ecarts))
                                         / len(comparables), 1) if comparables else None,
            "par_mois": dict(sorted(par_mois.items())),
            "ecart_median_pct": round(statistics.median(pct), 2) if pct else None,
            "ecart_max_pct": round(max(pct), 2) if pct else None,
            "superieurs_a_20_pct": sum(1 for p in pct if p > 20),
            "detail": ecarts,
        },
        "echelle_systematique": echelle,
        "champ_v": _unite_du_champ_v(comm, nous, exp),
        "_ce_qui_n_est_pas_etabli":
            "⚠️ Un écart est un ÉCART. L'export est la publication de "
            "l'opérateur, pas une preuve d'exactitude. Aucune correction n'est "
            "appliquée ici : les propositions vont dans une couche candidate.",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()

    for t in a.tickers:
        r = confronter(t, a.ref)
        if a.ecrire:
            CANDIDAT.mkdir(parents=True, exist_ok=True)
            (CANDIDAT / f"confrontation_{t}.json").write_text(
                json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"→ datasets/historiques_candidats/confrontation_{t}.json")
        court = {k: v for k, v in r.items() if k != "clotures"}
        if "clotures" in r:
            court["clotures"] = {k: v for k, v in r["clotures"].items() if k != "detail"}
        print(json.dumps(court, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

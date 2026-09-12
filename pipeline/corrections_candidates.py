#!/usr/bin/env python3
"""Propose des corrections d'historique — dans une COUCHE CANDIDATE, jamais
dans les chandelles publiées.

⚠️ RIEN N'EST APPLIQUÉ ICI. Ce programme écrit des propositions datées, chacune
avec son motif et son NIVEAU DE PREUVE. La décision d'appliquer appartient au
propriétaire, et passera par une livraison distincte.

TROIS NIVEAUX DE PREUVE, ET ILS NE SE VALENT PAS
────────────────────────────────────────────────
  etabli_par_la_mesure   deux séries identifiées se recoupent, le verdict ne
                         dépend d'aucune hypothèse
  etabli_par_l_absence   l'opérateur ne cote pas cette séance ; nous si
  hypothese_a_confirmer  l'écart est constaté, sa cause est supposée
"""
from __future__ import annotations
import argparse, csv, json, subprocess, sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
# `bvc_config` vit à la racine ; sans cela l'ajustement des splits lève.
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))
SORTIE = RACINE / "datasets" / "historiques_candidats"
CONTAMINATION = {"MSA": ("2026-05-13", "2026-06-16", "MUT")}

def _exp(t):
    """L'export, RAMENÉ À NOTRE ÉCHELLE quand une opération sur titres a eu lieu.

    ⚠️ Ma première version lisait l'export brut. Sur Managem, dont nos
    chandelles sont ajustées du split 10:1, cela produisait 704 « écarts » là
    où il y en a 23. Un générateur de corrections qui compare deux échelles
    différentes ne propose pas des corrections : il en fabrique.
    """
    from confronter_historique import lire_export, ajuster_splits
    brut = lire_export(sorted((RACINE/"sources"/t).glob("*.csv"))[-1])["seances"]
    return ajuster_splits(t, brut)["seances"]

def _nos(t, ref="origin/main"):
    s = subprocess.check_output(["git","show",f"{ref}:pipeline/candles/{t}.json"],
                                text=True, cwd=RACINE)
    return {b["d"]: b for b in json.loads(s)}

def _bougie(d, e):
    """Une bougie depuis l'export. ⚠️ `v` porte les TITRES ÉCHANGÉS, jamais le
    montant en dirhams : les deux grandeurs restent distinctes, et le montant
    est conservé à côté sous son propre nom."""
    c = e["cloture"]
    if c is None: return None
    return {"d": d, "o": e["ouverture"] if e["ouverture"] is not None else c,
            "h": e["plus_haut"] if e["plus_haut"] is not None else c,
            "l": e["plus_bas"] if e["plus_bas"] is not None else c, "c": c,
            "v": int(e["titres_echanges"] or 0),
            "_volume_mad": e["volume_mad"]}

def proposer(t, ref="origin/main"):
    exp, nous = _exp(t), _nos(t, ref)
    props = []

    # ── 1. Contamination d'identité ────────────────────────────────────────
    if t in CONTAMINATION:
        d1, d2, autre = CONTAMINATION[t]
        autre_exp = _exp(autre)
        fen = [d for d in sorted(exp) if d1 <= d <= d2]
        conc_autre = sum(1 for d in fen if d in nous and autre_exp.get(d, {}).get("cloture")
                         is not None and abs(nous[d]["c"] - autre_exp[d]["cloture"]) < 0.005)
        conc_soi = sum(1 for d in fen if d in nous and exp[d]["cloture"] is not None
                       and abs(nous[d]["c"] - exp[d]["cloture"]) < 0.005)
        props.append({
            "type": "remplacer", "seances": fen, "nombre": len(fen),
            "preuve": "etabli_par_la_mesure",
            "motif": f"nos cours de {t} sur cette fenêtre sont ceux de {autre} : "
                     f"{conc_autre}/{len(fen)} clôtures identiques à {autre}, "
                     f"{conc_soi}/{len(fen)} identiques à {t}. Les deux exports "
                     f"portent leur instrument SUR LA LIGNE DU COURS.",
            "cause_connue": "MANUAL_MAP identifiait les sociétés par NOM ; "
                            "l'entrée de ce titre a été corrigée le 23/06/2026 "
                            "(commit 48b3c583) sans que la donnée abîmée le soit",
            "remplacement": [b for b in (_bougie(d, exp[d]) for d in fen) if b],
        })

    # ── 2. Séances cotées et absentes de chez nous ─────────────────────────
    deb = min(nous)
    manq = sorted(d for d in exp if d >= deb and d not in nous)
    if manq:
        props.append({
            "type": "ajouter", "seances": manq, "nombre": len(manq),
            "preuve": "etabli_par_la_mesure",
            "motif": "l'opérateur cote ces séances, notre historique ne les "
                     "porte pas. Panne de collecte du 22 au 24 juin 2026.",
            "ajout": [b for b in (_bougie(d, exp[d]) for d in manq) if b],
        })

    # ── 3. Séances que nous seuls portons ──────────────────────────────────
    # ⚠️ SEULEMENT DANS LA PÉRIODE QUE L'EXPORT COUVRE. Ma première version
    # proposait de retirer 68 séances de HPS et de MNG — dont soixante-sept
    # ANTÉRIEURES au premier jour de l'export. L'export ne les cote pas parce
    # qu'il commence plus tard, pas parce qu'elles n'ont pas eu lieu.
    # Proposer leur suppression aurait détruit de l'historique valide.
    d1, d2 = min(exp), max(exp)
    fantomes = sorted(d for d in set(nous) - set(exp) if d1 <= d <= d2)
    if fantomes:
        props.append({
            "type": "retirer", "seances": fantomes, "nombre": len(fantomes),
            "preuve": "etabli_par_l_absence",
            "motif": "l'opérateur ne cote PAS ces séances alors qu'elles "
                     "tombent DANS la période qu'il couvre, et qu'il cote la "
                     "veille et le lendemain.",
            "_hors_perimetre": f"les séances antérieures à {d1} ne sont pas "
                               f"concernées : l'export commence à cette date. "
                               f"Notre profondeur supplémentaire n'est pas un "
                               f"défaut.",
            "hypothese_sur_la_cause": "le 30/07/2026 est la Fête du Trône. "
                                      "⚠️ Nous ne disposons d'aucun calendrier "
                                      "officiel des fériés : l'attribution est "
                                      "une hypothèse, l'absence de cotation est "
                                      "un fait.",
            "valeurs_actuelles": [nous[d] for d in fantomes],
        })

    # ── 3bis. Défaut d'ÉCHELLE sur un segment entier ───────────────────────
    conf = SORTIE / f"confrontation_{t}.json"
    if conf.exists():
        c = json.loads(conf.read_text(encoding="utf-8"))
        for seg in (c.get("echelle_systematique") or []):
            props.append({
                "type": "remettre_a_l_echelle", "seances": [seg["de"], seg["a"]],
                "nombre": seg["seances"], "preuve": "etabli_par_la_mesure",
                "motif": f"sur {seg['seances']} séances, nos cours valent "
                         f"{seg['rapport_median']} fois ceux de l'opérateur, avec "
                         f"une dispersion de {seg['dispersion_relative']*100:.1f} %. "
                         f"Un rapport CONSTANT n'est pas du bruit : c'est un "
                         f"facteur {seg['facteur']} appliqué de trop.",
                "facteur_a_corriger": seg["facteur"],
                "_comment_le_ratio_est_verifie":
                    "le ratio du split est déduit de la CAPITALISATION de "
                    "l'opérateur (capitalisation ÷ cours = nombre de titres), "
                    "jamais de notre propre registre.",
                "_conséquence": "AUCUN remplacement automatique n'est écrit ici : "
                                "remettre à l'échelle 486 séances est une "
                                "opération à décider, pas à subir.",
            })
        for sp in (c.get("splits", {}).get("appliques_a_l_export") or []):
            v = sp.get("verification") or {}
            if v and abs(v.get("ratio_mesure", 0) - sp["ratio_declare"]) > 0.01:
                props.append({
                    "type": "signaler", "seances": [sp["date"]], "nombre": 1,
                    "preuve": "etabli_par_la_mesure",
                    "motif": f"le registre déclare 1:{sp['ratio_declare']} ; la "
                             f"capitalisation de l'opérateur donne "
                             f"{v['ratio_mesure']}.",
                })

    # ── 4. Écarts dont la cause n'est pas établie ──────────────────────────
    # ⚠️ Les séances déjà couvertes par un défaut d'ÉCHELLE en sont exclues.
    # Sans cela, SOT annonçait 519 « écarts » là où il y a UN défaut sur un
    # segment et 33 écarts indépendants. Présenter un défaut unique comme 486
    # écarts trompe sur sa nature autant que sur son nombre.
    couvert = []
    for p_ in props:
        if p_["type"] == "remettre_a_l_echelle":
            couvert.append((p_["seances"][0], p_["seances"][1]))
    def _dans_un_segment(d):
        return any((a == "début" or d >= a) and (b == "fin" or d < b) for a, b in couvert)

    petits = []
    for d in sorted(set(exp) & set(nous)):
        if _dans_un_segment(d):
            continue
        a, b = nous[d].get("c"), exp[d]["cloture"]
        if a is None or b is None or abs(a - b) <= 0.005: continue
        if t in CONTAMINATION and CONTAMINATION[t][0] <= d <= CONTAMINATION[t][1]:
            continue
        petits.append({"seance": d, "notre_cloture": a, "operateur": b,
                       "ecart_pct": round((a - b) / b * 100, 2)})
    if petits:
        props.append({
            "type": "signaler", "seances": [p["seance"] for p in petits],
            "nombre": len(petits), "preuve": "hypothese_a_confirmer",
            "motif": "écarts constatés, faibles et non systématiques — ni le "
                     "jour, ni la veille, ni le lendemain de l'opérateur ne les "
                     "expliquent : la piste du décalage de date est ÉCARTÉE.",
            "hypothese_sur_la_cause":
                "⚠️ HYPOTHÈSE, NON VÉRIFIÉE. Jusqu'au 10/08/2026, la bougie du "
                "jour se figeait sur le premier run, gravant un cours de "
                "MILIEU DE SÉANCE comme clôture (57 bougies fausses sur 72 "
                "mesurées le 10/08). Ces écarts couvrent une période antérieure "
                "au correctif. Rien ne l'établit ici.",
            "_conséquence": "AUCUN remplacement proposé. Corriger sur une "
                            "hypothèse reviendrait à réécrire l'historique sur "
                            "une conviction.",
            "detail": petits,
        })
    return {"_quoi": f"corrections CANDIDATES pour {t} — aucune n'est appliquée",
            "ticker": t, "propositions": props,
            "_ce_qui_n_est_pas_etabli":
                "⚠️ L'export est la publication de l'opérateur, pas une preuve "
                "d'exactitude. Les propositions de niveau « hypothèse » ne "
                "doivent pas être appliquées en l'état."}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="+"); ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()
    for t in a.tickers:
        r = proposer(t, a.ref)
        if a.ecrire:
            SORTIE.mkdir(parents=True, exist_ok=True)
            (SORTIE / f"corrections_{t}.json").write_text(
                json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"→ datasets/historiques_candidats/corrections_{t}.json")
        for p in r["propositions"]:
            print(f"   [{p['preuve']:22s}] {p['type']:10s} {p['nombre']:>3d} séance(s) "
                  f"· {p['seances'][0]} → {p['seances'][-1]}")

if __name__ == "__main__":
    main()

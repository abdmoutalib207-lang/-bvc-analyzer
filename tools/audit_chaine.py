#!/usr/bin/env python3
"""Audit de la chaîne complète, titre par titre : de la pièce à l'affichage.

Demandé par un relecteur externe (16/10/2026) : vérifier AUTOMATIQUEMENT que la
note, les alertes et la fiche lisent les MÊMES valeurs. Quatre maillons :

  1. PIÈCE        faits_financiers.json / fondamentaux.json (ratios_publies) :
                  chaque ratio lu par la note porte valeur, date, formule/source.
  2. FORMULE      `detail_fond_score` est RECALCULÉ pour chaque titre, avec les
                  mêmes entrées que le moteur (PER = cours ÷ BPA 12 mois,
                  croissance sourcée, grandeurs contestées), puis comparé à
                  `note_fond` publié, composante par composante.
  3. PUBLICATION  `_meta.non_comparable` ↔ sa condition, `_meta.confidence` ↔
                  `_meta.garanties`, alertes recalculées par la même porte
                  (`ratio_effectif`) et recoupées avec les composantes
                  (signal et `v53` retirés avec le producteur v5.3, lot 2 du
                  06/11/2026) ; depuis le 06/11/2026, le SCORE BVC publié : état ↔ valeur, bornes, recomposition
                  depuis ses facteurs, version, recalcul depuis les chandelles.
  4. AFFICHAGE    ⚠️ STATIQUE seulement (aucun navigateur) : les composants du
                  terminal ne lisent que `note_fond`, `alertes`, `_meta` et les
                  champs de score publiés. Cela prouve que l'écran n'a pas de
                  seconde source ; cela ne prouve PAS qu'il se rend sans erreur
                  — voir `tools/qa_navigateur.js` pour cela.

Pour aller jusqu'au rendu (non fait ici) : étendre `tools/qa_navigateur.js` —
après l'ouverture d'une fiche, lire le texte de `.resume-note` (« Couverture : N % »)
et le nombre de `.alerte-verifiee`, et les comparer à `note_fond.couverture` et
`alertes.liste` de data.json ; lire aussi le texte de « Pourquoi cette note ? ».

Usage :
    python3 tools/audit_chaine.py                      # data.json du dépôt
    python3 tools/audit_chaine.py --data /chemin/data.json --json
    python3 tools/audit_chaine.py --racine DOSSIER     # un répertoire de travail

Code de sortie : 0 = aucune ERREUR ; 1 = au moins une incohérence de gravité
ERREUR. Les AVERTISSEMENTS (pièce incomplète, limite connue) ne font pas
échouer : ils se lisent dans la sortie.

Lecture seule : rien n'est écrit, aucun accès réseau.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

ERREUR, AVERT = "ERREUR", "AVERTISSEMENT"
TOLERANCE_NOTE = 0.005          # arrondi à 2 décimales côté moteur
COMPOSANTES = ("qualite", "croissance", "valorisation", "bilan")


# ── utilitaires ────────────────────────────────────────────────────────────
def _inc(titre, controle, gravite, message, publie=None, attendu=None) -> dict:
    return {"titre": titre, "controle": controle, "gravite": gravite,
            "message": message, "publie": publie, "attendu": attendu}


def _num(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _egal(a, b, tol=TOLERANCE_NOTE) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol


def _premier_nombre(texte: str | None):
    m = re.search(r"-?\d+(?:[.,]\d+)?", texte or "")
    return float(m.group(0).replace(",", ".")) if m else None


def _per(price, bpa):
    """Même définition que `update_data._per` (gardée identique par un test)."""
    return round(price / bpa, 1) if (bpa and bpa > 0 and price and price > 0) else None


def charger(racine: Path, data: Path | None = None) -> dict:
    """Les quatre fichiers que la chaîne lit. Un fichier absent donne {}."""
    def lire(p):
        try:
            return json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    fo = lire(racine / "fondamentaux.json")
    return {
        "data": lire(data or racine / "data.json"),
        "fondamentaux": {k: v for k, v in fo.items() if isinstance(v, dict)},
        "faits": lire(racine / "pipeline" / "faits_financiers.json"),
        "bpa": lire(racine / "bpa.json"),
    }


def contestations(fondamentaux: dict, faits: dict) -> dict:
    """{sym: motif} — la règle du moteur (`_dette_nette_contestee`), SANS toucher
    au registre global `CONTESTES` (qui appartient au moteur)."""
    from pipeline.smart_money.fond_score_sectoriel import _dette_nette_contestee
    sortie = {}
    for sym, f in fondamentaux.items():
        dn = (f.get("ratios_publies") or {}).get("dette_nette")
        motif = _dette_nette_contestee(dn if isinstance(dn, dict) else None, (faits or {}).get(sym) or {})
        if motif:
            sortie[sym] = motif
    return sortie


# ── maillon 1 : la pièce ───────────────────────────────────────────────────
_RATIOS_DE_LA_NOTE = ("roic", "dette_nette_ebitda", "dette_nette", "cash_conversion", "roe_12m", "roe_2025")


def controles_piece(sym, f, faits_sym, note_fond) -> list:
    out = []
    rp = (f or {}).get("ratios_publies") or {}
    mesures = " ".join(str((c or {}).get("mesure") or "") for c in (note_fond or {}).get("composantes", {}).values())
    for cle in _RATIOS_DE_LA_NOTE:
        x = rp.get(cle)
        if not isinstance(x, dict) or _num(x.get("valeur")) is None:
            continue
        manque = [k for k, ok in (("date", x.get("date")), ("formule ou sources", x.get("formule") or x.get("sources")))
                  if not ok]
        if manque:
            out.append(_inc(sym, "piece.ratio_sans_trace", AVERT,
                            f"ratio {cle} lu par la note sans {' ni '.join(manque)}", x.get("valeur")))
    if faits_sym:
        if not faits_sym.get("url") and not faits_sym.get("document"):
            out.append(_inc(sym, "piece.fait_sans_document", AVERT, "faits financiers sans document ni url"))
        for nom, fait in (faits_sym.get("faits") or {}).items():
            if not isinstance(fait, dict) or _num(fait.get("valeur")) is None:
                continue
            if fait.get("page") is None:
                out.append(_inc(sym, "piece.fait_sans_page", AVERT, f"fait {nom} sans page", fait.get("valeur")))
    return out


# ── maillon 2 : la formule, recalculée ─────────────────────────────────────
def recalculer_note_fond(sym, ticker, fondamentaux, bpa, contestes) -> dict:
    """Le détail que le moteur DOIT avoir publié, recalculé avec ses entrées :
    PER = cours ÷ BPA 12 mois (sinon BPA de l'exercice), croissance sourcée si
    le BPA 12 mois existe, grandeurs contestées suspendues. Même code, mêmes
    entrées — une divergence est donc une entrée qui a bougé, pas une formule."""
    from pipeline.smart_money import fond_score as F
    b = (bpa or {}).get(sym) or {}
    price = _num(ticker.get("price"))
    bpa12 = b.get("bpa_12m")
    per = _per(price, bpa12) if bpa12 is not None else _per(price, b.get("bpa"))
    sauve = dict(F.CONTESTES)
    try:
        F.CONTESTES.clear()
        F.CONTESTES.update(contestes)
        d = F.detail_fond_score(sym, fondamentaux if sym in fondamentaux else {},
                                per_publie=per, croissance_sourcee=bpa12 is not None)
    finally:
        F.CONTESTES.clear()
        F.CONTESTES.update(sauve)
    p_so = sum(c["poids"] for c in d["composantes"].values()
               if c["note"] is None and "sans objet" in (c.get("motif") or ""))
    d["couverture_applicable"] = round(d["couverture"] / (1 - p_so), 4) if p_so < 1 else None
    d["_per"] = per
    return d


def controler_note_fond(sym, t, attendu, contestes) -> list:
    out = []
    nf = t.get("note_fond")
    if not isinstance(nf, dict):
        return [_inc(sym, "note.absente", ERREUR, "note_fond absent de la fiche publiée")]
    comp = nf.get("composantes") or {}
    if set(comp) != set(COMPOSANTES):
        out.append(_inc(sym, "note.composantes", ERREUR,
                        "les quatre composantes ne sont pas toutes publiées", sorted(comp), list(COMPOSANTES)))
    if not _egal(nf.get("note"), attendu["note"]):
        out.append(_inc(sym, "note.recalcul", ERREUR, "la note publiée diffère de la note recalculée",
                        nf.get("note"), attendu["note"]))
    if not _egal(nf.get("couverture"), attendu["couverture"], 1e-4):
        out.append(_inc(sym, "note.couverture", ERREUR, "couverture publiée ≠ recalculée",
                        nf.get("couverture"), attendu["couverture"]))
    if not _egal(nf.get("couverture_applicable"), attendu["couverture_applicable"], 1e-4):
        out.append(_inc(sym, "note.couverture_applicable", ERREUR, "couverture applicable publiée ≠ recalculée",
                        nf.get("couverture_applicable"), attendu["couverture_applicable"]))
    for nom in COMPOSANTES:
        pub, att = comp.get(nom) or {}, attendu["composantes"][nom]
        for champ in ("note", "poids"):
            if not _egal(pub.get(champ), att.get(champ)):
                out.append(_inc(sym, f"composante.{nom}.{champ}", ERREUR,
                                f"{nom} : {champ} publié ≠ recalculé", pub.get(champ), att.get(champ)))
        for champ in ("mesure", "motif", "reserve"):
            if (pub.get(champ) or None) != (att.get(champ) or None):
                out.append(_inc(sym, f"composante.{nom}.{champ}", ERREUR,
                                f"{nom} : {champ} publié ≠ recalculé", pub.get(champ), att.get(champ)))
    # Cohérence interne : motif ↔ note, note ↔ seuil de couverture.
    if (nf.get("note") is None) != bool(nf.get("motif")):
        out.append(_inc(sym, "note.motif", ERREUR, "motif présent sans note absente, ou l'inverse",
                        nf.get("motif"), None if nf.get("note") is not None else "motif attendu"))
    from pipeline.smart_money.fond_score import COUVERTURE_MIN
    if (nf.get("couverture") or 0) < COUVERTURE_MIN and nf.get("note") is not None:
        out.append(_inc(sym, "note.sous_seuil", ERREUR,
                        f"note publiée alors que la couverture est sous COUVERTURE_MIN ({COUVERTURE_MIN})",
                        nf.get("couverture")))
    # ⚠️ 06/11/2026 : `score_fond` (pilier fondamental de la note v5.3) n'est
    # plus publié — le contrôle « score_fond = note_fond.note » part avec lui.
    # Grandeur contestée : jamais mesurée.
    if sym in contestes:
        for nom in ("qualite", "bilan"):
            c = comp.get(nom) or {}
            if c.get("note") is not None:
                out.append(_inc(sym, "contestee.mesuree", ERREUR,
                                f"grandeur contestée utilisée : {nom} est notée alors que la dette nette est contestée",
                                c.get("mesure"), "composante non notée"))
        for nom, c in comp.items():
            if re.search(r"dette nette|ROIC", str((c or {}).get("mesure") or "")) and (c or {}).get("note") is not None:
                out.append(_inc(sym, "contestee.mesure_citee", ERREUR,
                                f"{nom} cite une grandeur contestée dans sa mesure", c.get("mesure")))
    return out


# ── maillon 3 : non-comparabilité, confiance, alertes ──────────────────────
# ⚠️ 06/11/2026 — retrait de la note v5.3, lot 2 (décision d'Abd Moutalib :
# « l'ancien scoring doit disparaître »). Le moteur ne publie plus `v53`,
# `sig`, `score_fond`, `score_tech`, `poids`, `bonus`, `setup` ni
# `verdict_plafonne` : les contrôles du signal (suspendu, données
# insuffisantes, couverture partielle, signal ↔ confiance) et la
# recomposition de `v53` sont retirés avec eux. Ce que le lecteur voit encore
# — la confiance (`controler_confiance`), le Score BVC (`controler_score_bvc`)
# et le champ `_meta.non_comparable` lu par la vue PER — reste contrôlé.
NON_COMPARABLE = "Non comparable (liquidité)"     # libellé historique, plus publié


def controler_non_comparable(sym, t, contestes=None) -> list:
    """`_meta.non_comparable` présent SI ET SEULEMENT SI la condition publiée le
    veut (règle A, 27/10/2026) : technique neutralisée ET médiane sous le seuil,
    sauf titre suspendu, sans comptes, en reprise récente ou sans note — les
    priorités de `update_data.non_comparable_publie`."""
    from bvc_config import SEUIL_NON_COMPARABLE_DH
    del contestes
    out = []
    m, nf = t.get("_meta") or {}, t.get("note_fond") or {}
    tn = t.get("technique_neutralise") or None
    med = (tn or {}).get("montant_median_dh")
    peu_liquide = bool(tn) and (med if med is not None else 0) < SEUIL_NON_COMPARABLE_DH
    sans_donnees = (nf.get("note") is None or bool(m.get("comptes_absents"))
                    or bool(m.get("reprise_recente")))
    attendu = peu_liquide and not m.get("suspendu") and not sans_donnees
    bloc = m.get("non_comparable")
    if attendu != bool(bloc):
        out.append(_inc(sym, "non_comparable.meta", ERREUR,
                        "_meta.non_comparable doit être présent si et seulement si le titre est peu liquide "
                        f"(technique neutralisée, médiane < {SEUIL_NON_COMPARABLE_DH} DH), coté, avec note "
                        "et comptes", bloc, "présent" if attendu else "absent"))
    elif bloc and (bloc.get("seuil") != SEUIL_NON_COMPARABLE_DH or bloc.get("montant_median_dh") != med):
        out.append(_inc(sym, "non_comparable.meta", ERREUR,
                        "_meta.non_comparable ne reprend pas la médiane publiée et le seuil du moteur",
                        bloc, {"montant_median_dh": med, "seuil": SEUIL_NON_COMPARABLE_DH}))
    return out


# ── maillon 3 bis : le Score BVC publié — 06/11/2026 ───────────────────────
# Lot 1 du retrait de la note v5.3 : le score publié est le Score BVC. Les
# contrôles v53 / sig sont partis avec le producteur au lot 2. Ceux-ci
# vérifient ce que le terminal affiche.
#
# Les règles de forme sont celles de `pipeline/coherence.py::controler_score_bvc`
# — une seule écriture, lue par les deux contrôles. S'y ajoute ce que seul
# l'audit peut faire : la version, et le RECALCUL depuis les chandelles.
def controler_score_bvc(sym, t, bougies_de=None) -> list:
    from pipeline import score_bvc as sb
    from pipeline.coherence import controler_score_bvc as regles
    out = []
    b = t.get("score_bvc")
    if not isinstance(b, dict):
        return [_inc(sym, "score_bvc.absent", ERREUR, "fiche sans bloc score_bvc : le score affiché manque")]
    for a in regles(t):
        out.append(_inc(sym, f"score_bvc.{a['code']}", ERREUR, a["quoi"]))
    if b.get("version") != sb.VERSION:
        out.append(_inc(sym, "score_bvc.version", ERREUR,
                        "version du Score BVC publiée ≠ celle du module", b.get("version"), sb.VERSION))
    # ⚠️ RECALCUL : AVERTISSEMENT, pas erreur. Il relit les chandelles du
    # disque ; or `generate_candles.py` (17h) peut réécrire la dernière bougie
    # dans un commit qui ne régénère pas data.json. Un écart veut alors dire
    # « data.json pas encore régénéré », pas « score faux ». Mesuré le
    # 06/11/2026 sur le data.json publié : 80 recalculs sur 80 identiques.
    if bougies_de is not None:
        r = sb.score_titre_bvc({k: v for k, v in t.items() if k != "score_bvc"}, bougies_de(sym))
        pub = (b.get("valeur"), b.get("etat"), b.get("couverture_pct"))
        att = (r["valeur"], r["etat"], r["couverture_pct"])
        if pub != att:
            out.append(_inc(sym, "score_bvc.recalcul", AVERT,
                            "Score BVC recalculé depuis les chandelles ≠ publié (valeur, état, couverture) — "
                            "chandelles réécrites depuis le run ?", pub, att))
    return out


def bougies_depuis(racine: Path):
    """Lecteur de `pipeline/candles/<T>.json` (liste vide si absent ou illisible)."""
    def lire(sym):
        try:
            s = json.loads((racine / "pipeline" / "candles" / f"{sym}.json").read_text(encoding="utf-8"))
            return s if isinstance(s, list) else []
        except (OSError, ValueError):
            return []
    return lire


def controler_confiance(sym, t, contestes) -> list:
    out = []
    m, nf = t.get("_meta") or {}, t.get("note_fond") or {}
    conf, g = m.get("confidence"), m.get("garanties")
    if not isinstance(g, list) or len(g) != 5 or not all(isinstance(x, dict) and "critere" in x and "ok" in x for x in g):
        return [_inc(sym, "confiance.garanties", ERREUR, "_meta.garanties absent ou mal formé (5 critères attendus)", g)]
    somme = sum(1 for x in g if x["ok"])
    if conf is None:
        return [_inc(sym, "confiance.absente", ERREUR, "_meta.confidence absent")]
    if conf > somme:
        out.append(_inc(sym, "confiance.somme", ERREUR,
                        "confiance supérieure au nombre de garanties remplies", conf, f"≤ {somme}"))
    # Plafonds DOCUMENTÉS (update_data._meta_ticker) : suspension 0 ; sans comptes
    # ou sans note 1 ; liquidité < 100 000 DH 2. La confiance publiée doit être
    # exactement min(somme, plafonds) — une baisse sans plafond publié n'est pas expliquée.
    plafond = somme
    if m.get("suspendu"):
        plafond = 0
    if m.get("comptes_absents") or nf.get("note") is None:
        plafond = min(plafond, 1)
    # Reprise de cotation de moins de 20 séances (update_data : indicateurs
    # retirés, `isin_suspect` forcé, donc confiance ≤ 1). Publié dans
    # `_meta.reprise_recente` ; absent de ce contrôle jusqu'au 03/11/2026, faute
    # de reprise en cours depuis sa création (MNG, reprise du 03/11).
    if m.get("reprise_recente"):
        plafond = min(plafond, 1)
    ech, volmed = m.get("echange_median_dh"), m.get("vol_median20")
    if (ech is not None and ech < 100_000) or (ech is None and volmed is not None and volmed < 10):
        plafond = min(plafond, 2)
    if conf < plafond:
        out.append(_inc(sym, "confiance.plafond_inexplique", ERREUR,
                        "confiance plus basse que min(garanties, plafonds publiés) : aucun plafond publié ne l'explique "
                        "(isin_suspect ? non publié)", conf, plafond))
    elif conf > plafond:
        out.append(_inc(sym, "confiance.plafond_ignore", ERREUR,
                        "confiance au-dessus du plafond que les champs publiés imposent", conf, plafond))
    # Chaque garantie dit la vérité sur ce qu'elle nomme.
    ok = [bool(x["ok"]) for x in g]
    if ok[0] == bool(m.get("stale")):
        out.append(_inc(sym, "garantie.cours", ERREUR, "garantie « cours de la dernière séance » ≠ not stale", ok[0], not m.get("stale")))
    calculable = nf.get("note") is not None and sym not in contestes
    if ok[1] != calculable:
        out.append(_inc(sym, "garantie.note", ERREUR,
                        "garantie « note calculable, sans grandeur contestée » ≠ (note présente et non contestée)",
                        ok[1], calculable))
    if ech is not None and ok[4] != (ech >= 100_000):
        out.append(_inc(sym, "garantie.liquidite", ERREUR, "garantie de liquidité ≠ échange médian ≥ 100 000 DH", ok[4], ech))
    return out


_SEUIL_ALERTE = ("niveau", "theme", "raison", "valeur", "seuil", "source")


def controler_alertes(sym, t, f, contestes) -> list:
    out = []
    al = t.get("alertes")
    nf = t.get("note_fond") or {}
    if not isinstance(al, dict):
        return [_inc(sym, "alertes.absentes", ERREUR, "bloc alertes absent")]
    for i, a in enumerate(al.get("liste") or []):
        manque = [k for k in _SEUIL_ALERTE if not a.get(k)]
        if manque:
            out.append(_inc(sym, "alerte.champs", ERREUR, f"alerte « {a.get('raison')} » sans {', '.join(manque)}"))
        # La date : le terminal écrit « comptes au <x.date> » avec la date PROPRE de
        # l'alerte (jamais celle du bloc). Sans elle, l'écran dit « date inconnue ».
        if not a.get("date"):
            technique = a.get("theme") == "Technique"
            out.append(_inc(sym, "alerte.date", AVERT if technique else ERREUR,
                            f"alerte « {a.get('raison')} » sans date propre : l'écran écrirait « comptes au date inconnue »"
                            + (" (alerte technique, défaut connu : chiffre calculé sur nos chandelles)" if technique else ""),
                            a.get("source")))
    # Recalcul par la même fonction que le moteur, contestations appliquées.
    try:
        import update_data as U
        from pipeline.smart_money import fond_score as F
    except Exception as exc:                                        # noqa: BLE001
        return out + [_inc(sym, "alertes.import", ERREUR, f"update_data non importable : {exc}")]
    sauve = dict(F.CONTESTES)
    try:
        F.CONTESTES.clear()
        F.CONTESTES.update(contestes)
        att = U.detecter_alertes(f, t.get("rsi"), sym)
    finally:
        F.CONTESTES.clear()
        F.CONTESTES.update(sauve)
    if json.loads(json.dumps(att.get("liste"))) != al.get("liste") or att.get("evaluable") != al.get("evaluable"):
        out.append(_inc(sym, "alertes.recalcul", ERREUR, "alertes publiées ≠ alertes recalculées sur les mêmes entrées",
                        [x.get("raison") + " " + x.get("valeur") for x in al.get("liste") or []],
                        [x.get("raison") + " " + x.get("valeur") for x in att.get("liste") or []]))
    if sorted(att.get("non_evalues") or []) != sorted(al.get("non_evalues") or []):
        out.append(_inc(sym, "alertes.non_evalues", ERREUR, "liste « non évalué » publiée ≠ recalculée",
                        al.get("non_evalues"), att.get("non_evalues")))
    # Même chiffre que la note, ou alerte absente.
    comp = nf.get("composantes") or {}
    for a in al.get("liste") or []:
        v = _premier_nombre(a.get("valeur"))
        if a.get("raison", "").startswith("Dette nette"):
            if sym in contestes:
                out.append(_inc(sym, "contestee.alerte", ERREUR, "alerte de dette sur une grandeur contestée", a.get("valeur")))
            mes = (comp.get("bilan") or {}).get("mesure") or ""
            if "dette nette / EBITDA" in mes and not _egal(_premier_nombre(mes.split("EBITDA", 1)[-1]), v, 1e-9):
                out.append(_inc(sym, "alerte.vs_note", ERREUR, "dette/EBITDA de l'alerte ≠ celui de la note",
                                a.get("valeur"), mes))
            if "dette nette / EBITDA" not in mes:
                out.append(_inc(sym, "alerte.vs_note", ERREUR,
                                "alerte de dette alors que la note ne mesure pas la dette/EBITDA", a.get("valeur"), mes or comp.get("bilan")))
        if a.get("raison", "").startswith("La rentabilité du capital"):
            if sym in contestes:
                out.append(_inc(sym, "contestee.alerte", ERREUR, "alerte de ROIC sur une grandeur contestée", a.get("valeur")))
            mes = (comp.get("qualite") or {}).get("mesure") or ""
            if not mes.startswith("ROIC") or not _egal(_premier_nombre(mes), v, 1e-9):
                out.append(_inc(sym, "alerte.vs_note", ERREUR, "ROIC de l'alerte ≠ celui de la note", a.get("valeur"), mes))
            from pipeline.smart_money.fond_score import WACC_REF
            if _premier_nombre(a.get("seuil")) != WACC_REF:
                out.append(_inc(sym, "alerte.vs_note", ERREUR, "WACC de l'alerte ≠ WACC_REF de la note", a.get("seuil"), WACC_REF))
    return out


# ── l'audit de tous les titres ─────────────────────────────────────────────
def auditer(data: dict, fondamentaux: dict, faits: dict, bpa: dict, bougies_de=None) -> list:
    """La liste des incohérences (dicts). Vide = chaîne cohérente.

    `bougies_de(sym)` (facultatif) : les chandelles d'un titre, pour recalculer
    le Score BVC (avertissement seulement, voir `controler_score_bvc`)."""
    out = []
    tickers = (data or {}).get("tickers") or []
    if not tickers:
        return [_inc("*", "data.vide", ERREUR, "data.json sans titres")]
    contestes = contestations(fondamentaux, faits)
    for t in tickers:
        sym = t.get("symbol")
        if not sym:
            out.append(_inc("?", "data.symbole", ERREUR, "fiche sans symbole"))
            continue
        if not isinstance(t.get("_meta"), dict):
            out.append(_inc(sym, "meta.absent", ERREUR, "_meta absent"))
            continue
        attendu = recalculer_note_fond(sym, t, fondamentaux, bpa, contestes)
        out += controler_note_fond(sym, t, attendu, contestes)
        out += controles_piece(sym, fondamentaux.get(sym), (faits or {}).get(sym), t.get("note_fond"))
        out += controler_non_comparable(sym, t, contestes)
        out += controler_score_bvc(sym, t, bougies_de)
        out += controler_confiance(sym, t, contestes)
        out += controler_alertes(sym, t, fondamentaux.get(sym) or {}, contestes)
    return out


# ── maillon 4 : l'affichage, vérifié statiquement ──────────────────────────
# ⚠️ 06/11/2026 — le terminal n'affiche plus la note v5.3 (décision d'Abd
# Moutalib) : le score unique est le Score BVC (`score_bvc`). « Pourquoi cette
# note ? » et la pastille de palier v5.3 sont retirés ; la pastille de tranche
# (PastilleBVC) et les mesures bancaires en données (MesuresBancaires) les
# remplacent. Seul ce qui est vérifié À L'ÉCRAN suit l'écran ; les champs
# v5.3 ne sont plus publiés depuis le lot 2, et un composant qui les relirait
# reste refusé ci-dessous.
COMPOSANTS_AFFICHAGE = ("reservePrincipale", "ResumeNote", "DetailConfiance", "PastilleBVC", "MesuresBancaires")
# Les seuls champs de la fiche `r` que ces composants peuvent lire.
CHAMPS_AUTORISES = {"note_fond", "alertes", "_meta", "score_bvc", "risque"}
# Ce qui ne doit JAMAIS alimenter ces composants : une seconde source, ou la
# note v5.3 que le terminal n'affiche plus.
SECONDES_SOURCES = ("note_fond_metier", "STATIC", "SENTIMENT", "FOND_SCORES", "computeDisplayScore",
                    "r.v53", "r.sig", "r.score_fond", "r.score_tech", "r.bonus", "r.verdict_plafonne")


def _corps(src: str, nom: str) -> str | None:
    """Le texte de `const NOM=` jusqu'à la prochaine déclaration de tête de ligne."""
    m = re.search(rf"^const {nom}=", src, re.M)
    if not m:
        return None
    suite = re.search(r"^(?:const |/\*|//)", src[m.end():], re.M)
    return src[m.start(): m.end() + (suite.start() if suite else len(src))]


def auditer_affichage(src: str, bvc_config=None, score_bvc=None) -> list:
    """Vérification STATIQUE du terminal. Limite assumée : elle lit du texte,
    elle n'exécute pas l'écran."""
    out, T = [], "terminal"
    if bvc_config is None:
        import bvc_config
    if score_bvc is None:
        from pipeline import score_bvc
    for nom in COMPOSANTS_AFFICHAGE:
        corps = _corps(src, nom)
        if corps is None:
            out.append(_inc(T, "affichage.composant", ERREUR, f"composant {nom} introuvable dans terminal.src.html"))
            continue
        for seconde in SECONDES_SOURCES:
            if seconde in corps:
                out.append(_inc(T, "affichage.seconde_source", ERREUR, f"{nom} lit {seconde}, seconde source de l'affichage"))
        lus = set(re.findall(r"\br\.([A-Za-z_][A-Za-z0-9_]*)", corps))
        hors = sorted(lus - CHAMPS_AUTORISES)
        if hors:
            out.append(_inc(T, "affichage.champ_hors_liste", ERREUR,
                            f"{nom} lit des champs hors de la liste publiée : {', '.join(hors)}", hors))
    for nom, champ in (("reservePrincipale", "note_fond"), ("MesuresBancaires", "note_fond"),
                       ("ResumeNote", "alertes"), ("DetailConfiance", "garanties"),
                       ("PastilleBVC", "score_bvc")):
        corps = _corps(src, nom) or ""
        if champ == "note_fond" and "note_fond" not in corps:
            out.append(_inc(T, "affichage.lecture", ERREUR, f"{nom} ne lit pas note_fond"))
        if champ == "alertes" and "r.alertes" not in corps:
            out.append(_inc(T, "affichage.lecture", ERREUR, f"{nom} ne lit pas r.alertes"))
        if champ == "garanties" and "m.garanties" not in corps:
            out.append(_inc(T, "affichage.lecture", ERREUR, "DetailConfiance ne lit pas _meta.garanties"))
        if champ == "score_bvc" and "r.score_bvc" not in corps:
            out.append(_inc(T, "affichage.lecture", ERREUR, "PastilleBVC ne lit pas r.score_bvc"))
    # Le chemin data.json -> fiche : les champs AFFICHÉS sont transportés tels quels.
    for champ in ("note_fond", "alertes", "_meta", "score_bvc"):
        if not re.search(rf"\b{champ}:t\.{champ}\b", src):
            out.append(_inc(T, "affichage.transport", ERREUR, f"loadData ne transporte pas {champ}:t.{champ} tel quel"))
    # La valeur affichée est celle que le moteur publie, sans recalcul.
    if 'const valeurBVC=r=>{const s=r&&r.score_bvc;const v=s?s.valeur:null;' not in src:
        out.append(_inc(T, "affichage.score", ERREUR, "valeurBVC ne lit plus score_bvc.valeur tel quel"))
    # Seuil de couverture affiché = celui du moteur du Score BVC.
    seuil = score_bvc.COUVERTURE_MIN
    for motif in (f"au moins {seuil} % du poids", f"sous {seuil} % du poids"):
        if motif not in src:
            out.append(_inc(T, "affichage.seuil", ERREUR,
                            f"le terminal n'annonce plus le seuil de couverture du Score BVC ({seuil} %) : « {motif} »"))
    # Vue PER : la mention de liquidité lit le CHAMP du moteur, pas un libellé.
    if "m_.non_comparable" not in src:
        out.append(_inc(T, "affichage.non_comparable", ERREUR, "la vue PER ne lit pas _meta.non_comparable"))
    if "m.conf<=1" not in src or 'meta(r).conf<=1||valeurBVC(r)==null?"#8892a4"' not in src:
        out.append(_inc(T, "affichage.confiance", ERREUR, "la règle d'affichage « confiance ≤ 1 : score gris » a disparu"))
    if "conf:m.confidence??0" not in src:
        out.append(_inc(T, "affichage.confiance", ERREUR, "meta(r) ne lit plus _meta.confidence (repli 0)"))
    # Limite assumée, toujours rappelée.
    out.append(_inc(T, "affichage.limite", AVERT,
                    "contrôle STATIQUE : aucun rendu exécuté. Le tableau STATIC du terminal (valeurs de repli codées en "
                    "dur) n'est pas audité ; voir tools/qa_navigateur.js pour un contrôle dans un navigateur."))
    return out


# ── data.json publié plus ancien que ses entrées ? ─────────────────────────
ENTREES = ("fondamentaux.json", "bpa.json", "pipeline/faits_financiers.json",
           "pipeline/smart_money/fond_score.py", "pipeline/smart_money/fond_score_sectoriel.py",
           "pipeline/score_bvc.py", "pipeline/score_descriptif.py",
           "update_data.py", "bvc_config.py")


def entrees_plus_recentes(racine: Path, data: dict) -> list:
    """Les fichiers d'entrée dont la DERNIÈRE MODIFICATION (historique du dépôt)
    est postérieure à l'horodatage `updated` du data.json jugé : un échec
    d'audit sur un tel fichier peut vouloir dire « le moteur n'a pas encore
    tourné » plutôt que « défaut ». Meilleur effort : sans historique, liste
    vide (on ne conclut rien). Retourne [(fichier, date ISO du dernier commit)]."""
    import subprocess
    from datetime import datetime, timezone
    try:
        brut = str((data or {}).get("updated") or "").replace("Z", "+00:00")
        brut = re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", brut)
        quand = datetime.fromisoformat(brut)
        if quand.tzinfo is None:
            quand = quand.replace(tzinfo=timezone.utc)
    except ValueError:
        return []
    out = []
    for f in ENTREES:
        try:
            r = subprocess.run(["git", "log", "-1", "--format=%cI", "--", f], cwd=racine,
                               capture_output=True, text=True, timeout=30)
            iso = r.stdout.strip()
            if r.returncode == 0 and iso and datetime.fromisoformat(iso) > quand:
                out.append((f, iso))
        except (OSError, ValueError, subprocess.SubprocessError):
            return []
    return out


# ── sortie ─────────────────────────────────────────────────────────────────
def rapport_texte(incs: list, n_titres: int, retard: list | None = None) -> str:
    erreurs = [i for i in incs if i["gravite"] == ERREUR]
    avert = [i for i in incs if i["gravite"] == AVERT]
    lignes = [f"AUDIT DE LA CHAÎNE — {n_titres} titres — {len(erreurs)} erreur(s), {len(avert)} avertissement(s)"]
    for titre_g, liste in (("ERREURS", erreurs), ("AVERTISSEMENTS", avert)):
        if not liste:
            continue
        lignes += ["", f"{titre_g} :", f"{'titre':<10} {'contrôle':<34} message"]
        for i in sorted(liste, key=lambda x: (x["titre"], x["controle"])):
            det = ""
            if i["publie"] is not None or i["attendu"] is not None:
                det = f"  [publié={i['publie']!r} attendu={i['attendu']!r}]"
            lignes.append(f"{i['titre']:<10} {i['controle']:<34} {i['message']}{det}")
    if not erreurs:
        lignes += ["", "✔ aucune incohérence de gravité ERREUR"]
    elif retard:
        lignes += ["", "DIAGNOSTIC : le data.json jugé est ANTÉRIEUR à ses entrées — il n'a probablement pas été "
                       "régénéré depuis :"] + [f"  - {f} (commit du {iso})" for f, iso in retard]
        lignes.append("  Régénérer (python update_data.py, ou l'essai à blanc isolé de tests/test_audit_chaine.py) "
                      "avant de conclure à un défaut.")
    return "\n".join(lignes)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--racine", type=Path, default=RACINE, help="dossier portant fondamentaux.json, bpa.json, pipeline/…")
    ap.add_argument("--data", type=Path, default=None, help="data.json à juger (défaut : <racine>/data.json)")
    ap.add_argument("--terminal", type=Path, default=None, help="terminal.src.html (défaut : <racine>/terminal.src.html)")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    a = ap.parse_args(argv)
    ch = charger(a.racine, a.data)
    incs = auditer(ch["data"], ch["fondamentaux"], ch["faits"], ch["bpa"], bougies_depuis(a.racine))
    src_path = a.terminal or (a.racine / "terminal.src.html")
    try:
        incs += auditer_affichage(src_path.read_text(encoding="utf-8"))
    except OSError as exc:
        incs.append(_inc("terminal", "affichage.source", ERREUR, f"terminal.src.html illisible : {exc}"))
    n = len((ch["data"] or {}).get("tickers") or [])
    nb_err = sum(1 for i in incs if i["gravite"] == ERREUR)
    retard = entrees_plus_recentes(a.racine, ch["data"]) if nb_err else []
    if a.json:
        print(json.dumps({"titres": n, "erreurs": nb_err, "avertissements": len(incs) - nb_err,
                          "data_anterieur_aux_entrees": [{"fichier": f, "commit": iso} for f, iso in retard],
                          "incoherences": incs}, ensure_ascii=False, indent=2))
    else:
        print(rapport_texte(incs, n, retard))
    return 1 if nb_err else 0


if __name__ == "__main__":
    sys.exit(main())

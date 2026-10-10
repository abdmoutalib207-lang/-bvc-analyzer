#!/usr/bin/env python3
"""Note fondamentale PAR FAMILLE DE MÉTIER — la note PUBLIÉE depuis le 10/10/2026.

⚠️ DÉCISION D'ABD MOUTALIB, 10/10/2026 : la note fondamentale suit « les règles
de l'art du marché marocain, selon la spécificité de chaque secteur », et il a
assoupli R8 pour cela. Ce module REMPLACE la grille unique de `fond_score.py`
dans la note publiée (`score_fond`). ⚠️ LES POIDS DES PILIERS NE CHANGENT PAS
(Fond 65,28 % / Tech 34,72 % / NLP 0) : c'est le CONTENU du pilier fondamental
qui change, pas sa part dans la note composite. Spécification : agent
`verificateur-finance`. Historique : ce module a d'abord été un calcul FANTÔME
(30/09/2026, `datasets/note_sectorielle_2026-09-30.json`), jamais publié.

⚠️ CE QUE CE MODULE NE FAIT PAS (Vision Produit) : il ne prédit rien. La note
décrit la situation d'un titre au regard des comptes publiés et de ses pairs ;
elle n'annonce pas un cours.

POURQUOI UNE GRILLE PAR FAMILLE
`fond_score.py` applique la même grille aux 80 sociétés : ROIC − WACC, PER face
à un repère fixe, dette / EBITDA. Rien de cela n'a le même sens pour une
banque (la dette est l'activité), une foncière (la dette finance le patrimoine,
la valeur est l'actif net) ou un promoteur (le stock se finance par la dette).

LES FAMILLES (`bvc_config.FAMILLES_NOTE`, listes explicites de tickers)
  banque · assurance · financement · paiement
      rentabilité = ROE part du groupe 12 mois sur fonds propres MOYENS ;
      valorisation = PER 12 mois relatif ; P/B à la place du PER seulement si
      le résultat 12 mois est ≤ 0 ; ni bilan ni dette / EBITDA.
  fonciere · holding
      valorisation = P/B relatif à la famille (≥ 3 titres, sinon abstention) ;
      bilan = dette nette / fonds propres ; croissance du BPA exclue pour les
      foncières (la juste valeur des immeubles la fausse) : CA seulement.
  promoteur
      rentabilité = ROE (pas ROIC) ; bilan = dette nette / fonds propres ;
      valorisation = PER relatif, P/B affiché.
  mines
      valorisation = VE / EBITDA relatif si la donnée existe, sinon PER relatif.
  btp · telecom · utility · autre
      la grille d'origine : ROIC, PER relatif, dette / EBITDA, conversion.

LE DIVIDENDE n'entre dans AUCUN critère de cette grille. S'il y entrait un
jour, seul le dividende ORDINAIRE compterait (jamais un exceptionnel).

LES PRINCIPES
1. Seules des données CALCULÉES sur comptes publiés, datées. Aucune saisie.
2. UNE SEULE PORTE pour les ratios : `fond_score.ratio_effectif` /
   `roe_effectif`, qui appliquent `ROE_SANS_OBJET` (AFM, AGM) et
   `RATIOS_EN_VERIFICATION` (MSA). Le 10/10/2026, la version fantôme lisait
   `ratios_publies` en direct et contournait les deux : AFM publiait un ROE de
   103,7 %, MSA un ROIC de 47,6 %.
3. Un critère sans donnée S'ABSTIENT ; les poids se répartissent entre les
   critères présents. Moins de la MOITIÉ du poids disponible : pas de note
   (« Données insuffisantes »), jamais une note par défaut.
4. Valorisation RELATIVE : le ratio du titre rapporté à la médiane de sa
   FAMILLE (au moins 3 titres, sinon médiane du marché). Les sociétés sans
   comptes (`SANS_COMPTES`), à fonds propres négatifs ou suspendues sont
   écartées des médianes.
5. Aucun modificateur d'opinion (momentum, rerating, cycle) : non mesurés.

LES PALIERS — aucun n'est inventé ici
  [G] ceux de la grille existante de `fond_score.py` : rentabilité (écart à
      10 %), croissance, dette / EBITDA + conversion. Épinglés par
      `tests/test_note_sectorielle.py` contre `compute_fond_score`.
  [R] ceux de `note_per_relatif`, repris du calcul fantôme du 30/09 : nouveaux,
      DÉCLARÉS ET NON CALIBRÉS (aucun historique de fondamentaux avant le
      29/09/2026 pour les calibrer).
  Trois usages SANS palier sourcé, déclarés comme tels :
      · P/B relatif et VE/EBITDA relatif : paliers [R] du ratio relatif ;
      · dette nette / fonds propres : paliers [G] de dette / EBITDA,
        transposés tels quels ;
      · perte sur 12 mois (hors banques) : 1,5, la note la plus basse de la
        grille de valorisation.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RACINE))

from bvc_config import famille_note  # noqa: E402
from pipeline.smart_money.fond_score import (  # noqa: E402
    COUT_FONDS_PROPRES_REF, WACC_REF, ratio_effectif, roe_effectif,
)

# Poids en points entiers : une somme de flottants (0,3 + 0,2) vaut 0,5 « à un
# epsilon près », et le seuil d'abstention se joue précisément à 50.
POIDS = {"rentabilite": 40, "croissance": 30, "valorisation": 20, "bilan": 10}
SEUIL_POIDS = 50          # moins de la moitié du poids disponible : pas de note
MIN_TITRES_FAMILLE = 3    # médiane de famille : au moins 3 titres

FINANCIERES = ("banque", "assurance", "financement", "paiement")
MOTIF_SANS_COMPTES = "société sans comptes déposés (SANS_COMPTES)"


# ───────────────────────────── paliers ─────────────────────────────

def note_ecart_rentabilite(rendement: float, reference: float) -> float:
    """[G] Rentabilité : écart à la référence (10 %), grille de fond_score.py."""
    sp = rendement - reference
    return (9.5 if sp >= 15 else 8.5 if sp >= 10 else 7.0 if sp >= 5 else
            6.0 if sp >= 2 else 5.0 if sp >= 0 else 3.5 if sp >= -3 else 2.0)


def note_croissance(g: float) -> float:
    """[G] Croissance composite, grille de fond_score.py."""
    for s, n in ((100, 10.0), (50, 9.0), (25, 7.5), (10, 6.5), (5, 5.5), (0, 4.5), (-10, 3.0)):
        if g >= s:
            return n
    return 1.5


def note_relatif(ratio: float) -> float:
    """[R] Ratio du titre ÷ médiane de référence (PER, P/B ou VE/EBITDA)."""
    if ratio <= 0.6:
        return 9.5
    if ratio <= 0.8:
        return 8.5
    if ratio <= 1.0:
        return 7.0
    if ratio <= 1.25:
        return 5.5
    if ratio <= 1.6:
        return 4.0
    return 2.5


def note_dette(dne: float) -> float:
    """[G] Dette nette / EBITDA, grille de fond_score.py (sans la conversion)."""
    if dne < 0:
        return 9.0
    for borne, n in ((0.5, 8.5), (1.5, 7.0), (2.5, 5.5), (3.5, 4.0), (5.0, 2.5)):
        if dne < borne:
            return n
    return 1.5


def note_bilan_industriel(dne: float, cc: float | None) -> float:
    """[G] Dette / EBITDA ajustée de la conversion de trésorerie."""
    bs = note_dette(dne)
    if cc is not None:
        if cc >= 85:
            bs = min(10.0, bs + 0.5)
        elif cc < 40:
            bs = max(0.0, bs - 0.5)
    return bs


# ───────────────────────────── entrées ─────────────────────────────

def _num(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _fait(faits: dict, cle: str):
    x = ((faits or {}).get("faits") or {}).get(cle)
    return _num(x.get("valeur")) if isinstance(x, dict) else None


def _roe(sym, fiche, bpa, s1) -> dict | None:
    """ROE part du groupe sur 12 mois. Passe par `roe_effectif` (AFM/AGM sans
    objet, MSA en vérification). Fonds propres MOYENS (31/12/2025 et
    30/06/2026) quand les deux existent, sinon de CLÔTURE — dans les deux cas
    la base est dite."""
    base = roe_effectif(fiche, sym)
    if base is None:
        return None
    rn = _num((bpa or {}).get("rnpg_12m"))
    c0 = _num((s1 or {}).get("capitaux_propres_pg_31_12_2025"))
    c1 = _num((s1 or {}).get("capitaux_propres_pg_30_06_2026"))
    if base["cle"] == "roe_12m" and rn is not None and c0 and c1 and c0 > 0 and c1 > 0:
        return {"valeur": round(rn / ((c0 + c1) / 2) * 100, 2),
                "base": "fonds propres moyens, moyenne 2 points (31/12/2025 et 30/06/2026)"}
    cloture = "30/06/2026" if base["cle"] == "roe_12m" else "31/12/2025 (exercice 2025)"
    return {"valeur": base["valeur"], "base": f"fonds propres de clôture {cloture}"}


def _publie(fiche, sym, cle) -> float | None:
    """Un ratio par LA porte (`ratio_effectif`), mais seulement s'il vient des
    comptes publiés : la porte retombe sur la saisie, cette grille ne la lit pas."""
    r = ratio_effectif(fiche, sym, cle)
    return r["valeur"] if r and r.get("origine") == "comptes publiés" else None


def construire_entree(sym: str, fiche: dict | None, bpa: dict | None, s1: dict | None,
                      faits: dict | None, prix: float | None, pb: float | None, *,
                      sans_comptes: bool = False, suspendu: bool = False) -> dict:
    """Tout ce que la note lit pour UN titre, rassemblé et daté. Pure."""
    fiche, bpa, s1 = fiche or {}, bpa or {}, s1 or {}
    fam = famille_note(sym)
    rp = fiche.get("ratios_publies") or {}

    # Fonds propres négatifs : consolidés, part du groupe, ou S1.
    fp_vals = [_fait(faits, "capitaux_propres_part_groupe"), _fait(faits, "capitaux_propres_consolides"),
               _num(s1.get("capitaux_propres_pg_31_12_2025")), _num(s1.get("capitaux_propres_pg_30_06_2026"))]
    fp_negatifs = any(v is not None and v <= 0 for v in fp_vals)

    # Deux niveaux. SANS COMPTES : pas de note du tout (rien de publié à noter).
    # Fonds propres négatifs ou titre suspendu : le titre est noté sur ce qu'il
    # a, mais ses ratios sont écartés des MÉDIANES (un PER ou un P/B de société
    # aux fonds propres négatifs ne mesure pas une valorisation de pair).
    sans_note = MOTIF_SANS_COMPTES if sans_comptes else None
    hors_mediane = (sans_note or ("fonds propres négatifs" if fp_negatifs else
                                  "titre suspendu : cours non coté" if suspendu else None))

    b12 = _num(bpa.get("bpa_12m"))
    px = _num(prix) if prix and prix > 0 else None

    # Dette nette, EBITDA, fonds propres à la MÊME date (31/12/2025).
    dn = rp.get("dette_nette") if isinstance(rp.get("dette_nette"), dict) else None
    dette_nette = _num(dn.get("valeur")) if dn else None
    fp_cons = _fait(faits, "capitaux_propres_consolides")
    fp_pg = _fait(faits, "capitaux_propres_part_groupe")
    fp_dette, fp_base = (fp_cons, "consolidés") if fp_cons else (fp_pg, "part du groupe")
    gearing = None
    if dette_nette is not None and fp_dette and fp_dette > 0 and (dn or {}).get("date") == "2025-12-31":
        gearing = {"valeur": round(dette_nette / fp_dette, 2),
                   "mesure": f"dette nette {dette_nette:g} ÷ fonds propres {fp_base} {fp_dette:g} MMAD (31/12/2025)"}

    # VE / EBITDA : capitalisation du jour + dette nette + minoritaires, ÷ EBITDA 2025.
    ve = None
    eb = rp.get("ebitda") if isinstance(rp.get("ebitda"), dict) else None
    ebitda = _num(eb.get("valeur")) if eb else None
    actions = _num(s1.get("actions")) or _num(fiche.get("nb_actions"))
    if px and actions and ebitda and ebitda > 0 and dette_nette is not None and (dn or {}).get("date") == "2025-12-31":
        minoritaires = (fp_cons - fp_pg) if (fp_cons is not None and fp_pg is not None) else 0.0
        v = px * actions / 1e6 + dette_nette + minoritaires
        ve = {"valeur": round(v / ebitda, 2),
              "mesure": f"VE {v:.0f} ÷ EBITDA {ebitda:g} MMAD (2025)"}

    s1_ok = bool(fiche.get("source_s1_2026"))
    return {
        "sym": sym, "famille": fam, "sans_note": sans_note, "hors_mediane": hors_mediane, "prix": px,
        "bpa_12m": b12,
        "per": round(px / b12, 2) if px and b12 and b12 > 0 else None,
        "pb": _num(pb) if pb and pb > 0 else None,
        "ve_ebitda": ve,
        "roe": _roe(sym, fiche, bpa, s1),
        "roic": _publie(fiche, sym, "roic"),
        "dne": _publie(fiche, sym, "dette_nette_ebitda"),
        "cc": _publie(fiche, sym, "cash_conversion"),
        "dette_nette": _publie(fiche, sym, "dette_nette"),
        "gearing": gearing,
        "croissance_bpa": _num(fiche.get("croissance_bpa")) if s1_ok else None,
        "croissance_ca": _num(fiche.get("croissance_ca")) if s1_ok else None,
        "financiere": str(fiche.get("secteur") or "").startswith(("Banque", "Assurance", "Finance")),
    }


# ───────────────────────────── médianes ─────────────────────────────

def calculer_medianes(entrees: list[dict]) -> dict:
    """Médianes de référence par famille et pour le marché, pour chaque ratio.

    {ratio: {"famille": {fam: (médiane, n)}, "marche": (médiane, n)}}.
    Écartés : `hors_mediane` (sans comptes, fonds propres négatifs, suspendu).
    """
    def valeur(e, k):
        if k == "per":
            return e["per"]
        if k == "pb":
            return e["pb"]
        return (e["ve_ebitda"] or {}).get("valeur")

    out = {}
    for k in ("per", "pb", "ve_ebitda"):
        par_fam, tous = {}, []
        for e in entrees:
            v = valeur(e, k)
            if e["hors_mediane"] or v is None or v <= 0:
                continue
            par_fam.setdefault(e["famille"], []).append(v)
            tous.append(v)
        out[k] = {"famille": {f: (statistics.median(v), len(v)) for f, v in par_fam.items()},
                  "marche": (statistics.median(tous), len(tous)) if tous else (None, 0)}
    return out


def _reference(medianes: dict, k: str, fam: str, repli_marche: bool = True):
    """(médiane, libellé) : la famille si ≥ 3 titres, sinon le marché, sinon rien."""
    m, n = medianes[k]["famille"].get(fam, (None, 0))
    if m and n >= MIN_TITRES_FAMILLE:
        return m, f"médiane de la famille « {fam} » ({n} titres)"
    if repli_marche:
        m, n = medianes[k]["marche"]
        if m:
            return m, f"médiane du marché ({n} titres ; famille « {fam} » : moins de {MIN_TITRES_FAMILLE})"
    return None, None


# ───────────────────────────── la note ─────────────────────────────

def noter(e: dict, medianes: dict) -> dict:
    """Note d'un titre : {"note", "poids_disponible", "composantes", "abstentions", ...}.

    `note` est None sous la moitié du poids. Pure : tout vient de `e` et des
    médianes.
    """
    fam = e["famille"]
    comp, abst = {}, {}

    def poser(critere, mesure, note, **plus):
        comp[critere] = {"mesure": mesure, "note": note, "poids": POIDS[critere], **plus}

    if e["sans_note"]:
        return {"famille": fam, "note": None, "poids_disponible": 0, "composantes": {},
                "abstentions": {c: e["sans_note"] for c in POIDS}, "motif": e["sans_note"]}

    # ── Rentabilité ────────────────────────────────────────────────────────
    sur_roe = fam in FINANCIERES or fam in ("fonciere", "holding", "promoteur")
    roe, roic = e["roe"], e["roic"]
    if sur_roe or (roic is None and roe is not None):
        if roe is not None:
            poser("rentabilite", f"ROE {roe['valeur']:g} % sur {roe['base']}",
                  note_ecart_rentabilite(roe["valeur"], COUT_FONDS_PROPRES_REF))
        else:
            abst["rentabilite"] = "ROE non calculable sur comptes publiés (ou sans objet)"
    elif roic is not None:
        poser("rentabilite", f"ROIC {roic:g} % (comptes publiés)",
              note_ecart_rentabilite(roic, WACC_REF))
    else:
        abst["rentabilite"] = "ni ROIC ni ROE calculables sur comptes publiés"
    if "rentabilite" in comp and not sur_roe and roic is None:
        comp["rentabilite"]["mesure"] += " — ROIC non calculable, ROE à défaut"

    # ── Croissance ─────────────────────────────────────────────────────────
    cb = None if fam == "fonciere" else e["croissance_bpa"]
    cc_ = e["croissance_ca"]
    if cb is not None and cc_ is not None:
        g = cb * 0.6 + cc_ * 0.4
    else:
        g = cb if cb is not None else cc_
    if g is not None:
        poser("croissance", f"BPA {cb if cb is not None else '—'} % · CA {cc_ if cc_ is not None else '—'} %"
                            + (" (BPA exclu : juste valeur)" if fam == "fonciere" else ""),
              note_croissance(g))
    else:
        abst["croissance"] = "croissance non issue des dépôts S1 2026"

    # ── Valorisation ───────────────────────────────────────────────────────
    def par_per():
        if e["bpa_12m"] is None or e["prix"] is None:
            return "bpa_12m absent"
        if e["bpa_12m"] <= 0:
            return None                         # perte : traitée par l'appelant
        ref, lib = _reference(medianes, "per", fam)
        if ref is None:
            return "aucune médiane de référence"
        poser("valorisation", f"PER 12 m {e['per']:.1f} ÷ {lib} {ref:.1f}",
              note_relatif(e["per"] / ref), pb_affiche=e["pb"])
        return "ok"

    def par_pb(raison_perte=False):
        if e["pb"] is None:
            return "P/B non calculable sur faits sourcés"
        ref, lib = _reference(medianes, "pb", fam, repli_marche=False)
        if ref is None:
            return f"P/B : moins de {MIN_TITRES_FAMILLE} titres dans la famille « {fam} »"
        poser("valorisation", f"P/B {e['pb']:.2f} ÷ {lib} {ref:.2f}"
                              + (" (résultat 12 mois ≤ 0 : P/B à la place du PER)" if raison_perte else ""),
              note_relatif(e["pb"] / ref))
        return "ok"

    if fam in ("fonciere", "holding"):
        r = par_pb()
        if r != "ok":
            abst["valorisation"] = r
    elif fam == "mines" and e["ve_ebitda"] is not None:
        ref, lib = _reference(medianes, "ve_ebitda", fam)
        if ref is None:
            abst["valorisation"] = "aucune médiane VE/EBITDA"
        else:
            poser("valorisation", f"VE/EBITDA {e['ve_ebitda']['valeur']:.1f} ({e['ve_ebitda']['mesure']}) ÷ {lib} {ref:.1f}",
                  note_relatif(e["ve_ebitda"]["valeur"] / ref))
    else:
        r = par_per()
        if r is None:                            # résultat 12 mois ≤ 0
            if fam in FINANCIERES:
                r = par_pb(raison_perte=True)
            else:
                poser("valorisation", "perte sur 12 mois", 1.5)
                r = "ok"
        if r != "ok":
            abst["valorisation"] = r

    # ── Bilan ──────────────────────────────────────────────────────────────
    if fam in FINANCIERES:
        abst["bilan"] = "sans objet : la dette est l'activité d'un établissement financier"
    elif fam in ("fonciere", "holding", "promoteur"):
        if e["gearing"] is not None:
            poser("bilan", e["gearing"]["mesure"] + f" = {e['gearing']['valeur']:g}",
                  note_dette(e["gearing"]["valeur"]))
        else:
            abst["bilan"] = "dette nette / fonds propres non calculable à la même date"
    else:
        dne = e["dne"]
        if dne == 0 and e["financiere"]:
            dne = None
        if dne is None and not e["financiere"] and e["dette_nette"] is not None and e["dette_nette"] < 0:
            dne = -1.0                                   # trésorerie nette, EBITDA inconnu
        if dne is not None:
            poser("bilan", f"dette nette / EBITDA {dne:g}", note_bilan_industriel(dne, e["cc"]))
        else:
            abst["bilan"] = "dette nette / EBITDA non calculable (ou sans objet)"

    dispo = sum(c["poids"] for c in comp.values())
    note = round(sum(c["poids"] * c["note"] for c in comp.values()) / dispo, 2) if dispo >= SEUIL_POIDS else None
    return {"famille": fam, "note": note, "poids_disponible": dispo,
            "composantes": comp, "abstentions": abst,
            "motif": None if note is not None else f"poids disponible {dispo} % < {SEUIL_POIDS} %"}


def noter_univers(titres, prix: dict, pb: dict, fondamentaux: dict, bpa: dict,
                  s1: dict, faits: dict, sans_comptes=(), suspendus=()) -> dict:
    """{sym: résultat de `noter`} pour tous les `titres`. Pure.

    `prix` et `pb` sont ceux que le lecteur voit ; `s1` est le dict `titres` de
    datasets/resultats_s1_2026.json ; `faits` celui de pipeline/faits_financiers.json.
    """
    entrees = [construire_entree(
        s, fondamentaux.get(s), bpa.get(s), s1.get(s), faits.get(s), prix.get(s), pb.get(s),
        sans_comptes=s in sans_comptes, suspendu=s in suspendus) for s in titres]
    med = calculer_medianes(entrees)
    return {e["sym"]: noter(e, med) | {"entree": e} for e in entrees}


def charger_sources(racine: Path = RACINE) -> dict:
    """Les fichiers lus par la note, tels que le moteur les lit."""
    def lire(p):
        return json.loads((racine / p).read_text(encoding="utf-8"))
    return {"fondamentaux": lire("fondamentaux.json"), "bpa": lire("bpa.json"),
            "s1": lire("datasets/resultats_s1_2026.json").get("titres", {}),
            "faits": lire("pipeline/faits_financiers.json")}


def noter_depuis_fichiers(prix_surcharge: dict | None = None, racine: Path = RACINE) -> dict:
    """Note les 80 titres à partir des fichiers publiés : cours et P/B du
    `data.json`, éventuellement surchargés par `prix_surcharge` (le second
    pipeline, qui ne connaît que ses propres titres, complète ainsi l'univers
    dont les médianes ont besoin). Lecture seule."""
    from bvc_config import SANS_COMPTES, TICKERS_ALL, est_suspendu
    src = charger_sources(racine)
    data = json.loads((racine / "data.json").read_text(encoding="utf-8"))
    T = {t["symbol"]: t for t in data["tickers"]}
    prix = {s: t.get("price") for s, t in T.items()}
    prix.update({s: p for s, p in (prix_surcharge or {}).items() if p})
    return noter_univers(
        TICKERS_ALL, prix, {s: t.get("pb") for s, t in T.items()},
        src["fondamentaux"], src["bpa"], src["s1"], src["faits"],
        sans_comptes=set(SANS_COMPTES),
        suspendus={s for s in TICKERS_ALL if est_suspendu(s)})


def main() -> int:
    """Audit : note chaque titre sur les cours et P/B du data.json publié."""
    res = noter_depuis_fichiers()
    for s, r in res.items():
        print(f"{s:5} {r['famille']:12} note={r['note']}  poids={r['poids_disponible']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Note fondamentale PAR FAMILLE DE MÉTIER — MODE COMPARAISON (11/10/2026).

⚠️ ÉTAT : CALCULÉE ET PUBLIÉE À CÔTÉ (`note_fond_metier` dans data.json), PAS
RETENUE DANS LA NOTE. `score_fond`, `v53`, le signal, la confiance et le
plancher de publication restent sur la grille ACTUELLE (`fond_score.py`) tant
que les corrections demandées par Abd Moutalib le 11/10/2026 ne sont pas
validées. L'interrupteur est `bvc_config.NOTE_METIER_PUBLIEE` (faux).

DÉCISION D'ABD MOUTALIB, 10/10/2026 : la note fondamentale doit suivre « les
règles de l'art du marché marocain, selon la spécificité de chaque secteur », et
R8 est assoupli pour cela. ⚠️ LES POIDS DES PILIERS NE CHANGENT PAS (Fond
65,28 % / Tech 34,72 % / NLP 0) : seul le CONTENU de la note fondamentale
change. Spécification : agent `verificateur-finance`.

⚠️ CE QUE CE MODULE NE FAIT PAS (Vision Produit) : il ne prédit rien. La note
décrit la situation d'un titre au regard des comptes publiés ; elle n'annonce
pas un cours.

LES FAMILLES (`bvc_config.FAMILLES_NOTE`, listes explicites de tickers)
  banque · assurance · financement · paiement
      rentabilité = ROE ; valorisation = PER 12 mois relatif ; P/B comptable à
      la place du PER seulement si le résultat 12 mois est ≤ 0 ; pas de bilan.
  fonciere
      rentabilité SUSPENDUE : le ROE d'une foncière intègre les mêmes effets de
      juste valeur des immeubles qui ont fait exclure la croissance de son BPA ;
      croissance = CA seulement ; valorisation par P/B COMPTABLE (voir 3) ;
      bilan : dette nette / fonds propres AFFICHÉ, non noté (voir 1).
  holding
      rentabilité = ROE ; croissance ; P/B COMPTABLE ; bilan comme les foncières.
  promoteur
      rentabilité = ROE (pas ROIC) ; valorisation = PER relatif, P/B comptable
      affiché ; bilan : dette nette / fonds propres AFFICHÉ, non noté.
  mines
      valorisation = VE/EBITDA, UNIQUEMENT quand les conditions de cohérence
      sont remplies (voir 4) ; sinon SUSPENDUE, sans repli vers le PER.
  btp · telecom · utility · autre
      la grille d'origine : ROIC, PER relatif, dette / EBITDA, conversion.

LE DIVIDENDE n'entre dans AUCUN critère de cette grille. S'il y entrait un
jour, seul le dividende ORDINAIRE compterait.

LES RÈGLES (chacune a son test)
1. DETTE NETTE / FONDS PROPRES : aucun barème sourcé n'existe. Transposer celui
   de dette nette / EBITDA (100 % des fonds propres → 7/10) n'est pas justifié :
   le critère est SUSPENDU dans la note, sa valeur reste affichée, étiquetée.
2. FONCIÈRES ET HOLDING — LIMITE ANNONCÉE. La médiane de référence exige 3
   PAIRS (titre noté exclu). Avec 3 foncières, chacune n'a que 2 pairs : le P/B
   ne peut JAMAIS contribuer à leur note. REB est seul dans « holding » : idem.
   Avec ROE suspendu, bilan suspendu et P/B inutilisable, il ne reste aux
   foncières que la croissance du CA (30 % du poids) : PAS DE NOTE, et c'est le
   résultat attendu, pas un défaut. « P/B COMPTABLE » = cours × actions ÷
   capitaux propres part du groupe. L'ACTIF NET RÉÉVALUÉ (ANR) n'est PAS
   disponible : on ne dit jamais « P/ANR ».
3. TROIS ÉTATS DISTINCTS PARTOUT : ABSENT (la donnée manque : aucune valeur),
   ZÉRO CONFIRMÉ (la pièce dit zéro) et REMPLACEMENT (un indicateur voisin,
   étiqueté). Absent n'est jamais zéro : des minoritaires inconnus ne valent pas
   0 ; une trésorerie nette sans EBITDA ne devient pas « dette/EBITDA = −1 » :
   on constate la CATÉGORIE « trésorerie nette », jamais un multiple.
4. VE/EBITDA n'entre dans la note QUE si dette nette, minoritaires, EBITDA et
   capitalisation sont sur une période et un périmètre cohérents ET vérifiés :
   (a) dette nette, EBITDA et fonds propres (consolidés et part du groupe) datés
   du MÊME exercice ; (b) minoritaires connus (les deux fonds propres existent) ;
   (c) dette nette recoupée avec l'endettement net des faits financiers (écart
   ≤ 2 %) ; (d) nombre d'actions identique dans les deux sources ; (e) aucun
   bilan plus récent (30/06/2026) disponible pour ce titre. Sinon : SUSPENDU,
   avec le motif. Aucun repli décidé au cas par cas. Managem : dette nette
   10 933,2 (ratios) contre endettement net 12 674,0 (faits) — non rapprochable
   sur les données disponibles, donc suspendu. (Le seul constat « EBITDA 2025 <
   RNPG 12 mois » ne prouve rien — périodes, périmètres, exceptionnels — et
   n'est plus avancé.)
5. ROE : UNE SEULE CONVENTION, celle de l'EXERCICE 2025 = RNPG 2025 ÷ fonds
   propres. ÷ moyenne(31/12/2024, 31/12/2025) quand les deux sont structurés ;
   sinon ÷ clôture 31/12/2025, ÉTIQUETÉ par titre. À défaut de ROE d'exercice, le
   ROE 12 mois à fin juin 2026 est un REMPLACEMENT étiqueté. Jamais de mélange
   silencieux. Mesuré au 11/10/2026 : les fonds propres 31/12/2024 ne sont pas
   structurés (cités en texte libre pour 35 titres) : tous les titres sont sur
   la clôture.
6. COMPARAISON À LA COTE ENTIÈRE ≠ SECTORIELLE : faute de 3 pairs, la référence
   est la médiane de toute la cote (hors le titre) ; c'est ÉTIQUETÉ « non
   sectorielle », l'influence est MESURÉE (`dependance_marche` : critères
   concernés, note sans eux, écart) et les POIDS EFFECTIVEMENT UTILISÉS après
   abstentions sont publiés critère par critère.
7. Valorisation RELATIVE : médiane des PAIRS, le titre noté exclu (un titre
   médian qui se comparerait à lui-même obtiendrait 7,0 par construction) ; au
   moins 3 pairs. Écartés des médianes : sans comptes, fonds propres négatifs,
   suspendus.
8. Un critère absent ou suspendu S'ABSTIENT : ses poids passent aux autres ;
   moins de la MOITIÉ du poids disponible : pas de note.

LES PALIERS — aucun n'est inventé
  [G] ceux de `fond_score.py` : rentabilité (écart à 10 %), croissance, dette /
      EBITDA + conversion (épinglés par tests/test_note_sectorielle.py).
  [R] ceux de `note_per_relatif` (calcul fantôme du 30/09) : NON CALIBRÉS.
  Deux usages sans palier sourcé, déclarés : P/B comptable relatif et VE/EBITDA
  relatif (paliers [R]) ; une perte sur 12 mois hors banques vaut 1,5, la note la
  plus basse de la grille de valorisation.
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
    COUT_FONDS_PROPRES_REF, RATIOS_EN_VERIFICATION, ROE_SANS_OBJET, WACC_REF,
    ratio_effectif, roe_effectif,
)

# Poids en points entiers : 0,3 + 0,2 ne vaut pas exactement 0,5, et le seuil
# d'abstention se joue précisément à 50.
POIDS = {"rentabilite": 40, "croissance": 30, "valorisation": 20, "bilan": 10}
SEUIL_POIDS = 50          # moins de la moitié du poids disponible : pas de note
MIN_PAIRS = 3             # médiane de référence : au moins 3 pairs (titre noté exclu)
ECART_DETTE_MAX = 0.02    # dette nette recoupée avec l'endettement net : 2 %

FINANCIERES = ("banque", "assurance", "financement", "paiement")
MOTIF_SANS_COMPTES = "société sans comptes déposés (SANS_COMPTES)"

# Les états d'un critère. Trois comptent dans la note ; deux la laissent.
PRESENT, ZERO, REMPLACEMENT = "present", "zero_confirme", "remplacement"
ABSENT, SUSPENDU = "absent", "suspendu"
ETATS_NOTES = (PRESENT, ZERO, REMPLACEMENT)

LIBELLE_PB = "P/B comptable (cours × actions ÷ capitaux propres part du groupe ; actif net réévalué non disponible)"
LIBELLE_MARCHE = "cote entière — comparaison NON sectorielle"


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


def _piece(sources) -> str | None:
    if isinstance(sources, dict):
        return " ; ".join(f"{k} : {v}" for k, v in sources.items())
    return sources if isinstance(sources, str) else None


def _publie_complet(fiche, sym, cle) -> dict | None:
    """Un ratio par LA porte (`ratio_effectif`), avec sa date et sa pièce, mais
    seulement s'il vient des comptes publiés : la porte retombe sur la saisie,
    cette grille ne la lit pas. Aucun accès direct à la table des ratios
    ailleurs dans ce module."""
    r = ratio_effectif(fiche, sym, cle)
    return r if r and r.get("origine") == "comptes publiés" else None


def _publie(fiche, sym, cle) -> float | None:
    r = _publie_complet(fiche, sym, cle)
    return r["valeur"] if r else None


def _src_ratio(r: dict, cle: str) -> dict:
    return {"fichier": f"fondamentaux.json › ratios publiés › {cle}", "piece": _piece(r.get("sources")),
            "formule": r.get("formule")}


def _roe(sym, fiche, bpa, s1) -> dict | None:
    """ROE de l'EXERCICE 2025 — la convention unique (règle 5).

    Passe par `roe_effectif` (AFM/AGM sans objet, MSA en vérification). Fonds
    propres MOYENS (31/12/2024 et 31/12/2025) si les deux sont structurés ;
    sinon CLÔTURE 31/12/2025, étiqueté. À défaut de ROE d'exercice, le ROE 12
    mois à fin juin 2026 est un REMPLACEMENT étiqueté. Rend
    {"etat", "valeur", "base", "periode", "source"} ou {"etat": SUSPENDU|ABSENT,
    "motif"}.
    """
    if sym in ROE_SANS_OBJET:
        return {"etat": SUSPENDU, "motif": f"ROE sans objet : {ROE_SANS_OBJET[sym]}"}
    if sym in RATIOS_EN_VERIFICATION:
        return {"etat": SUSPENDU, "motif": f"ratios en vérification : {RATIOS_EN_VERIFICATION[sym]}"}
    if roe_effectif(fiche, sym) is None:
        return {"etat": ABSENT, "motif": "aucun ROE calculé sur comptes publiés"}
    r25 = _publie_complet(fiche, sym, "roe_2025")
    if r25 is not None:
        rn = _num((s1 or {}).get("rnpg_exercice_2025"))
        c0 = _num((s1 or {}).get("capitaux_propres_pg_31_12_2024"))
        c1 = _num((s1 or {}).get("capitaux_propres_pg_31_12_2025"))
        if rn is not None and c0 and c1 and c0 > 0 and c1 > 0:
            return {"etat": PRESENT, "valeur": round(rn / ((c0 + c1) / 2) * 100, 2),
                    "base": "RNPG 2025 ÷ fonds propres MOYENS (31/12/2024 et 31/12/2025)",
                    "periode": "exercice 2025", "source": {"fichier": "datasets/resultats_s1_2026.json",
                                                           "piece": (s1 or {}).get("source_capitaux_propres")}}
        return {"etat": PRESENT, "valeur": r25["valeur"],
                "base": "RNPG 2025 ÷ fonds propres de CLÔTURE 31/12/2025 (moyenne indisponible : "
                        "fonds propres 31/12/2024 non structurés)",
                "periode": "exercice 2025", "source": _src_ratio(r25, "roe_2025")}
    r12 = _publie_complet(fiche, sym, "roe_12m")
    if r12 is not None:
        return {"etat": REMPLACEMENT, "valeur": r12["valeur"],
                "base": "REMPLACEMENT : ROE 12 mois à fin juin 2026 ÷ fonds propres de clôture 30/06/2026 "
                        "(ROE d'exercice 2025 indisponible)",
                "periode": "12 mois au 30/06/2026", "source": _src_ratio(r12, "roe_12m")}
    return {"etat": ABSENT, "motif": "aucun ROE calculé sur comptes publiés"}


def _ve_ebitda(sym, fiche, bpa, s1, faits, px) -> dict:
    """VE/EBITDA, ou le motif pour lequel il n'entre pas (règle 4). Pure."""
    s1, faits = s1 or {}, faits or {}
    dn = _publie_complet(fiche, sym, "dette_nette")
    eb = _publie_complet(fiche, sym, "ebitda")
    if dn is None or eb is None:
        return {"etat": ABSENT, "motif": "dette nette ou EBITDA absents des comptes publiés"}
    ebitda, dette = _num(eb.get("valeur")), _num(dn.get("valeur"))
    if not ebitda or ebitda <= 0:
        return {"etat": SUSPENDU, "motif": f"EBITDA non positif ({ebitda})"}
    if not px:
        return {"etat": ABSENT, "motif": "cours absent : pas de capitalisation"}
    exercice = faits.get("exercice")
    date_ex = f"{exercice}-12-31" if exercice else None
    if not (dn.get("date") == eb.get("date") == date_ex):
        return {"etat": SUSPENDU, "motif": (f"périodes différentes : dette nette {dn.get('date')}, EBITDA "
                                            f"{eb.get('date')}, fonds propres {date_ex}")}
    cons, pg = _fait(faits, "capitaux_propres_consolides"), _fait(faits, "capitaux_propres_part_groupe")
    if cons is None or pg is None:
        return {"etat": ABSENT, "motif": "minoritaires inconnus (fonds propres consolidés ou part du groupe "
                                         "absents) : absent n'est pas zéro"}
    mino = round(cons - pg, 6) + 0.0          # + 0.0 : jamais « -0 »
    if mino < -1e-6:
        return {"etat": SUSPENDU, "motif": f"minoritaires négatifs ({mino:g}) : fonds propres incohérents"}
    en = _fait(faits, "endettement_net")
    if en is not None and en != 0 and abs(dette - en) / abs(en) > ECART_DETTE_MAX:
        return {"etat": SUSPENDU, "motif": (f"dette nette {dette:g} (ratios publiés) contredite par l'endettement "
                                            f"net {en:g} (faits financiers) : écart {abs(dette - en) / abs(en):.1%}, "
                                            f"plus de {ECART_DETTE_MAX:.0%}")}
    a_s1, a_fiche = _num(s1.get("actions")), _num((fiche or {}).get("nb_actions"))
    if not a_s1 or not a_fiche:
        return {"etat": ABSENT, "motif": "nombre d'actions non recoupé entre deux sources"}
    if a_s1 != a_fiche:
        return {"etat": SUSPENDU, "motif": f"nombre d'actions discordant : {a_s1:g} contre {a_fiche:g}"}
    if _num(s1.get("capitaux_propres_pg_30_06_2026")) is not None:
        return {"etat": SUSPENDU, "motif": ("un bilan plus récent (30/06/2026) existe pour ce titre ; dette nette "
                                            "et EBITDA datent du 31/12/2025")}
    cap = px * a_s1 / 1e6
    ve = cap + dette + mino
    return {"etat": PRESENT, "minoritaires_etat": ZERO if mino == 0 else PRESENT,
            "valeur": round(ve / ebitda, 2),
            "mesure": (f"VE {ve:.0f} = capitalisation {cap:.0f} + dette nette {dette:g} + minoritaires {mino:g} ; "
                       f"EBITDA {ebitda:g} (MMAD, 31/12/2025)"),
            "periode": "exercice 2025 (bilan au 31/12/2025, cours du jour)", "minoritaires": mino,
            "source": _src_ratio(eb, "ebitda") | {"dette_nette": _src_ratio(dn, "dette_nette")}}


def construire_entree(sym: str, fiche: dict | None, bpa: dict | None, s1: dict | None,
                      faits: dict | None, prix: float | None, pb: float | None, *,
                      sans_comptes: bool = False, suspendu: bool = False) -> dict:
    """Tout ce que la note lit pour UN titre, rassemblé, daté et sourcé. Pure."""
    fiche, bpa, s1, faits = fiche or {}, bpa or {}, s1 or {}, faits or {}
    fam = famille_note(sym)

    fp_vals = [_fait(faits, "capitaux_propres_part_groupe"), _fait(faits, "capitaux_propres_consolides"),
               _num(s1.get("capitaux_propres_pg_31_12_2025")), _num(s1.get("capitaux_propres_pg_30_06_2026"))]
    fp_negatifs = any(v is not None and v <= 0 for v in fp_vals)

    # Deux niveaux. SANS COMPTES : pas de note du tout. Fonds propres négatifs ou
    # titre suspendu : noté sur ce qu'il a, mais écarté des MÉDIANES.
    sans_note = MOTIF_SANS_COMPTES if sans_comptes else None
    hors_mediane = (sans_note or ("fonds propres négatifs" if fp_negatifs else
                                  "titre suspendu : cours non coté" if suspendu else None))

    b12 = _num(bpa.get("bpa_12m"))
    px = _num(prix) if prix and prix > 0 else None

    # Dette nette / fonds propres, à la MÊME date (AFFICHÉ, jamais noté : règle 1).
    dn = _publie_complet(fiche, sym, "dette_nette")
    dette_nette = _num(dn.get("valeur")) if dn else None
    fp_cons, fp_pg = _fait(faits, "capitaux_propres_consolides"), _fait(faits, "capitaux_propres_part_groupe")
    fp_dette, fp_base = (fp_cons, "consolidés") if fp_cons else (fp_pg, "part du groupe")
    gearing = None
    if dette_nette is not None and fp_dette and fp_dette > 0 and (dn or {}).get("date") == "2025-12-31":
        gearing = {"valeur": round(dette_nette / fp_dette, 2),
                   "mesure": f"dette nette {dette_nette:g} ÷ fonds propres {fp_base} {fp_dette:g} MMAD (31/12/2025)",
                   "source": _src_ratio(dn, "dette_nette")}

    s1_ok = bool(fiche.get("source_s1_2026"))
    return {
        "sym": sym, "famille": fam, "sans_note": sans_note, "hors_mediane": hors_mediane, "prix": px,
        "bpa_12m": b12,
        "bpa_source": {"fichier": "bpa.json › bpa_12m", "piece": bpa.get("source_12m"),
                       "periode": f"12 mois au {bpa.get('fin_12m')}" if bpa.get("fin_12m") else None},
        "per": round(px / b12, 2) if px and b12 and b12 > 0 else None,
        "pb": _num(pb) if pb and pb > 0 else None,
        "ve": _ve_ebitda(sym, fiche, bpa, s1, faits, px),
        "roe": _roe(sym, fiche, bpa, s1),
        "roic": _publie_complet(fiche, sym, "roic"),
        "dne": _publie_complet(fiche, sym, "dette_nette_ebitda"),
        "cc": _publie_complet(fiche, sym, "cash_conversion"),
        "dette_nette": dette_nette,
        "dette_nette_ref": dn,
        "gearing": gearing,
        "croissance_bpa": _num(fiche.get("croissance_bpa")) if s1_ok else None,
        "croissance_ca": _num(fiche.get("croissance_ca")) if s1_ok else None,
        "croissance_source": {"fichier": "fondamentaux.json › croissance_bpa, croissance_ca",
                              "piece": fiche.get("source_s1_2026"), "periode": "S1 2026 contre S1 2025"},
        "financiere": str(fiche.get("secteur") or "").startswith(("Banque", "Assurance", "Finance")),
    }


# ───────────────────────────── médianes ─────────────────────────────

def calculer_medianes(entrees: list[dict]) -> dict:
    """Les valeurs de référence par famille et pour la cote, pour chaque ratio.

    {ratio: {"famille": {fam: [(titre, valeur), ...]}, "marche": [(titre, valeur), ...]}}.
    On garde les valeurs ET les titres : la médiane se calcule ensuite SANS le
    titre noté (`_reference`). Écartés : `hors_mediane`. Le VE/EBITDA n'entre
    que s'il a passé les conditions de cohérence (état présent ou zéro).
    """
    def valeur(e, k):
        if k == "per":
            return e["per"]
        if k == "pb":
            return e["pb"]
        return e["ve"].get("valeur") if e["ve"]["etat"] in ETATS_NOTES else None

    out = {}
    for k in ("per", "pb", "ve_ebitda"):
        par_fam, tous = {}, []
        for e in entrees:
            v = valeur(e, k)
            if e["hors_mediane"] or v is None or v <= 0:
                continue
            par_fam.setdefault(e["famille"], []).append((e["sym"], v))
            tous.append((e["sym"], v))
        out[k] = {"famille": par_fam, "marche": tous}
    return out


def _reference(medianes: dict, k: str, fam: str, sym: str, repli_marche: bool = True):
    """(médiane, libellé, détail) des PAIRS du titre `sym`, lui-même exclu.

    Les autres titres de la famille s'ils sont au moins `MIN_PAIRS` ; sinon la
    COTE ENTIÈRE hors le titre (étiquetée non sectorielle) ; sinon rien.
    `détail` = {"type": "famille"|"cote_entiere", "n", "mediane", "pairs_famille"}.
    """
    pairs = [v for t, v in medianes[k]["famille"].get(fam, []) if t != sym]
    if len(pairs) >= MIN_PAIRS:
        m = statistics.median(pairs)
        return m, f"médiane des {len(pairs)} autres titres de la famille « {fam} »", {
            "type": "famille", "n": len(pairs), "mediane": round(m, 3), "pairs_famille": len(pairs)}
    if repli_marche:
        autres = [v for t, v in medianes[k]["marche"] if t != sym]
        if autres:
            m = statistics.median(autres)
            return m, (f"médiane de la COTE ENTIÈRE hors {sym} ({len(autres)} titres) — comparaison NON "
                       f"sectorielle : famille « {fam} » : {len(pairs)} pair(s), moins de {MIN_PAIRS}"), {
                "type": "cote_entiere", "n": len(autres), "mediane": round(m, 3), "pairs_famille": len(pairs)}
    return None, None, None


# ───────────────────────────── la note ─────────────────────────────

def noter(e: dict, medianes: dict, autoriser_cote: bool = True, _mesurer: bool = True) -> dict:
    """Note d'un titre : critères détaillés, note, poids disponible, dépendance à la cote.

    `autoriser_cote=False` interdit toute comparaison à la cote entière : sert à
    MESURER combien de points de note en dépendent (règle 6). Pure.
    """
    fam = e["famille"]
    crit: dict[str, dict] = {}

    def poser(nom, etat, **kw):
        crit[nom] = {"etat": etat, "poids_nominal": POIDS[nom], "poids_effectif": 0.0,
                     "valeur": kw.pop("valeur", None), "mesure": kw.pop("mesure", None),
                     "note": kw.pop("note", None), "motif": kw.pop("motif", None),
                     "source": kw.pop("source", None), "periode": kw.pop("periode", None),
                     "base": kw.pop("base", None), "reference": kw.pop("reference", None), **kw}

    if e["sans_note"]:
        for nom in POIDS:
            poser(nom, SUSPENDU, motif=e["sans_note"])
        return _conclure(e, fam, crit, medianes, autoriser_cote, _mesurer)

    # ── Rentabilité ────────────────────────────────────────────────────────
    sur_roe = fam in FINANCIERES or fam in ("fonciere", "holding", "promoteur")
    roe, roic = e["roe"], e["roic"]
    if sur_roe:
        if fam == "fonciere":
            poser("rentabilite", SUSPENDU,
                  motif="ROE suspendu pour les foncières : il intègre les effets de juste valeur des immeubles, "
                        "comme le BPA exclu de la croissance",
                  valeur=roe.get("valeur") if roe else None,
                  mesure=f"ROE {roe['valeur']:g} % — affiché, non noté" if roe and roe.get("valeur") is not None else None,
                  base=roe.get("base") if roe else None)
        else:
            _poser_roe(poser, roe, "rentabilite")
    elif roic is not None:
        zero = roic["valeur"] == 0
        poser("rentabilite", ZERO if zero else PRESENT, valeur=roic["valeur"],
              mesure=f"ROIC {roic['valeur']:g} % (comptes publiés)", periode=roic.get("date"),
              base=roic.get("base"), source=_src_ratio(roic, "roic"),
              note=note_ecart_rentabilite(roic["valeur"], WACC_REF))
    elif roe is not None and roe["etat"] in ETATS_NOTES:
        _poser_roe(poser, roe, "rentabilite", remplacement_roic=True)
    elif roe is not None and roe["etat"] == SUSPENDU:
        poser("rentabilite", SUSPENDU, motif=roe["motif"])
    else:
        poser("rentabilite", ABSENT, motif="ni ROIC ni ROE calculables sur comptes publiés")

    # ── Croissance ─────────────────────────────────────────────────────────
    cb = None if fam == "fonciere" else e["croissance_bpa"]
    cc_ = e["croissance_ca"]
    g = (cb * 0.6 + cc_ * 0.4) if (cb is not None and cc_ is not None) else (cb if cb is not None else cc_)
    if g is not None:
        poser("croissance", PRESENT,
              valeur=round(g, 2),
              mesure=f"BPA {cb if cb is not None else '—'} % · CA {cc_ if cc_ is not None else '—'} %"
                     + (" (BPA exclu : juste valeur des immeubles)" if fam == "fonciere" else ""),
              note=note_croissance(g), source=e["croissance_source"], periode="S1 2026 contre S1 2025")
    else:
        poser("croissance", ABSENT, motif="croissance non issue des dépôts S1 2026")

    # ── Valorisation ───────────────────────────────────────────────────────
    _valoriser(e, fam, medianes, autoriser_cote, poser)

    # ── Bilan ──────────────────────────────────────────────────────────────
    if fam in FINANCIERES:
        poser("bilan", SUSPENDU, motif="sans objet : la dette est l'activité d'un établissement financier")
    elif fam in ("fonciere", "holding", "promoteur"):
        gr = e["gearing"]
        if gr is None:
            poser("bilan", ABSENT, motif="dette nette / fonds propres non calculable à la même date")
        else:
            poser("bilan", SUSPENDU, valeur=gr["valeur"], mesure=gr["mesure"] + f" = {gr['valeur']:g} — affiché, non noté",
                  source=gr["source"], periode="31/12/2025",
                  motif="aucun barème sourcé pour dette nette / fonds propres : transposer celui de dette "
                        "nette / EBITDA n'est pas justifié")
    else:
        _bilan_industriel(e, poser)

    return _conclure(e, fam, crit, medianes, autoriser_cote, _mesurer)


def _poser_roe(poser, roe, nom, remplacement_roic=False):
    if roe is None or roe["etat"] in (ABSENT, SUSPENDU):
        poser(nom, roe["etat"] if roe else ABSENT, motif=(roe or {}).get("motif", "ROE non calculable"))
        return
    etat = roe["etat"]
    base = roe["base"] + (" — ROE à défaut de ROIC (REMPLACEMENT)" if remplacement_roic else "")
    if remplacement_roic and etat == PRESENT:
        etat = REMPLACEMENT
    poser(nom, ZERO if roe["valeur"] == 0 and etat == PRESENT else etat, valeur=roe["valeur"],
          mesure=f"ROE {roe['valeur']:g} % — {base}", periode=roe["periode"], base=base,
          source=roe["source"], note=note_ecart_rentabilite(roe["valeur"], COUT_FONDS_PROPRES_REF))


def _ref_dict(det, lib):
    return None if det is None else {**det, "libelle": lib}


def _valoriser(e, fam, med, cote, poser):
    def par_per():
        if e["bpa_12m"] is None or e["prix"] is None:
            poser("valorisation", ABSENT, motif="BPA 12 mois ou cours absent")
            return False
        if e["bpa_12m"] <= 0:
            return None
        ref, lib, det = _reference(med, "per", fam, e["sym"], repli_marche=cote)
        if ref is None:
            poser("valorisation", ABSENT, motif="aucune médiane de référence (moins de 3 pairs"
                                                + ("" if cote else ", cote entière interdite") + ")")
            return False
        poser("valorisation", PRESENT, valeur=e["per"],
              mesure=f"PER 12 m {e['per']:.1f} ÷ {lib} = {ref:.1f}", note=note_relatif(e["per"] / ref),
              reference=_ref_dict(det, lib), source=e["bpa_source"], periode=e["bpa_source"]["periode"],
              pb_comptable_affiche=e["pb"])
        return True

    def par_pb(perte=False):
        if e["pb"] is None:
            poser("valorisation", ABSENT, motif="P/B comptable non calculable sur faits sourcés "
                                                "(actif net réévalué non disponible)")
            return
        ref, lib, det = _reference(med, "pb", fam, e["sym"], repli_marche=False)
        if ref is None:
            poser("valorisation", ABSENT, valeur=e["pb"],
                  motif=(f"P/B comptable : moins de {MIN_PAIRS} pairs dans la famille « {fam} » (titre exclu), "
                         "pas de repli sur la cote ; actif net réévalué non disponible"),
                  mesure=f"P/B comptable {e['pb']:.2f} — affiché, non noté")
            return
        poser("valorisation", REMPLACEMENT if perte else PRESENT, valeur=e["pb"],
              mesure=f"P/B comptable {e['pb']:.2f} ÷ {lib} = {ref:.2f}"
                     + (" (résultat 12 mois ≤ 0 : P/B comptable à la place du PER)" if perte else ""),
              note=note_relatif(e["pb"] / ref), reference=_ref_dict(det, lib),
              source={"fichier": "faits_financiers.json (capitaux propres part du groupe) × cours",
                      "piece": "P/B comptable"}, periode="31/12/2025")

    if fam in ("fonciere", "holding"):
        par_pb()
    elif fam == "mines":
        ve = e["ve"]
        if ve["etat"] in ETATS_NOTES:
            ref, lib, det = _reference(med, "ve_ebitda", fam, e["sym"], repli_marche=cote)
            if ref is None:
                poser("valorisation", ABSENT, motif="aucune médiane VE/EBITDA de référence")
            else:
                poser("valorisation", ve["etat"], valeur=ve["valeur"],
                      mesure=f"VE/EBITDA {ve['valeur']:.1f} ({ve['mesure']}) ÷ {lib} = {ref:.1f}",
                      note=note_relatif(ve["valeur"] / ref), reference=_ref_dict(det, lib),
                      source=ve["source"], periode=ve["periode"], minoritaires_etat=ve["minoritaires_etat"])
        else:
            # Règle 4 : jamais de repli vers le PER décidé au cas par cas.
            poser("valorisation", ve["etat"], motif="VE/EBITDA suspendu : " + ve["motif"]
                  if ve["etat"] == SUSPENDU else "VE/EBITDA absent : " + ve["motif"])
    else:
        r = par_per()
        if r is None:                            # résultat 12 mois ≤ 0
            if fam in FINANCIERES:
                par_pb(perte=True)
            else:
                nul = e["bpa_12m"] == 0
                poser("valorisation", ZERO if nul else PRESENT, valeur=e["bpa_12m"],
                      mesure="résultat 12 mois nul (confirmé)" if nul else "perte sur 12 mois",
                      note=1.5, source=e["bpa_source"], periode=e["bpa_source"]["periode"])


def _bilan_industriel(e, poser):
    dne, cc = e["dne"], e["cc"]
    if dne is not None and not (dne["valeur"] == 0 and e["financiere"]):
        v = dne["valeur"]
        poser("bilan", ZERO if v == 0 else PRESENT, valeur=v,
              mesure=f"dette nette / EBITDA {v:g}" + (f" · conversion {cc['valeur']:g} %" if cc else ""),
              note=note_bilan_industriel(v, cc["valeur"] if cc else None),
              source=_src_ratio(dne, "dette_nette_ebitda"), periode=dne.get("date"))
    elif e["dette_nette"] is not None and e["dette_nette"] < 0 and not e["financiere"]:
        # Règle 3 : on constate la CATÉGORIE « trésorerie nette », jamais un
        # multiple (l'EBITDA est inconnu). Le palier [G] « dette nette < 0 »
        # s'applique à la catégorie.
        poser("bilan", REMPLACEMENT, valeur=None,
              mesure=f"trésorerie nette (dette nette {e['dette_nette']:g} MMAD) — EBITDA inconnu, aucun multiple",
              note=note_bilan_industriel(-1.0, cc["valeur"] if cc else None),
              source=_src_ratio(e["dette_nette_ref"], "dette_nette"), periode=e["dette_nette_ref"].get("date"),
              base="catégorie « trésorerie nette » : remplacement du multiple dette nette / EBITDA")
    else:
        poser("bilan", ABSENT, motif="dette nette / EBITDA non calculable (ou sans objet)")


def _conclure(e, fam, crit, medianes, autoriser_cote, mesurer) -> dict:
    comptes = {k: c for k, c in crit.items() if c["etat"] in ETATS_NOTES and c["note"] is not None}
    dispo = sum(c["poids_nominal"] for c in comptes.values())
    for k, c in crit.items():
        c["poids_effectif"] = round(100.0 * c["poids_nominal"] / dispo, 2) if k in comptes and dispo else 0.0
    note = (round(sum(c["poids_nominal"] * c["note"] for c in comptes.values()) / dispo, 2)
            if dispo >= SEUIL_POIDS else None)
    out = {"famille": fam, "note": note, "poids_disponible": dispo, "criteres": crit,
           "composantes": {k: {"mesure": c["mesure"], "note": c["note"], "poids": c["poids_nominal"]}
                           for k, c in comptes.items()},
           "abstentions": {k: (c["motif"] or c["etat"]) for k, c in crit.items() if k not in comptes},
           "motif": (e["sans_note"] if e["sans_note"] else
                     None if note is not None else f"poids disponible {dispo} % < {SEUIL_POIDS} %")}
    if mesurer and autoriser_cote:
        dep = [k for k, c in crit.items() if (c.get("reference") or {}).get("type") == "cote_entiere"]
        sans = noter(e, medianes, autoriser_cote=False, _mesurer=False)
        out["dependance_cote"] = {
            "criteres": dep, "note_sans_cote": sans["note"],
            "ecart_points": (round(note - sans["note"], 2) if note is not None and sans["note"] is not None else None),
            "note_inexistante_sans_cote": bool(dep and note is not None and sans["note"] is None)}
    return out


def noter_univers(titres, prix: dict, pb: dict, fondamentaux: dict, bpa: dict,
                  s1: dict, faits: dict, sans_comptes=(), suspendus=()) -> dict:
    """{sym: résultat de `noter`} pour tous les `titres`. Pure."""
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


# ───────────────────── plancher : panne des SOURCES seulement ─────────────────────

MIN_SOURCES = {"fondamentaux": 60, "bpa": 60, "faits": 50, "s1": 50}   # mesuré le 11/10 : 77, 76, 71, 72
EFFONDREMENT = 0.7        # moins de 70 % des notes du run précédent : effondrement


def problemes_sources(sources: dict, nb_notes: int | None = None, nb_notes_precedent: int | None = None) -> list[str]:
    """Pourquoi la publication de la note par famille doit être REFUSÉE, ou [].

    ⚠️ 11/10/2026 (Abd Moutalib) : on ne bloque QUE sur une panne des sources —
    fichiers de fondamentaux absents, vides, ou effondrés par rapport au run
    précédent — jamais sur l'abstention légitime d'un titre, MASI 1 compris. Un
    MASI 1 sans note est un AVERTISSEMENT expliqué (verifier_seance), pas un
    blocage.
    """
    out = []
    for nom, mini in MIN_SOURCES.items():
        n = len(sources.get(nom) or {})
        if n < mini:
            out.append(f"source « {nom} » absente ou vide : {n} entrées (minimum {mini})")
    if nb_notes is not None and nb_notes_precedent and nb_notes < EFFONDREMENT * nb_notes_precedent:
        out.append(f"notes effondrées : {nb_notes} contre {nb_notes_precedent} au run précédent")
    return out


def masi1_sans_note(titres) -> list[tuple[str, str]]:
    """Les titres du MASI 1 sans note par famille, avec le motif publié. Avertissement."""
    from bvc_config import TICKERS_ACTIFS
    par = {t.get("symbol"): t for t in titres}
    out = []
    for s in TICKERS_ACTIFS:
        nf = (par.get(s) or {}).get("note_fond_metier")
        if nf is not None and nf.get("note") is None:
            out.append((s, nf.get("motif") or "non précisé"))
    return out


def noter_depuis_fichiers(prix_surcharge: dict | None = None, racine: Path = RACINE) -> dict:
    """Note les 80 titres à partir des fichiers publiés : cours et P/B du
    `data.json`, éventuellement surchargés par `prix_surcharge`. Lecture seule."""
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

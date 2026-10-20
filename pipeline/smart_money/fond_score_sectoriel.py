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
   10 933,2 (ratios) contre endettement net 12 674,0 (faits) — RAPPROCHÉ le
   13/10/2026 sur pièce (+ dérivés de couverture 1 707,9 + comptes courants
   d'associés 33,0 = 12 674,1, périmètre déclaré p.68) : plus contesté. ADI et
   Mutandis restent non rapprochables, donc suspendus. (Le seul constat « EBITDA 2025 <
   RNPG 12 mois » ne prouve rien — périodes, périmètres, exceptionnels — et
   n'est plus avancé.)
5. ROE : UNE SEULE CONVENTION, celle de l'EXERCICE 2025 = RNPG 2025 ÷ fonds
   propres part du groupe. ÷ MOYENNE(31/12/2024, 31/12/2025) quand les deux sont
   relevés sur pièce, sur la MÊME base, et sans mouvement de fonds propres hors
   résultat. Sinon ÷ clôture 31/12/2025, ÉTIQUETÉ avec la raison. Contrôles, dans
   l'ordre (`_controle_moyenne`) : fonds propres positifs ; même état financier
   (la ligne citée porte les deux exercices, ou même page, ou même base déclarée) ;
   bases non contradictoires ; RNPG ÷ fonds propres 2025 qui reproduit le ROE
   publié (0,15 pt) ; opération sur le capital de l'exercice
   (`bvc_config.OPERATIONS_SUR_CAPITAL`, sur pièce) — écartée sauf si l'apport
   frais est ≤ 5 % des fonds propres 2024 (SGTM : 100 MMAD, 3,8 %) ; enfin le
   RÉSIDU R = FP2025 − FP2024 − RNPG2025, rapporté aux fonds propres 2024 :
   R > +5 % sans cause au registre = « mouvement de fonds propres hors résultat
   non expliqué » (M2M ; CASH, SOT, TGCC, VCNE et CIH relèvent du registre). WAF n'en fait
   plus partie : son résidu de +10,9 % est l'OCI (p.16) ; hors OCI il vaut −4,5 %.
   Seul un résidu POSITIF compte : un résidu négatif est une distribution de
   dividendes — |R| > 5 % écarterait 40 titres qui distribuent. Pondérer par la
   date n'est pas fait (dates sourcées pour VCNE seulement). À défaut de ROE
   d'exercice, le ROE 12 mois à fin juin 2026 est un REMPLACEMENT étiqueté. Jamais
   de mélange silencieux ; la clôture de référence pour mesurer l'écart est NON
   arrondie (RNPG ÷ fonds propres 2025).
   ASSURANCES (14/10/2026, décision d'Abd) : ROE HORS gains latents — fonds propres
   part du groupe moins la réserve OCI en 2024 comme en 2025, résidu compris
   (`FAMILLES_ROE_HORS_OCI`, réserves sur pièce dans
   `datasets/reserves_oci_assurances.json`) ; les gains latents suivent les marchés,
   pas l'activité (usage des analystes pour les assureurs IFRS 17). Sans réserve
   relevée : ROE avec OCI, étiqueté « OCI non relevé ». Hors assurances : aucun effet.
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
9. GRANDEUR CONTESTÉE ⇒ TOUT CRITÈRE QUI LA CONSOMME EST SUSPENDU (12/10/2026).
   Quand le recoupement d'une grandeur source échoue — dette nette des ratios
   publiés contre endettement net des faits financiers, écart > 2 % — tous les
   critères qui s'en nourrissent sont suspendus, avec le motif : ROIC et dette
   nette / EBITDA (leurs pièces citent la dette nette), VE/EBITDA, dette nette /
   fonds propres. Aucun ne reste noté sur la valeur contestée. Mesuré le 12/10 :
   ADI, MNG, MUT. Le 13/10, MNG est EXPLIQUÉ sur pièce (`endettement_net.
   rapprochement` : éléments cités, somme recalculée ici) et sort de la liste ;
   ADI (écart 58,5, recherche exhaustive vaine) et MUT (écart 161,2) restent
   contestés : on ne choisit pas une grandeur « cohérente » sans la pièce qui
   la fonde. Le ROE ne remplace jamais un ROIC contesté.
   RÈGLE UNIQUE (16/10/2026) : le chiffre de la société est rangé pour tous
   dans `endettement_net` (VCNE ne l'était pas : libre à 18,5 % d'écart quand
   ADI était contesté à 4,5 %) ; un écart > seuil n'est accepté que par des
   postes de la liste admise, chiffrés sur pièce, avec la définition de la
   société citée. Seuil et liste : registre de fond_score.py.
10. REMPLACEMENT D'UNE VALORISATION SUSPENDUE : règle PAR FAMILLE, jamais au cas
   par cas (`REMPLACEMENT_PAR_PER`). Le PER relatif remplace la valorisation
   suspendue d'une famille seulement si (a) le PER est déclaré pertinent pour
   cette famille (aujourd'hui : mines), (b) le BPA 12 mois est VÉRIFIÉ (dépôt
   AMMC cité) avec sa période explicite, (c) des comparables sont identifiés
   (pairs, ou cote entière étiquetée). Sinon : aucune substitution. Le
   remplacement est un état « remplacement », étiqueté.
11. NOTE PARTIELLE : une note où un critère ESSENTIEL (rentabilité ou
   valorisation) est absent ou suspendu est marquée `partielle`, avec la liste
   des critères manquants. Garde-fou (`limiter_signal_partiel`) : elle ne peut
   pas produire un signal plus favorable que celui de la grille actuelle du seul
   fait de la disparition de ce critère.

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
    COUT_FONDS_PROPRES_REF, EXPLICATIONS_ECART_DETTE_ADMISES, RATIOS_EN_VERIFICATION,
    ROE_SANS_OBJET, SEUIL_ECART_DETTE, WACC_REF, ratio_effectif, roe_effectif,
)

# Poids en points entiers : 0,3 + 0,2 ne vaut pas exactement 0,5, et le seuil
# d'abstention se joue précisément à 50.
POIDS = {"rentabilite": 40, "croissance": 30, "valorisation": 20, "bilan": 10}
SEUIL_POIDS = 50          # moins de la moitié du poids disponible : pas de note
MIN_PAIRS = 3             # médiane de référence : au moins 3 pairs (titre noté exclu)
# Dette nette recoupée avec l'endettement net de la société : LE seuil unique,
# défini avec la liste des explications admises dans le registre de fond_score.py.
ECART_DETTE_MAX = SEUIL_ECART_DETTE

FINANCIERES = ("banque", "assurance", "financement", "paiement")

# Règle 10 : familles dont la valorisation suspendue peut être remplacée par le
# PER relatif, et pourquoi le PER y est déclaré pertinent. Une famille absente
# de cette table n'a AUCUN remplacement (foncières et holding : le résultat
# intègre la juste valeur des immeubles, le PER n'y est pas pertinent).
REMPLACEMENT_PAR_PER = {
    "mines": "résultat d'exploitation courant : le PER relatif est lu à défaut de VE/EBITDA admissible",
}
ESSENTIELS = ("rentabilite", "valorisation")
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


def _dette_nette_contestee(dn: dict | None, faits: dict) -> str | None:
    """Le motif pour lequel la dette nette des ratios publiés est CONTESTÉE
    (recoupement échoué avec l'endettement net des faits financiers, > 2 %), ou
    None. Règle 9 : tout critère qui la consomme est alors suspendu."""
    en = _fait(faits, "endettement_net")
    if dn is None or en is None or en == 0:
        return None
    dette = _num(dn.get("valeur"))
    if dette is None or abs(dette - en) / abs(en) <= ECART_DETTE_MAX:
        return None
    if _rapprochement_etabli(dette, en, faits):
        return None
    return (f"grandeur contestée : dette nette {dette:g} (ratios publiés) contredite par l'endettement net "
            f"{en:g} (faits financiers), écart {abs(dette - en) / abs(en):.1%} (> {ECART_DETTE_MAX:.0%}), "
            "non expliqué sur pièce ; tout critère qui la consomme est suspendu")


def _rapprochement_etabli(dette: float, en: float, faits: dict) -> bool:
    """L'écart est-il EXPLIQUÉ sur pièce ? (13/10/2026, règle unique du 16/10)

    Oui seulement si `endettement_net.rapprochement` porte (a) la définition de
    la société citée (`definition_de_la_societe` : page et citation) et (b) des
    éléments chiffrés, chacun nommé par un `poste` de
    EXPLICATIONS_ECART_DETTE_ADMISES, avec sa page et sa citation, dont la somme
    AJOUTÉE à la dette nette retenue redonne l'endettement publié à
    ECART_DETTE_MAX près. La somme est RECALCULÉE ici : le drapeau `etabli` du
    fichier ne suffit pas, et une dette nette qui changerait invalide le
    rapprochement (`dette_nette_base`)."""
    fait = ((faits or {}).get("faits") or {}).get("endettement_net")
    rap = fait.get("rapprochement") if isinstance(fait, dict) else None
    if not isinstance(rap, dict) or rap.get("etabli") is not True:
        return False
    defi = rap.get("definition_de_la_societe")
    if not isinstance(defi, dict) or not isinstance(defi.get("page"), int) or not defi.get("citation"):
        return False
    base = _num(rap.get("dette_nette_base"))
    elements = rap.get("elements")
    if base is None or abs(base - dette) > 0.05 or not isinstance(elements, list) or not elements:
        return False
    total = dette
    for el in elements:
        v = _num(el.get("valeur")) if isinstance(el, dict) else None
        if v is None or not isinstance(el.get("page"), int) or not el.get("citation"):
            return False
        if el.get("poste") not in EXPLICATIONS_ECART_DETTE_ADMISES:
            return False
        total += v
    return abs(total - en) / abs(en) <= ECART_DETTE_MAX


def _consomme_dette_nette(ratio: dict | None) -> bool:
    """Le ratio cite-t-il la dette nette parmi ses pièces (ROIC, dette/EBITDA) ?"""
    src = (ratio or {}).get("sources")
    return isinstance(src, dict) and "dette_nette" in src


def _bpa_verifie(bpa: dict) -> bool:
    """BPA 12 mois vérifié : il existe, sa période est explicite et sa pièce cite
    un dépôt AMMC (règle 10 b)."""
    return bool(bpa.get("bpa_12m") is not None and bpa.get("fin_12m")
                and "ammc" in str(bpa.get("source_12m") or "").lower())


# ⚠️ ROE DES ASSURANCES HORS GAINS LATENTS (OCI) — décision d'Abd Moutalib, 14/10/2026.
# Pour les familles listées ici, le ROE se calcule sur les fonds propres part du groupe MOINS la
# réserve OCI (gains et pertes comptabilisés directement en capitaux propres), en 2024 comme en
# 2025 ; le numérateur reste le RNPG. RAISON : les gains latents d'un assureur suivent les marchés
# (valorisation des placements), pas l'activité d'assurance ; les inclure fait varier le
# dénominateur avec la bourse et dilue le ROE (WAF : 6,86 % avec, 10,05 % sans). C'est l'usage
# des analystes pour les assureurs sous IFRS 17 / IFRS 9. La règle ne s'applique QU'À cette
# famille (banques, foncières, industrie : inchangés). Elle exige la réserve OCI SUR PIÈCE
# (`datasets/reserves_oci_assurances.json`, page et citation) : sans elle, le ROE reste AVEC
# OCI, étiqueté « OCI non relevé » — jamais d'estimation.
FAMILLES_ROE_HORS_OCI = ("assurance",)
# Le résidu de fonds propres se calcule lui aussi HORS OCI : le mouvement des gains latents est
# expliqué, il ne justifie pas d'écarter la moyenne.

SEUIL_RESIDU_FP = 0.05      # résidu de fonds propres (hors résultat) au-delà duquel la moyenne est écartée
SEUIL_APPORT_FP = 0.05      # apport frais d'une opération sur le capital en deçà duquel elle est non significative
SEUIL_EXCEPTIONNEL_FP = 0.05  # dividende exceptionnel à partir duquel la moyenne simple est étiquetée
# Une cause sur pièce est « portée » si le reste |R + D - C| est d'au plus SEUIL_RESIDU_FP des fonds propres 2024.
MARGE_PALIER_ROE = 0.5      # drapeau « proche d'un palier de note » : à moins de 0,5 point d'une frontière
_ECARTS_PALIERS_ROE = (-3, 0, 2, 5, 10, 15)   # frontières de `note_ecart_rentabilite`, écart à la référence


def _chiffres(x) -> str:
    return "".join(ch for ch in str(x) if ch.isdigit())


def _fonds_propres_exercice(faits: dict, s1: dict) -> tuple:
    """(fonds propres 2025, fonds propres 2024) part du groupe : les faits financiers
    d'abord, à défaut les relevés du dépôt S1 (`capitaux_propres_pg_31_12_*`).
    Chaque élément : {"valeur", "page", "base", "note", "meme_base", "origine"} ou None."""
    F = (faits or {}).get("faits") or {}

    def depuis_faits(cle):
        f = F.get(cle)
        if isinstance(f, dict) and _num(f.get("valeur")) is not None:
            return {"valeur": float(f["valeur"]), "page": f.get("page"), "base": f.get("base"), "note": f.get("note"),
                    "valeur_au_rapport": f.get("valeur_au_rapport"), "meme_base": None,
                    "origine": "faits_financiers.json"}
        return None

    def depuis_s1(an):
        v = _num((s1 or {}).get(f"capitaux_propres_pg_31_12_{an}"))
        if v is None:
            return None
        return {"valeur": v, "page": (s1 or {}).get(f"capitaux_propres_pg_31_12_{an}_page"), "base": None,
                "valeur_au_rapport": None,
                "note": (s1 or {}).get(f"source_capitaux_propres_{an}"),
                "meme_base": bool((s1 or {}).get(f"capitaux_propres_pg_31_12_{an}_meme_base")),
                "origine": "datasets/resultats_s1_2026.json"}

    return (depuis_faits("capitaux_propres_part_groupe") or depuis_s1(2025),
            depuis_faits("capitaux_propres_part_groupe_2024") or depuis_s1(2024))


def _meme_etat(cp24f: dict, cp25f: dict) -> bool:
    """Les deux fonds propres viennent-ils du MÊME état financier, sur la même base ?

    On compare la base des CHIFFRES, pas le numéro de page : (a) la ligne citée
    pour 2024 imprime aussi le montant 2025 (les deux exercices sur la même
    ligne : NEJ p.104, BAL p.44), ou (b) les deux sont à la même page, ou (c) le
    relevé déclare expressément la même base (comparatif retraité, CIH)."""
    if cp24f.get("meme_base") or cp25f.get("meme_base"):
        return True
    def entier(v):                       # 132950333.23 → "132950333" (la ligne imprimée ne porte pas les décimales)
        n = _num(v)
        return _chiffres(int(n)) if n is not None else ""

    n24 = _chiffres(cp24f.get("note"))
    v25 = entier(cp25f.get("valeur_au_rapport"))
    v24 = entier(cp24f.get("valeur_au_rapport"))
    if v25 and v24 and v25 in n24 and v24 in n24:
        return True
    return cp24f.get("page") is not None and cp24f.get("page") == cp25f.get("page")


def _dividende_exercice(sym: str, faits: dict | None, exercice: int, calendrier: dict | None) -> dict | None:
    """Le dividende D versé dans l'exercice, en MMAD, AVEC sa pièce — ou None s'il n'est pas connu.

    Deux origines, dans cet ordre :
      1. `bvc_config.DIVIDENDES_VERSES_TABLEAU` : la ligne « Dividendes » du tableau de variation des
         capitaux propres consolidés (part du groupe), page citée. Elle prime : c'est ce qui est sorti
         des fonds propres, y compris un dividende d'avant la cotation (SGTM) ou d'avant un split (MNG).
      2. le calendrier `datasets/dividendes_bvc.json` × `nombre_actions_au_rapport` : les montants
         PAYÉS dans l'année civile de l'exercice, tels que versés (`montant`, pas le montant ajusté du
         split, qui est un montant par action d'aujourd'hui). Un titre PRÉSENT au calendrier sans
         versement dans l'exercice a D = 0 ; un titre ABSENT du calendrier, ou sans nombre d'actions,
         a un D INCONNU (None) : le silence d'un calendrier n'est pas une preuve de non-versement.

    ⚠️ Limite : un dividende versé avant la cotation n'est pas au calendrier (SGTM le montre) ; seul le
    tableau de variation l'établit. Le calendrier ignore aussi un nombre d'actions qui a varié dans
    l'exercice (opérations du registre : TGCC, SOT, CIH, CASH, VCNE jugées avant ce test).

    {"mmad", "origine": "tableau_variation" | "calendrier", "source", "page", "calendrier_mmad",
     "exceptionnels": [{"par_action", "paiement", "mmad"}]}"""
    from bvc_config import DIVIDENDES_VERSES_TABLEAU
    F = (faits or {}).get("faits") or {}
    n = _num((F.get("nombre_actions_au_rapport") or {}).get("valeur"))
    paiements = []
    if calendrier is not None and sym in calendrier:
        paiements = [x for x in calendrier[sym]
                     if str(x.get("paiement") or x.get("detachement") or "")[:4] == str(exercice)]
    cal_mmad = None
    if calendrier is not None and sym in calendrier:
        if not paiements:
            cal_mmad = 0.0
        elif n is not None:
            cal_mmad = round(sum(float(x["montant"]) for x in paiements) * n / 1e6, 3)
    exceptionnels = []
    if n is not None:
        exceptionnels = [{"par_action": float(x["montant"]), "paiement": x.get("paiement"),
                          "mmad": round(float(x["montant"]) * n / 1e6, 3)}
                         for x in paiements if str(x.get("type") or "").lower().startswith("exception")]
    tab = DIVIDENDES_VERSES_TABLEAU.get(sym)
    if tab and tab.get("exercice") == exercice:
        return {"mmad": float(tab["montant_mmad"]), "origine": tab.get("origine", "tableau_variation"), "source": tab["source"],
                "page": tab.get("page"), "calendrier_mmad": cal_mmad, "exceptionnels": exceptionnels}
    if cal_mmad is None:
        return None
    return {"mmad": cal_mmad, "origine": "calendrier",
            "source": ("datasets/dividendes_bvc.json (versements de l'année " + str(exercice) + ") × "
                       + (f"{n:g} actions (faits_financiers.json › nombre_actions_au_rapport)" if paiements
                          else "— aucun versement recensé dans l'exercice")),
            "page": None, "calendrier_mmad": cal_mmad, "exceptionnels": exceptionnels}


def _moyenne_ponderee_exceptionnel(rn: float, cp24: float, cp25: float, exc: dict, exercice: int) -> float | None:
    """ROE sur fonds propres moyens PONDÉRÉS du temps, quand UN dividende exceptionnel a été versé en
    cours d'année. INDICATIF : jamais appliqué à la note. Avant le versement, les fonds propres vont de
    FP2024 à FP2025 + D (la valeur d'avant le versement) ; après, ils valent FP2025. Pondération par
    le nombre de jours : (FP24 + FP25 + D)/2 × (365 − j)/365 + FP25 × j/365, j = jours restants."""
    from datetime import date
    try:
        y, m, d = (int(x) for x in str(exc["paiement"])[:10].split("-"))
        j = (date(exercice, 12, 31) - date(y, m, d)).days
    except (KeyError, ValueError, TypeError):
        return None
    if not 0 <= j <= 365:
        return None
    fp = (cp24 + cp25 + exc["mmad"]) / 2 * (365 - j) / 365 + cp25 * j / 365
    return round(rn / fp * 100, 2) if fp > 0 else None


def _etiquette_exceptionnel(trace: dict, rn, cp24, cp25, dividende: dict | None, exercice: int) -> dict | None:
    """L'étiquette d'un dividende EXCEPTIONNEL significatif versé dans l'exercice, ou None.

    Significatif = au moins `SEUIL_EXCEPTIONNEL_FP` des fonds propres 2024. La moyenne simple est
    conservée (la convention ne change pas) ; la moyenne pondérée du temps est donnée à titre
    INDICATIF, à côté, sans jamais entrer dans la note."""
    if not dividende or not dividende.get("exceptionnels") or rn is None or not cp24 or cp24 <= 0:
        return None
    exc = [e for e in dividende["exceptionnels"] if e["mmad"] / cp24 >= SEUIL_EXCEPTIONNEL_FP]
    if not exc:
        return None
    simple = trace.get("valeur_moyenne")
    pondere = _moyenne_ponderee_exceptionnel(rn, cp24, cp25, exc[0], exercice) if len(exc) == 1 else None
    quoi = " et ".join(f"{e['par_action']:g} DH payé le {_jj_mm_aaaa(e['paiement'])}" for e in exc)
    total = f"{sum(e['mmad'] for e in exc):,.1f}".replace(",", " ").replace(".", ",")
    txt = (f"dividende exceptionnel de {quoi} ({total} MMAD, "
           + f"{sum(e['mmad'] for e in exc) / cp24:.0%} des fonds propres 2024) : moyenne simple "
           + (f"{simple:.2f} %".replace(".", ",") if simple is not None else "n.d.")
           + (f", pondérée ≈ {pondere:.1f} %".replace(".", ",") if pondere is not None else "")
           + " — la pondérée est INDICATIVE, la note lit la moyenne simple")
    return {"etiquette": txt, "exceptionnels": exc, "roe_moyenne_simple": simple, "roe_moyenne_ponderee_indicatif": pondere}


def _n(x) -> str:
    """Un montant en MMAD à pleine précision (3 décimales au plus, zéros inutiles retirés), pour une
    formule que l'on recalcule à la main : `:g` arrondirait à 6 chiffres significatifs."""
    return f"{float(x):.3f}".rstrip("0").rstrip(".")


def _jj_mm_aaaa(iso) -> str:
    s = str(iso or "")[:10]
    return f"{s[8:10]}/{s[5:7]}/{s[:4]}" if len(s) == 10 else s


def _frontiere_roe(valeur: float) -> dict | None:
    """Le palier de note de rentabilité le plus proche, s'il est à moins de `MARGE_PALIER_ROE` points.

    La note de rentabilité est une grille à paliers (`note_ecart_rentabilite`) : un ROE à 0,35 point
    d'une frontière peut changer de note sur une révision d'un chiffre, un arrondi ou le choix de
    la convention. Le drapeau le dit AVANT que la note ne bascule."""
    proche = min((COUT_FONDS_PROPRES_REF + s for s in _ECARTS_PALIERS_ROE),
                 key=lambda seuil: abs(valeur - seuil))
    ecart = round(valeur - proche, 2)
    if abs(ecart) > MARGE_PALIER_ROE:
        return None
    haut = note_ecart_rentabilite(proche, COUT_FONDS_PROPRES_REF)
    bas = note_ecart_rentabilite(proche - 0.001, COUT_FONDS_PROPRES_REF)
    return {"seuil": proche, "ecart_points": ecart, "cote": "au-dessus" if ecart >= 0 else "en dessous",
            "note_au_dessus": haut, "note_en_dessous": bas,
            "etiquette": (f"à {abs(ecart):.2f} point du seuil de {proche:g} % ({'au-dessus' if ecart >= 0 else 'en dessous'} ; "
                          f"la note de rentabilité passe de {haut:g} à {bas:g} de l'autre côté)").replace(".", ",")}


def _controle_moyenne(sym, r25, rn, cp24f, cp25f, exercice, oci25: float = 0.0, oci24: float = 0.0,
                      dividende: dict | None = None) -> dict:
    """Verdict de la moyenne des fonds propres. Pure.

    {"code": None | motif, "motif": texte, "residu_mmad", "residu_pct" (AVANT dividende),
    "residu_apres_dividende_mmad/pct", "dividende", "cause", "operation": entrée du registre ou None,
    "non_significative": bool}. `code` None = la moyenne s'applique.
    Les codes : fonds_propres_non_positifs, base_non_confirmee, bases_contradictoires,
    numerateur_non_reproduit, registre_operation_capital, residu_cause_sur_piece, residu_non_explique.

    RÉSIDU APRÈS DIVIDENDE (14/10/2026). R = FP2025 − FP2024 − RNPG2025 contient le dividende versé
    (négatif) : une banque qui distribue 50 % de son résultat montre un R de −5 à −15 %, normal. Le test
    porte donc sur R + D (D = dividende de l'exercice, `_dividende_exercice`, avec sa pièce) :
    |R + D| > 5 % des fonds propres 2024 = un mouvement de fonds propres qui n'est NI du résultat NI
    un dividende, dans les DEUX sens (une perte de périmètre ou un retraitement écarte la moyenne
    comme un apport de capital). La cause, quand le rapport la nomme, est portée au registre
    `CAUSES_RESIDU_FONDS_PROPRES` (code `residu_cause_sur_piece`) à une condition, le TEST DU RESTE :
    |R + D − C| ≤ 5 % des fonds propres 2024 (C = montant de la cause), jugé sur UNE SEULE BASE — les
    fonds propres et le résultat du tableau de variation où se lit C (`tableau` du registre), jamais
    ceux du bilan mêlés à un C du tableau (BCP : 41 452 MMAD au tableau, 36 975 au bilan). Sinon
    l'étiquette dit « non expliqué ». Quand D est INCONNU, le test historique reste en vigueur — résidu POSITIF > 5 % seul —
    et le verdict le dit (`dividende` = None, mention dans `motif` et dans la base).
    """
    from bvc_config import CAUSES_RESIDU_FONDS_PROPRES, OPERATIONS_SUR_CAPITAL
    # Fonds propres HORS OCI pour une assurance (`oci25` = `oci24` = 0 ailleurs) : positivité, apport
    # frais et résidu se jugent sur ces fonds propres ; « même état » et reproduction du ROE publié
    # se jugent sur les montants imprimés.
    cp24, cp25 = cp24f["valeur"] - oci24, cp25f["valeur"] - oci25
    r = {"code": None, "motif": None, "residu_mmad": None, "residu_pct": None, "operation": None,
         "non_significative": False, "dividende": None, "residu_apres_dividende_mmad": None,
         "residu_apres_dividende_pct": None, "cause": None}
    if cp24 <= 0 or cp25 <= 0:
        return r | {"code": "fonds_propres_non_positifs",
                    "motif": f"fonds propres négatifs ou nuls ({cp24:g} ; {cp25:g})"}
    # Résidu de fonds propres hors résultat : R = FP2025 − FP2024 − RNPG2025. Il contient le dividende
    # (négatif) : le verdict porte sur R + D (voir la docstring), pas sur R.
    resid = cp25 - cp24 - rn
    r["residu_mmad"], r["residu_pct"] = round(resid, 3), round(resid / cp24 * 100, 2)
    if not _meme_etat(cp24f, cp25f):
        return r | {"code": "base_non_confirmee",
                    "motif": "base 2024 non confirmée identique : ni la ligne citée ne porte les deux exercices, "
                             f"ni la page (2025 p.{cp25f.get('page')}, 2024 p.{cp24f.get('page')}), "
                             "ni une déclaration de même base"}
    b25 = str(cp25f.get("base") or "").lower()
    b_roe = str(r25.get("base") or "").lower()
    if b25 and b_roe and (("social" in b25) != ("social" in b_roe)):
        return r | {"code": "bases_contradictoires",
                    "motif": f"bases différentes : fonds propres « {cp25f.get('base')} », ROE « {r25.get('base')} »"}
    # Le numérateur doit reproduire le ROE publié sur les fonds propres 2025 (écart ≤ 0,15 pt,
    # le ROE publié est arrondi à 0,1) : sinon résultat et fonds propres ne sont pas sur la même base.
    cp25_imprime = cp25f["valeur"]
    if abs(rn / cp25_imprime * 100 - r25["valeur"]) > 0.15:
        return r | {"code": "numerateur_non_reproduit",
                    "motif": f"RNPG {rn:g} ÷ fonds propres {cp25_imprime:g} = {rn / cp25_imprime * 100:.2f} % ne reproduit "
                             f"pas le ROE publié {r25['valeur']:g} %"}
    op = OPERATIONS_SUR_CAPITAL.get(sym)
    if op and op.get("exercice") == exercice:
        r["operation"] = op
        apport = op.get("apport_frais_mmad")
        if apport is not None and apport / cp24 <= SEUIL_APPORT_FP:
            r["non_significative"] = True      # apport frais ≤ 5 % des fonds propres 2024 : la moyenne tient
        else:
            return r | {"code": "registre_operation_capital",
                        "motif": "opération sur le capital dans l'exercice (registre) : " + op["nature"]
                                 + (f" — apport frais {apport:g} MMAD = {apport / cp24:.1%} des fonds propres 2024"
                                    if apport is not None else " — apport frais non relevé")}
    if dividende is None:
        # D inconnu : on ne peut pas dire si un résidu négatif est un dividende. Le test d'avant (résidu
        # POSITIF seul : il est entré des fonds propres qui ne sont pas du résultat) est conservé, et dit.
        r["dividende"] = None
        if resid / cp24 > SEUIL_RESIDU_FP:
            return r | {"code": "residu_non_explique",
                        "motif": (f"mouvement de fonds propres hors résultat non expliqué : résidu R = FP2025 − FP2024 − "
                                  f"RNPG2025 = {resid:g} MMAD, +{resid / cp24:.1%} des fonds propres 2024 "
                                  f"(seuil {SEUIL_RESIDU_FP:.0%}), cause absente du registre ; dividende de l'exercice "
                                  f"non relevé : test limité au résidu positif")}
        return r
    apres = resid + dividende["mmad"]
    r["dividende"] = dividende
    r["residu_apres_dividende_mmad"], r["residu_apres_dividende_pct"] = round(apres, 3), round(apres / cp24 * 100, 2)
    if abs(apres) / cp24 <= SEUIL_RESIDU_FP:
        return r
    cause = CAUSES_RESIDU_FONDS_PROPRES.get(sym)
    if cause and cause.get("exercice") != exercice:
        cause = None
    detail = (f"résidu après dividende R + D = {resid:g} + {dividende['mmad']:g} = {apres:g} MMAD, "
              f"{apres / cp24:+.1%} des fonds propres 2024 (seuil ±{SEUIL_RESIDU_FP:.0%} ; dividende "
              f"{dividende['origine'].replace('_', ' ')}"
              + (f", p.{dividende['page']}" if dividende.get("page") else "") + ")")
    if cause:
        # Le reste, sur UNE base : celle du tableau de variation si le registre la donne.
        tb = cause.get("tableau")
        if tb:
            r_base = tb["fonds_propres_2025"] - tb["fonds_propres_2024"] - tb["rnpg"]
            fp24_base, base = tb["fonds_propres_2024"], f"tableau de variation p.{tb['page']}"
        else:
            r_base, fp24_base, base = resid, cp24, "fonds propres de la note (bilan)"
        reste = r_base + dividende["mmad"] - cause["montant_mmad"]
        r["cause"] = cause | {"base_du_reste": base, "residu_sur_cette_base_mmad": round(r_base, 3),
                              "reste_mmad": round(reste, 3), "reste_pct": round(reste / fp24_base * 100, 2)}
        if abs(reste) / fp24_base <= SEUIL_RESIDU_FP:
            return r | {"code": "residu_cause_sur_piece",
                        "motif": (f"mouvement de fonds propres hors résultat et hors dividende, cause portée sur pièce : "
                                  f"{cause['libelle']} {cause['montant_mmad']:g} MMAD (p.{cause['page']}) ; reste "
                                  f"R + D − C = {r_base:g} + {dividende['mmad']:g} − ({cause['montant_mmad']:g}) = {reste:.3f} MMAD, "
                                  f"{reste / fp24_base:+.2%} des fonds propres 2024 (base : {base} ; seuil ±{SEUIL_RESIDU_FP:.0%}) "
                                  f"— {detail}")}
    return r | {"code": "residu_non_explique",
                "motif": ("mouvement hors résultat et hors dividende non expliqué : " + detail
                          + (f" ; la cause inscrite au registre ({cause['libelle']} {cause['montant_mmad']:g} MMAD) laisse un reste de "
                             f"{r['cause']['reste_mmad']:g} MMAD ({r['cause']['reste_pct']:+.2f} %, base : {r['cause']['base_du_reste']}) "
                             f"au-delà de ±{SEUIL_RESIDU_FP:.0%} : elle ne l'explique pas" if cause else
                             " ; cause absente du registre"))}


def _reserves_oci(sym: str, oci: dict | None) -> dict:
    """La réserve OCI (gains latents) d'une assurance, sur pièce, ou l'état « non relevé ».

    {"applicable", "etat": "releve" | "non_releve" | "non_applicable", "oci25", "oci24",
     "pieces": {...}}. Hors des familles de `FAMILLES_ROE_HORS_OCI` : non applicable, quoi
    que contienne le fichier. Une réserve n'est lue que PRÉSENTE ou NULLE CONFIRMÉE (jamais estimée)."""
    if famille_note(sym) not in FAMILLES_ROE_HORS_OCI:
        return {"applicable": False, "etat": "non_applicable", "oci25": None, "oci24": None, "pieces": {}}
    ro = ((oci or {}).get(sym) or {}).get("reserve_oci") or {}
    o25, o24 = ro.get("2025"), ro.get("2024")
    ok = all(isinstance(o, dict) and o.get("etat") in ("present", "zero_confirme") and _num(o.get("valeur")) is not None
             for o in (o25, o24))
    if not ok:
        return {"applicable": True, "etat": "non_releve", "oci25": None, "oci24": None, "pieces": {}}
    return {"applicable": True, "etat": "releve", "oci25": float(o25["valeur"]), "oci24": float(o24["valeur"]),
            "pieces": {"2025": f"p.{o25.get('page')} — {o25.get('citation')}", "2024": f"p.{o24.get('page')} — {o24.get('citation')}",
                       "etats": {"2025": o25["etat"], "2024": o24["etat"]}}}


def _roe(sym, fiche, bpa, s1, faits=None, moyenne=True, oci=None, dividendes=None) -> dict | None:
    """ROE de l'EXERCICE 2025 — la convention unique (règle 5).

    Passe par `roe_effectif` (AFM/AGM sans objet, MSA en vérification).
    ROE = RNPG 2025 ÷ MOYENNE(fonds propres part du groupe 31/12/2024,
    31/12/2025) quand les deux sont relevés sur pièce, sur la MÊME base et sans
    mouvement de fonds propres hors résultat (`_controle_moyenne`) ; sinon
    ÷ CLÔTURE 31/12/2025, ÉTIQUETÉ avec la raison (`convention` :
    moyenne | cloture_moyenne_ecartee | cloture_moyenne_indisponible). À défaut de
    ROE d'exercice, le ROE 12 mois à fin juin 2026 est un REMPLACEMENT étiqueté.
    `moyenne=False` force la clôture (mesure de l'effet de la convention).

    ASSURANCES (`FAMILLES_ROE_HORS_OCI`) : les fonds propres sont pris MOINS la réserve OCI,
    en 2024 comme en 2025 (voir la constante) ; le résidu aussi. Sans réserve relevée sur
    pièce, le ROE reste AVEC OCI, étiqueté « OCI non relevé ».

    ⚠️ ATL et WAF NE SE COMPARENT PAS TERME À TERME. ATL (Atlanta-Sanad) publie en NORMES MAROCAINES :
    ses plus-values latentes sur placements sont HORS BILAN (annexes), la réserve OCI est nulle parce
    qu'il n'existe pas de compte de gains latents aux fonds propres. WAF (Wafa Assurance) publie en
    IFRS 17 / IFRS 9 : les placements en juste valeur par OCI alimentent une réserve consolidée
    (4,7 Md MAD de gains latents en 2025, soit 4 747 MMAD). Retrancher l'OCI de WAF et rien chez ATL met les deux sur la
    même définition des fonds propres COMPTABLES hors gains latents, mais PAS sur la même réalité
    économique : les plus-values latentes d'ATL existent, elles sont ailleurs. L'OCI d'assurance
    consolidé d'ATW (Attijariwafa, banque-assurance) RESTE INCLUS : la règle se limite à la famille
    « assurance » (`FAMILLES_ROE_HORS_OCI`). Le livrable porte la même note.

    TROIS TRAITEMENTS DE L'OCI, ET POURQUOI (14/10/2026) :
      · ASSURANCES (WAF, ATL, SAF) : l'OCI est RETIRÉ des fonds propres. Il mesure la valorisation des
        placements en juste valeur, pas l'activité d'assurance ; il varie avec la bourse et dilue le
        ROE (WAF : 6,86 % avec, 10,05 % sans). Décision d'Abd Moutalib, usage des analystes d'assureurs.
      · ATW (banque-assurance) : l'OCI consolidé est CONSERVÉ. ATW est notée en famille « banque » ;
        la décision d'Abd limite le retrait aux assureurs. Mesure : son résidu après dividende est de
        +0,7 % des fonds propres 2024, l'OCI ne perturbe donc pas sa moyenne.
      · MNG (mines) : l'OCI n'est pas retranché, mais SA VARIATION ÉCARTE LA MOYENNE : −1 747 MMAD
        (couverture de flux de trésorerie, conversion), soit −16 % des fonds propres 2024, hors résultat
        et hors dividende, cause portée sur pièce. Les fonds propres moyens de deux clôtures ne
        représenteraient pas les fonds propres employés dans l'année ; la clôture est lue, étiquetée.

    DIVIDENDE (14/10/2026). Le verdict de la moyenne porte sur le résidu APRÈS dividende (voir
    `_controle_moyenne`). Un dividende EXCEPTIONNEL de plus de 5 % des fonds propres 2024 versé dans
    l'année fausse la moyenne simple (les fonds propres moyens de l'année sont plus bas que la moyenne
    des deux clôtures) : la moyenne simple est conservée MAIS étiquetée, avec la moyenne pondérée du
    temps à titre INDICATIF (TMA : 67 DH le 11/12/2025, moyenne simple 35,98 %, pondérée ≈ 32,4 %).

    TRAÇABILITÉ : `valeur_cloture_publiee` (ROE publié, arrondi à 0,1, avec OCI),
    `valeur_cloture_non_arrondie` (RNPG ÷ fonds propres 2025 sur la base retenue, sans arrondi —
    contre elle se mesure l'écart de la moyenne), `valeur_moyenne` (calculée même si écartée),
    résidu, pages ; pour une assurance, les quatre ROE avec et sans OCI.
    """
    if sym in ROE_SANS_OBJET:
        return {"etat": SUSPENDU, "motif": f"ROE sans objet : {ROE_SANS_OBJET[sym]}"}
    if sym in RATIOS_EN_VERIFICATION:
        return {"etat": SUSPENDU, "motif": f"ratios en vérification : {RATIOS_EN_VERIFICATION[sym]}"}
    if roe_effectif(fiche, sym) is None:
        return {"etat": ABSENT, "motif": "aucun ROE calculé sur comptes publiés"}
    r25 = _publie_complet(fiche, sym, "roe_2025")
    if r25 is not None:
        faits = faits or {}
        rn = _num((s1 or {}).get("rnpg_exercice_2025"))
        cp25f, cp24f = _fonds_propres_exercice(faits, s1)
        ro = _reserves_oci(sym, oci)
        # Hors OCI seulement si la réserve est relevée ET que le calcul est possible (RNPG et fonds propres 2025).
        hors_oci = ro["etat"] == "releve" and rn is not None and cp25f is not None
        o25, o24 = (ro["oci25"], ro["oci24"]) if hors_oci else (0.0, 0.0)
        src = _src_ratio(r25, "roe_2025")
        cp25x = cp25f["valeur"] - o25 if cp25f else None
        cp24x = cp24f["valeur"] - o24 if cp24f else None
        nulle = hors_oci and all(v == "zero_confirme" for v in ro["pieces"]["etats"].values())
        suffixe_oci = ((" — HORS gains latents (OCI) : réserve OCI NULLE confirmée sur pièce en 2024 et 2025 (aucune ligne "
                        "de gains latents aux fonds propres consolidés)" if nulle else
                        " — HORS gains latents (OCI) : fonds propres part du groupe moins la réserve OCI (2025 "
                        f"{o25:g} ; 2024 {o24:g})") if hors_oci else
                       " — AVEC gains latents : OCI non relevé" if ro["applicable"] else "")
        base_cloture = ("RNPG 2025 ÷ fonds propres de CLÔTURE 31/12/2025" + (" hors OCI" if hors_oci else ""))
        trace = {"valeur_cloture_publiee": r25["valeur"],
                 "valeur_cloture_non_arrondie": round(rn / cp25x * 100, 4) if rn is not None and cp25x and cp25x > 0 else None,
                 "valeur_moyenne": (round(rn / ((cp24x + cp25x) / 2) * 100, 2)
                                    if rn is not None and cp24x is not None and cp25x is not None and cp24x + cp25x > 0 else None),
                 "page_2025": (cp25f or {}).get("page"), "page_2024": (cp24f or {}).get("page"),
                 "fonds_propres_2025": (cp25f or {}).get("valeur"), "fonds_propres_2024": (cp24f or {}).get("valeur"),
                 "rnpg_2025": rn, "residu_mmad": None, "residu_pct": None, "moyenne_code": None,
                 "oci": {"applicable": ro["applicable"], "etat": ro["etat"], "reserve_2025": ro["oci25"],
                         "reserve_2024": ro["oci24"], "pieces": ro["pieces"],
                         "etiquette": ("hors OCI" if hors_oci else "OCI non relevé" if ro["applicable"] else None)}}
        if ro["applicable"] and cp25f and rn is not None:
            # Les quatre ROE d'une assurance, avec et sans gains latents (aucun choix caché).
            avec_c = rn / cp25f["valeur"] * 100 if cp25f["valeur"] > 0 else None
            avec_m = (rn / ((cp24f["valeur"] + cp25f["valeur"]) / 2) * 100) if cp24f else None
            sans_c = rn / (cp25f["valeur"] - ro["oci25"]) * 100 if ro["etat"] == "releve" else None
            sans_m = (rn / ((cp24f["valeur"] + cp25f["valeur"] - ro["oci24"] - ro["oci25"]) / 2) * 100
                      if ro["etat"] == "releve" and cp24f else None)
            trace["oci"] |= {"roe_avec_oci": {"cloture": round(avec_c, 2) if avec_c is not None else None,
                                              "moyenne": round(avec_m, 2) if avec_m is not None else None},
                             "roe_hors_oci": {"cloture": round(sans_c, 2) if sans_c is not None else None,
                                              "moyenne": round(sans_m, 2) if sans_m is not None else None}}
        if not moyenne:
            motif, genre = "moyenne non demandée", "cloture_moyenne_indisponible"
        elif cp24f is None or cp25f is None or rn is None:
            manque = ("fonds propres 31/12/2024 non relevés" if cp24f is None else
                      "fonds propres 31/12/2025 non relevés" if cp25f is None else "RNPG 2025 non relevé")
            motif, genre = manque, "cloture_moyenne_indisponible"
        else:
            exercice = faits.get("exercice") or 2025
            div = _dividende_exercice(sym, faits, exercice, dividendes)
            ctl = _controle_moyenne(sym, r25, rn, cp24f, cp25f, exercice, o25, o24, div)
            trace |= {"residu_mmad": ctl["residu_mmad"], "residu_pct": ctl["residu_pct"], "moyenne_code": ctl["code"],
                      "residu_apres_dividende_mmad": ctl["residu_apres_dividende_mmad"],
                      "residu_apres_dividende_pct": ctl["residu_apres_dividende_pct"],
                      "dividende": div, "cause_residu": ctl["cause"]}
            motif = ctl["motif"]
            genre = "cloture_moyenne_ecartee" if ctl["code"] else "moyenne"
        div_inconnu = (" ; dividende de l'exercice non relevé : résidu jugé sur son seul sens positif"
                       if moyenne and cp24f is not None and cp25f is not None and rn is not None
                       and trace.get("dividende") is None else "")
        if genre == "moyenne":
            cp24, cp25 = cp24f["valeur"], cp25f["valeur"]
            non_signif = (" ; opération sur le capital de l'exercice NON SIGNIFICATIVE (apport frais ≤ "
                          f"{SEUIL_APPORT_FP:.0%} des fonds propres 2024), moyenne conservée" if ctl["non_significative"] else "")
            exc = _etiquette_exceptionnel(trace, rn, cp24x, cp25x, trace.get("dividende"), faits.get("exercice") or 2025)
            trace |= {"dividende_exceptionnel": exc,
                      "formule": (f"{_n(rn)} ÷ moyenne({_n(cp24)}" + (f" − {_n(o24)}" if hors_oci else "") + f" ; {_n(cp25)}"
                                  + (f" − {_n(o25)}" if hors_oci else "") + ")")}
            out = trace | {
                "etat": PRESENT, "valeur": trace["valeur_moyenne"], "convention": genre,
                "base": (f"RNPG 2025 {rn:g} ÷ MOYENNE des fonds propres part du groupe (31/12/2024 {cp24:g} ; "
                         f"31/12/2025 {cp25:g}), même état financier{suffixe_oci}{non_signif}{div_inconnu}"
                         + (f" — {exc['etiquette']}" if exc else "")),
                "periode": "exercice 2025",
                "source": src | {"formule": trace["formule"], "formule_roe_publie": src.get("formule"),
                                 "fonds_propres_2024": (f"{cp24f['origine']} › fonds propres 31/12/2024"
                                                        + (f" (p.{cp24f['page']})" if cp24f.get("page") else "")),
                                 "rnpg_2025": "datasets/resultats_s1_2026.json › rnpg_exercice_2025"}
                          | ({"reserve_oci": ro["pieces"]} if hors_oci else {}),
                "moyenne_ecartee": None}
        else:
            etiquette = "moyenne écartée" if genre == "cloture_moyenne_ecartee" else "moyenne indisponible"
            valeur_cloture = trace["valeur_cloture_non_arrondie"] if hors_oci and trace["valeur_cloture_non_arrondie"] is not None else r25["valeur"]
            trace |= {"dividende_exceptionnel": None,
                      "formule": (f"{_n(rn)} ÷ ({_n(cp25f['valeur'])}" + (f" − {_n(o25)}" if hors_oci else "") + ")"
                                  if rn is not None and cp25f else None)}
            out = trace | {"etat": PRESENT, "valeur": round(valeur_cloture, 2) if hors_oci else valeur_cloture, "convention": genre,
                           "base": f"{base_cloture} ({etiquette} : {motif}){suffixe_oci}", "periode": "exercice 2025",
                           "source": src | ({"formule": trace["formule"], "formule_roe_publie": src.get("formule")}
                                            if trace["formule"] else {})
                                     | ({"reserve_oci": ro["pieces"]} if hors_oci else {}),
                           "moyenne_ecartee": motif}
        front = _frontiere_roe(out["valeur"])
        return out | {"frontiere_palier": front}
    r12 = _publie_complet(fiche, sym, "roe_12m")
    if r12 is not None:
        return {"etat": REMPLACEMENT, "valeur": r12["valeur"], "convention": "remplacement_12m",
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
    contestee = _dette_nette_contestee(dn, faits)
    if contestee:
        return {"etat": SUSPENDU, "motif": contestee}
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
                      sans_comptes: bool = False, suspendu: bool = False,
                      roe_moyenne: bool = True, oci: dict | None = None,
                      dividendes: dict | None = None) -> dict:
    """Tout ce que la note lit pour UN titre, rassemblé, daté et sourcé. Pure.

    `roe_moyenne=False` force le ROE sur la clôture (mesure de l'effet de la
    convention des fonds propres moyens)."""
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
        "roe": _roe(sym, fiche, bpa, s1, faits, roe_moyenne, oci, dividendes),
        "roic": _publie_complet(fiche, sym, "roic"),
        "dne": _publie_complet(fiche, sym, "dette_nette_ebitda"),
        "cc": _publie_complet(fiche, sym, "cash_conversion"),
        "dette_nette": dette_nette,
        "dette_nette_ref": dn,
        "dette_nette_contestee": _dette_nette_contestee(dn, faits),
        "bpa_verifie": _bpa_verifie(bpa),
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
    elif roic is not None and e["dette_nette_contestee"] and _consomme_dette_nette(roic):
        # Règle 9 : le ROIC consomme la dette nette contestée ; le ROE ne le remplace pas.
        poser("rentabilite", SUSPENDU, valeur=roic["valeur"],
              mesure=f"ROIC {roic['valeur']:g} % — affiché, non noté", motif="ROIC suspendu — " + e["dette_nette_contestee"],
              source=_src_ratio(roic, "roic"), periode=roic.get("date"))
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
                        "nette / EBITDA n'est pas justifié"
                        + (" ; de plus, " + e["dette_nette_contestee"] if e["dette_nette_contestee"] else ""))
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
          source=roe["source"], note=note_ecart_rentabilite(roe["valeur"], COUT_FONDS_PROPRES_REF),
          convention=roe.get("convention"), moyenne_ecartee=roe.get("moyenne_ecartee"),
          formule=roe.get("formule"), drapeau_palier=(roe.get("frontiere_palier") or {}).get("etiquette"))


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
            # Règle 4 : jamais de repli décidé au cas par cas. Règle 10 : le PER
            # remplace la valorisation suspendue seulement par règle de FAMILLE.
            motif_ve = ("VE/EBITDA suspendu : " if ve["etat"] == SUSPENDU else "VE/EBITDA absent : ") + ve["motif"]
            _remplacer_par_per(e, fam, med, cote, poser, ve["etat"], motif_ve)
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


def _remplacer_par_per(e, fam, med, cote, poser, etat_initial, motif_initial):
    """Règle 10 : remplacement de la valorisation suspendue par le PER relatif,
    défini PAR FAMILLE (`REMPLACEMENT_PAR_PER`), jamais pour un seul titre."""
    refus = None
    if fam not in REMPLACEMENT_PAR_PER:
        refus = f"PER non déclaré pertinent en remplacement pour la famille « {fam} »"
    elif not e["bpa_verifie"]:
        refus = "BPA 12 mois non vérifié (dépôt AMMC cité et période explicite requis)"
    elif e["bpa_12m"] is None or e["prix"] is None or e["bpa_12m"] <= 0:
        refus = "PER non défini (BPA 12 mois absent, nul ou négatif)"
    else:
        ref, lib, det = _reference(med, "per", fam, e["sym"], repli_marche=cote)
        if ref is None:
            refus = "aucun comparable identifié (moins de 3 pairs, cote entière indisponible)"
    if refus:
        poser("valorisation", etat_initial, motif=motif_initial + " ; aucun remplacement : " + refus)
        return
    poser("valorisation", REMPLACEMENT, valeur=e["per"],
          mesure=(f"PER 12 m {e['per']:.1f} ÷ {lib} = {ref:.1f} — REMPLACEMENT du VE/EBITDA "
                  f"({motif_initial}) ; règle de famille « {fam} » : {REMPLACEMENT_PAR_PER[fam]}"),
          note=note_relatif(e["per"] / ref), reference=_ref_dict(det, lib), source=e["bpa_source"],
          periode=e["bpa_source"]["periode"], pb_comptable_affiche=e["pb"],
          base="PER 12 mois ; BPA vérifié (dépôt AMMC), période explicite")


def _bilan_industriel(e, poser):
    dne, cc = e["dne"], e["cc"]
    if e["dette_nette_contestee"] and ((dne is not None and _consomme_dette_nette(dne))
                                       or (dne is None and e["dette_nette"] is not None)):
        # Règle 9 : dette nette / EBITDA (ou la catégorie trésorerie nette) consomme la dette nette contestée.
        poser("bilan", SUSPENDU, valeur=dne["valeur"] if dne else None,
              mesure=(f"dette nette / EBITDA {dne['valeur']:g} — affiché, non noté" if dne else None),
              motif="dette nette / EBITDA suspendu — " + e["dette_nette_contestee"])
    elif dne is not None and not (dne["valeur"] == 0 and e["financiere"]):
        v = dne["valeur"]
        poser("bilan", ZERO if v == 0 else PRESENT, valeur=v,
              mesure=(f"dette nette / EBITDA {'≤ ' if dne.get('borne') else ''}{v:g}"
                      + (" (borne, pas une valeur)" if dne.get("borne") else "")   # règle h, 20/10/2026
                      + (f" · conversion {cc['valeur']:g} %" if cc else "")),
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
    # Règle 11 : note PARTIELLE si un critère essentiel manque (absent ou suspendu).
    manquants = [k for k in ESSENTIELS if crit[k]["etat"] in (ABSENT, SUSPENDU)]
    out["criteres_essentiels_manquants"] = manquants
    out["partielle"] = bool(manquants and note is not None)
    if mesurer and autoriser_cote:
        dep = [k for k, c in crit.items() if (c.get("reference") or {}).get("type") == "cote_entiere"]
        sans = noter(e, medianes, autoriser_cote=False, _mesurer=False)
        out["dependance_cote"] = {
            "criteres": dep, "note_sans_cote": sans["note"],
            "ecart_points": (round(note - sans["note"], 2) if note is not None and sans["note"] is not None else None),
            "note_inexistante_sans_cote": bool(dep and note is not None and sans["note"] is None)}
    return out


def _source_compacte(src: dict | None) -> dict | None:
    """La source d'un critère réduite à l'essentiel pour data.json : le fichier et
    la première URL de la pièce (texte complet dans le livrable de comparaison)."""
    import re
    if not src:
        return None
    m = re.search(r"https?://\S+", str(src.get("piece") or ""))
    return {"fichier": src.get("fichier"), "piece": m.group(0).rstrip(" ;,.)") if m else None}


def detail_publie(r: dict | None) -> dict | None:
    """Ce que data.json publie de la note par famille, par titre : critère par
    critère, état, valeur, période, base, poids nominal et EFFECTIF, référence
    de comparaison (famille ou cote entière), dépendance à la cote entière.
    Les pièces sont réduites à leur URL ; le détail complet est dans
    `datasets/comparaison_note_metier_*.json`."""
    if not r:
        return None
    crit = {k: {**{c: v for c, v in c_.items() if c != "source"}, "source": _source_compacte(c_.get("source"))}
            for k, c_ in r["criteres"].items()}
    return {"famille": r["famille"], "note": r["note"], "poids_disponible": r["poids_disponible"],
            "motif": r["motif"], "partielle": r["partielle"],
            "criteres_essentiels_manquants": r["criteres_essentiels_manquants"],
            "criteres": crit, "dependance_cote": r.get("dependance_cote")}


def noter_univers(titres, prix: dict, pb: dict, fondamentaux: dict, bpa: dict,
                  s1: dict, faits: dict, sans_comptes=(), suspendus=(), roe_moyenne: bool = True,
                  oci: dict | None = None, dividendes: dict | None = None) -> dict:
    """{sym: résultat de `noter`} pour tous les `titres`. Pure."""
    entrees = [construire_entree(
        s, fondamentaux.get(s), bpa.get(s), s1.get(s), faits.get(s), prix.get(s), pb.get(s),
        sans_comptes=s in sans_comptes, suspendu=s in suspendus, roe_moyenne=roe_moyenne,
        oci=oci, dividendes=dividendes) for s in titres]
    med = calculer_medianes(entrees)
    return {e["sym"]: noter(e, med) | {"entree": e} for e in entrees}


def charger_sources(racine: Path = RACINE) -> dict:
    """Les fichiers lus par la note, tels que le moteur les lit."""
    def lire(p):
        return json.loads((racine / p).read_text(encoding="utf-8"))
    return {"fondamentaux": lire("fondamentaux.json"), "bpa": lire("bpa.json"),
            "s1": lire("datasets/resultats_s1_2026.json").get("titres", {}),
            "faits": lire("pipeline/faits_financiers.json"),
            "oci": lire("datasets/reserves_oci_assurances.json").get("titres", {}),
            # Calendrier des dividendes (D du résidu de fonds propres) : un fichier absent ne coupe pas la
            # note, D devient INCONNU et l'ancien test du résidu s'applique, étiqueté.
            "dividendes": (lire("datasets/dividendes_bvc.json").get("dividendes")
                           if (racine / "datasets/dividendes_bvc.json").exists() else None)}


# ───────────────────── plancher : panne des SOURCES seulement ─────────────────────

MIN_SOURCES = {"fondamentaux": 60, "bpa": 60, "faits": 50, "s1": 50}   # mesuré le 11/10 : 77, 76, 71, 72
EFFONDREMENT = 0.7        # moins de 70 % des notes du run précédent : ALERTE (pas un blocage)


def problemes_sources(sources: dict) -> list[str]:
    """Pourquoi la publication de la note par famille doit être REFUSÉE, ou [].

    ⚠️ 11-12/10/2026 (Abd Moutalib) : on ne bloque QUE sur des fichiers sources
    absents ou vides. Ni l'abstention légitime d'un titre (MASI 1 compris), ni une
    chute du nombre de notes — qu'une correction méthodologique peut provoquer —
    ne bloquent : la chute est une ALERTE (`alertes_notes`).
    """
    out = []
    for nom, mini in MIN_SOURCES.items():
        n = len(sources.get(nom) or {})
        if n < mini:
            out.append(f"source « {nom} » absente ou vide : {n} entrées (minimum {mini})")
    return out


def alertes_notes(nb_notes: int | None, nb_notes_precedent: int | None) -> list[str]:
    """Avertissements non bloquants : les notes tombent sous 70 % du run précédent."""
    if nb_notes is not None and nb_notes_precedent and nb_notes < EFFONDREMENT * nb_notes_precedent:
        return [f"ALERTE : {nb_notes} notes contre {nb_notes_precedent} au run précédent "
                f"(moins de {EFFONDREMENT:.0%}) — vérifier qu'il s'agit d'un changement de méthode, pas d'une panne"]
    return []


_RANG_SIGNAL = ("ÉVITER FORT", "ÉVITER", "ATTENDRE", "SURVEILLER", "ACHETER")


def _rang_signal(signal) -> int | None:
    sig = (signal or "").strip()
    for p in ("ÉVITER FORT", "ÉVITER", "ATTENDRE", "SURVEILLER", "ACHETER"):
        if sig.startswith(p):
            return _RANG_SIGNAL.index(p)
    return None            # « Données insuffisantes », « SUSPENDU » : hors échelle


def limiter_signal_partiel(signal_actuel, signal_simule, partielle: bool):
    """Règle 11 : une note PARTIELLE ne peut pas produire un signal plus
    favorable que celui de la grille actuelle. Rend le signal à publier.

    Hors échelle (« Données insuffisantes », « SUSPENDU »), rien n'est limité.
    """
    if not partielle:
        return signal_simule
    a, b = _rang_signal(signal_actuel), _rang_signal(signal_simule)
    if a is None or b is None:
        return signal_simule
    return signal_actuel if b > a else signal_simule


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


def noter_depuis_fichiers(prix_surcharge: dict | None = None, racine: Path = RACINE,
                          roe_moyenne: bool = True) -> dict:
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
        suspendus={s for s in TICKERS_ALL if est_suspendu(s)}, roe_moyenne=roe_moyenne,
        oci=src["oci"], dividendes=src["dividendes"])


def main() -> int:
    """Audit : note chaque titre sur les cours et P/B du data.json publié."""
    res = noter_depuis_fichiers()
    for s, r in res.items():
        print(f"{s:5} {r['famille']:12} note={r['note']}  poids={r['poids_disponible']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

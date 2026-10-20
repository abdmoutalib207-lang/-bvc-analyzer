#!/usr/bin/env python3
"""
Score fondamental v5.3 — composante 47% du score global
Calculé depuis fondamentaux.json (ROIC, PER, croissance, bilan)

Composantes [0-10]:
  Qualité       40%  Spread ROIC-WACC
  Croissance    30%  BPA (60%) + CA (40%) composite
  Valorisation  20%  Forward PER vs marché BVC
  Bilan         10%  Dette/EBITDA + cash conversion ; banques : bilan bancaire (20/10/2026)

Modificateurs: momentum, rerating, cycle_commodities

⚠️ CETTE GRILLE N'EST PLUS CELLE DE LA NOTE PUBLIÉE (10/10/2026, décision
d'Abd Moutalib). `score_fond` suit désormais la grille de la FAMILLE du titre :
voir `fond_score_sectoriel.py`. Ce module reste la source de TROIS choses :
la porte unique des ratios (`ratio_effectif`, `roe_effectif`, garde-fous
`ROE_SANS_OBJET` et `RATIOS_EN_VERIFICATION`), les références WACC_REF et
COUT_FONDS_PROPRES_REF, et les paliers que la grille par famille reprend
(épinglés par tests/test_note_sectorielle.py). `compute_fond_score` ne sert
plus qu'à la note provisoire de la boucle d'`update_data.py`, remplacée au
second passage.
"""
import json
from pathlib import Path

_FOND_PATH = Path(__file__).parent.parent.parent / "fondamentaux.json"
_cache: dict = {}


def _load() -> dict:
    global _cache
    if not _cache:
        try:
            _cache = json.loads(_FOND_PATH.read_text(encoding="utf-8"))
        except Exception:
            _cache = {}
    return _cache


def reload():
    """Force le rechargement de fondamentaux.json (utile en CI)."""
    global _cache
    _cache = {}
    return _load()


# ⚠️ LES RATIOS CALCULÉS SUR COMPTES PUBLIÉS PRIMENT — 01/10/2026, décision
# d'Abd Moutalib (R8), après mesure. Au 01/10 : 79 ratios calculés sur 31
# titres hors MSA (ROIC, dette nette / EBITDA, conversion de trésorerie) ; la
# note fondamentale bouge sur 28, et 10 titres changent de palier sur les
# notes publiées le jour même (9 vers le bas, SNA vers le haut). Principe posé par lui : « rectifier les anciens calculs faux grâce
# aux publications, et continuer la chronologie avec les nouvelles ». Dès
# qu'un ratio est calculé dans `ratios_publies` (pipeline/ratios_financiers.py,
# chaque fait avec sa page), la note le lit à la place de la valeur saisie ;
# les prochains ratios calculés s'appliqueront donc d'eux-mêmes.
# La valeur saisie reste dans le fichier, intacte : elle n'est plus lue que
# faute de ratio calculé.
# ⚠️ Pas de backtest possible : les ratios calculés n'existent que depuis le
# 29/09/2026. Le remplacement rend la note plus honnête, il ne prouve pas
# qu'elle prédit mieux.
# ⚠️ MSA SORT DE LA LISTE LE 15/10/2026. Motif d'entrée (01/10) : « ROIC calculé
# de 47,6 % contre 17 saisi — capital investi d'un concessionnaire portuaire à
# recouper ». Recoupé sur le rapport 2025 (faits_financiers.json › MSA ›
# `_controles_ratios_2025.reserves_verifiees`) : comptes en NORMES MAROCAINES
# (CNC avis n°5, p.125), pas d'IFRIC 12 ni d'IFRS 16 ; les immobilisations de
# Marsa Maroc sont dans le capital investi, les biens du domaine public de la
# concession n'y sont pas (CAC p.133, non chiffrés) ; 47,6 % = identité du
# bilan (actif immobilisé + BFR − provisions durables = CP + dette nette), et
# les variantes qui réintègrent les provisions (31,4 à 33,5 %) restent dans la
# même tranche de la grille (écart ≥ 15 points). La saisie 17 n'a pas de pièce
# et aucune base du bilan ne la reproduit (19,6 % sur le total de l'actif).
# Le mécanisme reste : un titre inscrit ici garde l'écart consigné et n'est
# plus lu jusqu'au recoupement.
RATIOS_EN_VERIFICATION: dict[str, str] = {}


def _publie(f: dict, sym: str, cle: str):
    """Le ratio calculé sur comptes publiés, ou None. Seule une valeur
    numérique compte : « sans objet » n'est pas une mesure."""
    if sym in RATIOS_EN_VERIFICATION:
        return None
    x = (f.get("ratios_publies") or {}).get(cle)
    v = x.get("valeur") if isinstance(x, dict) else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


# ⚠️ LES SOCIÉTÉS FINANCIÈRES N'ONT NI ROIC, NI DETTE NETTE / EBITDA, NI
# CONVERSION DE TRÉSORERIE — 02/10/2026, lot 1 des rectifications demandées
# par Abd Moutalib (« des chiffres et des calculs corrects »). Pour une
# banque, la dette EST l'activité ; un EBITDA n'existe pas. Mesuré le 02/10 :
# le ROIC saisi à la main était encore lu dans la note de neuf financières
# (ATW 22,8 %, BOA 19,5 %, CASH 18 %…), alors que le calcul sur comptes les
# déclare « sans objet ». Ces trois ratios rendent désormais None pour elles,
# dans la note comme dans les alertes.
FINANCIERS = ("Banque", "Assurance", "Finance")
# Coût des fonds propres de RÉFÉRENCE, le même pour toutes les financières,
# auquel le ROE est comparé. ⚠️ HYPOTHÈSE DÉCLARÉE, pas une mesure : c'est la
# valeur que la grille utilisait déjà par défaut (WACC 10). Elle sera
# remplacée par la méthode unique du lot « WACC », ou retirée.
COUT_FONDS_PROPRES_REF = 10.0
_SANS_OBJET_FINANCIERES = ("roic", "dette_nette_ebitda", "cash_conversion")


# Le ROE n'a pas de sens pour un COURTIER qui distribue tout son résultat :
# AFMA affiche 103 % parce que ses capitaux propres hors résultat de l'année
# sont négatifs (−2,3 MDH, rachats de minoritaires imputés) — vérifié le
# 02/10/2026 par l'agent verificateur-finance. Arithmétiquement vrai, il ne
# mesure rien de comparable. Rentabilité non évaluée pour ces titres.
ROE_SANS_OBJET = {
    "AFM": "courtier en assurance — capitaux propres hors résultat négatifs, ROE 103 % sans signification",
    "AGM": "intermédiaire en assurance — distribue l'essentiel de son résultat, ROE social 46 % sans signification",
}


def est_financiere(f: dict | None) -> bool:
    return str((f or {}).get("secteur") or "").startswith(FINANCIERS)


def roe_effectif(f: dict | None, sym: str) -> dict | None:
    """ROE calculé sur comptes publiés : douze mois glissants s'il existe,
    sinon l'exercice 2025. Jamais une saisie. Pure."""
    if sym in ROE_SANS_OBJET:
        return None
    for cle in ("roe_12m", "roe_2025"):
        v = _publie(f or {}, sym, cle)
        if v is not None:
            x = f["ratios_publies"][cle]
            return {"valeur": v, "origine": "comptes publiés", "cle": cle,
                    "date": x.get("date"), "formule": x.get("formule")}
    return None


# ⚠️ GRANDEURS CONTESTÉES — 14/10/2026 (diagnostic externe, point 3).
# La nouvelle grille suspendait la dette nette contredite par les faits
# financiers ; l'ancienne, publiée, la lisait quand même — ADI et MUT notés
# sur un ROIC et une dette/EBITDA contestés, confiance 5/5. Le registre est
# rempli par `charger_contestations()` au démarrage du moteur ; la porte
# unique le consulte, si bien que note, alertes et écran lisent la même
# chose. Vide par défaut : un appelant qui ne le charge pas garde l'ancien
# comportement.
#
# ⚠️ RÈGLE UNIQUE DE L'ÉCART DE DETTE NETTE — 16/10/2026 (relecture externe :
# ADI contesté pour 4,5 % d'écart, VCNE libre malgré 18,5 %, parce que le
# chiffre de Vicenne n'était rangé que dans `_ecarts_mesures`).
#   1. RANGEMENT : le chiffre que la SOCIÉTÉ annonce (endettement net, dette
#      nette ou trésorerie nette, même date, même base) est rangé pour TOUS au
#      même endroit — `faits_financiers.json › <titre> › faits › endettement_net`,
#      signé (négatif = trésorerie nette), avec sa page. Jamais seulement dans
#      `_ecarts_mesures` (garde-fou : tests/test_regle_ecart_dette.py).
#   2. CONCORDANCE : écart à la dette nette recalculée au bilan ≤
#      SEUIL_ECART_DETTE (en valeur relative du chiffre de la société) : rien
#      à expliquer.
#   3. AU-DELÀ, l'écart n'est accepté QUE s'il est EXPLIQUÉ SUR PIÈCE
#      (`endettement_net.rapprochement`) : la définition de la société citée
#      (page, citation), et chaque élément de passage nommé par un poste de
#      EXPLICATIONS_ECART_DETTE_ADMISES, chiffré, avec page et citation ; le
#      module recalcule la somme, et l'écart RÉSIDUEL doit rester ≤ au même
#      seuil. Sinon : CONTESTÉ, et ROIC, dette nette/EBITDA, dette nette sont
#      suspendus. Aucune exception par titre, aucun seuil propre à un titre.
SEUIL_ECART_DETTE = 0.02
EXPLICATIONS_ECART_DETTE_ADMISES: dict[str, str] = {
    "ifrs16_location": "dettes locatives IFRS 16 ou crédit-bail, comptés d'un côté et pas de l'autre",
    "derives_couverture": "instruments dérivés de couverture (MtM), hors dette nette du fichier",
    "comptes_courants_associes": "comptes courants d'associés, hors dette nette du fichier",
    "mise_en_equivalence": "titres ou prêts des sociétés mises en équivalence",
    "depots_tresorerie_bloquee": "dépôts, cautionnements, trésorerie bloquée",
    "titres_de_placement": "titres de placement comptés ou non en trésorerie",
    "dettes_de_financement": "dettes de financement exclues par la définition de la société "
                             "(sa « trésorerie nette » ne retient que les soldes bancaires et placements)",
    # ⚠️ RÈGLE a — 20/10/2026 — IFRS 3.39-40 (contrepartie différée ou éventuelle
    # d'un regroupement) et IAS 7.16 (acquisitions d'immobilisations à crédit :
    # flux d'INVESTISSEMENT, pas de financement). La note lit la dette financière
    # STRICTE, inchangée ; une dette d'acquisition comptée par la société n'est
    # qu'un poste du PONT, admis seulement s'il est CHIFFRÉ sur pièce avec sa page.
    # Un chiffre donné en pourcentage porte son `incertitude` d'arrondi, et le
    # résidu doit tenir aux deux extrêmes. Elle forme la « dette nette élargie »,
    # publiée HORS NOTE (`ratios_publies.dette_nette_elargie`).
    "dettes_acquisition": "dettes d'acquisition (fournisseurs d'immobilisations, compléments de prix) comptées "
                          "par la société, hors dette financière stricte — IFRS 3.39-40, IAS 7.16",
}
CONTESTES: dict[str, str] = {}
# Ratios qui consomment la dette nette (ROIC : capital investi = fonds
# propres + dette nette).
_CONSOMMENT_DETTE_NETTE = ("roic", "dette_nette_ebitda", "dette_nette")


def charger_contestations(fondamentaux: dict, faits: dict) -> dict:
    """Remplit CONTESTES {sym: motif} depuis la règle de la note par famille
    (`_dette_nette_contestee`). Une seule définition de la contestation."""
    from pipeline.smart_money.fond_score_sectoriel import _dette_nette_contestee
    CONTESTES.clear()
    for sym, f in (fondamentaux or {}).items():
        if not isinstance(f, dict):
            continue
        dn = (f.get("ratios_publies") or {}).get("dette_nette")
        motif = _dette_nette_contestee(dn if isinstance(dn, dict) else None,
                                       (faits or {}).get(sym) or {})
        if motif:
            CONTESTES[sym] = motif
    return dict(CONTESTES)


def ratio_effectif(f: dict | None, sym: str, cle: str) -> dict | None:
    """LA valeur d'un ratio que tout le moteur doit lire — note, alertes,
    écran. {"valeur", "origine", "date"} ou None. Fonction pure.

    ⚠️ POURQUOI UNE SEULE PORTE — 01/10/2026. Le jour où la note est passée
    aux ratios calculés, les alertes sont restées sur la saisie : ADI
    affichait « dette critique 5,5× l'EBITDA » pendant que sa note lisait
    2,26× (audit externe du 01/10). Deux lectures d'un même ratio finissent
    toujours par diverger ; il n'y en a plus qu'une.
    """
    f = f or {}
    if cle in _SANS_OBJET_FINANCIERES and est_financiere(f):
        return None
    if cle in _CONSOMMENT_DETTE_NETTE and sym in CONTESTES:
        return None                     # contestée : ni note, ni alerte, ni saisie
    v = _publie(f, sym, cle)
    if v is not None:
        x = f["ratios_publies"][cle]
        # `sources` et `base` : la PIÈCE du calcul, lue par la note par famille
        # pour dire d'où vient chaque chiffre (ajout du 11/10/2026, sans effet
        # sur la valeur).
        return {"valeur": v, "origine": "comptes publiés", "date": x.get("date"),
                "formule": x.get("formule"), "sources": x.get("sources"), "base": x.get("base"),
                **({"periode": x["periode"]} if x.get("periode") else {}),
                **({"borne": x["borne"]} if x.get("borne") else {}),
                **({"reserve": x["reserve"]} if x.get("reserve") else {})}
    s = f.get(cle)
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return {"valeur": float(s), "origine": "saisie", "date": f.get("date_maj"),
                "source": f.get("source")}
    return None


# ⚠️ LOT 4 DES RECTIFICATIONS — 02/10/2026, demande d'Abd Moutalib : plus
# aucune saisie manuelle lue par la note.
# - WACC : 29 valeurs saisies entre 9 et 11 %, sans méthode. Remplacées par
#   UNE référence déclarée pour toutes les sociétés — la même que le coût des
#   fonds propres des financières. Hypothèse, pas une mesure.
# - Momentum, rerating, cycle : jugements saisis à la main (76, 29 et 3
#   titres), sans source ; ils ne modifient plus la note. Les champs restent
#   dans le fichier pour la trace.
# - Croissance et PER : lus seulement quand ils viennent des comptes publiés
#   (`croissance_sourcee`, `per_publie`) ; sinon « non évalué » (5,0), et
#   plus jamais un défaut inventé (PER 15 → « juste valeur » 7,0).
WACC_REF = 10.0


# ⚠️ CE QUI N'EST PAS MESURÉ N'EST PAS NOTÉ — 14/10/2026.
#
# Accord d'Abd Moutalib (constats H1, H2, M2 de la chasse aux échecs
# silencieux ; point 3 du diagnostic externe : « une donnée manquante ne doit
# pas devenir une qualité moyenne de 5/10 »). Jusqu'ici, pour l'appel du
# moteur : ROIC absent → 10 saisi (q = 5,0), croissance non sourcée → 5,0,
# pas de PER → 5,0, dette absente → 1,0× fictif (7,0), financière → bilan
# 5,0, titre absent du fichier → 5,0. Chaque défaut tirait la note vers le
# milieu et se lisait comme une mesure.
# Désormais une composante non mesurée est RETIRÉE et les poids des autres
# sont remis à l'échelle ; sous COUVERTURE_MIN du poids total, pas de note
# (« Données insuffisantes »). Les seuils de chaque grille sont inchangés.
# Réserves VALIDÉES par la contre-vérification (verificateur-finance, 15/10/2026),
# attachées à la composante qu'elles nuancent et affichées sur la fiche.
RESERVES_RATIOS = {
    # ⚠️ TMA, 16/10/2026 — mesuré à blanc, NON appliqué : la note lit le bilan de
    # l'exercice (31/12/2025). Sur le bilan le plus récent (Total_Maroc_S1_26.pdf
    # p.4 : dettes financières 473,879 + 841,200 − trésorerie 988,736 = +326,3),
    # dette nette/EBITDA 0,19 (EBITDA de l'exercice) à 0,22 (12 mois glissants) :
    # grille 8,5 au lieu de 9,0, note fondamentale 7,0 → 6,95, palier ACHETER ★★
    # → SURVEILLER ★ dans les deux variantes. La règle de choix de période
    # (dernier bilan publié pour tous, EBITDA 12 mois glissants) reste à décider.
    # Règle b appliquée le 20/10/2026 : la note lit désormais le 30/06/2026.
    "TMA": {"bilan": "Dette nette +326,3 MMAD au 30/06/2026 (comptes S1, p.4 : dettes financières 473,9 + 841,2 − "
                     "trésorerie 988,7) ÷ EBITDA 12 mois 1 515,8 (exercice 1 685,5 + S1 2026 562,2 − S1 2025 731,9) "
                     "= 0,22 — règle b du 20/10/2026. Au 31/12/2025 : trésorerie nette de 288,6 (−0,17). "
                     "Bilan au 30/06 : saisonnalité du besoin en fonds de roulement. "
                     "27,5 MMAD de passif non courant non ventilé (avis d'AGO p.6)."},
    "BAL": {"bilan": "Trésorerie nette reposant sur 6,9 MMAD de placements : sans eux, pas de note de bilan "
                     "(note 5,28 au lieu de 5,65)."},
    "MOX": {"qualite": "ROIC des seules sociétés intégrées (titres mis en équivalence retirés, p.32-33)."},
    "UNI": {"qualite": "ROIC des seules sociétés intégrées (titres mis en équivalence retirés, p.33)."},
    "MSA": {"qualite": "ROIC sur le capital apporté par le groupe : l'infrastructure portuaire "
                       "appartient au concédant et n'est pas au bilan (CAC, RFA 2025 p.133). Non "
                       "comparable au ROIC d'un propriétaire d'actifs ; à lire avec la marge "
                       "d'exploitation (44,3 %, p.122)."},
    "VCNE": {"bilan": "Trésorerie nette annoncée 311 (p.19) / 315 (p.13) contre 368,7 au bilan, "
                      "écart non expliqué sur pièce : grandeur contestée. Dont 523,7 MMAD de "
                      "placements (produit de l'introduction en bourse, nature non publiée) ; "
                      "EBITDA tel que publié, sans définition (RFA 2025 p.20-21, p.57)."},
    # 20/10/2026, validé sur pièce par verificateur-finance.
    "NEJ": {"bilan": "EBITDA calculé sur les amortissements consolidés NETS DES REPRISES (tableau des "
                     "flux, RFA 2025 p.106 : 37,618), seule ligne consolidée qui les isole ; ils sont "
                     "inférieurs aux dotations du social (55,2, p.83)."},
    # Règle c (20/10/2026) : croissance retraitée sur les MONTANTS de l'émetteur.
    "T2S": {"croissance": "BPA +65,5 % = 91 ÷ 55 − 1, S1 2025 retraité de la cession Varian (montants ajustés du "
                          "communiqué S1 p.1) ; publié brut −16,1 %. 55 est arrondi au MDH : croissance pondérée "
                          "49,8 % (91 ÷ 55) ou 50,2 % (91,307 ÷ 55), le seuil de 50 % de la grille passe dans "
                          "l'incertitude d'arrondi (palier 7,5 ou 9,0).",
            "valorisation": "BPA sur le nombre d'actions actuel, traitement IAS 33 des actions de priorité non "
                            "établi : PER plafond (voir la réserve du BPA)."},
    # Règle c (20/10/2026) : réserve « PER non récurrent », sans retraitement.
    "MDP": {"valorisation": "PER non récurrent — PER sur un résultat 12 mois (6,1 MDH, comptes sociaux) qui doit l'exercice "
                            "2025 au NON COURANT (+22,1 MDH ; résultat d'exploitation −10,4 ; RFA 2025 "
                            "p.41) : bénéfice non récurrent. Examen limité S1 « sous réserve » des CAC "
                            "(8,6 MDH chiffrés).",
            "croissance": "Comptes sociaux ; examen limité S1 2026 « sous réserve » des CAC (p.3)."},
}
POIDS_FOND = {"qualite": 0.40, "croissance": 0.30, "valorisation": 0.20, "bilan": 0.10}
COUVERTURE_MIN = 0.5


def _grille_spread(sp: float) -> float:
    return (9.5 if sp >= 15 else 8.5 if sp >= 10 else 7.0 if sp >= 5 else
            6.0 if sp >= 2 else 5.0 if sp >= 0 else 3.5 if sp >= -3 else 2.0)


def _grille_croissance(growth: float) -> float:
    return (10.0 if growth >= 100 else 9.0 if growth >= 50 else 7.5 if growth >= 25 else
            6.5 if growth >= 10 else 5.5 if growth >= 5 else 4.5 if growth >= 0 else
            3.0 if growth >= -10 else 1.5)


def _grille_per(fper: float) -> float:
    return (9.5 if fper <= 8 else 8.5 if fper <= 12 else 7.0 if fper <= 17 else
            5.5 if fper <= 25 else 4.0 if fper <= 35 else 2.5 if fper <= 50 else 1.5)


def _grille_bilan(dne: float, cc: float | None) -> float:
    bs = (9.0 if dne < 0 else 8.5 if dne < 0.5 else 7.0 if dne < 1.5 else 5.5 if dne < 2.5
          else 4.0 if dne < 3.5 else 2.5 if dne < 5.0 else 1.5)
    if cc is not None:
        if cc >= 85:
            bs = min(10.0, bs + 0.5)
        elif cc < 40:
            bs = max(0.0, bs - 0.5)
    return bs


# ⚠️ GRILLE BANCAIRE — 20/10/2026, accord d'Abd Moutalib (cadre : usage du
# métier, directives de Bank Al-Maghrib, IFRS 9). Pour les 7 banques (secteur
# « Banque » : ATW, BCP, BOA, CIH, CDM, CFGB, BMC), la composante « bilan »
# n'est plus retirée : elle devient le BILAN BANCAIRE, qui REMPLACE la dette
# nette / EBITDA, et le coefficient d'exploitation entre dans la QUALITÉ à
# côté du ROE (une seule fois : il n'est pas dans le bilan). Ratios recalculés
# sur pièce par pipeline/ratios_financiers.py (`calculer_bancaire`), jamais
# les taux publiés.
#   bilan bancaire = moyenne à POIDS ÉGAUX des sous-mesures présentes :
#     solvabilité globale (marge sur le minimum BAM), coût du risque ÷ encours
#     net moyen, couverture Bucket 3 ; une sous-mesure absente est retirée et
#     les poids renormalisés (BCP : pas de solvabilité publiée → deux
#     sous-mesures, avec réserve).
#   qualité = moyenne à POIDS ÉGAUX de la grille ROE − 10 et de la grille du
#     coefficient ; l'une absente : l'autre seule.
#   ⚠️ Poids égaux : HYPOTHÈSE DÉCLARÉE, faute de référence qui en fixe d'autres.
#
# LES SEUILS — chacun justifié (R12) :
#   · plancher RÉGLEMENTAIRE de la solvabilité : 12 % (Bank Al-Maghrib,
#     circulaire 14/G/2013 ; pièces : BMCI RFA 2025 p.13 « Ratio de solvabilité
#     (Seuil Min 12%) », CIH RFA 2025 p.22 « (minimum exigible 12 %) » —
#     faits_financiers.json › _grille_bancaire › minimum_solvabilite_bam).
#     Sous le minimum : 1,5, la note la plus basse de la grille de bilan.
#   · paliers au-dessus : DISTRIBUTION OBSERVÉE sur les banques notées le
#     20/10/2026 — quartiles (méthode inclusive) arrondis au pas déclaré ;
#     meilleur quart 8,5, deuxième 7,0, troisième 5,5, dernier 4,0 (l'échelle
#     de `_grille_bilan`). C'est une note RELATIVE à la place, pas un jugement
#     absolu : aucun barème BAM ni de place sourcé n'existe au-delà du minimum.
#     `tests/test_grille_bancaire.py` recalcule les quartiles depuis
#     fondamentaux.json et échoue si un seuil ne les reproduit plus.
SOLVABILITE_MIN_BAM = 12.0
PALIERS_BANCAIRES = {
    # nom: (sens, seuils du meilleur au moins bon, pas d'arrondi, justification)
    "solvabilite_globale": ("haut", (2.5, 2.0, 1.0), 0.5,
        "marge sur le minimum BAM de 12 %, en points ; 6 banques (BCP ne publie pas) : 12,86 13,13 13,40 "
        "14,42 14,85 18,66 % → marges 0,86 1,13 1,40 2,42 2,85 6,66 ; quartiles 1,20 / 1,91 / 2,74 → 1,0 / 2,0 / 2,5"),
    "cout_du_risque_encours": ("bas", (0.75, 1.0, 1.5), 0.25,
        "% de l'encours net moyen, exercice 2025 ; 7 banques : 0,23 0,64 0,85 1,10 1,44 1,55 1,83 ; "
        "quartiles 0,75 / 1,10 / 1,49 → 0,75 / 1,00 / 1,50"),
    "couverture_bucket3": ("haut", (75.0, 70.0, 60.0), 5.0,
        "% au 30/06/2026 ; 7 banques : 40,5 48,8 69,2 70,5 71,7 75,5 79,9 ; quartiles 59,0 / 70,5 / 73,6 → 60 / 70 / 75"),
    "coefficient_exploitation": ("bas", (45.0, 46.0, 47.0), 1.0,
        "% sur 12 mois au 30/06/2026 ; 7 banques : 38,6 43,6 45,8 46,4 46,7 47,1 57,0 ; "
        "quartiles 44,6 / 46,4 / 46,9 → 45 / 46 / 47"),
}
NOTES_QUARTS = (8.5, 7.0, 5.5, 4.0)
NOTE_SOUS_MINIMUM = 1.5
LIBELLES_BANCAIRES = {"solvabilite_globale": "solvabilité globale", "cout_du_risque_encours": "coût du risque",
                      "couverture_bucket3": "couverture Bucket 3", "coefficient_exploitation": "coefficient d'exploitation"}


def grille_bancaire(nom: str, x: float) -> float:
    """La note d'une sous-mesure bancaire. Pure."""
    sens, seuils, _, _ = PALIERS_BANCAIRES[nom]
    if nom == "solvabilite_globale":
        x = x - SOLVABILITE_MIN_BAM
        if x < 0:
            return NOTE_SOUS_MINIMUM
    for s, n in zip(seuils, NOTES_QUARTS):
        if (x >= s) if sens == "haut" else (x <= s):
            return n
    return NOTES_QUARTS[-1]


def est_banque(f: dict | None) -> bool:
    return str((f or {}).get("secteur") or "").startswith("Banque")


def _sous_mesure_bancaire(f: dict, sym: str, nom: str) -> dict | None:
    """Une sous-mesure de la grille bancaire lue dans `ratios_publies`, notée."""
    v = _publie(f, sym, nom)
    if v is None:
        return None
    x = f["ratios_publies"][nom]
    note = grille_bancaire(nom, v)
    mesure = f"{LIBELLES_BANCAIRES[nom]} {v:g} %"
    if nom == "solvabilite_globale":
        mesure += f" (minimum BAM {SOLVABILITE_MIN_BAM:g} %, marge {v - SOLVABILITE_MIN_BAM:+.2f} pt)"
    elif nom == "cout_du_risque_encours":
        mesure += " de l'encours net moyen"
    _p, _d = str(x.get("periode") or ""), str(x.get("date") or "")
    _jj = "/".join(reversed(_d.split("-"))) if _d else "?"
    quand = (f"12 mois au {_jj}" if _p.startswith("12 mois") else
             "exercice 2025" if _p.startswith("exercice 2025") else f"au {_jj}")
    mesure += f", {quand} → {note:g}"
    return {"nom": nom, "libelle": LIBELLES_BANCAIRES[nom], "valeur": v, "unite": "%", "date": x.get("date"),
            "periode": x.get("periode"), "formule": x.get("formule"), "sources": x.get("sources"),
            "note": note, "mesure": mesure, **({"reserve": x["reserve"]} if x.get("reserve") else {})}


def detail_fond_score(sym: str, fondamentaux: dict = None, per_publie: float | None = None,
                      croissance_sourcee: bool = False) -> dict:
    """La note fondamentale du moteur, composante par composante.

    {"note": float | None, "couverture": float, "composantes": {nom: {"note",
    "poids", "mesure" | "motif"}}}. Une composante non mesurée porte
    `note: None` et son motif ; elle ne pèse rien. Pure (hors CONTESTES)."""
    data = fondamentaux if fondamentaux is not None else _load()
    f = data.get(sym) or {}
    comp = {}

    def non(nom, motif):
        comp[nom] = {"note": None, "poids": POIDS_FOND[nom], "motif": motif}

    def oui(nom, note, mesure):
        comp[nom] = {"note": note, "poids": POIDS_FOND[nom], "mesure": mesure}

    if not f:
        for nom in POIDS_FOND:
            non(nom, "société absente de fondamentaux.json")
        return {"note": None, "couverture": 0.0, "composantes": comp}

    # QUALITÉ — ROIC − WACC (ROE − coût des fonds propres pour une financière)
    if est_financiere(f):
        _roe = roe_effectif(f, sym)
        # Banques : le coefficient d'exploitation à côté du ROE (grille bancaire, 20/10/2026).
        _coef = _sous_mesure_bancaire(f, sym, "coefficient_exploitation") if est_banque(f) else None
        if _roe is None and _coef is None:
            non("qualite", "ROE non calculé sur comptes publiés")
        elif _coef is None:
            oui("qualite", _grille_spread(_roe["valeur"] - COUT_FONDS_PROPRES_REF),
                f"ROE {_roe['valeur']:g} % − {COUT_FONDS_PROPRES_REF:g}")
        else:
            _parts, _notes = [], [_coef["note"]]
            if _roe is not None:
                _nr = _grille_spread(_roe["valeur"] - COUT_FONDS_PROPRES_REF)
                _notes.insert(0, _nr)
                _parts.append(f"ROE {_roe['valeur']:g} % − {COUT_FONDS_PROPRES_REF:g} → {_nr:g}")
            else:
                _parts.append("ROE non calculé sur comptes publiés (retiré)")
            _parts.append(_coef["mesure"])
            oui("qualite", round(sum(_notes) / len(_notes), 2),
                " ; ".join(_parts) + f" — moyenne à poids égaux de {len(_notes)} sous-mesure(s)")
            comp["qualite"]["sous_mesures"] = [_coef]
    else:
        _r = ratio_effectif(f, sym, "roic")
        if sym in CONTESTES:
            non("qualite", "ROIC suspendu — " + CONTESTES[sym])
        elif not _r or _r.get("origine") != "comptes publiés":
            non("qualite", "ROIC non calculé sur comptes publiés (saisie sans pièce écartée)")
        else:
            oui("qualite", _grille_spread(_r["valeur"] - WACC_REF),
                f"ROIC {_r['valeur']:g} % − WACC {WACC_REF:g}")

    # CROISSANCE — BPA 60 % + CA 40 %, seulement si le BPA 12 mois est établi
    if croissance_sourcee:
        growth = float(f.get("croissance_bpa") or 0) * 0.6 + float(f.get("croissance_ca") or 0) * 0.4
        oui("croissance", _grille_croissance(growth), f"croissance pondérée {growth:g} %")
        # Règle d (20/10/2026) : périmètre élargi sans pro forma en montants → réserve.
        _pr = (f.get("croissance_perimetre") or {}).get("reserve")
        if _pr:
            comp["croissance"]["reserve"] = _pr
    else:
        non("croissance", "croissance non établie sur comptes semestriels")

    # VALORISATION — PER tiré des comptes
    if isinstance(per_publie, (int, float)) and not isinstance(per_publie, bool) and per_publie > 0:
        oui("valorisation", _grille_per(float(per_publie)), f"PER {per_publie:g}")
    else:
        non("valorisation", "pas de PER positif tiré des comptes")

    # BILAN — dette nette / EBITDA sur comptes publiés, ou trésorerie nette
    _sm = ([s for s in (_sous_mesure_bancaire(f, sym, n) for n in
                        ("solvabilite_globale", "cout_du_risque_encours", "couverture_bucket3")) if s]
           if est_financiere(f) and est_banque(f) else [])
    if _sm:
        # BILAN BANCAIRE (20/10/2026) : remplace la dette nette / EBITDA.
        oui("bilan", round(sum(s["note"] for s in _sm) / len(_sm), 2),
            "bilan bancaire : " + " ; ".join(s["mesure"] for s in _sm)
            + f" — moyenne à poids égaux de {len(_sm)} sous-mesure(s) sur 3")
        comp["bilan"]["sous_mesures"] = _sm
        _abs = ((f.get("ratios_publies") or {}).get("solvabilite_globale_absente") or {}).get("motif")
        _res = ([f"solvabilité retirée, poids renormalisé — {_abs}"]
                if _abs and not any(s["nom"] == "solvabilite_globale" for s in _sm) else [])
        _res += [f"{s['libelle']} : {s['reserve']}" for s in _sm if s.get("reserve")]
        if _res:
            comp["bilan"]["reserve"] = " | ".join(_res)
    elif est_financiere(f):
        # ⚠️ MANQUANT, pas « sans objet » (15/10/2026) : la dette/EBITDA n'a pas
        # de sens pour une financière, mais son ÉQUIVALENT (coût du risque,
        # qualité des créances, solvabilité) en a un — intégré pour les banques
        # le 20/10/2026 (grille bancaire), pas pour les assurances ni les
        # sociétés de financement.
        non("bilan", "équivalent bancaire non intégré (coût du risque, qualité des créances, "
                     "solvabilité) — la dette/EBITDA ne s'applique pas à une financière")
    elif sym in CONTESTES:
        non("bilan", "dette nette suspendue — " + CONTESTES[sym])
    else:
        _d = ratio_effectif(f, sym, "dette_nette_ebitda")
        _dne = _d["valeur"] if _d and _d.get("origine") == "comptes publiés" else None
        _mesure = f"dette nette / EBITDA {_dne:g}" if _dne is not None else None
        if _mesure and (_d or {}).get("borne") == "supérieure":   # règle h, 20/10/2026
            _mesure = f"dette nette / EBITDA ≤ {_dne:g} (borne supérieure démontrée, pas une valeur)"
        # Règle b (20/10/2026) : le motif du choix de période est publié dans la mesure.
        if _mesure and (_d or {}).get("periode"):
            _mesure += f" — période : {_d['periode']}"
        if _dne is None:
            _dn = _publie(f, sym, "dette_nette")
            if _dn is not None and _dn < 0:
                _dne, _mesure = -1.0, "trésorerie nette positive"
        if _dne is None:
            non("bilan", "dette nette / EBITDA non calculée sur comptes publiés")
        else:
            _c = ratio_effectif(f, sym, "cash_conversion")
            _cc = _c["valeur"] if _c and _c.get("origine") == "comptes publiés" else None
            oui("bilan", _grille_bilan(_dne, _cc), _mesure)
            if (_d or {}).get("reserve") and _mesure.startswith("dette nette / EBITDA"):
                comp["bilan"]["reserve"] = _d["reserve"]   # saisonnalité du BFR au 30/06

    for nom, txt in RESERVES_RATIOS.get(sym, {}).items():
        if nom in comp and comp[nom]["note"] is not None:
            comp[nom]["reserve"] = txt
    couv = round(sum(c["poids"] for c in comp.values() if c["note"] is not None), 4)
    note = None
    if couv >= COUVERTURE_MIN:
        note = round(min(max(sum(c["note"] * c["poids"] for c in comp.values()
                                 if c["note"] is not None) / couv, 0.0), 10.0), 2)
    return {"note": note, "couverture": couv, "composantes": comp}


def compute_fond_score(sym: str, fondamentaux: dict = None,
                       per_publie: float | None = None,
                       croissance_sourcee: bool | None = None) -> float:
    """
    Retourne le score fondamental [0-10].
    fondamentaux: dict optionnel — si None, chargé depuis fondamentaux.json.
    per_publie: PER sur douze mois glissants calculé sur les comptes publiés
        (cours du jour ÷ BPA 12 mois). Prime sur `forward_per` quand il existe.
    Retourne 5.0 si le ticker est absent du fichier.
    """
    # Appel du moteur (`croissance_sourcee` renseigné) : rien de non mesuré
    # n'est noté — peut rendre None. Les autres appelants, historiques,
    # gardent l'ancienne formule.
    if croissance_sourcee is not None:
        return detail_fond_score(sym, fondamentaux, per_publie, croissance_sourcee)["note"]
    data = fondamentaux if fondamentaux is not None else _load()
    f = data.get(sym, {})
    if not f:
        return 5.0

    # QUALITÉ (40%) — spread ROIC-WACC : capacité à créer de la valeur
    _r     = ratio_effectif(f, sym, "roic") or {}
    # ⚠️ Une saisie à 0 retombe sur 10 (`or 10`), comportement antérieur gardé.
    roic   = _r["valeur"] if _r.get("origine") == "comptes publiés" else float(f.get("roic") or 10)
    wacc   = WACC_REF
    spread = roic - wacc
    if   spread >= 15: q = 9.5
    elif spread >= 10: q = 8.5
    elif spread >= 5:  q = 7.0
    elif spread >= 2:  q = 6.0
    elif spread >= 0:  q = 5.0
    elif spread >= -3: q = 3.5
    else:              q = 2.0
    # Financières : le ROE publié, comparé au coût des fonds propres de
    # référence, sur la même grille. Sans ROE publié : non évalué (5,0) —
    # jamais la saisie.
    if est_financiere(f):
        _roe = roe_effectif(f, sym)
        if _roe is None:
            q = 5.0
        else:
            sp = _roe["valeur"] - COUT_FONDS_PROPRES_REF
            q = (9.5 if sp >= 15 else 8.5 if sp >= 10 else 7.0 if sp >= 5 else
                 6.0 if sp >= 2 else 5.0 if sp >= 0 else 3.5 if sp >= -3 else 2.0)

    # CROISSANCE (30%) — BPA 60% + CA 40%
    cbpa   = float(f.get("croissance_bpa") or 0)
    cca    = float(f.get("croissance_ca")  or 0)
    growth = cbpa * 0.6 + cca * 0.4
    if croissance_sourcee is False: g = 5.0   # saisie non sourcée : non évaluée
    elif growth >= 100: g = 10.0
    elif growth >= 50:  g = 9.0
    elif growth >= 25:  g = 7.5
    elif growth >= 10:  g = 6.5
    elif growth >= 5:   g = 5.5
    elif growth >= 0:   g = 4.5
    elif growth >= -10: g = 3.0
    else:               g = 1.5

    # VALORISATION (20%) — Forward PER vs marché BVC (médiane ≈ 17-20x)
    # ⚠️ LE PER PUBLIÉ PRIME SUR LE « FORWARD » SAISI — 01/10/2026, décision
    # d'Abd Moutalib (R8), après mesure. `forward_per` est une saisie de mai,
    # sans méthode : 12,5 pour ADI quand ses comptes donnent 19,4 et DATA+
    # 18,6 ; 1 634,59 pour RDS. Audit externe de la fiche ADI du 01/10. Sur
    # 37 titres, 16 s'écartaient de plus de 30 % de l'estimation DATA+.
    # Mesure au 01/10 (notes de 14h56) : 63 titres sur 76 ont un PER sur
    # douze mois publié ; 38 notes bougent, 9 paliers changent. Trois options
    # mesurées (PER publié, DATA+ 2026e, valorisation neutralisée) ; celle-ci
    # retenue parce qu'elle ne lit que des faits sourcés.
    # ⚠️ C'est un PER RÉALISÉ, pas prévisionnel : la grille de seuils
    # (8 / 12 / 17 / 25 / 35 / 50) n'a pas été recalibrée. Un titre en perte
    # n'a pas de PER (`_per` rend None) et garde la saisie.
    if croissance_sourcee is not None and not (isinstance(per_publie, (int, float)) and per_publie > 0):
        fper = None                     # appel du moteur sans PER publié : non évalué
    else:
        fper = (float(per_publie) if isinstance(per_publie, (int, float)) and per_publie > 0
                else float(f.get("forward_per") or 15))
    if   fper is None: v = 5.0  # non évalué (aucun PER tiré des comptes)
    elif fper <= 0:  v = 5.0   # aberrant → neutre
    elif fper <= 8:  v = 9.5   # très décoté
    elif fper <= 12: v = 8.5   # décoté
    elif fper <= 17: v = 7.0   # juste valeur
    elif fper <= 25: v = 5.5   # légèrement premium
    elif fper <= 35: v = 4.0   # premium
    elif fper <= 50: v = 2.5   # très premium
    else:            v = 1.5   # spéculatif

    # BILAN (10%) — dette/EBITDA + cash conversion
    #
    # ⚠️ `X or défaut` prend UNE VALEUR pour UNE ABSENCE quand cette valeur
    # vaut zéro. Défaut réel, signalé par l'audit externe du 09/09/2026.
    #
    # ⚠️ MAIS LE CORRECTIF NAÏF ÉTAIT FAUX, et l'auditeur l'avait pressenti en
    # écrivant qu'« une dette nette nulle ne signifie pas automatiquement le
    # meilleur bilan possible ». Mesuré le 10/09 : `fondamentaux.json` compte
    # HUIT zéros exacts — six banques, un assureur, un agroalimentaire. Pour un
    # établissement financier, le ratio dette nette / EBITDA n'a pas de sens :
    # ce zéro est un REMPLISSAGE, pas une mesure. Traiter ces zéros comme un
    # bilan sain relevait 19 titres de +0,08 sur la foi d'un blanc.
    #
    # Le fichier ne permet PAS de distinguer « mesuré à zéro » de « sans
    # objet » — les deux s'écrivent 0.0. Tant que la donnée ne porte pas cette
    # distinction, on ne l'invente pas : le zéro n'est retenu comme mesure que
    # là où le ratio a un sens, et les secteurs financiers gardent le
    # comportement antérieur. C'est une limite de la DONNÉE, consignée comme
    # telle plutôt que masquée par une hypothèse.
    # Relevé le 10/09 : les huit zéros sont ATW, BCP, BOA, CDM, CFGB, CIH
    # (« Banque »), WAF (« Assurance ») et CSR (« Agroalimentaire - Sucre »).
    # Seul ce dernier est une société industrielle, pour qui le ratio a un
    # sens — son zéro est donc retenu comme mesure, avec la réserve qu'aucune
    # source primaire ne l'a confirmé à ce jour.
    # ⚠️ LE VOCABULAIRE DES SECTEURS A CHANGÉ LE 17/09/2026, ET CETTE LISTE EN
    # DÉPEND. Elle citait « Société de financement » et « Leasing », deux
    # libellés de l'ancienne taxonomie maison qui n'existent plus : le
    # référentiel de la cote dit « Finance ». Une liste qui nomme des secteurs
    # disparus ne protège plus personne — elle attend qu'une société de
    # financement affiche une dette nette nulle pour se tromper en silence.
    #
    # ⚠️ Vérifié avant la bascule : sur les huit titres à dette nette nulle
    # (ATW, BCP, BOA, CDM, CFGB, CIH, WAF, CSR), AUCUN ne change de traitement,
    # et aucun titre au secteur « Finance » n'a de dette nette nulle. Aucune
    # note ne bouge (R8).
    _SANS_OBJET = ("Banque", "Assurance", "Finance")
    _dne = (ratio_effectif(f, sym, "dette_nette_ebitda") or {}).get("valeur")
    _sect = f.get("secteur") or ""
    if _dne == 0 and any(_sect.startswith(s) for s in _SANS_OBJET):
        _dne = None                      # sans objet : on ne conclut rien
    # ⚠️ TRÉSORERIE NETTE SANS EBITDA — 02/10/2026. Une société dont la
    # dette nette calculée sur ses comptes est NÉGATIVE (plus de trésorerie
    # que de dettes) a le meilleur bilan possible, quel que soit son EBITDA.
    # Faute d'EBITDA publié, le ratio manquait et la note retombait sur une
    # dette fictive de 1,0× l'EBITDA (DAR, SBS ; M2M et S2M au lot 3b).
    if _dne is None and not est_financiere(f):
        _dn = _publie(f, sym, "dette_nette")
        if _dn is not None and _dn < 0:
            _dne = -1.0
    dne = float(_dne) if _dne is not None else 1.0
    _cc = (ratio_effectif(f, sym, "cash_conversion") or {}).get("valeur")
    cc  = float(_cc) if _cc is not None else 70
    if   dne < 0:   bs = 9.0   # trésorerie nette positive
    elif dne < 0.5: bs = 8.5
    elif dne < 1.5: bs = 7.0
    elif dne < 2.5: bs = 5.5
    elif dne < 3.5: bs = 4.0
    elif dne < 5.0: bs = 2.5
    else:           bs = 1.5
    if cc >= 85:    bs = min(10.0, bs + 0.5)
    elif cc < 40:   bs = max(0.0,  bs - 0.5)
    # Financières : bilan NON ÉVALUÉ (5,0) tant que le coût du risque et le
    # coefficient d'exploitation recalculés sur comptes ne sont pas intégrés
    # — plutôt qu'une dette 1,0× et une conversion 70 % inventées par défaut.
    if est_financiere(f):
        bs = 5.0

    # Score composite
    fond = q * 0.40 + g * 0.30 + v * 0.20 + bs * 0.10

    # Modificateurs — saisies sans source, NEUTRALISÉS le 02/10/2026 pour
    # l'appel du moteur (`croissance_sourcee` renseigné). Conservés pour les
    # autres appelants historiques, qui ne passent pas ce paramètre.
    if croissance_sourcee is not None:
        return round(min(max(fond, 0.0), 10.0), 2)
    mom = str(f.get("momentum_fondamental") or "").lower()
    if "très positif" in mom or "tres positif" in mom:
        fond += 0.5
    elif "positif" in mom:
        fond += 0.25
    elif "négatif" in mom or "negatif" in mom:
        fond -= 0.5

    if f.get("rerating"):
        fond += 0.3

    cyc = str(f.get("cycle_commodities") or "").lower()
    if cyc == "bullish":
        fond += 0.2
    elif cyc == "bearish":
        fond -= 0.2

    return round(min(max(fond, 0.0), 10.0), 2)


def score_all(fondamentaux: dict = None) -> dict:
    """Retourne {sym: fond_score} pour tous les tickers dans fondamentaux.json."""
    data = fondamentaux if fondamentaux is not None else _load()
    return {sym: compute_fond_score(sym, data) for sym in data}

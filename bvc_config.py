"""Point de vérité unique pour les constantes BVC Analyzer."""

from datetime import datetime, timedelta, timezone

# ── Noms officiels des sociétés cotées BVC ──────────────────────────────────
# Source de vérité : ces noms priment sur tout ce que retournent les scrapers.
COMPANY_NAMES: dict = {
    # ── Grandes capitalisations ─────────────────────────────────────────────
    # ⚠️ SOURCE DES LIBELLÉS, ET CE QU'ELLE N'EST PAS (17/09/2026).
    #
    # Ces noms sont confrontés au relevé de la cote
    # (`datasets/referentiel/cote_bvc.json`) par un test bloquant, mais ils ne
    # sont PAS recopiés depuis lui : ses libellés sont des noms d'affichage,
    # tronqués. L'export de l'opérateur lui-même écrit « MUTANDIS SCA » et
    # « TOTALENERGIES MARKETING MAROC » là où le relevé dit « Mutandis » et
    # « TotalEnergies Maroc ».
    #
    # La règle retenue : on adopte le libellé du relevé UNIQUEMENT là où le
    # nôtre était un sigle nu ou une raison sociale que le marché n'emploie
    # pas. Cinq cas, chacun commenté. Partout ailleurs le nôtre est plus
    # complet, et c'est lui qui reste.
    "IAM":  "Maroc Telecom",  # raison sociale Itissalat Al-Maghrib ; la cote, la presse et le public disent Maroc Telecom
    "ATW":  "Attijariwafa Bank",
    "BCP":  "Banque Populaire",  # le sigle nu ne disait rien au lecteur
    "BOA":  "Bank of Africa",
    "CIH":  "CIH Bank",  # sigle nu — la banque se nomme CIH Bank
    "CDM":  "Crédit du Maroc",
    "WAF":  "Wafa Assurance",
    "LHM":  "Holcim Maroc SA",
    "GAZ":  "Afriquia Gaz",
    "ATL":  "AtlantaSanad",
    "HPS":  "HPS",
    "LBV":  "Label Vie",
    "LES":  "Lesieur Cristal",
    "TQA":  "Taqa Morocco",
    "MRL":  "Maroc Leasing",
    "TMA":  "TotalEnergies Marketing Maroc",
    "CMT":  "Minière Touissit",
    "MNG":  "Managem",
    "SMI":  "Société Métallurgique d'Imiter",  # sigle nu
    # ── Moyennes capitalisations ─────────────────────────────────────────────
    "AKD":  "Akdital",
    "ARD":  "Aradei Capital",
    "SAF":  "Sanlam Maroc",
    "OUL":  "Oulmès",
    "CIM":  "Ciments du Maroc",
    "CTM":  "CTM",
    "ZLD":  "Zellidja",
    "SOT":  "Sothema",
    "MSA":  "Sodep-Marsa Maroc",
    "ADI":  "Alliances",
    "ADH":  "Douja Prom Addoha",
    "TGCC": "TGCC SA",
    "CFGB": "CFG Bank",
    "CASH": "Cash Plus SA",
    "SGTM": "SGTM SA",
    "CMGP": "CMGP Group",
    "VCNE": "Vicenne",
    "RIS":  "Risma",
    "CSR":  "Cosumar",
    "SNA":  "Sonasid",
    "SRM":  "Société de Réalisations Mécaniques",  # la forme sociale était amputée
    "RDS":  "Résidences Dar Saada",
    "ALU":  "Aluminium du Maroc",
    "MGL":  "Maghrebail",
    "DAR":  "Dari Couspate",
    "IMI":  "Immorente Invest",
    "DTT":  "Disty Technologies",
    # ── Petites capitalisations ──────────────────────────────────────────────
    "DSW":  "Disway",
    "MOX":  "Maghreb Oxygène",
    "STR":  "Stroc Industrie",
    "TIM":  "Timar",
    "SNP":  "SNEP",
    "SLM":  "Salafin",
    "JET":  "Jet Contractors",
    "M2M":  "M2M Group",
    "INV":  "Involys",
    "S2M":  "S2M",  # « S.M Monétique » était une troncature de screener ; le relevé de la cote et le marché disent S2M
    "COL":  "Colorado",
    "AFM":  "AFMA",
    "AGM":  "Agma",
    "FNB":  "Fénie Brossette",
    "BAL":  "Balima",
    "NEJ":  "Auto Nejma",
    "HAL":  "Auto Hall",
    "BMC":  "BMCI",
    "CAR":  "Cartier Saada",
    "AFI":  "Afric Industries SA",
    "MIC":  "Microdata",
    "MUT":  "Mutandis SCA",
    "ENK":  "Ennakl",
    "EQD":  "Crédit Eqdom",
    "DHO":  "Delta Holding",
    "PPM":  "Promopharm SA",
    "REB":  "Rebab",
    "SBS":  "Société des Boissons du Maroc",
    "STK":  "Stokvis Nord Afrique",
    "UNI":  "Unimer",
    "IBM":  "IB Maroc.com",
    # ── Ajouts du 10/08/2026 : cotés à la BVC mais absents de notre univers.
    # ISIN vérifiés chacun sur au moins deux sources indépendantes ; détail
    # dans ISIN_MAP plus bas.
    "T2S":  "T2S Group Holding",
    "MDP":  "Med Paper",
    "DLM":  "Delattre Levivier Maroc",
    "DIS":  "Diac Salaf",
}

# ── Secteurs ────────────────────────────────────────────────────────────────
# Taxonomie canonique, 22 secteurs pour 81 sociétés (moyenne 3,7 par secteur).
#
# Elle remplace une table qui comptait 43 libellés — dont « Technologies »,
# « Technologies & Paiement » et « Distribution IT » comme trois secteurs
# distincts, et 19 secteurs à membre unique. À cette granularité un filtre
# sectoriel ne filtre rien et une moyenne sectorielle n'a aucun sens
# statistique (cf. whatsapp_analysis/phase7_stocks.py, qui calcule un
# sector_rank et des agrégats par secteur).
#
# Méthode : croisement de notre table historique avec celle de casabourse.app
# (82 sociétés, relevé du 09/08/2026). Aucune des deux ne fait autorité — les
# deux contenaient des erreurs, corrigées ici :
#   VCNE  était « Distribution pétrolière » chez nous, « Immobilier » chez eux
#   NEJ   était « Pétrole & Gaz » chez nous — Auto Nejma distribue des voitures
#   BAL   était « Assurances » chez nous — Balima est une foncière
#   AFI   était « Industrie » chez nous — Afric Industries produit des abrasifs
#
# ⚠️ Le référentiel officiel BVC (casablanca-bourse.com) n'était pas joignable
# au moment de cette révision. Les six classements ci-dessous restent à valider
# contre la fiche officielle : VCNE, REB, BAL, NEJ, AFI, SRM.
COMPANY_SECTORS: dict = {
    # ⚠️ SECTEURS ALIGNÉS SUR LE RÉFÉRENTIEL DE LA COTE (17/09/2026).
    #
    # Trois taxonomies coexistaient et se contredisaient : celle-ci (22 valeurs),
    # `SECTOR_MAP` dans whatsapp_analysis/phase7_stocks.py, et le champ `secteur`
    # de fondamentaux.json — 45 libellés libres, du type « Mines - Plomb/Argent/
    # Zinc » ou « Fintech / Paiements SaaS ». 55 titres sur 77 divergeaient du
    # relevé officiel. Un secteur écrit trois fois de trois façons n'est pas un
    # classement, c'est trois classements.
    #
    # La source est désormais `datasets/referentiel/cote_bvc.json`, et un test
    # bloquant vérifie la concordance.
    #
    # ⚠️ Le secteur n'entre dans AUCUN calcul de score — vérifié avant la bascule.
    # Aucune note ne bouge (R8).
    "ADH": "Immobilier",
    "ADI": "Immobilier",
    "AFI": "Industrie",
    "AFM": "Assurance",
    "AGM": "Assurance",
    "AKD": "Santé",
    "ALU": "Matériaux",
    "ARD": "Immobilier",
    "ATL": "Assurance",
    "ATW": "Banque",
    "BAL": "Immobilier",
    "BCP": "Banque",
    "BMC": "Banque",
    "BOA": "Banque",
    "CAR": "Agroalimentaire",
    "CASH": "Finance",
    "CDM": "Banque",
    "CFGB": "Banque",
    "CIH": "Banque",
    "CIM": "Matériaux",
    "CMGP": "Industrie",
    "CMT": "Mines",  # absent du relevé du 16/09 — Minière Touissit — plomb, zinc, argent
    "COL": "Matériaux",
    "CSR": "Agroalimentaire",
    "CTM": "Transport",
    "DAR": "Agroalimentaire",
    "DHO": "Holding",
    "DIS": "Finance",  # absent du relevé du 16/09 — Diac Salaf — société de financement
    "DLM": "Industrie",  # absent du relevé du 16/09 — Delattre Levivier Maroc — chaudronnerie et montage industriel
    "DSW": "Technologie",
    "DTT": "Technologie",
    "ENK": "Automobile",
    "EQD": "Finance",
    "FNB": "Distribution",
    "GAZ": "Énergie",
    "HAL": "Distribution",
    "HPS": "Technologie",
    "IAM": "Télécom",
    "IBM": "Technologie",
    "IMI": "Immobilier",
    "INV": "Technologie",
    "JET": "Construction",
    "LBV": "Distribution",
    "LES": "Agroalimentaire",
    "LHM": "Matériaux",
    "M2M": "Technologie",
    "MDP": "Industrie",
    "MGL": "Finance",
    "MIC": "Technologie",
    "MNG": "Mines",
    "MOX": "Matériaux",
    "MRL": "Finance",
    "MSA": "Transport",
    "MUT": "Agroalimentaire",
    "NEJ": "Distribution",
    "OUL": "Agroalimentaire",
    "PPM": "Santé",
    "RDS": "Immobilier",
    "REB": "Industrie",
    "RIS": "Tourisme",
    "S2M": "Technologie",
    "SAF": "Assurance",
    "SBS": "Agroalimentaire",
    "SGTM": "Construction",
    "SLM": "Finance",
    "SMI": "Mines",
    "SNA": "Matériaux",
    "SNP": "Matériaux",
    "SOT": "Santé",
    "SRM": "Industrie",
    "STK": "Distribution",
    "STR": "Industrie",
    "T2S": "Santé",
    "TGCC": "Construction",
    "TMA": "Énergie",
    "TQA": "Énergie",
    "UNI": "Agroalimentaire",
    "VCNE": "Santé",
    "WAF": "Assurance",
    "ZLD": "Industrie",
}

# ── Sigles ambigus ──────────────────────────────────────────────────────────
# Tickers qui sont aussi des mots courants en français ou en darija. Partout où
# l'on cherche un sigle dans du texte libre — actualités, corpus WhatsApp — ils
# ne comptent qu'en MAJUSCULES, et encore : « une DAR à Marrakech » ou « paiement
# CASH » restent des faux positifs. On les exclut donc de la reconnaissance par
# sigle ; leur nom complet suffit à les retrouver (« dari couspate », « cash plus »).
#
# Liste établie en mesurant, sur un corpus français réel, combien de fois chaque
# ticker apparaît comme mot isolé : « les » sortait 140 fois sur 300 articles.
# Ne pas l'allonger par précaution — chaque entrée coûte du rappel.
SIGLES_AMBIGUS: set = {
    "LES", "CAR", "DAR", "GAZ", "BAL", "SOT", "COL", "UNI",
    "CASH", "RIS", "SAF", "TIM", "MIC", "MUT", "ADI", "NEJ",
    "DIS", "MDP",
}

ISIN_MAP: dict = {
    "ADH": "MA0000011512", "AFM": "MA0000012296", "AFI": "MA0000012114",
    "GAZ": "MA0000010951", "AGM": "MA0000010944", "AKD": "MA0000012585",
    "ADI": "MA0000011819", "ALU": "MA0000010936", "ARD": "MA0000012460",
    "ATL": "MA0000011710", "ATW": "MA0000012445", "HAL": "MA0000010969",
    "NEJ": "MA0000011009", "BAL": "MA0000011991", "BOA": "MA0000012437",
    "BCP": "MA0000011884", "BMC": "MA0000010811", "CAR": "MA0000011868",
    "CDM": "MA0000010381", "CIH": "MA0000011454", "CIM": "MA0000010506",
    "CMT": "MA0000011793", "COL": "MA0000011934", "CSR": "MA0000012247",
    "CTM": "MA0000010340", "DAR": "MA0000011421", "DHO": "MA0000011850",
    "DTT": "MA0000012536", "DSW": "MA0000011637", "ENK": "MA0000011942",
    "EQD": "MA0000010357", "FNB": "MA0000011587", "HPS": "MA0000012619",
    "IBM": "MA0000011132", "IMI": "MA0000012387", "INV": "MA0000011579",
    "JET": "MA0000012080", "LBV": "MA0000011801", "LHM": "MA0000012320",
    "LES": "MA0000012031", "M2M": "MA0000011678", "MOX": "MA0000010985",
    "MGL": "MA0000011215", "MNG": "MA0000012866",
    # MRL — Maroc Leasing. Corrigé le 01/09/2026 : portait MA0000012270, que le
    # journal du 02/07 signalait déjà comme « absent du référentiel BVC officiel »
    # sans savoir par quoi le remplacer.
    # Source : fiche société CDG Capital Bourse (société de bourse agréée),
    # /Bourse/market/MLE?tab=FicheSociete, relevée le 01/09/2026 — « MLE ·
    # MAROC LEASING · MA0000010035 ».
    # Recoupement arithmétique, c'est lui qui emporte la décision : capital
    # social 277 676 800 ÷ valeur nominale 100 = 2 776 768 titres ; la
    # capitalisation de la fiche, 1 081 689 974,40, divisée par ce nombre donne
    # 389,55 — au centime le cours que nous publions. Même instrument, donc.
    "MRL": "MA0000010035",
    "IAM": "MA0000011488", "MIC": "MA0000012163", "MUT": "MA0000012395",
    "OUL": "MA0000010415", "PPM": "MA0000011660", "REB": "MA0000010993",
    "RDS": "MA0000012239", "RIS": "MA0000011462", "S2M": "MA0000012106",
    "SLM": "MA0000011744", "SAF": "MA0000012007", "SMI": "MA0000010068",
    "STK": "MA0000012700", "SNP": "MA0000011728", "MSA": "MA0000012312",
    "SON": "MA0000010019", "SOT": "MA0000012833", "SRM": "MA0000011595",
    "SBS": "MA0000010365", "STR": "MA0000012056", "TQA": "MA0000012205",
    "TGC": "MA0000012528", "TIM": "MA0000011686", "TMA": "MA0000012262",
    "UNI": "MA0000012023", "WAF": "MA0000010928", "ZLD": "MA0000010571",
    # IPOs
    "CFGB": "MA0000012627", "CMGP": "MA0000012718", "VCNE": "MA0000012759",
    "CASH": "MA0000012767", "SGTM": "MA0000012783",
    # Aliases utilisés par le pipeline v9
    "TGCC": "MA0000012528",  # alias de TGC
    "SNA":  "MA0000010019",  # alias de SON
    # ── Ajouts du 10/08/2026 ────────────────────────────────────────────────
    # Sociétés cotées qui manquaient à notre univers. Chaque ISIN est recoupé
    # sur deux sources au moins, conformément à la règle d'audit croisé (R2) :
    #   T2S  note d'information AMMC (« Code ISIN MA0000012858 · Ticker T2S »)
    #        + capitalisation IDBourse = 240,20 × 21 785 174 au centime près
    #   MDP  URL instrument CDG Capital Bourse + fiche BVC codevaleur 6500
    #   DLM  URL instrument CDG Capital Bourse (profil société)
    #   DIS  URL instrument CDG Capital Bourse ET ebourse CIH Bank
    "T2S":  "MA0000012858",
    "MDP":  "MA0000012593",
    "DLM":  "MA0000012551",
    "DIS":  "MA0000010639",
}

TICKERS_DEFAUT: list = [
    "SMI", "MNG", "RIS", "RDS", "CSR", "SOT",
    "ADI", "MSA", "ADH", "TGC", "CMT", "SRM",
    "CFGB", "CMGP", "VCNE", "CASH", "SGTM",
]

IDB_NAME_MAP: dict = {"MTO": "CMT", "ALLI": "ADI", "TGC": "TGCC", "GTM": "SGTM"}

# ── Mapping OFFICIEL IDBourse ↔ nos tickers ─────────────────────────────────
# IDBourse (DATA+ / screener) utilise sa propre nomenclature de tickers.
# Cette table fait AUTORITÉ : en cas d'anomalie nom/ticker, IDBourse prime.
# clé = NOTRE ticker (bvc_config) → valeur = ticker IDBourse.
# ⚠️ Inversions critiques à ne jamais confondre :
#   - IDBourse "SNA" = STOKVIS NORD AFRIQUE  → notre STK
#   - IDBourse "SID" = SONASID               → notre SNA
#   - IDBourse "SBM" = STE DES BOISSONS MAROC → notre SBS
IDB_TICKER_MAP: dict = {
    "ADH": "ADH",   "ADI": "ADI",   "AFI": "AFI",   "AFM": "AFM",
    "AGM": "AGM",   "AKD": "AKT",   "ALU": "ALM",   "ARD": "ARD",
    "ATL": "ATL",   "ATW": "ATW",   "BCP": "BCP",   "BMC": "BCI",
    "BOA": "BOA",   "CAR": "CRS",   "CASH": "CAP",  "CDM": "CDM",
    "CFGB": "CFG",  "CIH": "CIH",   "CIM": "CMA",   "CMGP": "CMG",
    "CMT": "CMT",   "COL": "COL",   "CSR": "CSR",   "CTM": "CTM",
    "DAR": "DRI",   "DHO": "DHO",   "DSW": "DWY",   "DTT": "DYT",
    "ENK": "NKL",   "EQD": "EQD",   "FNB": "FBR",   "GAZ": "GAZ",
    "HAL": "ATH",   "HPS": "HPS",   "IAM": "IAM",   "IBM": "IBC",
    "IMI": "IMO",   "INV": "INV",   "JET": "JET",   "LBV": "LBV",
    "LES": "LES",   "LHM": "LHM",   "M2M": "M2M",   "MGL": "MAB",
    # BAL et REB — ajoutés le 02/09/2026. Le CLAUDE.md les notait « sans
    # ticker IDBourse » depuis le 02/07, et `fetch_all_cdg` les écartait donc
    # en silence faute de traduction. CDG les sert pourtant sous leur propre
    # code : « BALIMA » et « REBAB COMPANY », vérifiés sur la charge utile, et
    # aucun de nos autres titres ne revendiquait ces codes.
    # ⚠️ L'identité n'est PAS supposée par égalité de chaîne — c'est le piège
    # SNA/Stokvis. Elle est lue dans le libellé servi par la source.
    "BAL": "BAL",   "REB": "REB",
    "MIC": "MIC",   "MNG": "MNG",   "MOX": "MOX",   "MRL": "MLE",
    "MSA": "MSA",   "MUT": "MUT",   "NEJ": "NEJ",   "OUL": "OUL",
    "PPM": "PRO",   "RDS": "RDS",   "RIS": "RIS",   "S2M": "S2M",
    "SAF": "SAH",   "SBS": "SBM",   "SGTM": "GTM",  "SLM": "SLF",
    "SMI": "SMI",   "SNA": "SID",   "SNP": "SNP",   "SOT": "SOT",
    "SRM": "SRM",   "STK": "SNA",   "STR": "STR",   "TGCC": "TGC",
    "TMA": "TMA",   "TQA": "TQM",   "UNI": "UMR",   "VCNE": "VCN",
    "WAF": "WAA",   "ZLD": "ZDJ",
    "T2S": "T2S",   "MDP": "MDP",   "DLM": "DLM",   "DIS": "DIS",
    # ZLD ajouté le 10/08/2026. La colonne "-" observée le 02/07 venait de la
    # page idbourse.com/masi, qui ne liste que les composantes de l'indice —
    # Zellidja n'en fait pas partie. L'API la renvoie bien :
    #     {"name": "ZELLIDJA S.A", "url": ".../instruments/ZDJ", "dernier_cours": 345}
    # Sans cette entrée, la ligne était rejetée et ZLD retombait sur le
    # statique (243 DH au lieu de 345, soit -30%).
    #
    # Sociétés SANS ticker IDBourse : BAL (Balima), REB (Rebab Company)
    # → laissées telles quelles. TIM (Timar) : absente du listing.
}


# ⚠️ RÈGLE DE PRUDENCE PROVISOIRE — 15/10/2026 (accord d'Abd Moutalib, verdict
# externe). Sous ce seuil de couverture APPLICABLE (poids des composantes
# mesurées, hors composantes sans objet pour le métier), la note reste publiée
# comme indicative mais aucun verdict de palier n'est émis : « Couverture
# partielle ». 75 % n'est PAS une frontière validée ; à revoir par mesure.
COUVERTURE_VERDICT_MIN = 0.75

# ⚠️ RÈGLE A — TITRES TRÈS PEU LIQUIDES NON COMPARABLES (27/10/2026, accord R8
# d'Abd Moutalib). Quand le pilier technique est neutralisé faute d'échanges
# (`technique_neutralise` publié) ET que son `montant_median_dh` est sous ce
# seuil, la note v53 reste calculée et affichée mais n'est PAS comparable à
# celle d'un titre liquide : signal « Non comparable (liquidité) », champ
# `_meta.non_comparable`, rang après tous les titres comparables. « SUSPENDU »
# et « Données insuffisantes » gardent la priorité ; la règle passe avant
# « Couverture partielle ».
#   · La médiane est celle de `pipeline/technique_fiable.py` : montant (cours ×
#     titres) des 20 dernières séances ÉCHANGÉES — convention de la mesure
#     préalable, gardée telle quelle. Ce n'est pas `_meta.echange_median_dh`
#     (point « liquidité » de la confiance), calculé autrement.
#   · Sans aucune séance échangée, la médiane est absente : traitée comme 0.
#   · 100 000 DH est le seuil du point « liquidité » de la confiance ; il est
#     sous celui de la neutralisation technique (125 947 DH). Pas une frontière
#     validée par mesure de performance : une convention de lisibilité.
SEUIL_NON_COMPARABLE_DH = 100_000


def code_affiche(sym: str) -> str:
    """Le code OFFICIEL BVC d'un symbole interne — celui que la fiche affiche
    (`data.json › code_bvc`). Tout texte publié l'emploie (14/10/2026) : notre
    clé interne « SNA » est Sonasid, le code officiel « SNA » est Stokvis."""
    return IDB_TICKER_MAP.get(sym, sym)

# ── Opérations sur titres : splits (divisions de valeur nominale) ───────────
# Les sources historiques (XLSX, BVCscrap) identifient les sociétés par NOM et
# renvoient des cours NON ajustés : après un split, tout l'historique antérieur
# reste à l'ancienne échelle → fausse chute de -90% dans le graphe, indicateurs
# (MA, Bollinger, 52w) faussés, et variation calculée hors limite BVC ±10% (R10).
#
# Chaque entrée : date d'effet + ratio. Les cours ANTÉRIEURS à la date d'effet
# sont divisés par le ratio. Ne s'applique qu'aux données FRAÎCHEMENT
# téléchargées — les candles déjà stockées sont ajustées (cf. adjust_splits).
# ─────────────────────────────────────────────────────────────────────────────
# JOURS FÉRIÉS À DATE FIXE
# ─────────────────────────────────────────────────────────────────────────────
# UNIQUEMENT les fêtes du calendrier grégorien : leur date ne bouge jamais,
# donc cette table ne périme pas. Les fêtes religieuses (Aïd al-Fitr, Aïd
# al-Adha, Nouvel an hégirien, Mawlid) suivent le calendrier lunaire et ne sont
# confirmées par décret que quelques jours à l'avance — les inscrire ici
# produirait une liste fausse au bout d'un an, et une liste fausse est pire
# que pas de liste : elle donne une confiance injustifiée.
#
# ⚠️ Ce calendrier n'est PAS l'autorité. Il ne fait qu'abaisser le seuil de
# `_recaler_seance_fantome()`, qui reste le juge : c'est la donnée du marché
# qui décide si une séance a eu lieu, pas une table écrite d'avance. Si la
# Bourse cotait un jour férié, la détection statistique ne s'y tromperait pas.
#
# Le 14/08/2026 (Allégeance Oued Eddahab) est le cas qui a motivé cette table :
# 71 bougies écrites pour un jour sans cotation.
JOURS_FERIES_FIXES: set = {
    (1,  1),   # Nouvel An
    (1, 11),   # Manifeste de l'Indépendance
    (1, 14),   # Nouvel An amazigh (Yennayer) — férié officiel depuis 2024
    (5,  1),   # Fête du Travail
    (7, 30),   # Fête du Trône
    (8, 14),   # Allégeance Oued Eddahab
    (8, 20),   # Révolution du Roi et du Peuple
    (8, 21),   # Fête de la Jeunesse
    (11, 6),   # Marche Verte
    (11, 18),  # Fête de l'Indépendance
}


# ⚠️ DES SÉANCES QUI ONT EU LIEU, PUIS N'ONT PLUS EXISTÉ.
#
# Un jour férié est connu d'avance. Une séance ANNULÉE ne l'est pas : elle
# s'ouvre, elle cote, et l'opérateur la retire après coup. Les cours ont été
# réellement échangés, et pourtant ils ne comptent pas.
#
# ⚠️ AUCUNE DE NOS TROIS SOURCES NE DIT QU'UNE SÉANCE A ÉTÉ ANNULÉE. Elles
# servent des cours, pas leur statut. Le 17/09/2026, BMCE a continué de servir
# 55 titres datés du jour, avec leurs volumes, des heures d'échange réparties de
# 09h30 à 11h18 — une séance parfaitement crédible pour qui ne lit que les
# chiffres. C'est un angle mort du moteur, et il ne se comble que par une
# déclaration écrite à la main.
#
# Cette table est donc une INSTRUCTION, au même titre que SUSPENSIONS : elle
# n'est pas déduite, elle est reçue.
# ─────────────────────────────────────────────────────────────────────────
# DÉCALAGE HORAIRE DU MAROC — un fait réglementaire, donc un registre
# ─────────────────────────────────────────────────────────────────────────
#
# ⚠️ POURQUOI CE REGISTRE EXISTE, ET CE QU'IL A COÛTÉ
#
# Le 23/09/2026, tout le raisonnement horaire du projet était faux d'une heure.
# Le Maroc a changé d'heure le DIMANCHE 20/09 À MINUIT et est passé à UTC+0 ;
# la base de fuseaux du conteneur, figée en avril 2025, l'ignorait et
# répondait encore UTC+1.
#
# Conséquences mesurées, toutes en production :
#   — le cron « 45 14 » présenté comme le run de 15h45 tombait en réalité à
#     14h45 locales, soit QUARANTE-CINQ MINUTES AVANT la clôture de 15h30 ;
#   — le contrôle d'horodatage plaçait la clôture une heure trop tôt et
#     acceptait donc un fichier qui ne la contenait pas ;
#   — le champ `updated` de data.json avançait d'une heure.
#
# ⚠️ ET J'AVAIS EU L'AVERTISSEMENT SANS LE COMPRENDRE. La veille, deux tests
# passaient en local et échouaient en intégration, avec exactement une heure
# d'écart. J'en ai conclu que le runner GitHub avait une base périmée et j'ai
# FORCÉ UTC+1 en dur. C'était l'inverse : le runner était à jour, et c'est moi
# qui ai inscrit l'erreur dans le code.
#
# La leçon tient en une ligne : **un décalage horaire est un fait déclaré par
# un État, pas une constante à deviner.** Il se constate sur pièce, comme un
# split ou une suspension — voir R11.
#
# Chaque entrée vaut À PARTIR de sa date, jusqu'à la suivante. Le Maroc est à
# UTC+1 depuis 2018, sauf pendant le Ramadan où il revient à UTC+0.
DECALAGES_MAROC: list = [
    {"depuis": "2018-10-28", "offset": 1,
     "source": "décret 2.18.855 — heure légale UTC+1 permanente"},
    {"depuis": "2026-02-08", "offset": 0,
     "source": "retour à UTC+0 pour le Ramadan 1447"},
    {"depuis": "2026-03-29", "offset": 1,
     "source": "fin du Ramadan, retour à UTC+1"},
    {"depuis": "2026-09-20", "offset": 0,
     "source": "changement d'heure du dimanche 20/09 à minuit, constaté sur "
               "place par Abd Moutalib le 23/09/2026 ; la base de fuseaux du "
               "conteneur (avril 2025) l'ignorait encore"},
]


def decalage_maroc(jour) -> int:
    """Le décalage horaire du Maroc, en heures, à la date donnée.

    `jour` est une chaîne « AAAA-MM-JJ » ou tout objet dont `str()` commence
    par une telle date. Renvoie 0 ou 1.

    ⚠️ Le registre FAIT FOI. On n'interroge pas la base de fuseaux du système :
    elle peut être plus ancienne que le dernier décret, et c'est exactement ce
    qui s'est produit le 23/09/2026.
    """
    d = str(jour)[:10]
    offset = DECALAGES_MAROC[0]["offset"]
    for e in DECALAGES_MAROC:
        if d >= e["depuis"]:
            offset = e["offset"]
        else:
            break
    return offset


def heure_maroc(instant: datetime | None = None) -> datetime:
    """L'heure légale marocaine, selon le registre `DECALAGES_MAROC`.

    `instant` : un datetime AVEC fuseau (maintenant si absent). Renvoie le même
    instant exprimé à l'heure du Maroc.

    ⚠️ C'EST LA SEULE HORLOGE DU PROJET. Relevé par l'audit indépendant du
    26/09 : la porte de rattrapage lisait `ZoneInfo("Africa/Casablanca")`,
    la garde shell du workflow `TZ=Africa/Casablanca date`, et le reste du
    moteur ce registre. Les deux premières répondaient UTC+1, le registre
    UTC+0 : la porte jugeait l'âge d'un fichier écrit à l'heure du registre
    avec une montre qui avançait d'une heure.
    """
    n = (instant or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return n.astimezone(timezone(timedelta(hours=decalage_maroc(n.date()))))


SEANCES_ANNULEES: dict = {
    "2026-09-17": {
        "motif": "séance définitivement arrêtée par la Bourse de Casablanca pour "
                 "incident technique. Toutes les transactions, saisies, "
                 "modifications et annulations d'ordres de la journée sont "
                 "annulées. La reprise se fera sur la base des carnets d'ordres "
                 "arrêtés à la clôture du mercredi 16 septembre, en tenant compte "
                 "de la validité des ordres.",
        "source": "communication de la Bourse de Casablanca relayée par Abd "
                  "Moutalib le 17/09/2026 ; incident signalé le matin même par "
                  "Alphabourse, « Bourse de Casablanca : la séance suspendue », "
                  "publié le 17/09/2026 à 10h39",
        "constate": "échanges observés de 09h30 à 11h18 puis plus rien ; "
                    "47 484 titres au total contre 216,3 MDH pour la séance "
                    "complète du 16/09",
        "⚠️": "Les cours de cette journée ont réellement été cotés. Ils sont "
              "néanmoins SANS OBJET : la Bourse les a annulés. Ne pas les "
              "republier, ne pas les conserver comme clôture, ne pas les "
              "utiliser comme référence de variation.",
    },
}


SEANCES_SANS_COTATION: dict = {
    "2026-07-30": {
        "motif": "Fête du Trône — la Bourse de Casablanca n'a pas ouvert. "
                 "Aucune séance n'a eu lieu ce jour-là.",
        "source": "(7, 30) figure dans JOURS_FERIES_FIXES depuis l'origine du "
                  "projet ; et les 27 exports « Cours » de l'opérateur reçus "
                  "les 22-23/09/2026 omettent tous cette date, alors qu'ils "
                  "listent les séances SANS ÉCHANGE. Deux pièces "
                  "indépendantes, dont une émanant de l'opérateur lui-même.",
        "constate": "34 titres portaient encore une bougie ce jour-là au "
                    "23/09/2026, dont 15 MASI 1. Leurs valeurs ne suivent "
                    "aucun motif unique : 3 des 15 valent la clôture de la "
                    "VEILLE, 5 celle du LENDEMAIN, les 7 autres ne "
                    "correspondent à aucune séance connue.",
        "⚠️": "À ne pas confondre avec une séance ANNULÉE. Le 17/09 a "
              "réellement été coté puis annulé par la Bourse ; le 30/07 n'a "
              "jamais eu lieu. La conséquence sur les séries est la même — la "
              "bougie n'a pas lieu d'être — mais la cause diffère, et c'est "
              "elle qu'un registre doit consigner.",
    },
}


def seance_sans_cotation(date_iso: str) -> bool:
    """Vrai si la Bourse n'a pas ouvert ce jour-là.

    ⚠️ DISTINCT DE `seance_annulee()`, ET CE N'EST PAS UNE NUANCE D'ÉCRITURE.
    Une séance annulée A EU LIEU puis a été effacée par l'opérateur ; une
    séance sans cotation n'a jamais existé. Les deux sortent des séries, mais
    seule la première a pu servir de référence de variation à quelqu'un.

    ⚠️ ET CE REGISTRE NE REMPLACE PAS `JOURS_FERIES_FIXES` : celui-là dit quels
    jours du calendrier sont fériés, celui-ci quelles DATES précises n'ont pas
    coté — y compris les fériés mobiles, que le calendrier lunaire rend
    impossibles à déduire d'une règle.

    Même prudence que `seance_annulee` sur les entrées nulles.
    """
    try:
        return date_iso[:10] in SEANCES_SANS_COTATION
    except (TypeError, IndexError):
        return False


def seance_annulee(date_iso: str) -> bool:
    """Vrai si cette séance a été annulée par l'opérateur après coup.

    ⚠️ Même prudence que `est_ferie_fixe` sur les entrées nulles : `date_iso`
    vaut None dès qu'un titre n'a pas de séance connue.
    """
    try:
        return date_iso[:10] in SEANCES_ANNULEES
    except (TypeError, IndexError):
        return False


def est_ferie_fixe(date_iso: str) -> bool:
    """Vrai si la date « AAAA-MM-JJ » tombe sur un férié à date fixe."""
    # ⚠️ `TypeError` fait partie des cas à absorber : `date_iso` vaut None dès
    # qu'un titre n'a pas de séance connue (`_meta.prix_asof` peut être nul), et
    # `None[:10]` lève TypeError et non AttributeError. Sans lui, un appel sur
    # un titre non coté faisait tomber le run entier. Trouvé par les tests.
    try:
        _, m, j = date_iso[:10].split("-")
        return (int(m), int(j)) in JOURS_FERIES_FIXES
    except (ValueError, AttributeError, TypeError):
        return False


SPLITS: dict = {
    # Managem : VN 100 → VN 10 le 27/07/2026. Actions 11 864 676 → 118 646 760.
    # Nouvel ISIN MA0000012866 (ancien MA0000011058 radié).
    "MNG": [{"date": "2026-07-27", "ratio": 10}],

    # Sothema : VN 50 → VN 10 le 05/05/2026. Actions ×5 → 38 309 500.
    # AGE du 25/03/2026. Ajouté le 08/09/2026 — le split avait été appliqué à
    # la main dans `bpa.json` et dans les chandelles, mais JAMAIS déclaré ici.
    # ⚠️ Sans cette entrée, un re-téléchargement complet de l'historique
    # réintroduisait des cours pré-split : c'est exactement le défaut du 01/08
    # sur Managem, « l'ajustement split ne tenait qu'un run ». Sothema était
    # juste par chance, pas par construction.
    # ⚠️ Les chandelles stockées sont DÉJÀ ajustées (aucune rupture détectée le
    # 08/09). `adjust_splits()` ne s'applique qu'aux séries fraîchement
    # téléchargées, avant fusion : aucun risque de double division.
    # ⚠️ ISIN À TRANCHER : la presse donne MA0000012833 comme code POST-split,
    # ce que porte notre ISIN_MAP ; le référentiel Maroclear des valeurs
    # actives, relevé le 05/09, donne MA0000012502. Les deux ne peuvent pas
    # être vrais. Ne rien changer sans recoupement — R2.
    "SOT": [{"date": "2026-05-05", "ratio": 5}],
}


# ─────────────────────────────────────────────────────────────────────────────
# Suspensions de cotation
# ─────────────────────────────────────────────────────────────────────────────
#
# Ouvert le 09/09/2026, après CMT.
#
# CE QUE LE MOTEUR NE SAVAIT PAS FAIRE
# ────────────────────────────────────
# Un titre suspendu ne cote plus. La source, elle, continue de rediffuser le
# dernier cours connu, estampillé du jour. Le moteur y voyait donc une séance
# normale à variation nulle : il a écrit 28 chandelles fantômes sur CMT, du
# 17/07 au 01/09, toutes à 4 350 DH et volume zéro — et il a publié dessus un
# signal **ACHETER ★★** sur un instrument que personne n'a le droit d'acheter.
#
# POURQUOI LES GARDE-FOUS EXISTANTS N'ONT PAS SUFFI
# ─────────────────────────────────────────────────
# Trois s'en sont approchés sans conclure :
#   · R9 (chg=0 ET vol=0) a bien reconnu la donnée comme stale — c'est même
#     exactement sa signature — mais « stale » veut dire « pas rafraîchi », pas
#     « ne cote plus ». Le titre était marqué stale ET portait un signal.
#   · le plafond de liquidité du 01/09 a ramené la confiance à 2, parce que le
#     volume médian est nul. Mais le garde-fou d'affichage se déclenche à 1.
#   · l'étape 6c refuse d'écrire une bougie depuis un prix stale — elle a bien
#     joué ; les 28 bougies viennent d'avant, quand la source datait encore le
#     cours du jour.
# Aucun ne pouvait conclure, parce qu'aucun ne dispose de l'information : la
# suspension est un FAIT JURIDIQUE publié par le régulateur, pas une propriété
# statistique de la série. Elle ne se déduit pas des cours — un titre suspendu
# et un titre simplement illiquide produisent exactement les mêmes nombres.
# D'où ce registre, tenu à la main comme SPLITS, et sourcé.
#
# ⚠️ Une suspension a une FIN, et elle n'est pas connue d'avance. Laisser
# `reprise` à None signifie « toujours suspendu ». À relire à chaque avis AMMC.
COTATION_AU_FIXING: dict = {
    # ⚠️ Inscrit le 03/10/2026, sur pièce. Les titres peu liquides ne cotent
    # pas en continu (09h30-15h30) mais au FIXING de 14h30 : un seul prix par
    # séance, donc ouverture = plus haut = plus bas = clôture. Les figures qui
    # lisent les mèches (marteau, avalement, doji) et l'amplitude des séances
    # (ATR) n'y ont pas de sens.
    #
    # ⚠️ LE MODE CHANGE DANS LE TEMPS : la Bourse reclasse selon la liquidité.
    # Mesuré dans nos chandelles (part des séances plates, O=H=B=C) :
    #   SRM  continu jusqu'en juillet 2026, fixing depuis août (18/18)
    #   EQD  fixing depuis février 2026 environ
    #   AFM  fixing depuis février 2026 environ
    #   SLM  fixing d'août 2025 à juin 2026, REVENU en continu en juillet 2026
    # Cette liste n'établit donc le mode que pour la séance qu'elle date. Pour
    # l'historique, c'est la bougie elle-même qui dit si elle porte des
    # extrêmes réels — jamais cette liste appliquée à reculons.
    "seance": "2026-10-02",
    "source": ("CDG Capital Bourse, « Indices du samedi 3 octobre 2026 » "
               "(séance du vendredi 02/10, transactions horodatées 14:30-14:32), "
               "sha256 5ae9c28a…, fourni par Abd Moutalib"),
    # Nos tickers. Codes officiels du bulletin : AFM AGM BAL DIS DLM DRI EQD
    # MAB MLE NEJ OUL PRO REB SAM SRM UMR. SAM (Samir) est hors univers.
    "tickers": ["AFM", "AGM", "BAL", "DIS", "DLM", "DAR", "EQD", "MGL",
                "MRL", "NEJ", "OUL", "PPM", "REB", "SRM", "UNI"],
}


SUSPENSIONS: dict = {
    # Diac Salaf — société de financement EN LIQUIDATION JUDICIAIRE.
    # ⚠️ Inscrit le 03/10/2026. Abd Moutalib : « sous liquidation judiciaire
    # depuis 2013 » — le jugement n'a pas encore été lu, la date de 2013 reste
    # donc une déclaration. Ce qui est ÉTABLI sur pièce : l'export « Cours » de
    # l'opérateur (casablanca-bourse.com, 03/10/2023 → 02/10/2026, sha256
    # 5f5c0167…, datasets/historiques_importes/DIS.json) ne compte AUCUNE
    # transaction en trois ans ; sa seule ligne cotée est la séance annulée du
    # 17/09/2026, à 0 titre. Le terminal publiait pourtant 26,25 DH, une note
    # de 5,0 et le signal ATTENDRE : un titre qui ne cote pas n'a ni signal ni
    # note. La suspension court depuis la première date de la pièce.
    "DIS": [{
        "depuis": "2023-10-03",
        "motif": "liquidation judiciaire (depuis 2013 selon Abd Moutalib, jugement non lu) — aucune transaction",
        "source": "casablanca-bourse.com, export « Cours » 03/10/2023 → 02/10/2026 : 0 titre échangé, 0 transaction",
        "url": "datasets/historiques_importes/DIS.json",
    }],
    # Delattre Levivier Maroc — EN LIQUIDATION.
    # ⚠️ Inscrit le 03/10/2026. Abd Moutalib : « suspendu depuis le 09/01/2023,
    # liquidation » — date déclarée, pièce juridique non lue. Ce qui est ÉTABLI
    # sur pièce : l'export « Cours » de l'opérateur (04/10/2023 → 02/10/2026,
    # sha256 ecba3872…, datasets/historiques_importes/DLM.json) ne compte AUCUNE
    # transaction en trois ans. Même traitement que DIS : la suspension court
    # depuis la première date de la pièce, pas depuis la date déclarée.
    "DLM": [{
        "depuis": "2023-10-04",
        "motif": "liquidation (suspendu depuis le 09/01/2023 selon Abd Moutalib, pièce non lue) — aucune transaction",
        "source": "casablanca-bourse.com, export « Cours » 04/10/2023 → 02/10/2026 : 0 titre échangé, 0 transaction",
        "url": "datasets/historiques_importes/DLM.json",
    }],
    # Compagnie Minière de Touissit — MASI 1.
    # OPA obligatoire d'AYRAD GROUP LIMITED, OSEAD Fund, OSEAD MAROC MINING et
    # la CIMR agissant de concert, déposée le 16/07/2026 après le franchissement
    # du seuil de 40 % des droits de vote (pacte d'actionnaires du 13/07/2026).
    # L'AMMC a demandé la suspension à la Bourse le 17/07 — avis DO/EM/07/2026.
    "CMT": [{
        "depuis": "2026-07-17",
        # ⚠️ REPRISE CONSTATÉE, PAS SUPPOSÉE. Le bulletin « Indices du mercredi
        # 16 septembre 2026 » de CDG Capital Bourse — sha256
        # 55f7c0790efc62435f45fa4ad63e83e1c471b9e033f4c935593df7fcefdb4a97 —
        # cote CMT à 2 438,00, +9,97 %, 1 titre échangé à 15:30:00. Les
        # bulletins des 14 et 15/09 la donnaient encore entièrement à zéro :
        # la reprise a donc eu lieu CE jour-là.
        #
        # ⚠️ LE COURS DE RÉFÉRENCE A ÉTÉ REMIS À ZÉRO PAR L'OPÉRATEUR. Le
        # +9,97 % implique une veille à 2 216,97, alors que la dernière séance
        # cotée du 16/07 fermait à 4 350. Ce n'est PAS un split et la série
        # historique ne doit pas être ajustée : c'est une reprise après OPA,
        # avec une nouvelle référence fixée par la Bourse.
        "reprise": "2026-09-16",
        "reprise_source": ("bulletin CDG « Indices du mercredi 16 septembre 2026 », "
                           "sha256 55f7c079…, CMT 2 438,00 +9,97 % à 15:30:00"),
        "cours_de_reprise": 2438.0,
        "reference_impliquee": 2217.0,
        # ⚠️ CHIFFRE LU CHEZ LE RÉGULATEUR, PLUS DÉDUIT D'UN BULLETIN.
        # Il valait 2216.97, obtenu en divisant le cours de reprise par sa
        # variation (2 438 ÷ 1,0997). La décision AMMC DO/EM/010/2026 du
        # 15/09/2026 fixe le prix de l'offre à 2 217 MAD exactement :
        # moyenne à parts égales du cours moyen pondéré 12 mois (2 523) et
        # de la transaction de référence (1 910). La variation publiée est
        # la même dans les deux cas — +9,97 % — mais un nombre déduit n'a
        # pas le statut d'un nombre établi par l'autorité.
        "reference_source": "AMMC, décision de recevabilité DO/EM/010/2026 du 15/09/2026, section 4 : cours moyen pondéré 12 mois 2 523 MAD (50 %) + transaction de référence 1 910 MAD (50 %) = 2 217 MAD",
        "reference_piece": "datasets/pieces_ammc/AMMC_recevabilite_OPA_CMT_2026-09-15.pdf",
        "reference_piece_sha256": "8240a798df3c4ef0d2c144e527beec377ce006ff19922181d1cd22ec15c028fa",
        "motif": "OPA obligatoire (Ayrad / OSEAD / CIMR)",
        "source": "AMMC, avis de dépôt DO/EM/07/2026 du 17/07/2026",
        "url": "https://www.ammc.ma/sites/default/files/OPA_Avis%20d%C3%A9p%C3%B4t_CMT_%20FR.pdf",
        # Dernière séance portant un VOLUME réel : 67 515 titres échangés.
        # ⚠️ La source diffuse depuis le 17/07 un cours de 4 350 DH, que le
        # moteur a recopié en 28 bougies à volume nul. On ne sait pas trancher
        # entre un dernier échange réel le matin du 17 avant la suspension et
        # un simple cours de référence : aucune de ces 28 lignes ne porte de
        # volume, et le bulletin CDG donne le titre entièrement à zéro. Le
        # chiffre est donc consigné tel qu'observé, sans lui prêter un sens
        # qu'aucune source ne confirme.
        "dernier_cours_cote": {"date": "2026-07-16", "valeur": 4501.0, "volume": 67515},
        "cours_diffuse_depuis_suspension": 4350.0,
    }],
}


# ⚠️ SOCIÉTÉS COTÉES SANS COMPTES DÉPOSÉS — registre créé le 06/10/2026.
#
# Un titre qui cote encore mais ne publie plus de comptes n'a pas de pilier
# fondamental : la table figée qui le remplaçait affichait une note (IBM : 5,2,
# ATTENDRE) sur des chiffres de 2022, sans rien dire. Comme une suspension, le
# fait se CONSTATE sur pièce (R11) : dernier dépôt lu au catalogue de l'AMMC.
# Effet : confiance plafonnée à 1, signal « Données insuffisantes », motif
# affiché sur la fiche. La note chiffrée reste visible, en gris.
SANS_COMPTES: dict = {
    "IBM": {
        "dernier_depot": "2023-10-31",
        "motif": "aucun compte déposé depuis l'exercice 2022 et le S1 2023 ; "
                 "demande de placement en redressement judiciaire (communiqué du 10/01/2023)",
        "source": "AMMC — IB_Maroc_2022_S1_23.pdf (31/10/2023) et "
                  "CP_IB_Maroc_redressement_judiciaire.pdf ; aucun dépôt 2023, 2024 ni 2025 "
                  "(datasets/exercice_2025_rectifie.json, _ecartes)",
    },
    # ⚠️ Inscrits le 10/10/2026 avec l'accord d'Abd Moutalib. Déjà dans
    # SUSPENSIONS (aucune transaction en trois ans). RADIATION NON ÉTABLIE :
    # aucune décision AMMC ni avis de la Bourse trouvés le 10/10 — d'où ce
    # registre et non VALEURS_RADIEES. À déplacer sur pièce de radiation.
    "DIS": {
        "dernier_depot": "2012-09-26",
        "motif": "agrément retiré par Bank Al-Maghrib le 28/02/2013, liquidation ; "
                 "dernier état : situation au 30/06/2012 (capitaux propres −160,3 MDH)",
        "source": "AMMC — Diac_S1_2012.pdf (attestation du 26/09/2012) et "
                  "CP_CDVM_Diac_Salaf_20130304.pdf ; aucun acte postérieur au catalogue",
        # Mention affichée — décision d'Abd Moutalib du 20/10/2026 : le titre
        # reste dans l'univers (la Bourse le liste encore, 20/10/2026), avec
        # son statut écrit en clair.
        "statut_juridique": "Liquidée",
    },
    "DLM": {
        "dernier_depot": "2022-04-29",
        "motif": "demande de mise en liquidation déposée le 04/11/2022 ; "
                 "derniers comptes : exercice 2021",
        "source": "AMMC — DLM_2021.pdf (29/04/2022), CP_DLM_post_CA_10_11_22.pdf ; "
                  "aucun dépôt postérieur au catalogue",
        # Mention affichée — décision d'Abd Moutalib du 20/10/2026.
        "statut_juridique": "Liquidation judiciaire",
    },
}


def sans_comptes(ticker: str) -> dict | None:
    """Le constat d'absence de comptes, ou None."""
    return SANS_COMPTES.get(ticker)


# ⚠️ FAMILLES DE LA NOTE FONDAMENTALE — 10/10/2026, décision d'Abd Moutalib :
# la note suit « les règles de l'art du marché marocain, selon la spécificité
# de chaque secteur ». Spécification de l'agent verificateur-finance.
#
# Par LISTE EXPLICITE de tickers, jamais par préfixe de `COMPANY_SECTORS` :
# ce dernier range ensemble des métiers qui ne se notent pas pareil (« Finance »
# réunit crédit-bail, paiement et crédit à la consommation ; « Assurance »
# réunit assureurs et courtiers ; « Immobilier » réunit foncières et
# promoteurs). Un titre absent de ces listes relève de la famille « autre »
# (industrie, distribution, services) — la grille d'origine.
#
# Cas à relire, laissés tels que la spécification les range :
#   · AFM, AGM — « Assurance » au référentiel, mais COURTIERS : pas de ROE
#     exploitable (`ROE_SANS_OBJET`), notés comme des sociétés de services.
#   · REB — « Industrie » au référentiel, traité en HOLDING (Rebab Company).
#   · DHO — « Holding » au référentiel (Delta Holding), laissé dans « autre ».
#   · ZLD — « Industrie » au référentiel ; groupe diversifié (Zellidja), laissé
#     dans « autre » faute de pièce tranchant son métier.
#   · DIS — « Finance », en liquidation : famille « financement », exclu des
#     médianes et de la note par `SANS_COMPTES`.
FAMILLES_NOTE: dict = {
    "banque":     ("ATW", "BCP", "BMC", "BOA", "CDM", "CFGB", "CIH"),
    "assurance":  ("ATL", "WAF", "SAF"),
    "financement": ("EQD", "MGL", "MRL", "SLM", "DIS"),
    "paiement":   ("CASH",),
    "holding":    ("REB",),
    "fonciere":   ("ARD", "IMI", "BAL"),
    "promoteur":  ("ADH", "ADI", "RDS"),
    "btp":        ("JET", "SGTM", "TGCC"),
    "mines":      ("CMT", "MNG", "SMI"),
    "telecom":    ("IAM",),
    "utility":    ("TQA",),
}

# ⚠️ MÉTHODE COMPTABLE PAR SOCIÉTÉ — registre créé le 27/10/2026, accord d'Abd
# Moutalib (idée reprise du dépôt BVC Nour, qui ne confond jamais une base
# sociale, une base IFRS et une base en normes marocaines ; AUCUN fait n'en est
# repris : chaque entrée ci-dessous est établie sur la pièce citée, relue ici).
#
# Pourquoi : un même ratio ne mesure pas la même chose selon la méthode. Une
# foncière qui évalue ses immeubles de placement à la JUSTE VALEUR (IAS 40)
# porte en résultat — donc dans son ROE — la variation de valeur du patrimoine ;
# une foncière qui les tient au COÛT HISTORIQUE (amortis) n'en porte aucune. La
# note par métier (`fond_score_sectoriel.noter`) ne suspend le ROE d'une
# foncière que si ce registre établit la juste valeur.
#
# Champs :
#   referentiel          le référentiel des comptes LUS PAR LA NOTE (la base des
#                        faits de pipeline/faits_financiers.json), cité.
#   immeubles_placement  "juste_valeur" | "cout" | "non_etabli". Jamais deviné :
#                        sans pièce, "non_etabli" — et la note garde alors la
#                        suspension prudente d'avant le registre.
#   source               fichier, url, sha256 de la copie relue, et pour chaque
#                        affirmation la page (page du PDF) et la citation exacte.
#
# ⚠️ Les rapports annuels cités ne sont PAS commités (10 à 16 Mo) : l'empreinte
# est celle de la copie relue le 27/10/2026 ; pour IMI, elle est identique à
# celle déjà enregistrée dans datasets/pieces/IMI/index.json.
METHODE_COMPTABLE: dict = {
    "ARD": {
        "exercice": 2025,
        "referentiel": "IFRS tel qu'adopté dans l'Union européenne — comptes consolidés",
        "immeubles_placement": "juste_valeur",
        "source": {
            "fichier": "Aradei_Capital_RFA_2025.pdf",
            "url": "https://www.ammc.ma/sites/default/files/Aradei_Capital_RFA_2025.pdf",
            "sha256": "272fdb3d9d6ead47bee49030106ae671774421580c0e7f4f44cf8d8fe354e658",
            "citations": [
                {"page": 7, "objet": "referentiel",
                 "texte": "La société Aradei Capital a établi les comptes consolidés au titre de l'exercice clos "
                          "le 31 Décembre 2025 en conformité avec le référentiel IFRS tel qu'adopté dans "
                          "l'Union Européenne et applicable à cette date."},
                {"page": 8, "objet": "immeubles_placement",
                 "texte": "En application de la norme IAS 40, les immeubles de placement sont valorisés à "
                          "leur valeur de marché."},
            ],
        },
    },
    "IMI": {
        "exercice": 2025,
        "referentiel": "normes comptables internationales (IFRS) adoptées dans l'Union européenne — comptes "
                       "consolidés (la société publie AUSSI des consolidés en normes marocaines ; la note lit "
                       "les IFRS : faits_financiers.json › IMI, base « consolidé IFRS »)",
        "immeubles_placement": "juste_valeur",
        "source": {
            "fichier": "Immorente_Invest_RFA_2025.pdf",
            "url": "https://www.ammc.ma/sites/default/files/Immorente_Invest_RFA_2025.pdf",
            "sha256": "a17430459e934288da9b28fe7c7a59f550bd4ecc28b74cb6af80515f0714b2b4",
            "citations": [
                {"page": 22, "objet": "referentiel",
                 "texte": "Les états financiers consolidés du Groupe Immorente Invest sont préparés en "
                          "conformité avec les normes comptables internationales adoptées au sein de l'Union "
                          "Européenne au 31 décembre 2025 et telles que publiées à cette même date."},
                {"page": 22, "objet": "immeubles_placement",
                 "texte": "Les immeubles de placement sont évalués à leur juste valeur. La périodicité de "
                          "réévaluation de la juste valeur est annuelle."},
            ],
        },
    },
    "BAL": {
        "exercice": 2025,
        "referentiel": "normes marocaines (Conseil National de Comptabilité) — comptes consolidés",
        "immeubles_placement": "cout",
        "source": {
            "fichier": "Balima_RFA_2025_0.pdf",
            "url": "https://www.ammc.ma/sites/default/files/Balima_RFA_2025_0.pdf",
            "sha256": "b81d7f5f74da6f29c27e25f04b696c3cc7c7b52a9dae7f66a93291cfcdd7c8e6",
            "citations": [
                {"page": 46, "objet": "referentiel",
                 "texte": "Les comptes consolidés du Groupe BALIMA sont établis conformément aux Normes "
                          "Marocaines telles que prescrites par le Conseil National de Comptabilité."},
                {"page": 47, "objet": "immeubles_placement",
                 "texte": "Le patrimoine immobilier n'a pas été réévalué et est inscrit au coût historique."},
                {"page": 60, "objet": "immeubles_placement",
                 "texte": "Le patrimoine immobilier n'a pas été réévalué et demeure inscrit au coût historique."},
            ],
        },
    },
}
EVALUATIONS_IMMEUBLES = ("juste_valeur", "cout", "non_etabli")


def methode_comptable(ticker: str) -> dict | None:
    """L'entrée du registre METHODE_COMPTABLE, ou None (non établie)."""
    return METHODE_COMPTABLE.get(ticker)


def immeubles_a_juste_valeur(ticker: str) -> bool | None:
    """True : juste valeur établie sur pièce ; False : coût établi sur pièce ;
    None : non établi (absent du registre, ou « non_etabli »)."""
    ev = (METHODE_COMPTABLE.get(ticker) or {}).get("immeubles_placement")
    return {"juste_valeur": True, "cout": False}.get(ev)
# ⚠️ OPÉRATIONS SUR LE CAPITAL DE L'EXERCICE 2025 — registre créé le 13/10/2026.
#
# R11 : une opération sur titres se CONSTATE sur pièce, elle ne se déduit pas
# d'une série. Une augmentation de capital ou une introduction en bourse dans
# l'exercice change le niveau des fonds propres sans rapport avec la
# rentabilité : la MOYENNE simple (31/12/2024, 31/12/2025) sous-estime alors les
# fonds propres réellement employés et surestime le ROE. La note par famille
# (`fond_score_sectoriel._roe`) écarte la moyenne et lit la clôture, étiquetée.
# Pondérer par la date n'est pas fait : seules deux dates sont sourcées (VCNE ;
# le visa de SOT, qui n'est pas la date de l'opération), et le profil des fonds
# propres dans l'exercice (résultat, dividendes) ne l'est pour aucun titre.
# Pièces : pipeline/faits_financiers.json (notes des faits fonds propres 2024 et
# nombre d'actions) et les rapports cités. Un titre absent d'ici peut encore voir
# sa moyenne écartée par la garde de variation (> 30 %), sans cause établie.
OPERATIONS_SUR_CAPITAL: dict = {
    "TGCC": {"exercice": 2025, "date": "2025-07-02", "apport_frais_mmad": 2199.99945,
             "nature": "augmentation de capital réservée au public de 2 199 999 450 MAD, décidée le 02/07/2025 "
                       "(la société est cotée depuis décembre 2021 : ce n'est PAS une introduction en bourse)",
             "source": "TGCC RFA 2025 p.64 et p.72 (« L'augmentation de capital social réservée au public pour "
                       "un montant de 2 199 999 450 dirhams »), cotation depuis décembre 2021 p.68 ; "
                       "faits_financiers.json › TGCC"},
    "VCNE": {"exercice": 2025, "date": "2025-07-15", "apport_frais_mmad": 719.979984,
             "nature": "augmentation de capital de l'introduction en bourse",
             "source": "Vicenne RFA 2025 p.58, tableau de variation des capitaux propres (719 979 984 MAD, "
                       "boucle exactement à 1 244 927 997) ; faits_financiers.json › VCNE"},
    "SOT": {"exercice": 2025, "date": None, "apport_frais_mmad": 630.428,
            "nature": "augmentation de capital par apport en nature (capital +20,336 ; prime +610,092 MMAD) et "
                      "entrée de Soludia Maghreb",
            "source": "Sothema RFA 2025 p.43 (visa AMMC du 09/12/2025 : date du visa, pas de l'opération) et "
                      "p.65 ; faits_financiers.json › SOT"},
    "CASH": {"exercice": 2025, "date": None, "apport_frais_mmad": None,
             "nature": "introduction en bourse : division du titre puis augmentation de capital (capital "
                       "54 250 → 245 531 KMAD), toutes deux avant la clôture",
             "source": "Cash Plus RFA 2025 (capital au 31/12/2025 : 24 553 090 actions) ; faits_financiers.json › CASH"},
    # CIH — corrigé le 14/10/2026 (contre-vérification) : l'APPORT FRAIS de l'augmentation de capital en
    # numéraire est de 1 500 MMAD (« augmentation de capital de 1,5 milliard de dirhams » p.79 ;
    # « 4 108 341 nouvelles actions » p.181, avis d'émission) — pas 1 680,619. Ce dernier chiffre est la
    # ligne « Opérations sur capital » du tableau de variation (p.26), part du groupe : capital +410,834,
    # réserves +1 269,785. Il englobe l'augmentation en numéraire ET d'autres opérations sur capital de
    # l'exercice (prime comprise, souscription du personnel) ; il est conservé SOUS UN AUTRE NOM,
    # `operations_sur_capital_tableau_mmad`, et ne sert pas de seuil.
    "CIH": {"exercice": 2025, "date": None, "apport_frais_mmad": 1500.0,
            "operations_sur_capital_tableau_mmad": 1680.619,
            "nature": "augmentation de capital en numéraire de 1,5 milliard de dirhams (4 108 341 actions "
                      "nouvelles) ; le tableau de variation des fonds propres part du groupe porte 1 680,619 MMAD "
                      "sur la ligne « Opérations sur capital »",
            "source": "CIH Bank RFA 2025 p.79 (« augmentation de capital de 1,5 milliard de dirhams ») et p.181 "
                      "(« émission de 4 108 341 nouvelles actions ») ; ligne « Opérations sur capital 1 680 619 » "
                      "du tableau de variation des capitaux propres p.26 ; datasets/resultats_s1_2026.json › CIH"},
    # SGTM — examiné le 14/10/2026 (RFA 2025 p.88-89) : en juin 2025, 100 MMAD d'augmentation en
    # numéraire et 800 MMAD d'incorporation de réserves, SANS effet sur les fonds propres ; l'introduction en
    # bourse n'apporte rien aux fonds propres au 31/12/2025. Apport frais : 100 ÷ 2 619,799 = 3,8 % des
    # fonds propres 2024, sous le seuil de 5 % : opération NON SIGNIFICATIVE, la moyenne tient.
    "SGTM": {"exercice": 2025, "date": "2025-06", "apport_frais_mmad": 100.0,
             "nature": "juin 2025 : augmentation en numéraire de 100 MMAD et incorporation de réserves de 800 MMAD "
                       "(sans effet sur les fonds propres) ; capital 300 000 → 1 200 000 KMAD ; l'introduction "
                       "en bourse n'apporte rien aux fonds propres au 31/12/2025",
             "source": "SGTM RFA 2025 p.87 (capital) et p.88-89 (opérations) ; faits_financiers.json › SGTM"},
}


# ─────────────────── nombre d'actions de la période, pour le BPA (IAS 33) ───────────────────
# RÈGLE e — 20/10/2026 (verificateur-finance, tranché par Abd Moutalib : la norme prime).
# IAS 33.19-20 : le BPA de base se calcule sur le nombre MOYEN PONDÉRÉ d'actions ordinaires en
# circulation pendant la période. IAS 33.21(a) : une émission en numéraire compte à partir de sa date
# (ici la date où l'organe social CONSTATE la réalisation) ; postérieure à la clôture, elle est exclue.
# IAS 33.26-28 et 33.64 : une division du nominal ou une attribution gratuite est rétro-ajustée sur
# TOUTES les périodes présentées, même si elle intervient après la clôture.
#
# Ce registre ne porte que les titres dont le capital a varié sur les périodes lues (exercice 2025,
# douze mois au 30/06/2026) ; un titre absent garde nombre pondéré = nombre actuel. Chaque mouvement
# porte sa pièce (R11 : une opération sur titres se CONSTATE, elle ne se déduit pas d'une série).
#   nature "numeraire" : `avant` → `apres`, compté à partir de `date` (exclu si après la fin) ;
#   nature "division"  : `ratio`, appliqué à tout ce qui précède `date`, quelle que soit la période.
# `denominateur_ambigu` : la pièce ne tranche pas le traitement IAS 33 → le calcul garde le nombre
# ACTUEL et publie `reserve` (consigne du 20/10/2026 : « n'invente pas »).
HISTORIQUE_ACTIONS: dict = {
    "CIH": {"mouvements": [
        {"date": "2025-07-31", "nature": "numeraire", "avant": 31497283, "apres": 35605624,
         "source": "CIH Bank RFA 2025 p.36 note R12 (« Nombre d'actions ordinaires émises 35 605 624 "
                   "31 497 283 », déc-25 / déc-24) et p.181 (« émission de 4 108 341 nouvelles actions », "
                   "communiqué « Résultats Augmentation de Capital ») ; date : communiqué de l'émetteur relayé "
                   "par boursenews.ma le 06/08/2025 : « Le Conseil d'Administration, réuni en date du "
                   "31 juillet 2025, a constaté la réalisation effective de cette opération » (souscription "
                   "du 4 au 23 juillet 2025). Le BPA S1 2025 publié (19,5) est sur 31 497 283 : émission "
                   "postérieure au 30/06/2025, confirmée."},
        {"date": "2026-07-28", "nature": "numeraire", "avant": 35605624, "apres": 38641338,
         "source": "CP_CIH_Bank_resultats_augmentation_capital_numeraire.pdf p.1 et "
                   "CP_CIH_resultats_augmentation_reservee_personnel.pdf p.1 (AMMC) : conseil du 28/07/2026, "
                   "« Nombre d'actions anciennes 35 605 624 / Nombre d'actions nouvelles 3 035 714 / Nouveau "
                   "nombre d'action total 38 641 338 » — après la clôture du 30/06/2026 : exclu."},
    ]},
    "CDM": {"mouvements": [
        {"date": "2026-07-23", "nature": "numeraire", "avant": 10881214, "apres": 11626499,
         "source": "https://www.ammc.ma/sites/default/files/CP_CDM_cloture_augmentation_capital.pdf p.1 : "
                   "« Le Directoire, lors de sa réunion du 23 juillet 2026, a constaté que l'augmentation du "
                   "capital social par émission de 745.285 actions nouvelles […] est définitivement réalisée » ; "
                   "capital porté à 1 162 649 900 DH. Avant : 10 881 214 (avis de dividende 2025 : "
                   "522 298 272 = 48 × 10 881 214 ; capital au 30/06/2026 1 088 121 KDH, CDM_S1_26.pdf). "
                   "Après la clôture du 30/06/2026 : exclu. ⚠️ Le dépôt S1 publie un RNPG par action 2025 "
                   "de 79,44 (10 870 xxx actions) contre 79,36 ici : écart de 0,1 % non expliqué (titres "
                   "propres ?), consigné."},
    ]},
    "TGCC": {"mouvements": [
        {"date": "2025-07-24", "nature": "numeraire", "avant": 31639850, "apres": 34674332,
         "source": "TGCC RFA 2025 (https://www.ammc.ma/sites/default/files/TGCC_RFA_2025.pdf) p.64 (pages "
                   "imprimées 126-127), tableau « Travaux du Conseil d'administration » : « Réunion du 02 "
                   "juillet 2025 Décision d'augmentation du capital social d'un montant de 2 199 999 450,00 "
                   "MAD » puis « Réunion du 24 juillet 2025 Constatation de l'augmentation du capital social "
                   "d'un montant de 30 344 820 MAD » (= 3 034 482 actions × 10 MAD de nominal). Nombres : p.102 "
                   "note 13 (« Nombre total d'actions 34 674 332 31 639 850 », déc-25 / déc-24), p.72 et p.98 "
                   "(« émission de 3 034 482 actions nouvelles »), 34 674 332 − 3 034 482 = 31 639 850. "
                   "Chronologie recoupée : souscription du 14 au 18/07/2025 et résultats définitifs "
                   "(3 034 482 actions attribuées à 725 MAD) dans CP_TGCC_resultats_augmentation_capital.pdf "
                   "p.1 (le PDF ne porte pas de date ; le calendrier du RFA p.68 place le « communiqué relatif aux "
                   "résultats de l'augmentation de capital » au 01/08/2025), capital 316 398 500 → "
                   "346 743 320 DH (p.78). Émission postérieure au 30/06/2025 : le BPA S1 2025 reste sur "
                   "31 639 850 ; comptée dans le douze mois et dans l'exercice 2025 à partir du 24/07/2025. "
                   "⚠️ Le tableau du RFA (note 13) retient le nombre de FIN d'exercice (34 674 332) pour le "
                   "résultat de base par action 27,46, non le nombre pondéré : le BPA 2025 publié par "
                   "l'émetteur est donc inférieur à celui d'IAS 33.19-21 ; la règle e (20/10/2026) prime."},
    ]},
    "T2S": {"denominateur_ambigu": True, "mouvements": [],
            "reserve": "BPA sur le nombre d'actions ACTUEL (21 785 174), faute de pouvoir trancher IAS 33. "
                       "Lu le 20/10/2026 dans T2S_IPO_DR_010_2026.pdf : les 1 239 actions de priorité A et "
                       "1 239 B (« assorties de droits financiers particuliers », p.26 note 6) étaient le plan "
                       "d'intéressement du management (MIP, p.152 : « actions ordinaires gratuites » « en "
                       "contrepartie de l'atteinte des objectifs de performance ») ; converties le 08/06/2026 "
                       "en 840 042 actions ordinaires par incorporation de réserves (p.28) ; nominal divisé "
                       "par 2 au premier jour de cotation (p.21) ; 1 569 506 actions nouvelles de l'introduction "
                       "(juillet 2026, p.37). Deux lectures d'IAS 33 restent possibles et aucune n'est écrite "
                       "par l'émetteur (pas de note « résultat par action ») : attribution gratuite rétro-"
                       "ajustée (IAS 33.28 : 20 215 668 actions, BPA 12 mois 9,25) ou actions à émission "
                       "conditionnelle comptées du 08/06/2026 (IAS 33.24 et 52 : ≈ 18,64 M, ≈ 10,03). Dans les "
                       "deux, les actions de l'introduction, postérieures à la clôture, seraient exclues : le "
                       "BPA publié ici (sur 21,79 M) est donc un PLANCHER."},
}


def actions_ponderees(ticker: str, debut: str, fin: str, actuel: int) -> dict:
    """Nombre moyen pondéré d'actions sur [debut, fin] (dates ISO incluses) — IAS 33.19-20, 21, 26-28, 64.

    Renvoie {"nombre", "methode", "reserve"}. Titre absent du registre : nombre actuel, méthode
    « actuel (capital inchangé) ». Registre ambigu : nombre actuel et sa réserve."""
    from datetime import date as _d
    e = HISTORIQUE_ACTIONS.get(ticker)
    if not e:
        return {"nombre": actuel, "methode": "nombre actuel (capital inchangé sur la période)", "reserve": None}
    if e.get("denominateur_ambigu"):
        return {"nombre": actuel, "methode": "nombre actuel (traitement IAS 33 non établi)",
                "reserve": e.get("reserve")}
    d0, d1 = _d.fromisoformat(debut), _d.fromisoformat(fin)
    mvts = sorted(e["mouvements"], key=lambda m: m["date"])
    num = [m for m in mvts if m["nature"] == "numeraire"]

    def n_brut(j):            # actions en circulation le jour j, unités du jour j
        n = num[0]["avant"] if num else actuel
        for m in num:
            if _d.fromisoformat(m["date"]) <= j:
                n = m["apres"]
        return n

    def facteur(j):           # divisions postérieures au jour j : rétro-ajustement (IAS 33.64)
        f = 1
        for m in mvts:
            if m["nature"] == "division" and _d.fromisoformat(m["date"]) > j:
                f *= m["ratio"]
        return f

    jours = (d1 - d0).days + 1
    total = sum(n_brut(_d.fromordinal(d0.toordinal() + k)) * facteur(_d.fromordinal(d0.toordinal() + k))
                for k in range(jours))
    return {"nombre": round(total / jours), "reserve": e.get("reserve"),
            "methode": f"moyenne pondérée IAS 33 du {debut} au {fin} ({jours} jours)"}


# ─────────────────── dividendes versés dans l'exercice, lus au tableau de variation ───────────────────
# Le résidu de fonds propres R = FP2025 − FP2024 − RNPG2025 contient, en premier lieu, le dividende versé.
# Le test de la moyenne porte sur le résidu APRÈS dividende : R + D. D se lit d'abord ICI, au tableau de
# variation des capitaux propres consolidés (part du groupe), ligne « Dividendes » ; à défaut, au
# calendrier `datasets/dividendes_bvc.json` × nombre d'actions au rapport (voir `fond_score_sectoriel.
# _dividende_exercice`). Le tableau prime : il compte ce qui est réellement sorti des fonds propres
# (dividende d'avant la cotation de SGTM, qu'aucun calendrier de la BVC ne connaît ; titres propres ;
# split de MNG). Chaque entrée porte sa pièce et sa page.
DIVIDENDES_VERSES_TABLEAU: dict = {
    # CTM — corrigé le 14/10/2026 (troisième contre-vérification) : D est le dividende NET versé,
    # 30,651 MMAD. Le tableau de variation (p.68) montre le BRUT, -31 651, compensé par la ligne
    # « Distributions reçues +999 » : prendre le brut sans la ligne qui le compense surévalue D de 1,0 MMAD.
    "CTM": {"exercice": 2025, "montant_mmad": 30.651, "page": 66, "origine": "flux_de_trésorerie",
            "source": "CTM RFA 2025 p.66, flux de trésorerie consolidé : « Dividendes versés aux actionnaires de la "
                      "société mère (30 651) » KMAD ; comptes sociaux p.54 : 30 649 450 = 25 DH × 1 225 978 actions ; "
                      "le tableau de variation p.68 montre le brut « Dividendes versés (31 651) », compensé par « "
                      "Distributions reçues 999 » : -31 651 + 999 = -30 652"},
    "BCP": {"exercice": 2025, "montant_mmad": 2134.781, "page": 12,
            "source": "BCP rapport financier 2025 p.12, tableau de variation des capitaux propres : « Dividendes "
                      "-2 134 781 -2 134 781 123 273 -2 011 508 » KMAD (total part du groupe 2 134 781)"},
    "MNG": {"exercice": 2025, "montant_mmad": 475.0, "page": 87,
            "source": "Managem RFA 2025 p.87, variation des capitaux propres consolidés 2025 : « Dividendes "
                      "distribués -475 -475 -62 -536 » MMAD (475 part du groupe ; 40 DH × 11 864 676 actions "
                      "avant le split 10:1 du 27/07/2026 = 474,6)"},
    "SGTM": {"exercice": 2025, "montant_mmad": 500.0, "page": 88,
             "source": "SGTM RFA 2025 p.88, variation des capitaux propres consolidés : « Dividendes (500 000) "
                       "(500 000) (500 000) » KMAD en 2025 — versé AVANT l'introduction en bourse, donc absent du "
                       "calendrier de la BVC"},
    # RIS — le tableau de variation passe avant le calendrier (décision du 14/10/2026, règle de la PR #241).
    # ⚠️ ÉCART NON EXPLIQUÉ de 60,000 MMAD avec le calendrier : 7 DH × 14 326 947 actions (p.45) = 100,289 ;
    # le tableau imprime 160,289. La cause n'est pas établie dans le rapport lu ; on n'en suppose aucune.
    "RIS": {"exercice": 2025, "montant_mmad": 160.289, "page": 36,
            "source": "Risma RFA 2025 p.36, tableau de variation des capitaux propres consolidés : « Dividendes "
                      "distribués bruts de précompte - - (160 289) (160 289) (8 434) (168 723) » KMAD (160 289 part "
                      "du groupe ; 168 723 avec les minoritaires, flux de trésorerie « Dividendes payés (168 723) »). "
                      "Le calendrier (7 DH × 14 326 947 actions, p.14 et p.45) donne 100,289 : ÉCART de 60,000 MMAD, "
                      "cause non établie"},
    "CIH": {"exercice": 2025, "montant_mmad": 440.953, "page": 26,
            "source": "CIH Bank RFA 2025 p.26, tableau de variation des capitaux propres : « Dividendes -440 953 » "
                      "KMAD part du groupe (-485 420 avec les minoritaires)"},
}

# ─────────────────── mouvements de fonds propres hors résultat, établis sur pièce ───────────────────
# Quand le résidu APRÈS dividende dépasse 5 % des fonds propres 2024, la moyenne est écartée. Si le
# rapport nomme la cause, elle est inscrite ici et l'étiquette dit « cause portée sur pièce » ; sinon
# l'étiquette est « mouvement hors résultat et hors dividende non expliqué ». R11 : un fait se
# constate sur pièce, il ne se déduit pas du chiffre.
# TEST DU RESTE (14/10/2026) : la cause est « portée » si, une fois retranchée, il ne reste pas plus de
# 5 % des fonds propres 2024 : |R + D - C| <= 5 %. Le reste se juge sur UNE SEULE BASE : `tableau` donne
# les fonds propres 2024, 2025 et le résultat tels qu'ils sont imprimés au tableau de variation, la
# même page que C ; R = FP2025 - FP2024 - RNPG se calcule sur ces trois chiffres, jamais mêlé à ceux
# du bilan (BCP : le tableau porte 41 452 MMAD de fonds propres part du groupe, le bilan en lit 36 975).
CAUSES_RESIDU_FONDS_PROPRES: dict = {
    "CTM": {"exercice": 2025, "montant_mmad": -144.434, "page": 68,
            "libelle": "« Autres retraitements » de consolidation",
            "tableau": {"fonds_propres_2024": 362.360, "fonds_propres_2025": 243.479, "rnpg": 56.204, "page": 68},
            "source": "CTM RFA 2025 p.68, capitaux propres consolidés : « Autres retraitements - - (144 434) - (144 433) "
                      "142 469 (1 963) » KMAD (réserves consolidées, part du groupe) ; boucle avec les « Distributions "
                      "reçues » +999 KMAD : -31 651 + 56 204 + 999 - 144 433 = -118 881 = 243 479 - 362 360"},
    "BCP": {"exercice": 2025, "montant_mmad": -2119.062, "page": 12,
            "libelle": "« Variation de périmètre »",
            "tableau": {"fonds_propres_2024": 41068.956, "fonds_propres_2025": 41452.033, "rnpg": 4503.361, "page": 12},
            "source": "BCP rapport financier 2025 p.12, tableau de variation des capitaux propres : « Variation de "
                      "périmètre -2 106 834 -11 572 -656 -2 119 062 -7 207 -2 126 269 » KMAD (total part du groupe "
                      "-2 119 062) ; fonds propres part du groupe du tableau : « Capitaux propres clôture 31/12/2024 "
                      "... 41 068 956 », « 31/12/2025 ... 41 452 033 »"},
    "MNG": {"exercice": 2025, "montant_mmad": -1747.0, "page": 87,
            "libelle": "autres éléments du résultat global, part du groupe -1 747 (couverture -1 158, conversion "
                       "-408, autres -280, impôts +108, actuariels -9)",
            "tableau": {"fonds_propres_2024": 10688.0, "fonds_propres_2025": 11478.0, "rnpg": 3002.0, "page": 87},
            "source": "Managem RFA 2025 p.87, variation des capitaux propres consolidés 2025 : « Résultat global total de "
                      "l'année - -1 339 -408 3 002 1 255 » MMAD part du groupe, soit 1 255 - 3 002 = -1 747 = « Résultat "
                      "couverture des flux de trésorerie -1 158 » + « Pertes et profits de conversion -408 » + « Autres "
                      "éléments du résultat global -280 » + « Impôts relatifs aux autres éléments du résultat global +108 » "
                      "+ « Gains / pertes actuariels -9 » (tableau en millions de dirhams, arrondi à l'unité)"},
}


FAMILLE_NOTE_PAR_DEFAUT: str = "autre"


def famille_note(ticker: str) -> str:
    """La famille de notation fondamentale d'un titre (liste explicite)."""
    for fam, titres in FAMILLES_NOTE.items():
        if ticker in titres:
            return fam
    return FAMILLE_NOTE_PAR_DEFAUT


def est_suspendu(ticker: str, date_iso: str | None = None) -> dict | None:
    """Renvoie la suspension en vigueur à `date_iso`, ou None.

    `date_iso` par défaut : aujourd'hui. Le dict renvoyé est celui du registre —
    ne pas le muter, il est partagé.
    """
    periodes = SUSPENSIONS.get(ticker)
    if not periodes:
        return None
    jour = (date_iso or datetime.now().strftime("%Y-%m-%d"))[:10]
    for p in periodes:
        if jour < p["depuis"]:
            continue
        reprise = p.get("reprise")
        if reprise is None or jour < reprise:
            return p
    return None


def adjust_splits(ticker: str, candles: list, date_key: str = "d") -> list:
    """Ajuste les cours pré-split d'une série FRAÎCHEMENT téléchargée.

    `candles` : liste de dicts façon {"d": "YYYY-MM-DD", "o","h","l","c","v"}.
    Les champs de prix antérieurs à chaque date d'effet sont divisés par le ratio.
    Le volume n'est PAS touché (unité non homogène entre sources).

    ⚠️ Ne JAMAIS appliquer à des candles déjà stockées/ajustées : le second
    passage re-diviserait les cours (double split). À n'utiliser que sur la
    sortie brute d'une source externe, avant fusion avec l'existant.
    """
    splits = SPLITS.get(ticker)
    if not splits or not candles:
        return candles
    for sp in splits:
        eff, ratio = sp["date"], sp["ratio"]
        for k in candles:
            if str(k.get(date_key, ""))[:10] < eff:
                for f in ("o", "h", "l", "c"):
                    if isinstance(k.get(f), (int, float)):
                        k[f] = round(k[f] / ratio, 2)
    return candles


# 19 tickers actifs du pipeline BVC (MASI 1)
TICKERS_ACTIFS: list = [
    "ADH", "ADI", "AKD", "CASH", "CFGB", "CMGP", "CMT", "CSR",
    "MNG", "MSA", "RDS", "RIS", "SGTM", "SMI", "SNA", "SOT",
    "SRM", "TGCC", "VCNE",
]

# Tous les tickers uniques de la BVC (TGCC/SNA = formes canoniques, TGC/SON exclus)
# 77 valeurs — ordre : grande cap → moyenne → petite
# ⚠️ Valeurs RADIÉES de la cote — exclues de toute analyse.
# Une société radiée n'a plus de cours : aucune source ne la sert, elle tombe
# jusqu'au dernier repli qui la recopie d'un run à l'autre, indéfiniment. Le
# terminal affichait ainsi Timar à 195 DH avec un PER, vingt-sept mois après sa
# sortie de cote — et son cours de retrait était de 660 DH, pas 195.
#
#   SAM  SAMIR   suspendue depuis le 06/08/2015, cours figé à 127,80,
#                liquidation judiciaire depuis 2016 — jamais intégrée
#   TIM  Timar   radiée le 10/06/2024, après une offre publique de retrait
#                obligatoire de Financière Clasquin Euromed à 660 DH
#                (franchissement du seuil de 95 %)
#
# Vérifié le 01/09/2026 : Timar est absente du bulletin officiel de la BVC
# (81 instruments) comme du flux CDG en direct (81 instruments).
VALEURS_RADIEES: dict = {
    "SAM": {"date": "2015-08-06", "motif": "suspension prolongée, liquidation judiciaire"},
    "TIM": {"date": "2024-06-10", "motif": "offre publique de retrait obligatoire à 660 DH"},
}

TICKERS_ALL: list = [
    # Grandes capitalisations
    "IAM", "ATW", "BCP", "BOA", "CIH", "CDM", "WAF",
    "LHM", "GAZ", "ATL", "HPS", "LBV", "LES", "TQA", "MRL", "TMA",
    "CMT", "MNG", "SMI",
    # Moyennes capitalisations
    "AKD", "ARD", "SAF", "OUL", "CIM", "CTM", "ZLD",
    "SOT", "MSA", "ADI", "ADH", "TGCC", "CFGB", "CASH", "SGTM",
    "CMGP", "VCNE", "RIS", "CSR", "SNA", "SRM", "RDS",
    "ALU", "MGL", "DAR", "IMI", "DTT",
    # Petites capitalisations
    "DSW", "MOX", "STR", "SNP", "SLM", "JET", "M2M",   # TIM retiré : radiée le 10/06/2024
    "INV", "S2M", "COL", "AFM", "AGM", "FNB", "BAL", "NEJ",
    "HAL", "BMC", "CAR", "AFI", "MIC", "MUT", "ENK", "EQD",
    "DHO", "PPM", "REB", "SBS", "STK", "UNI", "IBM",
    # Ajouts du 10/08/2026 — T2S est l'introduction du 27/07/2026
    "T2S", "MDP", "DLM", "DIS",
]


# ⚠️ SCORE CANONIQUE — 29/09/2026. La version de la formule qui produit la
# note publiée (`v53`) et son signal (`sig`). Émise sur chaque titre de
# data.json et sur chaque séance de pipeline/score_history.json, pour qu'une
# note se relise toujours avec la formule qui l'a produite.
# À CHANGER à toute modification de pondération, de bonus ou de palier (R8).
#   v5.3-gel-nlp-2026-09-29 : Fond 65,28 / Tech 34,72 / NLP 0 (25/09), six
#   bonus du corpus retirés et ACHAT FORT suspendu (29/09).
#   v5.3-sans-note-figee-2026-09-29 : la pénalité « Upside négatif » se
#   déclenche sur la note calculée, plus sur la table saisie le 03/06.
#   v5.3-sans-invention-2026-09-30 : plus aucun indicateur technique
#   inventé (RSI 50, MA = cours, extrêmes ±15 %, recopie du run précédent) ;
#   la pénalité « Upside négatif » lit l'upside PUBLIÉ, objectifs périmés
#   retirés.
#   v5.3-sans-malus-figes-2026-09-30 : « Red flags » et « Upside négatif »
#   gelés (table FOND_DATA écrite en dur) ; les alertes sont calculées,
#   expliquées et affichées, sans effet sur la note.
#   v5.3-seances-echangees-2026-09-30 : le RSI ne compte que les séances
#   réellement échangées (un jour sans transaction n'est pas une cotation).
#   v5.3-ratios-publies-2026-10-01 : ROIC, dette nette / EBITDA et
#   conversion de trésorerie lus dans les ratios calculés sur comptes
#   publiés quand ils existent, à la place de la saisie de juin (MSA tenu à
#   l'écart jusqu'au recoupement de son ROIC).
#   v5.3-per-publie-2026-10-01 : la valorisation lit le PER sur douze mois
#   des comptes publiés (cours ÷ BPA 12 mois) au lieu du `forward_per` saisi.
#   v5.3-financieres-roe-2026-10-02 : banques, assurances et sociétés de
#   financement notées sur le ROE publié (vérifié à la main), plus jamais sur
#   un ROIC, une dette / EBITDA ou une conversion saisis.
#   v5.3-sans-saisie-2026-10-02 : plus aucune saisie lue par la note — WACC
#   de référence unique (10 %), modificateurs momentum / rerating / cycle
#   retirés (33 titres bonifiés de +0,25 à +1,0, aucun pénalisé), croissance
#   et PER seulement tirés des comptes, sinon non évalués.
#   v5.3-fond-sectoriel-2026-10-10 : la note fondamentale suit la FAMILLE du
#   titre (banque, assurance, foncière, promoteur, mines…, voir FAMILLES_NOTE),
#   valorisations relatives à la médiane de la famille ; un critère sans donnée
#   s'abstient ; moins de la moitié du poids : « Données insuffisantes ». Les
#   poids des piliers (65,28 / 34,72 / 0) ne changent pas.
#   v5.3-croissance-pb-2026-10-27 : accord R8 d'Abd Moutalib du 22/10/2026
#   (audit verificateur-finance, lot B). Croissance : une partie absente (BPA
#   ou CA) est retirée et le poids restant remis à l'échelle, plus jamais
#   comptée 0 % (B1) ; base S1 2025 négative → pas de croissance BPA, même
#   quand l'émetteur publie un pourcentage (B2, HPS). P/B : nombre d'actions
#   de la capitalisation (B3, T2S) et fonds propres les plus récents relevés
#   sur pièce, 30/06/2026 quand ils existent (B4). Poids des piliers inchangés.
#   v5.3-non-comparable-2026-10-27 : accord R8 d'Abd Moutalib du 27/10/2026.
#   Aucune note ne change. Règle A : titre très peu liquide (technique
#   neutralisée ET montant médian < SEUIL_NON_COMPARABLE_DH) → signal « Non
#   comparable (liquidité) », `_meta.non_comparable`, classé après les titres
#   comparables. Règle B : foncière sans note par métier → « Couverture
#   partielle » (étiquette seule).
# ⚠️ MODE COMPARAISON (11/10/2026). Abd Moutalib a validé le principe d'une note
# par métier (10/10) mais exige des corrections avant toute bascule : tant que
# cet interrupteur est FAUX, `score_fond`, `v53`, le signal, la confiance et le
# plancher de publication restent ceux de la grille ACTUELLE ; la note par
# famille est calculée et publiée À CÔTÉ (`note_fond_metier`). Le passer à vrai
# est une décision, pas un correctif : il change les deux points d'application
# (update_data.appliquer_note_sectorielle et pipeline/collect_financial_data.py)
# et la version du score.
NOTE_METIER_PUBLIEE: bool = False
SCORE_VERSION = ("v5.3-fond-sectoriel-2026-10-10" if NOTE_METIER_PUBLIEE
                 else "v5.3-non-comparable-2026-10-27")

"""Point de vérité unique pour les constantes BVC Analyzer."""

# ── Noms officiels des sociétés cotées BVC ──────────────────────────────────
# Source de vérité : ces noms priment sur tout ce que retournent les scrapers.
COMPANY_NAMES: dict = {
    # ── Grandes capitalisations ─────────────────────────────────────────────
    # Noms conformes PDF Wafabourse séance fermée 25/06/2026
    "IAM":  "Itissalat Al-Maghrib",
    "ATW":  "Attijariwafa Bank",
    "BCP":  "BCP",
    "BOA":  "Bank of Africa",
    "CIH":  "CIH",
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
    "SMI":  "SMI",
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
    "SRM":  "Réalisations Mécaniques",
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
    "S2M":  "S.M Monétique",
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
}

# ── Secteurs ────────────────────────────────────────────────────────────────
# Taxonomie canonique, 21 secteurs pour 77 sociétés (moyenne 3,7 par secteur).
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
    # ── Finance ─────────────────────────────────────────────────────────────
    "ATW":  "Banques",
    "BCP":  "Banques",
    "BOA":  "Banques",
    "CIH":  "Banques",
    "CDM":  "Banques",
    "BMC":  "Banques",
    "CFGB": "Banques",
    "WAF":  "Assurances",
    "SAF":  "Assurances",
    "ATL":  "Assurances",
    "AFM":  "Assurances",          # courtage — pas un secteur à part entière
    "AGM":  "Assurances",          # idem
    "MRL":  "Sociétés de financement",
    "MGL":  "Sociétés de financement",
    "SLM":  "Sociétés de financement",
    "EQD":  "Sociétés de financement",
    "CASH": "Sociétés de financement",
    # ── Immobilier & construction ───────────────────────────────────────────
    "ADH":  "Immobilier",
    "ADI":  "Immobilier",
    "RDS":  "Immobilier",
    "ARD":  "Immobilier",          # foncière cotée
    "IMI":  "Immobilier",          # foncière cotée
    "BAL":  "Immobilier",          # ⚠️ à valider — était « Assurances »
    "TGCC": "BTP & Construction",
    "SGTM": "BTP & Construction",
    "JET":  "BTP & Construction",
    "LHM":  "Matériaux de construction",
    "CIM":  "Matériaux de construction",
    "AFI":  "Matériaux de construction",   # ⚠️ à valider — abrasifs
    # ── Industrie & matières premières ──────────────────────────────────────
    "CMT":  "Mines",
    "MNG":  "Mines",
    "SMI":  "Mines",
    "ZLD":  "Mines",
    "SNA":  "Sidérurgie & Métallurgie",
    "ALU":  "Sidérurgie & Métallurgie",
    "SRM":  "Ingénierie & Industrie",      # ⚠️ à valider
    "STR":  "Ingénierie & Industrie",
    "COL":  "Chimie",
    "SNP":  "Chimie",
    "MOX":  "Chimie",              # gaz industriels
    # ── Énergie ─────────────────────────────────────────────────────────────
    "TQA":  "Énergie",
    "GAZ":  "Énergie",
    "TMA":  "Énergie",
    # ── Consommation ────────────────────────────────────────────────────────
    "CSR":  "Agroalimentaire",
    "LES":  "Agroalimentaire",
    "DAR":  "Agroalimentaire",
    "CAR":  "Agroalimentaire",
    "UNI":  "Agroalimentaire",
    "MUT":  "Agroalimentaire",
    "OUL":  "Boissons",
    "SBS":  "Boissons",
    "LBV":  "Distribution",
    "FNB":  "Distribution",
    "HAL":  "Distribution",
    "NEJ":  "Distribution",        # ⚠️ à valider — était « Pétrole & Gaz »
    "ENK":  "Distribution",
    "CMGP": "Distribution",
    "STK":  "Distribution",
    # ── Santé ───────────────────────────────────────────────────────────────
    "SOT":  "Santé & Pharmacie",
    "PPM":  "Santé & Pharmacie",
    "AKD":  "Santé & Pharmacie",
    "VCNE": "Santé & Pharmacie",   # ⚠️ à valider — dispositifs médicaux
    # ── Technologies ────────────────────────────────────────────────────────
    "IAM":  "Télécommunications",
    "HPS":  "Technologies",
    "M2M":  "Technologies",
    "MIC":  "Technologies",
    "INV":  "Technologies",
    "IBM":  "Technologies",
    "S2M":  "Technologies",
    "DSW":  "Distribution IT",
    "DTT":  "Distribution IT",
    # ── Services ────────────────────────────────────────────────────────────
    "CTM":  "Transport & Logistique",
    "MSA":  "Transport & Logistique",
    "TIM":  "Transport & Logistique",
    "RIS":  "Tourisme & Loisirs",
    "DHO":  "Holdings",
    "REB":  "Holdings",            # ⚠️ à valider — était « Textile »
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
    "MGL": "MA0000011215", "MNG": "MA0000012866", "MRL": "MA0000012270",
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
    "MIC": "MIC",   "MNG": "MNG",   "MOX": "MOX",   "MRL": "MLE",
    "MSA": "MSA",   "MUT": "MUT",   "NEJ": "NEJ",   "OUL": "OUL",
    "PPM": "PRO",   "RDS": "RDS",   "RIS": "RIS",   "S2M": "S2M",
    "SAF": "SAH",   "SBS": "SBM",   "SGTM": "GTM",  "SLM": "SLF",
    "SMI": "SMI",   "SNA": "SID",   "SNP": "SNP",   "SOT": "SOT",
    "SRM": "SRM",   "STK": "SNA",   "STR": "STR",   "TGCC": "TGC",
    "TMA": "TMA",   "TQA": "TQM",   "UNI": "UMR",   "VCNE": "VCN",
    "WAF": "WAA",   "ZLD": "ZDJ",
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

# ── Opérations sur titres : splits (divisions de valeur nominale) ───────────
# Les sources historiques (XLSX, BVCscrap) identifient les sociétés par NOM et
# renvoient des cours NON ajustés : après un split, tout l'historique antérieur
# reste à l'ancienne échelle → fausse chute de -90% dans le graphe, indicateurs
# (MA, Bollinger, 52w) faussés, et variation calculée hors limite BVC ±10% (R10).
#
# Chaque entrée : date d'effet + ratio. Les cours ANTÉRIEURS à la date d'effet
# sont divisés par le ratio. Ne s'applique qu'aux données FRAÎCHEMENT
# téléchargées — les candles déjà stockées sont ajustées (cf. adjust_splits).
SPLITS: dict = {
    # Managem : VN 100 → VN 10 le 27/07/2026. Actions 11 864 676 → 118 646 760.
    # Nouvel ISIN MA0000012866 (ancien MA0000011058 radié).
    "MNG": [{"date": "2026-07-27", "ratio": 10}],
}


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
    "DSW", "MOX", "STR", "TIM", "SNP", "SLM", "JET", "M2M",
    "INV", "S2M", "COL", "AFM", "AGM", "FNB", "BAL", "NEJ",
    "HAL", "BMC", "CAR", "AFI", "MIC", "MUT", "ENK", "EQD",
    "DHO", "PPM", "REB", "SBS", "STK", "UNI", "IBM",
]

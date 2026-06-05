"""Point de vérité unique pour les constantes BVC Analyzer."""

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
    "EQD": "MA0000010357", "FNB": "MA0000011587", "HPS": "MA0000011611",
    "IBM": "MA0000011132", "IMI": "MA0000012387", "INV": "MA0000011579",
    "JET": "MA0000012080", "LBV": "MA0000011801", "LHM": "MA0000012320",
    "LES": "MA0000012031", "M2M": "MA0000011678", "MOX": "MA0000010985",
    "MGL": "MA0000011215", "MNG": "MA0000011058", "MRL": "MA0000010035",
    "IAM": "MA0000011488", "MIC": "MA0000012163", "MUT": "MA0000012395",
    "OUL": "MA0000010415", "PPM": "MA0000011660", "REB": "MA0000010993",
    "RDS": "MA0000012239", "RIS": "MA0000011462", "S2M": "MA0000012106",
    "SLM": "MA0000012007", "SAF": "MA0000011744", "SMI": "MA0000010068",
    "STK": "MA0000011843", "SNP": "MA0000011728", "MSA": "MA0000012312",
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

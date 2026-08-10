"""Constantes partagées entre tous les scrapers."""
import random
import sys
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from bvc_config import (ISIN_MAP, TICKERS_DEFAUT, TICKERS_ALL,  # noqa: E402
                        TICKERS_ACTIFS, IDB_TICKER_MAP)

# Ticker officiel BVC/IDBourse → le nôtre. Indispensable à l'ingestion : la
# source renvoie le code officiel, qui n'est pas toujours le nôtre (SID pour
# Sonasid, ZDJ pour Zellidja), et attribue même SNA à Stokvis là où nous
# l'attribuons à Sonasid.
IDB_TICKER_INV = {idb: nous for nous, idb in IDB_TICKER_MAP.items()}

PROXY = "https://corsproxy.io/?"

TICKERS = TICKERS_ACTIFS   # 19 MASI 1 — expansion 77 à traiter séparément (timeout)

IPO_RECENT = {"CASH", "VCNE", "SGTM"}

# IDBourse utilise des noms différents pour certains tickers
IDB_NAME_MAP = {
    "MTO":  "CMT",
    "ALLI": "ADI",
    "TGC":  "TGCC",
    "GTM":  "SGTM",
}

# Yahoo Finance suffix map (.CS = Bourse de Casablanca)
YF_MAP = {
    # Tickers actifs (19)
    "ADI":  "ADI.CS",  "ADH":  "ADH.CS",  "AKD":  "AKD.CS",
    "CASH": "CASH.CS", "CFGB": "CFGB.CS", "CMGP": "CMGP.CS",
    "CMT":  "CMT.CS",  "CSR":  "CSR.CS",  "MNG":  "MNG.CS",
    "MSA":  "MSA.CS",  "RDS":  "RDS.CS",  "RIS":  "RIS.CS",
    "SGTM": "SGTM.CS", "SMI":  "SMI.CS",  "SNA":  "SNA.CS",
    "SOT":  "SOT.CS",  "SRM":  "SRM.CS",  "TGCC": "TGC.CS",
    "VCNE": "VCNE.CS",
    # Grandes capitalisations
    "IAM":  "IAM.CS",  "ATW":  "ATW.CS",  "BCP":  "BCP.CS",
    "BOA":  "BOA.CS",  "CIH":  "CIH.CS",  "CDM":  "CDM.CS",
    "WAF":  "WAF.CS",  "LHM":  "LHM.CS",  "GAZ":  "GAZ.CS",
    "ATL":  "ATL.CS",  "HPS":  "HPS.CS",  "LBV":  "LBV.CS",
    "LES":  "LES.CS",  "TQA":  "TQA.CS",  "MRL":  "MRL.CS",
    "TMA":  "TMA.CS",
    # Moyennes capitalisations
    "ARD":  "ARD.CS",  "SAF":  "SAF.CS",  "OUL":  "OUL.CS",
    "CIM":  "CIM.CS",  "CTM":  "CTM.CS",  "ZLD":  "ZLD.CS",
    "ALU":  "ALU.CS",  "MGL":  "MGL.CS",  "DAR":  "DAR.CS",
    "IMI":  "IMI.CS",  "DTT":  "DTT.CS",
    # Petites capitalisations
    "DSW":  "DSW.CS",  "MOX":  "MOX.CS",  "STR":  "STR.CS",
    "TIM":  "TIM.CS",  "SNP":  "SNP.CS",  "SLM":  "SLM.CS",
    "JET":  "JET.CS",  "M2M":  "M2M.CS",  "INV":  "INV.CS",
    "S2M":  "S2M.CS",  "COL":  "COL.CS",  "AFM":  "AFM.CS",
    "AGM":  "AGM.CS",  "FNB":  "FNB.CS",  "BAL":  "BAL.CS",
    "NEJ":  "NEJ.CS",  "HAL":  "HAL.CS",  "BMC":  "BMC.CS",
    "CAR":  "CAR.CS",  "AFI":  "AFI.CS",  "MIC":  "MIC.CS",
    "MUT":  "MUT.CS",  "ENK":  "ENK.CS",  "EQD":  "EQD.CS",
    "DHO":  "DHO.CS",  "PPM":  "PPM.CS",  "REB":  "REB.CS",
    "SBS":  "SBS.CS",  "STK":  "STK.CS",  "UNI":  "UNI.CS",
    "IBM":  "IBM.CS",
}

HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept-Language": "fr-MA,fr;q=0.9",
        "Accept": "text/html,*/*;q=0.8",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Accept-Language": "fr,en-US;q=0.7",
        "Accept": "application/json,*/*;q=0.8",
    },
]


def timeout_session(retries: int = 3, backoff: float = 1.5) -> requests.Session:
    """Session requests avec retry + backoff exponentiel."""
    sess = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    sess.mount("http://", adapter)
    sess.mount("https://", adapter)
    return sess

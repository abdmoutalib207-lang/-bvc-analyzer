"""Constantes partagées entre tous les scrapers."""
import random
import sys
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from bvc_config import ISIN_MAP, TICKERS_DEFAUT  # noqa: E402

PROXY = "https://corsproxy.io/?"

TICKERS = [
    "ADI", "ADH", "AKD", "CASH", "CFGB", "CMGP", "CMT", "CSR",
    "MNG", "MSA", "RDS", "RIS", "SGTM", "SMI", "SNA", "SOT",
    "SRM", "TGCC", "VCNE",
]

IPO_RECENT = {"CASH", "VCNE", "SGTM"}

# Yahoo Finance suffix map
YF_MAP = {
    "ADI":  "ADI.CS",  "ADH":  "ADH.CS",  "AKD":  "AKD.CS",
    "CASH": "CASH.CS", "CFGB": "CFGB.CS", "CMGP": "CMGP.CS",
    "CMT":  "CMT.CS",  "CSR":  "CSR.CS",  "MNG":  "MNG.CS",
    "MSA":  "MSA.CS",  "RDS":  "RDS.CS",  "RIS":  "RIS.CS",
    "SGTM": "SGTM.CS", "SMI":  "SMI.CS",  "SNA":  "SNA.CS",
    "SOT":  "SOT.CS",  "SRM":  "SRM.CS",  "TGCC": "TGC.CS",
    "VCNE": "VCNE.CS",
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

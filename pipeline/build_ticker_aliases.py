#!/usr/bin/env python3
"""
Reconstruit pipeline/ticker_aliases.py à partir des noms officiels.

Deux référentiels concordants : bvc_config.COMPANY_NAMES (noms IDBourse,
validés le 02/07) et la liste Wafabourse fournie par Abd Moutalib. Les alias
existants qui restent cohérents sont conservés — certains sont de vraies
variantes d'usage qu'aucune génération automatique ne trouverait
(« maroc telecom » pour Itissalat Al-Maghrib, par exemple).

Règle de sûreté : le tagging fait de la correspondance exacte de sous-chaîne.
Un alias trop court ou trop générique taggue tout. On écarte donc les alias de
moins de 5 caractères et une liste de termes passe-partout.
"""
import sys, re, unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))
from bvc_config import COMPANY_NAMES
from ticker_aliases import TICKER_ALIASES as ANCIENS

# Noms tels qu'affichés par Wafabourse (PDF du 09/08/2026).
WAFA = {
 "ADH":"Addoha", "AFM":"AFMA", "AFI":"Afric Industries", "GAZ":"Afriquia Gaz",
 "AGM":"Agma", "AKD":"Akdital", "ADI":"Alliances", "ALU":"Aluminium du Maroc",
 "ARD":"Aradei Capital", "ATL":"AtlantaSanad", "ATW":"Attijariwafa Bank",
 "HAL":"Auto Hall", "NEJ":"Auto Nejma", "BAL":"Balima", "BOA":"Bank of Africa",
 "BCP":"BCP", "BMC":"BMCI", "CAR":"Cartier Saada", "CASH":"Cash Plus",
 "CFGB":"CFG Bank", "CIH":"CIH", "CIM":"Ciments du Maroc", "CMGP":"CMGP Group",
 "CMT":"CMT", "COL":"Colorado", "CSR":"Cosumar", "CDM":"Crédit du Maroc",
 "EQD":"Crédit Eqdom", "CTM":"CTM", "DAR":"Dari Couspate", "DHO":"Delta Holding",
 "DTT":"Disty Technologies", "DSW":"Disway", "ENK":"Ennakl", "FNB":"Fénie Brossette",
 "LHM":"Holcim Maroc", "HPS":"HPS", "IBM":"IB-Maroc.com", "IMI":"Immorente",
 "INV":"Involys", "IAM":"Itissalat Al Maghrib", "JET":"Jet Contractors",
 "LBV":"Label Vie", "LES":"Lesieur-Cristal", "M2M":"M2M Group",
 "MOX":"Maghreb Oxygène", "MGL":"Maghrebail", "MNG":"Managem",
 "MRL":"Maroc Leasing", "MSA":"Marsa Maroc", "MIC":"Microdata", "MUT":"Mutandis",
 "OUL":"Oulmès", "PPM":"Promopharm", "REB":"Rebab", "RDS":"Résidences Dar Saada",
 "RIS":"Risma", "S2M":"S2M", "SLM":"Salafin", "SAF":"Sanlam Maroc", "SBS":"SBM",
 "SGTM":"SGTM", "SMI":"SMI", "SNP":"SNEP", "SNA":"Sonasid", "SOT":"Sothema",
 "SRM":"SRM", "STK":"Stokvis Nord Afrique", "STR":"Stroc Industrie",
 "TQA":"Taqa Morocco", "TGCC":"TGCC", "TMA":"TotalEnergies", "UNI":"Unimer",
 "VCNE":"Vicenne", "WAF":"Wafa Assurance", "ZLD":"Zellidja", "TIM":"Timar",
}

# Termes trop génériques : seuls, ils taggueraient une grande part des articles.
INTERDITS = {
 "maroc","bank","banque","groupe","group","société","societe","sa","holding",
 "capital","industries","industrie","gaz","energie","énergie","assurance",
 "bourse","equity","invest","finance","credit","crédit","company","afrique",
 "immobilier","mines","ciments","total","bcp","cmt","hps","smi","srm","s2m",
 "cih","ctm","sbm","tgcc","sgtm","afma","agma",
}

def sans_accent(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")

def variantes(nom):
    """Décline un nom officiel en formes rencontrées dans la presse."""
    n = nom.lower().strip()
    out = {n, sans_accent(n)}
    out.add(n.replace("-", " "));  out.add(sans_accent(n).replace("-", " "))
    out.add(n.replace("'", ""));   out.add(n.replace(".", ""))
    # « Groupe X », « X Maroc », « X SA » : formes courantes en presse
    base = re.sub(r"\s+(sa|s\.a\.?|group|groupe)$", "", n).strip()
    if base != n:
        out.add(base); out.add(sans_accent(base))
    for f in (f"groupe {base}", f"{base} maroc", f"{base} sa"):
        out.add(f); out.add(sans_accent(f))
    return out

def sur(a):
    """Un alias est-il assez discriminant pour de la correspondance exacte ?"""
    a = a.strip()
    return len(a) >= 5 and a not in INTERDITS and not a.isdigit()

# Index des noms officiels : sert à rejeter les alias hérités qui désignent
# en réalité une AUTRE société. L'ancien fichier attribuait ainsi
# « maroc leasing » à Maghrebail — deux sociétés de leasing confondues.
OFFICIELS = {}
for t, n in COMPANY_NAMES.items():
    OFFICIELS[n.lower()] = t
    OFFICIELS[sans_accent(n.lower())] = t
for t, n in WAFA.items():
    OFFICIELS.setdefault(n.lower(), t)

nouveau = {}
for tk in sorted(COMPANY_NAMES):
    cand = set()
    for src in (COMPANY_NAMES.get(tk), WAFA.get(tk)):
        if src:
            cand |= variantes(src)
    # on garde les anciens alias encore plausibles : ce sont des usages réels
    for a in ANCIENS.get(tk, []):
        a = a.lower()
        if OFFICIELS.get(a, tk) != tk:      # désigne une autre société → rejeté
            print(f"   ⚠️  {tk}: alias « {a} » rejeté — c'est {OFFICIELS[a]}")
            continue
        cand.add(a)
    # un alias contenu dans un autre est redondant pour du substring
    gardes = sorted({a for a in cand if sur(a)}, key=len)
    final = []
    for a in gardes:
        if not any(a != b and b in a for b in final):
            final.append(a)
    nouveau[tk] = sorted(final)

# ── contrôle de collision : un alias ne doit désigner qu'une société ──
index = {}
for tk, als in nouveau.items():
    for a in als:
        index.setdefault(a, []).append(tk)
collisions = {a: t for a, t in index.items() if len(t) > 1}

corps = "\n".join(
    f'    "{tk}": [' + ", ".join(f'"{a}"' for a in als) + "],"
    for tk, als in nouveau.items())

(RACINE / "pipeline" / "ticker_aliases.py").write_text(
f'''"""Alias de sociétés cotées, pour rattacher un article à un ticker.

Généré depuis les noms officiels : bvc_config.COMPANY_NAMES (référentiel
IDBourse validé le 02/07/2026) croisé avec la liste Wafabourse du 09/08/2026.

Le tagging fait de la correspondance EXACTE de sous-chaîne, jamais de
correspondance floue — mesurée le 09/08, celle-ci taggue 40 sociétés sur un
article traitant du chômage. En conséquence, un alias doit être discriminant :
les termes de moins de 5 caractères et les mots passe-partout (« maroc »,
« banque », « groupe », « equity »…) sont exclus à la génération.

Ne pas éditer à la main : relancer le générateur si un nom officiel change.
"""

TICKER_ALIASES = {{
{corps}
}}
''', encoding="utf-8")

print(f"✅ {len(nouveau)} tickers")
print(f"   alias au total : {sum(len(v) for v in nouveau.values())} "
      f"(avant : {sum(len(v) for v in ANCIENS.values())})")
print(f"   collisions : {collisions if collisions else 'aucune ✅'}")

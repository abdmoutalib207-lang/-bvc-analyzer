"""
BVC Ticker Aliases — Source de vérité pour le tagging NLP articles de presse.

Chaque ticker a une liste de formes alternatives (alias) permettant de
détecter les mentions dans les articles avec flexibilité.

Source de vérité : bvc_config.py (COMPANY_NAMES, COMPANY_SECTORS)
Utilisé par : pipeline/fetch_news.py (exact + fuzzy matching)
"""

TICKER_ALIASES: dict[str, list[str]] = {
    # ── Grandes capitalisations ────────────────────────────────────────────────
    "IAM":  [
        "maroc telecom", "itissalat al-maghrib", "itissalat al maghrib",
        "iam telecom", "maroc télécoms", "iam maroc",
    ],
    "ATW":  [
        "attijariwafa bank", "attijariwafa", "attijari wafa",
        "attijari bank", "groupe attijariwafa", "attijari wafa bank",
    ],
    "BCP":  [
        "banque centrale populaire", "banques populaires",
        "crédit populaire du maroc", "groupe banque populaire", "bcp maroc",
    ],
    "BOA":  [
        "bank of africa", "bmce bank of africa", "bmce bank",
        "banque of africa", "boa maroc",
    ],
    "CIH":  [
        "cih bank", "crédit immobilier et hôtelier",
        "cih banque", "cih maroc", "credit immobilier hotelier",
    ],
    "CDM":  [
        "crédit du maroc", "credit du maroc", "cdm maroc", "cdm bank",
    ],
    "WAF":  [
        "wafa assurance", "wafa insurance", "wafassurance",
    ],
    "LHM":  [
        "lafargeholcim maroc", "lafarge holcim maroc", "lafarge maroc",
        "holcim maroc", "lafargeholcim", "lhm maroc",
    ],
    "GAZ":  [
        "afriquia gaz", "afriquia gas", "gaz afriquia",
    ],
    "ATL":  [
        # ATL = AtlantaSanad (assurance) — NE PAS CONFONDRE avec Auto Hall (HAL)
        "atlantasanad", "atlanta sanad", "atlasanad",
        "assurances atlanta", "atlanta assurances", "atlanta sanad assurance",
    ],
    "HPS":  [
        "hightech payment systems", "hightech payment system",
        "hps payment", "hps worldwide", "high tech payment", "hps maroc",
    ],
    "LBV":  [
        "label vie", "label'vie", "labelvie",
        "groupe label vie", "label vie maroc", "supermarchés label vie",
    ],
    "LES":  [
        "lesieur cristal", "lesieur-cristal", "lesieur maroc",
    ],
    "TQA":  [
        "taqa morocco", "taqa maroc", "jlec",
        "jordan low electricity", "taqa power", "taqa energy",
    ],
    "MRL":  [
        # MRL = Marsa Maroc (entité distincte de MSA — ISINs différents)
        "marsa maroc", "sodep maroc", "marsa maroc sa",
        "sodep-marsa", "port maroc",
    ],
    "TMA":  [
        "totalenergies marketing maroc", "total energies maroc",
        "total maroc", "total marketing maroc", "totalenergies maroc",
    ],
    "CMT":  [
        "compagnie minière de touissit", "minière de touissit",
        "touissit", "cmt touissit", "compagnie touissit",
    ],
    "MNG":  [
        "managem", "groupe managem", "managem group",
        "managem mining", "managem sa",
    ],
    "SMI":  [
        "s.m. imiter", "sm imiter", "société métallurgique imiter",
        "smiter", "imiter mines", "metallurgique imiter",
    ],
    # ── Moyennes capitalisations ───────────────────────────────────────────────
    "AKD":  [
        "akdital", "groupe akdital", "cliniques akdital",
        "akdital santé", "cliniques privées akdital",
    ],
    "ARD":  [
        "aradei capital", "aradei",
        "aradei foncière", "groupe aradei",
    ],
    "SAF":  [
        # SAF = Sanlam Maroc (ex-Saham Assurance, rebranding 2021)
        "sanlam maroc", "saham assurance", "saham finances",
        "saham maroc", "sanlam assurance",
    ],
    "OUL":  [
        "oulmès", "eaux minérales d'oulmès", "les eaux minerales oulmès",
        "groupe oulmès", "oulmès brasseries", "minerales oulmès",
    ],
    "CIM":  [
        # CIM = Ciments du Maroc (groupe Holcim) — NE PAS CONFONDRE avec CIMAT (différente société)
        "ciments du maroc", "ciments maroc", "cim maroc",
        "ciments du maroc sa", "groupe ciments maroc",
    ],
    "CTM":  [
        "compagnie de transports au maroc", "ctm voyages",
        "ctm transport", "ctm bus", "ctm maroc",
    ],
    "ZLD":  [
        # ZLD = Zellidja (mines) — NE PAS CONFONDRE avec Zalagh (volaille, non coté)
        "zellidja", "compagnie des mines de zellidja",
        "zellidja mines", "société zellidja",
    ],
    "SOT":  [
        "sothema", "laboratoires sothema", "sothema pharma",
        "sothema maroc", "labo sothema",
    ],
    "MSA":  [
        # MSA = Marsa Maroc (entité distincte de MRL — ISINs différents)
        # NE PAS CONFONDRE avec MUT = Mutandis SCA
        "marsa maroc", "sodep marsa", "marsa portuaire",
        "marsa tanger", "port marsa maroc",
    ],
    "ADI":  [
        "alliances développement immobilier", "alliances développement",
        "alliance développement", "alliances immobilier", "alliances adi",
    ],
    "ADH":  [
        "addoha", "groupe addoha", "douja promotion addoha",
        "douja promotion", "addoha immobilier",
    ],
    "TGCC": [
        "tgcc", "travaux généraux de construction de casablanca",
        "groupe tgcc", "tgcc construction",
    ],
    "CFGB": [
        "cfg bank", "cfg banks", "cfg maroc",
        "cfg capital bank", "cfgb maroc",
    ],
    "CASH": [
        "cash plus", "cash plus maroc", "cash plus transfert",
    ],
    "SGTM": [
        "sgtm", "société générale de travaux du maroc",
        "sgtm travaux", "sgtm maroc",
    ],
    "CMGP": [
        "cmgp group", "cmgp", "cmgp distribution",
        "cmgp matériaux", "cmgp groupe",
    ],
    "VCNE": [
        "vivo energy maroc", "vivo energy", "vivo maroc",
        "vivo energy distribution",
    ],
    "RIS":  [
        "risma", "résidences touristiques de montagne",
        "risma hôtellerie", "risma tourisme", "risma hotels",
    ],
    "CSR":  [
        "cosumar", "cosumar sa", "compagnie sucrière marocaine",
        "cosumar sucre", "raffinerie cosumar",
    ],
    "SNA":  [
        "sonasid", "société nationale de sidérurgie",
        "sonasid maroc", "sonasid acier",
    ],
    "SRM":  [
        # SRM = Réalisations Mécaniques — NE PAS CONFONDRE avec Stokvis (STK)
        "réalisations mécaniques", "realisations mecaniques",
        "srm maroc", "srm industrie",
    ],
    "RDS":  [
        "résidences dar saada", "dar saada",
        "dar saâda", "résidences dar saâda",
    ],
    "ALU":  [
        "aluminium du maroc", "aluminium maroc",
        "alu maroc", "groupe aluminium maroc",
    ],
    "MGL":  [
        "maghrebail", "maroc leasing",
        "maghrebail sa", "leasing maghreb",
    ],
    "DAR":  [
        "dari couspate", "dar couspate",
        "dari couspate maroc", "couspate",
    ],
    "IMI":  [
        "immorente invest", "immorente",
        "immorente foncière", "immorente reit",
    ],
    "DTT":  [
        "disty technologies", "disty tech",
        "disty technologies maroc", "dtt distribution",
    ],
    # ── Petites capitalisations ────────────────────────────────────────────────
    "DSW":  [
        # DSW = Disway (distribution IT) — anciennement Delattre Levivier Maroc
        "disway", "dis way maroc",
        "disway distribution", "disway it", "disway maroc",
    ],
    "MOX":  [
        "maghreb oxygène", "maghreb oxygene",
        "maghreb oxy", "mox gaz",
    ],
    "STR":  [
        # STR = Stroc Industrie (BTP) — NE PAS CONFONDRE avec STK = Stokvis
        "stroc industrie", "stroc maroc",
        "stroc construction", "groupe stroc",
    ],
    "TIM":  [
        "timar", "timar maroc",
        "timar transport", "timar logistique",
    ],
    "SNP":  [
        "snep", "snep maroc",
        "société nationale d'électrolyse et de pétrochimie",
        "snep chimie", "snep industrie",
    ],
    "SLM":  [
        "salafin", "salafin maroc",
        "salafin crédit", "salafin consommation",
    ],
    "JET":  [
        "jet contractors", "jet contractor",
        "jet contractors maroc", "jet btp",
    ],
    "M2M":  [
        "m2m group", "m2m maroc",
        "m2m groupe", "m2m technologies",
    ],
    "INV":  [
        "involys", "involys maroc",
        "involys informatique", "involys tech",
    ],
    "S2M":  [
        "s2m group", "s.m. monétique", "sm monétique",
        "soft mobile maroc", "s2m maroc",
    ],
    "COL":  [
        "colorado", "colorado peintures",
        "colorado maroc", "colorado paints",
    ],
    "AFM":  [
        # AFM = AFMA (courtage assurance) — NE PAS CONFONDRE avec AFI = Afric Industries
        "afma", "afma courtage", "afma maroc",
        "agence fassi maroc assurance",
    ],
    "AGM":  [
        # AGM = Agma Lahlou-Tazi (courtage assurance)
        "agma lahlou-tazi", "agma lahlou tazi",
        "agma courtage", "agma assurances",
    ],
    "FNB":  [
        "fenie brossette", "fenié brossette",
        "fenie-brossette", "fenie brossette maroc",
    ],
    "BAL":  [
        "balima", "société balima",
        "balima assurances", "balima maroc",
    ],
    "NEJ":  [
        # NEJ = Auto Nejma (concessionnaire automobile)
        "auto nejma", "nejma automobiles",
        "nejma auto", "groupe auto nejma",
    ],
    "HAL":  [
        # HAL = Auto Hall (distribution automobile) — NE PAS CONFONDRE avec ATL = AtlantaSanad
        "auto hall", "autohall", "groupe auto hall",
        "auto hall maroc", "auto-hall",
    ],
    "BMC":  [
        # BMC = BMCI (Banque Marocaine pour le Commerce et l'Industrie, groupe BNP Paribas)
        # NE PAS CONFONDRE avec SBM = Société des Boissons du Maroc (non coté BVC Analyzer)
        "bmci", "banque marocaine pour le commerce et l'industrie",
        "bmci maroc", "bnp paribas maroc",
    ],
    "CAR":  [
        "cartier saada", "cartier saâda",
        "cartier saada maroc", "groupe cartier saada",
    ],
    "AFI":  [
        # AFI = Afric Industries — NE PAS CONFONDRE avec AFM = AFMA ou AGM = Agma
        "afric industries", "afric industries sa",
        "afric industries maroc", "afi industrie",
    ],
    "MIC":  [
        "microdata", "microdata maroc",
        "microdata maroc sa", "groupe microdata",
    ],
    "MUT":  [
        # MUT = Mutandis SCA (FMCG) — NE PAS CONFONDRE avec MSA = Marsa Maroc
        "mutandis sca", "mutandis",
        "mutandis maroc", "mutandis groupe",
    ],
    "ENK":  [
        "enkaje", "enkaje maroc",
        "enkaje services", "société enkaje",
    ],
    "EQD":  [
        "equity", "eqdom",
        "eqdom maroc", "equity maroc",
    ],
    "DHO":  [
        # DHO = Delta Holding — NE PAS CONFONDRE avec ADH = Douja/Addoha
        "delta holding", "delta holding maroc",
        "groupe delta holding", "delta industries",
    ],
    "PPM":  [
        "papelera de tetuan", "papelera maroc",
        "papelera de tétouan", "papeteries maroc",
    ],
    "REB":  [
        "rebab company", "rebab",
        "rebab maroc", "rebab textile",
    ],
    "SBS":  [
        # SBS = Super Céréales
        "super céréales", "super cereales",
        "super céréales maroc", "sbs céréales",
    ],
    "STK":  [
        # STK = Stokvis Nord Afrique (distribution industrielle) — NE PAS CONFONDRE avec STR = Stroc Industrie
        "stokvis nord afrique", "stokvis",
        "stokvis maroc", "stokvis distribution",
    ],
    "UNI":  [
        "unimer", "unimer maroc",
        "unimer sa", "unimer agroalimentaire",
    ],
    "IBM":  [
        # IBM = IB Maroc.com (technologies) — toujours préfixer avec "ib maroc" pour éviter confusion avec IBM Corp
        "ib maroc", "ib maroc.com", "ibmaroc",
    ],
}

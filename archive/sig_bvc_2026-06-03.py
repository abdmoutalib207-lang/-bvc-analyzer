"""ARCHIVE — table « Signal communauté BVC » retirée du moteur le 29/09/2026.

Écrite à la main le 03/06/2026 (commit 2a7313ea), jamais recalculée depuis.
Elle était publiée dans `data.json` sous `sigBvc` et contredisait le signal
calculé (`sig`) sur 38 titres sur 80 au 29/09. Son origine n'est pas établie :
elle ne coïncide pas avec le classement de la phase 13 du moteur NLP
(`whatsapp_analysis/output/final_rankings.csv`). Conservée pour la trace
(règle : archiver, ne pas supprimer). Plus aucun code ne la lit.
"""

SIG_BVC = {
    # Tickers actifs (19)
    "CMT":"ACHETER","SMI":"ACHETER","CASH":"SURVEILLER","MNG":"ACHETER",
    "AKD":"ACHETER","SOT":"ACHETER","SGTM":"SURVEILLER","MSA":"SURVEILLER",
    "CFGB":"ATTENDRE","RIS":"ATTENDRE","ADI":"ATTENDRE","VCNE":"ATTENDRE",
    "CMGP":"ATTENDRE","CSR":"ATTENDRE","TGCC":"ATTENDRE","ADH":"ATTENDRE",
    "SRM":"ATTENDRE","SNA":"EVITER","RDS":"EVITER",
    # Grandes capitalisations
    "IAM":"ACHETER","ATW":"ACHETER","BCP":"ACHETER","BOA":"SURVEILLER",
    "CIH":"SURVEILLER","CDM":"SURVEILLER","WAF":"SURVEILLER",
    "LHM":"ACHETER","GAZ":"ACHETER","ATL":"ACHETER","HPS":"ACHETER",
    "LBV":"SURVEILLER","LES":"SURVEILLER","TQA":"ACHETER","MRL":"ACHETER","TMA":"SURVEILLER",
    # Moyennes capitalisations
    "ARD":"ACHETER","SAF":"SURVEILLER","OUL":"SURVEILLER","CIM":"ACHETER",
    "CTM":"SURVEILLER","ZLD":"ATTENDRE","ALU":"ATTENDRE","MGL":"ATTENDRE",
    "DAR":"ATTENDRE","IMI":"ACHETER","DTT":"SURVEILLER",
    # Petites capitalisations — défaut ATTENDRE
    "DSW":"ATTENDRE","MOX":"ATTENDRE","STR":"ATTENDRE","TIM":"ATTENDRE",
    "SNP":"ATTENDRE","SLM":"ATTENDRE","JET":"ATTENDRE","M2M":"SURVEILLER",
    "INV":"ATTENDRE","S2M":"ATTENDRE","COL":"ATTENDRE",
}

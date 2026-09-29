"""ARCHIVE — « note BVC de référence », retirée du moteur le 29/09/2026.

Saisie à la main le 03/06/2026 (commit 2a7313ea), jamais recalculée ; 21
titres sur 80 à 5,00 par défaut. Publiée sous `bvc` (et `delta`) jusqu'au
29/09 (score canonique, PR #113). Son dernier usage — la condition de la
pénalité « Upside négatif » — a été remplacé le même jour par la note
calculée du titre, avec l'accord d'Abd Moutalib (R8). Conservée pour la
trace ; plus aucun code ne la lit.
"""

BVC_SCORES_BASE = {
    # Tickers actifs (19)
    "CMT":7.16,"SMI":6.95,"CASH":6.73,"MNG":6.59,"AKD":6.20,"SOT":6.62,
    "SGTM":5.77,"MSA":6.28,"CFGB":5.44,"RIS":4.71,"ADI":5.00,"VCNE":4.93,
    "CMGP":5.17,"CSR":4.58,"TGCC":5.22,"ADH":4.28,"SRM":4.88,"SNA":4.10,"RDS":3.76,
    # Grandes capitalisations
    "IAM":7.08,"ATW":7.25,"BCP":7.00,"BOA":6.58,"CIH":6.75,"CDM":6.75,
    "WAF":6.92,"LHM":7.10,"GAZ":7.20,"ATL":6.90,"HPS":7.15,"LBV":6.70,
    "LES":6.60,"TQA":7.05,"MRL":6.88,"TMA":6.65,
    # Moyennes capitalisations
    "ARD":6.45,"SAF":6.55,"OUL":6.30,"CIM":6.80,"CTM":6.20,"ZLD":5.40,
    "ALU":6.10,"MGL":5.70,"DAR":5.20,"IMI":6.35,"DTT":6.15,
    # Petites capitalisations
    "DSW":5.90,"MOX":5.85,"STR":5.60,"TIM":5.45,"SNP":5.20,"SLM":6.10,
    "JET":5.65,"M2M":6.10,"INV":5.40,"S2M":5.65,"COL":5.90,
    "AFM":6.10,"AGM":6.05,"FNB":5.60,"BAL":5.85,
}

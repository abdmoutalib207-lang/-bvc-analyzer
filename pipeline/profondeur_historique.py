"""Pourquoi tel titre n'a pas trois ans de chandelles — et ce qui manque.

LA QUESTION DE NOURE, LE 16/09/2026
──────────────────────────────────
« Pourquoi on ne produit pas les 3 ans de bougies alors que nous avons
l'historique ? »

La réponse mesurée est que **nous ne l'avons pas** pour la moitié de la cote,
et que la profondeur de nos chandelles est exactement celle des exports Excel
déposés à la main dans `data/historique/`.

Relevé le 16/09 sur les 75 fichiers de `pipeline/candles/` :

    31 titres à 750 séances et plus   → 31 ont un export Excel  (31/31)
    33 titres sous 250 séances        →  2 ont un export Excel  (CASH, SGTM,
                                          tous deux introduits fin 2025)

La corrélation est totale, et elle a une cause de code, pas de hasard.

CE QUI EMPÊCHE LE RATTRAPAGE
────────────────────────────
`fetch_bvcscrap_extension(nom, from_date)` demande à la source les séances
postérieures à `from_date + 1 jour`, où `from_date` est la DERNIÈRE séance déjà
détenue. Le collecteur ne sait donc qu'ALLONGER VERS L'AVANT. Un titre dont le
fichier commence le 19/05/2026 commencera toujours le 19/05/2026 : on ne
redemande jamais ce qui précède.

Ce n'est pas un défaut de la source — `loadata()` accepte n'importe quelle date
de début. C'est un défaut de ce que nous lui demandons.

CE QUI EST POSSIBLE AUJOURD'HUI, ET CE QUI NE L'EST PAS
───────────────────────────────────────────────────────
⚠️ Vérifié le 16/09 depuis l'environnement d'exécution :
  · `casablanca-bourse.com` ne répond pas (connexion refusée, pas un 403) ;
  · `BVCscrap.loadata()` remonte une erreur de décodage sur les trois titres
    essayés — la source qu'il interroge ne rend plus le format attendu.

Le rattrapage ne peut donc PAS se faire depuis ici. Il se fera par les exports
Excel, comme les 44 déjà déposés — c'est-à-dire à la main, titre par titre,
depuis la fiche de l'opérateur.

Ce module ne collecte rien. Il DIT ce qui manque, pour que la liste à demander
soit exacte plutôt que devinée.

    python pipeline/profondeur_historique.py
    python pipeline/profondeur_historique.py --manquants   (la liste seule)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CANDLES = Path(__file__).parent / "candles"
XLSX = RACINE / "data" / "historique"

# Une « année » de cotation à la BVC, en séances. 52 semaines de 5 jours moins
# les fériés : la mesure sur nos séries les plus longues donne 802 séances pour
# trois ans et trois mois, soit ~250 par an.
SEANCES_PAR_AN = 250


def inventaire() -> list[dict]:
    """Un relevé par titre : profondeur, première séance, export présent."""
    exports = {f.stem for f in XLSX.glob("*.xlsx")} if XLSX.is_dir() else set()
    out = []
    for f in sorted(CANDLES.glob("*.json")):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        c = c if isinstance(c, list) else c.get("candles", [])
        dates = sorted(x["d"] for x in c if isinstance(x, dict) and x.get("d"))
        if not dates:
            continue
        out.append({
            "ticker": f.stem,
            "seances": len(dates),
            "debut": dates[0],
            "fin": dates[-1],
            "annees": round(len(dates) / SEANCES_PAR_AN, 1),
            "export_excel": f.stem in exports,
        })
    return out


def manquants(inv: list[dict], annees: float = 3.0) -> list[dict]:
    """Les titres sous le seuil ET sans export — ceux qu'on peut rattraper.

    ⚠️ Un titre sans export mais introduit récemment n'est PAS un manque : il
    n'a pas d'historique parce qu'il n'a pas d'existence. On ne peut pas le
    savoir depuis les seules chandelles, et ce module ne le devine pas — il
    signale la date de première séance pour que la lecture le tranche.
    """
    seuil = annees * SEANCES_PAR_AN
    return [t for t in inv if t["seances"] < seuil and not t["export_excel"]]


def main() -> int:
    inv = inventaire()
    if not inv:
        print("aucune chandelle lisible")
        return 1
    seuls = "--manquants" in sys.argv

    if not seuls:
        print(f"  {len(inv)} titres avec des chandelles\n")
        print(f"  {'titre':<7}{'séances':>8}{'ans':>6}  {'début':<12}{'export Excel'}")
        for t in sorted(inv, key=lambda x: x["seances"]):
            print(f"  {t['ticker']:<7}{t['seances']:>8}{t['annees']:>6}  "
                  f"{t['debut']:<12}{'oui' if t['export_excel'] else '—'}")
        profonds = [t for t in inv if t["seances"] >= 3 * SEANCES_PAR_AN]
        avec = [t for t in profonds if t["export_excel"]]
        print(f"\n  {len(profonds)} titres à trois ans ou plus, "
              f"dont {len(avec)} avec un export Excel "
              f"({'la totalité' if len(avec) == len(profonds) else 'pas tous'})")

    liste = manquants(inv)
    print(f"\n  {len(liste)} titres rattrapables — sous trois ans ET sans export :")
    for t in sorted(liste, key=lambda x: x["debut"]):
        print(f"    {t['ticker']:<7}{t['seances']:>5} séances, depuis {t['debut']}")
    print("\n  ⚠️ Un titre introduit récemment n'a pas d'historique à rattraper.")
    print("     La date de première séance ci-dessus permet de faire le tri.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

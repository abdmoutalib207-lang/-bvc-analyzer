#!/usr/bin/env python3
"""Un ratio ne veut rien dire seul — il veut dire quelque chose dans son secteur.

⚠️ CE QUE CE MODULE RÉPARE
──────────────────────────
D'une lecture extérieure du terminal, transmise par Abd Moutalib le 24/09/2026 :

    « Le PER de 21,1 et le P/B de 2,16 sont exacts, mais un P/B de 2,16 n'a pas
      le même sens dans l'immobilier que dans les télécoms. Un score qui compare
      un promoteur à l'ensemble de la cote, sans référence à son secteur,
      produit une note qui mesure la moyenne du marché autant que la société. »

C'est juste. Une banque à 1,2 de price-to-book est chère ; un éditeur de
logiciels à 1,2 est bradé. Publier le chiffre nu laisse le lecteur faire une
comparaison que personne ne peut faire de tête sur 80 titres.

⚠️ CE MODULE NE TOUCHE PAS AU SCORE — R8
Il **publie une lecture**, il ne modifie aucune pondération ni aucune note.
Faire entrer le rang sectoriel dans le calcul changerait le score de tous les
titres, ce que R8 interdit sans backtesting et accord explicite. Le rang est
donc une information à côté du chiffre, pas dedans.

⚠️ ET IL DIT QUAND IL NE PEUT PAS CONCLURE
La cote de Casablanca compte des secteurs à un ou deux titres. Un « rang 1 sur
1 » n'informe de rien, et un « au-dessus de la médiane » calculé sur deux
valeurs est un tirage au sort. En dessous de `MIN_PAIRS` comparables, le module
rend `None` — ce qui se lit « pas assez de pairs », et non « dans la moyenne ».

C'est la même discipline que le seuil de preuve du sentiment d'actualité : ne
pas produire un chiffre quand on n'a pas de quoi le fonder.
"""

from __future__ import annotations

from statistics import median

# En dessous, un rang n'informe pas. Quatre comparables, c'est le minimum pour
# qu'un « au-dessus de la médiane » distingue autre chose que le hasard — et
# c'est ce que les secteurs de la cote permettent le plus souvent.
MIN_PAIRS = 4

# Les ratios pour lesquels un rang sectoriel a un sens. Le dividende y figure :
# un rendement de 3 % est ordinaire dans les télécoms et remarquable dans la
# santé.
RATIOS = ("pe", "pb", "div")

# ⚠️ Pour ces ratios, BAS vaut mieux que haut — un PER faible dit « pas cher ».
# Le rang 1 doit donc désigner le titre le plus attrayant, pas le plus grand
# nombre, sinon le classement se lit à l'envers.
PLUS_BAS_EST_MIEUX = {"pe", "pb"}


def _valeur(t: dict, ratio: str):
    """La valeur du ratio, ou None si elle n'est pas exploitable.

    ⚠️ Un PER négatif n'est pas un PER bas : c'est une société en perte, et la
    comparaison de valorisation n'a plus de sens. Le classer parmi les moins
    chers le ferait remonter en tête d'un classement « bon marché ».
    """
    v = t.get(ratio)
    if isinstance(v, bool) or v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    if ratio in PLUS_BAS_EST_MIEUX and v <= 0:
        return None
    if ratio == "div" and v < 0:
        return None
    return v


def rangs(tickers: list[dict]) -> dict:
    """{symbol: {ratio: {...}}} — la place de chaque titre dans SON secteur.

    Fonction pure. Pour chaque ratio et chaque secteur, elle rend :
      · `valeur`   ce que porte le titre ;
      · `mediane`  celle du secteur, calculée sur les titres renseignés ;
      · `rang`     1 = le plus attrayant, selon le sens du ratio ;
      · `pairs`    combien de titres ont servi à établir le rang ;
      · `ecart_pct` l'écart à la médiane sectorielle, en pourcentage.
    """
    par_secteur: dict[str, list[dict]] = {}
    for t in tickers or []:
        if isinstance(t, dict) and t.get("sector"):
            par_secteur.setdefault(t["sector"], []).append(t)

    out: dict[str, dict] = {}
    for secteur, groupe in par_secteur.items():
        for ratio in RATIOS:
            couples = [(t.get("symbol"), _valeur(t, ratio)) for t in groupe]
            couples = [(s, v) for s, v in couples if v is not None]
            if len(couples) < MIN_PAIRS:
                continue
            med = median(v for _, v in couples)
            # Le rang 1 revient au plus attrayant, pas au plus grand nombre.
            ordre = sorted(couples, key=lambda sv: sv[1],
                           reverse=ratio not in PLUS_BAS_EST_MIEUX)
            place = {s: i + 1 for i, (s, _) in enumerate(ordre)}
            for s, v in couples:
                out.setdefault(s, {})[ratio] = {
                    "valeur": round(v, 2),
                    "mediane_secteur": round(med, 2),
                    "rang": place[s],
                    "pairs": len(couples),
                    "ecart_pct": (round((v - med) / med * 100, 1)
                                  if med else None),
                    "secteur": secteur,
                }
    return out


def resume(rangs_par_titre: dict, tickers: list[dict]) -> dict:
    """Ce que la normalisation a pu établir, et ce qu'elle n'a pas pu.

    ⚠️ Le second chiffre compte autant que le premier : il dit sur combien de
    titres la lecture sectorielle est muette, et pourquoi.
    """
    secteurs = {}
    for t in tickers or []:
        if isinstance(t, dict) and t.get("sector"):
            secteurs[t["sector"]] = secteurs.get(t["sector"], 0) + 1
    trop_petits = {s: n for s, n in sorted(secteurs.items()) if n < MIN_PAIRS}
    return {
        "titres_classes": len(rangs_par_titre),
        "titres_total": len(tickers or []),
        "min_pairs": MIN_PAIRS,
        "secteurs_trop_petits": trop_petits,
        "_lecture": (
            f"{len(rangs_par_titre)} titres situés dans leur secteur. Les "
            f"autres appartiennent à un secteur de moins de {MIN_PAIRS} "
            f"comparables renseignés : un rang y serait un tirage au sort."),
    }


def main() -> int:
    import json
    import sys
    from pathlib import Path

    chemin = Path(sys.argv[1] if len(sys.argv) > 1
                  else Path(__file__).resolve().parent.parent / "data.json")
    flux = json.loads(chemin.read_text(encoding="utf-8"))
    t = flux.get("tickers") or []
    r = rangs(t)
    print(json.dumps({"resume": resume(r, t), "detail": r},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

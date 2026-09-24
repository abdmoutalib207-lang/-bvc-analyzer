#!/usr/bin/env python3
"""Le score a-t-il séparé les gagnants des perdants ? Mesure, sans promesse.

⚠️ POURQUOI CE FICHIER EST LE PLUS IMPORTANT DU DÉPÔT
─────────────────────────────────────────────────────
Le terminal publie une note sur 10 depuis des mois. **Rien ne dit ce qu'elle
vaut.** On ne sait pas ce qu'un 8/10 annonçait il y a trois mois, ni ce que le
titre a fait ensuite. Sans cette mesure, la note est une opinion habillée en
chiffre — et c'est la première chose qu'un lecteur averti demandera.

⚠️ LA MÉTHODE : CE QUI A ÉTÉ PUBLIÉ, PAS CE QU'ON RECALCULE
Le piège classique d'un backtest est de rejouer le modèle d'aujourd'hui sur les
données d'hier. Ici c'est impossible et ce serait malhonnête : les fondamentaux
sont saisis à la main et figés à leur valeur actuelle, le sentiment aussi. Les
appliquer à juin donnerait au modèle la connaissance du futur.

On lit donc les scores **réellement publiés**, dans l'historique git de
`data.json` — 1 917 commits, 88 jours, 5 035 couples (jour, titre). Ce que le
terminal affichait ce jour-là, confronté à ce que le titre a fait ensuite.
Aucune reconstruction, aucune hypothèse.

⚠️ LES QUATRE LIMITES, ÉNONCÉES AVANT LES RÉSULTATS
Les taire rendrait le chiffre inutilisable ; les dire après le rendrait
suspect.

  1. **Quatre mois, pas six ans.** Du 02/06 au 24/09/2026. Et seulement 19
     titres jusqu'en août, 80 depuis septembre. C'est peu pour conclure.
  2. **Les observations se CHEVAUCHENT.** Le rendement à 20 séances du lundi
     partage 19 séances avec celui du mardi. L'écart-type calculé naïvement
     est donc sous-estimé, et un écart qui paraît net peut n'être que du bruit
     répété. C'est signalé, pas corrigé — le corriger demande un modèle que
     cet échantillon ne justifie pas.
  3. **La période 18/06 → 06/08 est POLLUÉE.** Les scores publiés alors
     reposaient sur des clôtures fausses, découvertes et corrigées le 23/09.
     Les rendements, eux, sont calculés sur les séries corrigées. Les deux
     régimes sont donc décomposés séparément.
  4. **Aucun coût n'est déduit** : ni frais, ni fourchette, ni impact. Sur des
     titres dont certains échangent quelques centaines de titres par séance,
     cela suffit à effacer un écart.
  5. ⚠️ **La période utile commence le 10/08, pas le 02/06.** Le bloc `_meta`
     — donc le score de confiance — n'existe que depuis cette date. Les
     1 898 observations antérieures sont écartées faute de pouvoir distinguer
     un signal publié d'un signal que le produit refusait d'émettre. Il reste
     3 137 observations sur six semaines, pas quatre mois.
  6. ⚠️ **Les horizons longs portent sur un échantillon BIAISÉ.** Une
     observation à 20 séances exige 20 séances de recul : elles ne couvrent
     donc que le DÉBUT de la période, jusqu'au 02/09. Si cette sous-période
     a été particulière, le chiffre la décrit, elle, et non la période
     entière. C'est ce qu'on observe :

         5 séances    n = 1 615   alpha moyen  +0,04 %
        10 séances    n = 1 248   alpha moyen  −0,01 %
        20 séances    n =   522   alpha moyen  −3,65 %

     L'écart entre les trois ne dit pas que l'horizon long est mauvais : il
     dit que les trois ne mesurent pas la même chose.

⚠️ CE QUE LE PREMIER RELEVÉ MONTRE, ET QU'IL FAUT DIRE
Aux horizons où l'échantillon est complet — 5 et 10 séances, plus de mille
observations chacun —, **l'alpha moyen est nul**. Le score ne crée pas de
valeur mesurable sur cette période.

Les paliers extrêmes, eux, comptent 8 à 70 observations : on ne conclut pas.
Une pente apparaît, et elle va dans le mauvais sens — plus le score est haut,
plus l'alpha est faible — mais elle repose sur trop peu de cas pour être autre
chose qu'une piste à surveiller.

⚠️ CE MODULE NE PROMET RIEN. Il mesure et publie, y compris quand le résultat
est mauvais — surtout quand il est mauvais.
"""

from __future__ import annotations

import json
import statistics
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CANDLES = RACINE / "pipeline" / "candles"

# Horizons mesurés, en séances ouvrées. Cinq jours ≈ une semaine, vingt ≈ un
# mois. Au-delà, l'échantillon de quatre mois ne laisse plus assez de fenêtres
# complètes pour que la mesure veuille dire quelque chose.
HORIZONS = (5, 10, 20)

# Les paliers que le terminal donne à lire. Ce ne sont pas des quantiles : ce
# sont les seuils auxquels un utilisateur réagit, et c'est donc ceux-là qu'il
# faut mesurer.
PALIERS = ((0, 4, "≤ 4 — évitement"), (4, 5.5, "4 à 5,5 — attente"),
           (5.5, 7, "5,5 à 7 — surveillance"), (7, 10.01, "≥ 7 — achat"))

# La correction des clôtures fausses porte sur cette fenêtre. Avant sa borne
# haute, les scores publiés reposaient sur des prix erronés.
FIN_PERIODE_POLLUEE = "2026-08-06"

# ⚠️ EN DESSOUS, ON NE CONCLUT PAS. Le premier jet de ce module écrivait
# « le score NE sépare PAS » sur un palier de HUIT observations. C'est un
# verdict tiré d'un tirage, et il aurait été cité comme un résultat.
# Trente n'est pas magique — c'est le minimum en dessous duquel une moyenne de
# rendements ne distingue rien d'un hasard.
MIN_OBSERVATIONS = 30

MASI = RACINE / "pipeline" / "masi_history.json"


def scores_publies(depuis_git=True) -> dict:
    """{date: {ticker: {v53, sig, conf}}} — ce que le terminal AFFICHAIT.

    Un commit par jour, le dernier — celui qui porte la clôture. `git log` est
    antichronologique, donc le premier vu pour une date est le plus tardif.
    """
    log = subprocess.run(
        ["git", "log", "main", "--format=%H %ad", "--date=format:%Y-%m-%d",
         "--", "data.json"],
        capture_output=True, text=True, cwd=RACINE).stdout.splitlines()
    par_jour: dict[str, str] = {}
    for ligne in log:
        h, _, d = ligne.partition(" ")
        par_jour.setdefault(d.strip(), h)

    out: dict[str, dict] = {}
    for d, h in sorted(par_jour.items()):
        brut = subprocess.run(["git", "show", f"{h}:data.json"],
                              capture_output=True, text=True, cwd=RACINE).stdout
        try:
            flux = json.loads(brut)
        except (json.JSONDecodeError, ValueError):
            continue
        lignes = {}
        for x in flux.get("tickers") or []:
            v, sym = x.get("v53"), x.get("symbol")
            if sym and isinstance(v, (int, float)) and not isinstance(v, bool):
                lignes[sym] = {"v53": round(float(v), 2),
                               "conf": (x.get("_meta") or {}).get("confidence")}
        if lignes:
            out[d] = lignes
    return out


def series() -> dict[str, list]:
    """Les clôtures par titre, telles qu'elles sont AUJOURD'HUI — corrigées."""
    out = {}
    for f in sorted(CANDLES.glob("*.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out[f.stem] = [(b["d"], float(b["c"])) for b in s
                       if b.get("c") and float(b["c"]) > 0]
    return out


def indice() -> list:
    """La série du MASI, pour mesurer l'écart au marché.

    ⚠️ ELLE ÉTAIT FAUSSE JUSQU'AU 24/09. Trois séances sur cinq portaient la
    valeur du run de midi, jusqu'à 256 points d'écart — 1,4 %. Un backtest
    bâti là-dessus aurait comparé le score à un marché imaginaire. Le défaut
    a été trouvé en préparant ce module, et corrigé avant qu'il ne serve.
    """
    try:
        d = json.loads(MASI.read_text(encoding="utf-8")).get("seances") or {}
    except (OSError, json.JSONDecodeError):
        return []
    return sorted((k, float(v)) for k, v in d.items() if v)


def rendement_futur(serie: list, date: str, horizon: int):
    """Le rendement en % entre la clôture de `date` et celle `horizon` séances
    plus tard, ou None si la fenêtre n'est pas complète.

    ⚠️ Le point de départ est la clôture du jour où le score a été PUBLIÉ. On
    n'achète donc pas au cours qui a servi à le calculer — on achète après,
    comme un lecteur le ferait. Prendre le cours du jour même serait supposer
    qu'on a agi avant de savoir.
    """
    for i, (d, _) in enumerate(serie):
        if d == date:
            if i + horizon >= len(serie):
                return None
            depart, arrivee = serie[i][1], serie[i + horizon][1]
            return None if depart <= 0 else (arrivee / depart - 1) * 100
    return None


def _stats(valeurs: list) -> dict:
    if not valeurs:
        return {"n": 0}
    return {
        "n": len(valeurs),
        "moyenne_pct": round(statistics.mean(valeurs), 2),
        "mediane_pct": round(statistics.median(valeurs), 2),
        "part_positive_pct": round(
            100 * sum(1 for v in valeurs if v > 0) / len(valeurs), 1),
        "ecart_type": round(statistics.pstdev(valeurs), 2) if len(valeurs) > 1 else None,
    }


def mesurer(scores: dict, prix: dict, horizons=HORIZONS,
            confiance_min=2, masi=None) -> dict:
    """Le rendement observé après chaque score publié, par palier.

    ⚠️ `confiance_min` écarte les titres que le terminal lui-même présentait
    comme « Données insuffisantes ». Les inclure mesurerait la performance de
    signaux que le produit refuse d'émettre — et gonflerait ou dégraderait le
    résultat sans rien dire de ce qui est réellement publié.
    """
    masi = indice() if masi is None else masi
    par_horizon = {}
    for h in horizons:
        paliers = {lib: [] for _, _, lib in PALIERS}
        avant, apres, tous = [], [], []
        for date, lignes in scores.items():
            for sym, e in lignes.items():
                if sym not in prix:
                    continue
                if confiance_min is not None and (e.get("conf") is None
                                                  or e["conf"] < confiance_min):
                    continue
                r = rendement_futur(prix[sym], date, h)
                if r is None:
                    continue
                # ⚠️ L'ÉCART AU MARCHÉ, ET NON LE RENDEMENT BRUT.
                # Sur la période mesurée, TOUS les paliers sont négatifs : le
                # MASI a reculé. Un score qui choisit des titres perdant 6 %
                # quand le marché perd 8 % est utile ; le rendement brut le
                # dirait mauvais. La question n'est pas « gagne-t-on », c'est
                # « fait-on mieux que ne rien choisir ».
                rm = rendement_futur(masi, date, h) if masi else None
                if rm is not None:
                    r = r - rm
                v = e["v53"]
                for lo, hi, lib in PALIERS:
                    if lo <= v < hi:
                        paliers[lib].append(r)
                        break
                tous.append(r)
                (avant if date <= FIN_PERIODE_POLLUEE else apres).append(r)
        par_horizon[f"{h}_seances"] = {
            "par_palier": {lib: _stats(v) for lib, v in paliers.items()},
            "ensemble": _stats(tous),
            "avant_le_06_08_donnees_polluees": _stats(avant),
            "apres_le_06_08": _stats(apres),
        }
    return par_horizon


def verdict(mesure: dict) -> dict:
    """Le score sépare-t-il ? Réponse en une ligne, et elle peut être « non ».

    ⚠️ Le critère est simple et volontairement sévère : le palier « achat »
    doit faire MIEUX que le palier « évitement », à chaque horizon. Un modèle
    qui n'y parvient pas ne classe pas — quelles que soient ses moyennes.
    """
    lignes = {}
    for h, d in mesure.items():
        achat = d["par_palier"].get("≥ 7 — achat", {})
        evite = d["par_palier"].get("≤ 4 — évitement", {})
        if (achat.get("n", 0) < MIN_OBSERVATIONS
                or evite.get("n", 0) < MIN_OBSERVATIONS):
            lignes[h] = {
                "conclusion": "ÉCHANTILLON INSUFFISANT — on ne conclut pas",
                "n_achat": achat.get("n", 0), "n_evitement": evite.get("n", 0),
                "minimum_requis": MIN_OBSERVATIONS,
            }
            continue
        ecart = achat["moyenne_pct"] - evite["moyenne_pct"]
        lignes[h] = {
            "ecart_achat_moins_evitement_pts": round(ecart, 2),
            "conclusion": ("le score sépare" if ecart > 0
                           else "le score NE sépare PAS"),
            "n_achat": achat["n"], "n_evitement": evite["n"],
            "⚠️": ("écart en points d'ALPHA — rendement moins celui du MASI. "
                   "Observations chevauchantes : l'écart-type est sous-estimé "
                   "et cet écart peut n'être que du bruit répété."),
        }
    return lignes


def main() -> int:
    scores = scores_publies()
    prix = series()
    mesure = mesurer(scores, prix)
    jours = sorted(scores)
    print(json.dumps({
        "_avertissement": (
            "MESURE, PAS PROMESSE. Les rendements sont des ÉCARTS AU MASI, "
            "pas des gains. Quatre mois d'historique, observations "
            "chevauchantes, période 18/06→06/08 fondée sur des clôtures depuis "
            "corrigées, et aucun coût de transaction déduit — ni frais, ni "
            "fourchette, ni impact, ce qui suffit à effacer un écart sur des "
            "titres peu liquides. Ce chiffre dit ce qui s'est passé sur un "
            "échantillon court ; il ne dit pas ce qui se passera."),
        "periode": [jours[0], jours[-1]] if jours else None,
        "jours": len(jours),
        "observations": sum(len(v) for v in scores.values()),
        "verdict": verdict(mesure),
        "detail": mesure,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

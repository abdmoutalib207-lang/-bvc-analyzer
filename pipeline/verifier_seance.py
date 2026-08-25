#!/usr/bin/env python3
"""Contrôle qu'une séance cotée a bien été enregistrée, et alerte sinon.

Le critère de succès du projet est « un run J+1 réussi chaque soir, publié
avant 8h00, trente jours consécutifs sans échec ». Ce critère n'était pas
mesurable : rien ne prévenait quand un run manquait. Il fallait que quelqu'un
regarde.

Ce script est ce quelqu'un. Il tourne après le filet de sécurité de 18h, et
sort en code 1 si la séance du jour n'est pas correctement gravée — ce qui
fait échouer le workflow, et GitHub envoie alors un courriel au propriétaire
du dépôt. Pas de service tiers, pas de secret à gérer : l'alerte passe par le
seul canal déjà en place.

⚠️ Il ne commite rien. Le quota de publication de GitHub Pages est la
ressource rare du projet — un contrôle qui produirait un commit par jour
consommerait ce qu'il est censé protéger.

Un jour sans séance — week-end ou férié à date fixe — n'est pas un échec :
le script sort alors en 0 sans rien dire.
"""

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).parent))

from bvc_config import TICKERS_ACTIFS                    # noqa: E402
from seance import derniere_seance_connue                # noqa: E402

# Casablanca est à UTC+1 toute l'année.
TZ_CA = timezone(timedelta(hours=1))

# En deçà, la séance n'a pas été collectée : un jour coté normal grave une
# bougie pour environ soixante-dix titres. Le seuil laisse la marge d'une
# source partiellement défaillante sans laisser passer un run à vide.
MIN_BOUGIES = 50
MIN_PRIX_DU_JOUR = 50


# Écart maximal toléré entre aujourd'hui et la dernière séance enregistrée.
# Cinq jours couvrent le plus long enchaînement réel : les 20 et 21/08 étaient
# fériés, suivis du week-end, soit cinq jours entre le 19 et le 24.
# Au-delà, ce n'est plus un calendrier chargé, c'est un pipeline arrêté.
JOURS_SANS_SEANCE_MAX = 5


def _seance_de_reference():
    """Dernière séance réellement enregistrée, et son âge en jours.

    ⚠️ Volontairement déduite des DONNÉES et non d'un calendrier. Les fériés
    marocains sont en partie lunaires — le Mawlid des 25 et 26/08 n'a pas de
    date fixe et n'est confirmé par décret que peu de temps avant. Un contrôle
    fondé sur une liste écrite d'avance aurait crié à l'échec ces jours-là,
    alors que le moteur se comportait parfaitement. Une alerte qui se trompe
    est pire que pas d'alerte : on cesse de la lire.

    La question posée n'est donc pas « la Bourse a-t-elle coté aujourd'hui ? »,
    à laquelle on ne sait pas répondre, mais « la dernière séance connue est-
    elle trop ancienne ? », à laquelle les chandelles répondent seules.
    """
    derniere = derniere_seance_connue()
    if not derniere:
        return None, 0
    ecart = (datetime.now(TZ_CA).date()
             - datetime.strptime(derniere, "%Y-%m-%d").date()).days
    return derniere, ecart


def _controles(jour, ecart):
    """Liste de (intitulé, réussi, détail). Aucun effet de bord."""
    resultats = []

    def ajouter(intitule, ok, detail=""):
        resultats.append((intitule, bool(ok), detail))

    ajouter(f"séance récente ({JOURS_SANS_SEANCE_MAX} jours au plus)",
            ecart <= JOURS_SANS_SEANCE_MAX,
            f"dernière séance le {jour}, il y a {ecart} jour(s)")

    # ── data.json ────────────────────────────────────────────────────────
    try:
        data = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    except Exception as e:
        ajouter("data.json lisible", False, str(e))
        return resultats

    lignes = data.get("tickers") or []
    if isinstance(lignes, dict):
        lignes = list(lignes.values())
    titres = {x.get("symbol"): x for x in lignes if x.get("symbol")}
    ajouter("data.json lisible", True, f"{len(titres)} titres")

    # `updated` est l'heure du RUN, pas la date de la séance. Les deux
    # diffèrent dès qu'un jour n'est pas coté : le 25/08, férié, le pipeline
    # tournait bien et republiait la séance du 24. Exiger l'égalité faisait
    # échouer le contrôle alors que le moteur se comportait parfaitement.
    # Ce qui importe est que le fichier ait été régénéré récemment.
    horodatage = str(data.get("updated") or "")
    try:
        age_h = (datetime.now(TZ_CA)
                 - datetime.fromisoformat(horodatage)).total_seconds() / 3600
    except Exception:
        age_h = 1e9
    ajouter("data.json régénéré depuis moins de 24 h", age_h <= 24,
            f"{horodatage or 'absent'} ({age_h:.1f} h)" if age_h < 1e8
            else (horodatage or "absent"))

    asof = Counter((x.get("_meta") or {}).get("prix_asof") for x in titres.values())
    du_jour = asof.get(jour, 0)
    ajouter(f"prix de la séance ({MIN_PRIX_DU_JOUR} minimum)",
            du_jour >= MIN_PRIX_DU_JOUR, f"{du_jour} titres au {jour}")

    sources = Counter((x.get("_meta") or {}).get("source_prix") for x in titres.values())
    replis = sources.get("static", 0) + sources.get("data_json_precedent", 0)
    ajouter("sources de prix réelles", replis <= 5,
            f"{sources.get('idbourse', 0)} idbourse · {sources.get('medias24', 0)} "
            f"medias24 · {replis} replis muets")

    absents = [t for t in TICKERS_ACTIFS if not (titres.get(t, {}).get("price") or 0) > 0]
    ajouter("les 19 titres MASI 1 ont un prix", not absents, absents or "tous présents")

    hors = [t for t, x in titres.items()
            if x.get("v53") is not None and not 0 <= x["v53"] <= 10]
    ajouter("score v5.3 dans [0, 10]", not hors, hors or "conforme")

    # Règle R10 : la BVC plafonne la variation à ±10 % par séance.
    aberrantes = [(t, x.get("chg")) for t, x in titres.items()
                  if abs(x.get("chg") or 0) > 10]
    ajouter("aucune variation au-delà de ±10 %", not aberrantes,
            aberrantes or "conforme")

    sans_meta = [t for t, x in titres.items() if not x.get("_meta")]
    ajouter("chaque titre porte son bloc _meta", not sans_meta,
            sans_meta or "tous")

    # On vérifie que l'indice porte la date de la dernière séance, pas qu'il
    # soit « non périmé » : un jour sans cotation, il EST périmé au sens du
    # terminal — c'est la valeur de la veille — et c'est le comportement
    # attendu. Exiger le contraire punissait le moteur d'avoir raison.
    masi = data.get("masi") or {}
    ajouter("MASI daté de la dernière séance",
            str(masi.get("asof") or "")[:10] == jour,
            f"{masi.get('value')} au {masi.get('asof')} · périmé={masi.get('stale')}")

    # ── chandelles ───────────────────────────────────────────────────────
    dossier = RACINE / "pipeline" / "candles"
    n = 0
    for f in dossier.glob("*.json"):
        try:
            serie = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(serie, list) and serie and serie[-1].get("d") == jour:
            n += 1
    ajouter(f"bougies de la séance ({MIN_BOUGIES} minimum)",
            n >= MIN_BOUGIES, f"{n} titres")

    return resultats


def main():
    jour, ecart = _seance_de_reference()
    if jour is None:
        print("ÉCHEC : aucune chandelle lisible — le pipeline n'a jamais écrit.")
        return 1

    resultats = _controles(jour, ecart)
    echecs = [r for r in resultats if not r[1]]

    largeur = max(len(i) for i, _, _ in resultats)
    print(f"Contrôle de la séance du {jour}\n")
    for intitule, ok, detail in resultats:
        print(f"  {'OK   ' if ok else 'ÉCHEC'}  {intitule.ljust(largeur)}  {detail}")

    # Résumé dans l'interface GitHub Actions, pour n'avoir pas à ouvrir le log.
    import os
    resume = os.environ.get("GITHUB_STEP_SUMMARY")
    if resume:
        with open(resume, "a", encoding="utf-8") as fh:
            fh.write(f"## Séance du {jour}\n\n")
            fh.write("| | Contrôle | Détail |\n|---|---|---|\n")
            for intitule, ok, detail in resultats:
                fh.write(f"| {'✅' if ok else '❌'} | {intitule} | {detail} |\n")

    if echecs:
        print(f"\n{len(echecs)} contrôle(s) en échec — la séance du {jour} "
              f"n'est pas correctement enregistrée.")
        return 1
    print(f"\nSéance du {jour} enregistrée et conforme.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

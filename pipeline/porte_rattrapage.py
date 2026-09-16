"""La porte du cron de rattrapage : y a-t-il lieu de relancer le moteur ?

POURQUOI CE FICHIER EXISTE
──────────────────────────
Le mercredi 16/09/2026 à 11h08 Casablanca — une heure trente-huit APRÈS
l'ouverture — le terminal servait encore la clôture du 15. `data.json` portait
`updated: 2026-09-16T03:15`, et 78 titres sur 80 au `prix_asof` du 15/09.

Deux choses avaient manqué, et la seconde est la grave.

1. Le cron de 09h40 n'est pas parti. C'est le mal connu : GitHub décale ses
   tâches programmées de deux à huit heures, quand il ne les oublie pas.

2. LE FILET DE SÉCURITÉ N'A PAS VU LE TROU. Le cron horaire de rattrapage
   existe précisément pour ça, et sa porte a répondu « à jour — rien à
   rattraper ». Elle jugeait sur la DATE DU FICHIER, pas sur la SÉANCE QU'IL
   PORTE : un run de 3h du matin — un rattrapage tardif de la veille — suffisait
   à lui faire croire la journée couverte. Et sa première règle exigeait en
   outre qu'il soit 10h30 passées.

   Conséquence mesurée : entre 9h30 et 16h30, un fichier fabriqué avant
   l'ouverture était réputé à jour. Le terminal aurait montré la veille pendant
   toute la séance.

CE QUI TRANCHE DÉSORMAIS
────────────────────────
La SÉANCE QUE LE FICHIER PORTE — `_meta.prix_asof`, pris à la majorité des
titres — et non l'heure à laquelle on l'a écrit. Un fichier daté d'aujourd'hui
mais rempli des cours d'hier n'est pas à jour ; c'est exactement ce qu'il
fallait savoir dire.

⚠️ LE FREIN, ET POURQUOI IL EST INDISPENSABLE. Un jour férié, la séance du jour
n'existera jamais : sans frein, la règle ci-dessus déclencherait un run par
heure, donc un commit par heure, et le quota de reconstruction de GitHub Pages —
la ressource rare du projet — y passerait. Le frein est simple : une tentative
par fenêtre. Si un run a déjà eu lieu dans la fenêtre courante sans ramener les
cours du jour, c'est que la Bourse ne cote pas, et recommencer n'y changerait
rien. Au pire deux runs supplémentaires par jour, et seulement les jours où
quelque chose a réellement manqué.

⚠️ AUCUN CALENDRIER DE JOURS FÉRIÉS N'EST INTRODUIT. Les fériés marocains
suivent en partie le calendrier lunaire et une telle liste ne serait pas tenue
à jour — c'est le raisonnement retenu le 14/08 pour les séances fantômes, et il
vaut ici. Le frein se déduit des données.

    python pipeline/porte_rattrapage.py            # lit data.json et décide
    python pipeline/porte_rattrapage.py --pourquoi # explique sans décider
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RACINE = Path(__file__).resolve().parent.parent
CASA = ZoneInfo("Africa/Casablanca")

# Bornes des deux fenêtres, en HHMM Casablanca.
#
# 09h50 : vingt minutes après l'ouverture de 9h30. C'est le délai déjà retenu
# pour le cron du matin — « le temps que les titres peu liquides impriment un
# premier cours ». Avant, un run les compterait comme périmés.
OUVERTURE_FENETRE_MATIN = 950
# 16h00 : la clôture est à 15h30, le run qui fixe le cours définitif vise 15h45.
OUVERTURE_FENETRE_SOIR = 1600
# 16h30 : au-delà, un fichier du jour antérieur à 15h45 n'a pas vu la clôture.
CONTROLE_CLOTURE = 1630
HEURE_DU_RUN_DE_CLOTURE = 1545


def seance_portee(data: dict) -> str | None:
    """La séance que le fichier porte, à la majorité de ses titres.

    ⚠️ À LA MAJORITÉ, ET NON AU PREMIER TITRE VENU. Il y a toujours quelques
    valeurs qui n'ont pas coté et gardent la date de leur dernière séance —
    relevé le 16/09 : 57 titres au 16, 15 au 15, 2 au 14. Prendre le premier
    venu ferait dépendre la décision de l'ordre du fichier.
    """
    dates = Counter(
        (t.get("_meta") or {}).get("prix_asof")
        for t in data.get("tickers") or []
        if (t.get("_meta") or {}).get("prix_asof")
    )
    return dates.most_common(1)[0][0] if dates else None


def _hhmm(horodatage: str) -> int | None:
    """« 2026-09-16T03:15:41+0100 » → 315. None si illisible."""
    try:
        heure = horodatage.split("T", 1)[1]
        return int(heure[:2]) * 100 + int(heure[3:5])
    except (IndexError, ValueError):
        return None


def decider(maintenant: int, aujourd_hui: str, data: dict | None) -> tuple[bool, str]:
    """(faut-il lancer le moteur, pourquoi).

    `maintenant` est en HHMM Casablanca, `aujourd_hui` en AAAA-MM-JJ.
    """
    if not data:
        return True, "data.json illisible ou absent — on lance, c'est plus sûr que de supposer"

    ecrit_le = data.get("updated") or ""
    jour_ecriture = ecrit_le.split("T", 1)[0]
    heure_ecriture = _hhmm(ecrit_le)
    asof = seance_portee(data)

    if asof is None:
        return True, "aucun titre ne porte de date de séance — fichier douteux"

    porte_le_jour = asof == aujourd_hui
    ecrit_aujourd_hui = jour_ecriture == aujourd_hui

    # ── Fenêtre du matin : la séance du jour manque pendant qu'elle a lieu ──
    if OUVERTURE_FENETRE_MATIN <= maintenant < OUVERTURE_FENETRE_SOIR and not porte_le_jour:
        if ecrit_aujourd_hui and heure_ecriture is not None \
                and heure_ecriture >= OUVERTURE_FENETRE_MATIN:
            return False, (f"déjà tenté à {heure_ecriture:04d} sans ramener les cours "
                           f"du jour (le fichier porte le {asof}) — la Bourse ne cote "
                           "probablement pas aujourd'hui")
        return True, (f"la séance du jour manque : le fichier porte le {asof} "
                      f"et il est {maintenant:04d}")

    # ── Fenêtre du soir : la journée entière a été manquée ──────────────────
    if maintenant >= OUVERTURE_FENETRE_SOIR and not porte_le_jour:
        if ecrit_aujourd_hui and heure_ecriture is not None \
                and heure_ecriture >= OUVERTURE_FENETRE_SOIR:
            return False, (f"déjà tenté à {heure_ecriture:04d} sans ramener les cours "
                           f"du jour (le fichier porte le {asof})")
        return True, (f"journée manquée : le fichier porte encore le {asof}")

    # ── Le run qui fixe le cours définitif a sauté ──────────────────────────
    #
    # Le fichier porte bien la séance du jour, mais il a été écrit AVANT 15h45 :
    # il a donc capté un cours de milieu de séance, pas la clôture. C'est le run
    # qui compte le plus, et celui-ci le rattrape.
    if maintenant >= CONTROLE_CLOTURE and ecrit_aujourd_hui \
            and heure_ecriture is not None and heure_ecriture < HEURE_DU_RUN_DE_CLOTURE:
        return True, (f"rien depuis la clôture : dernier passage à "
                      f"{heure_ecriture:04d}, avant {HEURE_DU_RUN_DE_CLOTURE}")

    return False, f"à jour — le fichier porte la séance du {asof}"


def main() -> int:
    chemin = RACINE / "data.json"
    try:
        data = json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:
        data = None
    now = datetime.now(CASA)
    maintenant = now.hour * 100 + now.minute
    aujourd_hui = now.strftime("%Y-%m-%d")
    run, pourquoi = decider(maintenant, aujourd_hui, data)
    print(f"{'🛟' if run else '✅'} {pourquoi}")
    if "--pourquoi" not in sys.argv:
        print(f"run={'true' if run else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
from zoneinfo import ZoneInfo
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).parent))

from bvc_config import TICKERS_ACTIFS, decalage_maroc    # noqa: E402
from seance import derniere_seance_connue                # noqa: E402

# ⚠️ PAS `ZoneInfo`. Voir le bloc sur `_fuseau()` plus bas : la base de
# fuseaux du conteneur, figée en avril 2025, ignorait le passage du Maroc à
# UTC+0 du 20/09/2026. Le fuseau se lit dans le registre `DECALAGES_MAROC`.
def _maintenant_local() -> datetime:
    """L'heure locale marocaine, d'après le registre."""
    n = datetime.now(timezone.utc)
    return n.astimezone(timezone(timedelta(hours=decalage_maroc(n.date()))))

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

# Heure de clôture de la Bourse de Casablanca.
HEURE_CLOTURE = (15, 30)

# ⚠️ LE DÉCALAGE VIENT DU REGISTRE, PAS D'UNE CONSTANTE ET PAS DU SYSTÈME.
#
# Ce fichier a porté `UTC_PLUS_1 = timezone(timedelta(hours=1))` écrit en dur,
# et c'était faux. Le Maroc est passé à UTC+0 le dimanche 20/09/2026 à minuit ;
# pendant trois séances le contrôle a placé la clôture une heure trop tôt et
# aurait accepté un fichier qui ne la contenait pas.
#
# ⚠️ J'avais eu l'avertissement et je l'ai mal lu. Deux tests passaient en
# local et échouaient en intégration avec exactement une heure d'écart. J'en ai
# conclu que le runner GitHub avait une base de fuseaux périmée et j'ai forcé
# UTC+1. C'était l'inverse : le runner était à jour.
#
# Ni la constante ni `ZoneInfo` ne conviennent — la première ignore les
# décrets, la seconde dépend d'une base dont on ne maîtrise ni la version ni la
# fraîcheur. Le décalage est un FAIT DÉCLARÉ : il vit dans `DECALAGES_MAROC`.
def _fuseau(jour) -> timezone:
    """Le fuseau du Maroc à la date donnée, d'après le registre."""
    return timezone(timedelta(hours=decalage_maroc(jour)))


def derniere_cloture_ecoulee(maintenant: datetime) -> datetime:
    """Le dernier 15h30 Casablanca déjà passé, à l'instant donné.

    Fonction pure : elle ne lit ni fichier ni réseau.

    ⚠️ POURQUOI ELLE EXISTE — LE CHIEN DE GARDE A DIT « TOUT VA BIEN » LES DEUX
    JOURS OÙ LE PRODUIT ÉTAIT CASSÉ
    ────────────────────────────────────────────────────────────────────────
        18/09 21h07   contrôle VERT.   data.json écrit à 04h44, portant le 16/09.
                      La séance du 18 avait eu lieu et n'était nulle part.
        21/09 22h07   contrôle VERT.   data.json écrit à 11h44, annonçant 60
                      titres « au 21/09 » — des cours figés EN PLEINE SÉANCE,
                      clôtures et volumes tronqués. BCP publiait 1 337 titres
                      échangés quand la séance en avait vu 469 537.

    Les douze contrôles vérifiaient la présence, la cohérence, les bornes.
    Aucun ne demandait la seule chose qui tranche : **un fichier écrit à 11h44
    ne peut pas contenir la clôture de 15h30.** C'est une comparaison de deux
    dates, et elle aurait attrapé les deux jours.

    ⚠️ ET ELLE NE CRIE PAS AU LOUP UN JOUR FÉRIÉ. Le moteur tourne les jours
    fériés comme les autres et réécrit `data.json` — avec les mêmes cours, mais
    avec un horodatage frais. Le contrôle ne demande pas « la Bourse a-t-elle
    coté ? », question à laquelle nous ne savons pas répondre sans calendrier
    lunaire, mais « le moteur a-t-il tourné depuis la dernière clôture ? », à
    laquelle l'horloge répond seule. C'est le même raisonnement que pour les
    séances fantômes du 14/08 : déduire des données, jamais d'une liste.
    """
    # ⚠️ On raisonne dans le décalage FIXE UTC+1, celui que le moteur écrit.
    # `maintenant` peut arriver naïf ou dans n'importe quel fuseau ; ce qui
    # compte est l'instant, pas l'étiquette.
    # Le fuseau dépend de la DATE, et la date du fuseau. On tranche par la
    # date UTC : les deux ne divergent qu'entre minuit et 1h du matin, où le
    # décalage vaut de toute façon la même chose des deux côtés.
    if maintenant.tzinfo is None:
        maintenant = maintenant.replace(tzinfo=timezone.utc)
    fuseau = _fuseau(maintenant.astimezone(timezone.utc).date())
    ici = maintenant.astimezone(fuseau)
    cloture = ici.replace(hour=HEURE_CLOTURE[0], minute=HEURE_CLOTURE[1],
                          second=0, microsecond=0)
    if ici < cloture:
        cloture -= timedelta(days=1)
    return cloture


def horodatage_couvre_la_cloture(horodatage: str,
                                 maintenant: datetime) -> tuple[bool, str]:
    """Le fichier a-t-il été écrit après la dernière clôture écoulée ?

    Renvoie (verdict, détail lisible). Fonction pure, et c'est volontaire :
    la DÉCISION doit être éprouvable seule.

    ⚠️ ELLE EXISTE PARCE QU'UN MUTANT A SURVÉCU. La première version comparait
    les dates à l'intérieur de la liste des contrôles, et mes tests ne
    vérifiaient que la présence de la ligne dans le source. Inverser `>=` en
    `<=` — donc accepter exactement ce qu'on voulait refuser — ne faisait
    rougir aucun test. **Vérifier qu'une ligne existe n'est pas vérifier
    qu'elle fonctionne.**

    Un horodatage illisible ou absent vaut échec : on ne présume pas de
    l'innocence d'un fichier qui ne sait pas dire quand il a été écrit.
    """
    cloture = derniere_cloture_ecoulee(maintenant)
    try:
        ecrit = datetime.fromisoformat(horodatage)
    except (TypeError, ValueError):
        return False, f"horodatage illisible : {horodatage or 'absent'}"
    if ecrit.tzinfo is None:
        ecrit = ecrit.replace(tzinfo=cloture.tzinfo)
    ecrit = ecrit.astimezone(cloture.tzinfo)
    detail = (f"écrit le {ecrit:%d/%m à %Hh%M}, clôture du "
              f"{cloture:%d/%m à %Hh%M}")
    if ecrit < cloture:
        return False, detail + (" — le fichier est ANTÉRIEUR à la clôture "
                                "qu'il prétend porter")
    return True, detail


def _seance_de_reference():
    """La source extérieure détermine la séance attendue, pas le dépôt."""
    from pipeline.seance_source import derniere_seance_source
    derniere = derniere_seance_source()
    if not derniere:
        return None, 0
    ecart = (_maintenant_local().date()
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
        age_h = (_maintenant_local()
                 - datetime.fromisoformat(horodatage)).total_seconds() / 3600
    except Exception:
        age_h = 1e9
    ajouter("data.json régénéré depuis moins de 24 h", age_h <= 24,
            f"{horodatage or 'absent'} ({age_h:.1f} h)" if age_h < 1e8
            else (horodatage or "absent"))

    # ⚠️ LE CONTRÔLE QUI MANQUAIT, ET QUI AURAIT VU LES DEUX PANNES.
    # Un fichier écrit avant la clôture ne peut pas la contenir. Voir
    # `derniere_cloture_ecoulee()` pour le détail des 18 et 21/09.
    apres_cloture, detail = horodatage_couvre_la_cloture(
        horodatage, _maintenant_local())
    ajouter("data.json écrit après la dernière clôture", apres_cloture, detail)

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

    # Règle R10 : la BVC plafonne la variation à ±10 % par séance, sur le
    # COURS D'UNE SOCIÉTÉ. Le contrôle porte bien sur les titres un à un —
    # l'indice, lui, n'est pas soumis à ce plafond (précision du 05/09/2026).
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

    # Une bougie ne peut pas ouvrir ni clôturer hors de sa propre fourchette.
    # Contrôle ajouté le 04/09/2026, après avoir trouvé 3 238 bougies (9,9 %)
    # dont le plus haut était inférieur à l'ouverture : l'étape 6c amorçait
    # les extrêmes sur la seule clôture. La source est corrigée, ce test
    # interdit la rechute — et il porte sur TOUT l'historique, pas seulement
    # sur la dernière séance, parce que trois écrivains distincts y touchent.
    incoherentes = []
    for f in dossier.glob("*.json"):
        try:
            serie = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(serie, list):
            continue
        for b in serie:
            o, h, l, c = (b.get(k) for k in ("o", "h", "l", "c"))
            if None in (o, h, l, c):
                continue
            if l > min(o, c) + 1e-9 or h < max(o, c) - 1e-9:
                incoherentes.append(f"{f.stem} {b.get('d')}")
    ajouter("bougies cohérentes (l ≤ o,c ≤ h)", not incoherentes,
            f"{len(incoherentes)} incohérentes — {', '.join(incoherentes[:3])}…"
            if incoherentes else "toutes")

    return resultats


def main():
    try:
        jour, ecart = _seance_de_reference()
    except Exception as e:
        print(f"ÉCHEC — fraîcheur non vérifiable : {e}")
        return 1
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

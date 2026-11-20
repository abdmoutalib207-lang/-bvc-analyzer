#!/usr/bin/env python3
"""État du service publié — lots 3.1 et 3.5 de la feuille de route (20/11/2026).

POURQUOI CE FICHIER
───────────────────
Le critère de succès du projet est « un bulletin J+1 publié avant 8h00,
trente jours consécutifs sans échec ». Jusqu'ici il ne se lisait nulle part :
le contrôle du soir (`verifier_seance.py`) ne commite rien — à raison, le quota
de reconstruction de GitHub Pages est la ressource rare du projet — et son
verdict ne vit que dans l'onglet Actions. Le terminal n'avait aucun moyen de
dire « à jour » ou « en retard depuis le JJ/MM ».

Ce module écrit `etat_service.json` à la racine servie par Pages, à côté de
`data.json` dont il dérive. Il est appelé par `update_bvc` DANS l'étape de
commit existante, et seulement quand un autre fichier est déjà indexé : il ne
produit jamais de commit à lui seul.

CE QU'IL MESURE, ET CE QU'IL NE MESURE PAS
──────────────────────────────────────────
⚠️ Le compteur publié n'est PAS « jours consécutifs avec `verifier_seance`
vert ». Ce verdict n'est lisible que par l'API GitHub (résultat des runs) et
ne laisse aucun fichier ; depuis les fichiers du dépôt, il n'est pas
mesurable. Le compteur dit ce qu'il mesure vraiment :

    jours ouvrés consécutifs avec une CLÔTURE PUBLIÉE À TEMPS

« Clôture publiée » reprend les trois contrôles de `verifier_seance` qui se
vérifient sur le seul `data.json` : au moins 50 titres au prix de la séance,
fichier écrit après la clôture de 15h30, MASI daté de la séance. « À temps » :
avant 8h00 (heure de Casablanca) le jour ouvré suivant — la promesse du
bulletin. Un jour ouvré est un jour de semaine qui n'est ni un férié à date
fixe, ni une date inscrite à `SEANCES_SANS_COTATION` ou `SEANCES_ANNULEES`.
⚠️ Un férié lunaire NON inscrit au registre compte comme une séance manquée :
le compteur penche du côté prudent, et la parade est d'inscrire la date.

LE JOURNAL
──────────
Le dépôt est cloné en profondeur 1 par `actions/checkout` : l'historique git
n'existe pas pendant le run. Le fichier porte donc son propre journal (séance →
première publication conforme), repris d'un passage à l'autre. Il a été
amorcé une fois, en local, par `--reconstruire-git` sur l'historique des
commits `data:` ; c'est la seule commande qui lise git.

    python3 pipeline/etat_service.py                 # écrit etat_service.json
    python3 pipeline/etat_service.py --stdout        # affiche sans écrire
    python3 pipeline/etat_service.py --reconstruire-git 2026-10-08   # amorçage local

Bibliothèque standard seulement (R4). Une erreur sort sur stderr (R5) et le
code de sortie est non nul : le workflow l'écrit en avertissement sans
bloquer la publication de data.json.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from bvc_config import (decalage_maroc, est_ferie_fixe, heure_maroc,  # noqa: E402
                        seance_annulee, seance_sans_cotation)
from pipeline.porte_rattrapage import seance_portee  # noqa: E402

SCHEMA = "etat_service/1"
SORTIE = RACINE / "etat_service.json"

# Mêmes seuils que verifier_seance.py (MIN_PRIX_DU_JOUR, HEURE_CLOTURE) ;
# un test vérifie l'égalité.
MIN_TITRES_CLOTURE = 50
HEURE_CLOTURE = (15, 30)
# Le bulletin est promis avant 8h00 le jour ouvré suivant.
HEURE_LIMITE = (8, 0)
# Seuil d'alerte de l'agent operateur-production pour un dépôt non lu.
FILE_JOURS_OUVRES_MAX = 5
# Taille du journal reporté d'un passage à l'autre (≈ 4 mois de séances).
JOURNAL_MAX = 90

DEFINITION_COMPTEUR = (
    "Jours ouvrés consécutifs, en remontant depuis la dernière séance échue, "
    f"pour lesquels data.json a publié la clôture à temps : au moins "
    f"{MIN_TITRES_CLOTURE} titres au prix de la séance, fichier écrit après la "
    "clôture de 15h30 et MASI daté de la séance, avant 8h00 (Casablanca) le jour "
    "ouvré suivant. Jour ouvré : du lundi au vendredi, hors fériés à date fixe et "
    "dates inscrites au registre (SEANCES_SANS_COTATION, SEANCES_ANNULEES). "
    "Une séance dont l'échéance n'est pas passée est en attente : elle ne compte "
    "ni ne rompt. Ce n'est PAS le verdict de verifier_seance, qui n'est lisible "
    "que dans GitHub Actions.")


# ── Calendrier et horloge ──────────────────────────────────────────────────

def _jour(x) -> date:
    return x if isinstance(x, date) and not isinstance(x, datetime) else date.fromisoformat(str(x)[:10])


def jour_ouvre(j) -> bool:
    """Jour où une séance est attendue (lun.-ven., hors fériés et registres)."""
    j = _jour(j)
    iso = j.isoformat()
    return (j.weekday() < 5 and not est_ferie_fixe(iso)
            and not seance_sans_cotation(iso) and not seance_annulee(iso))


def jour_ouvre_suivant(j) -> date:
    j = _jour(j) + timedelta(days=1)
    while not jour_ouvre(j):
        j += timedelta(days=1)
    return j


def jour_ouvre_precedent(j) -> date:
    j = _jour(j) - timedelta(days=1)
    while not jour_ouvre(j):
        j -= timedelta(days=1)
    return j


def _local(j, hm) -> datetime:
    """L'instant `hm` (heure, minute) du jour `j`, à l'heure du registre."""
    j = _jour(j)
    tz = timezone(timedelta(hours=decalage_maroc(j.isoformat())))
    return datetime(j.year, j.month, j.day, hm[0], hm[1], tzinfo=tz)


def cloture(j) -> datetime:
    return _local(j, HEURE_CLOTURE)


def echeance(j) -> datetime:
    """Limite de publication de la séance `j` : 8h00 le jour ouvré suivant."""
    return _local(jour_ouvre_suivant(j), HEURE_LIMITE)


def lire_instant(s) -> datetime | None:
    """ISO 8601 (« +0000 » accepté) → datetime avec fuseau ; None si illisible.

    Un horodatage sans fuseau est lu à l'heure du registre de sa date.
    """
    if not s:
        return None
    texte = re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", str(s).strip().replace("Z", "+00:00"))
    texte = texte.replace(" ", "T", 1) if "T" not in texte else texte
    try:
        t = datetime.fromisoformat(texte)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone(timedelta(hours=decalage_maroc(t.date().isoformat()))))
    return t


def derniere_seance_echue(maintenant: datetime) -> date:
    """Le dernier jour ouvré dont la clôture de 15h30 est passée."""
    j = heure_maroc(maintenant).date()
    if not jour_ouvre(j) or maintenant < cloture(j):
        j = jour_ouvre_precedent(j)
    return j


# ── Une publication de data.json ───────────────────────────────────────────

def publication(data: dict) -> dict:
    """Ce qu'un data.json publie : séance portée, titres à cette séance, heure."""
    lignes = data.get("tickers") or []
    if isinstance(lignes, dict):
        lignes = list(lignes.values())
    seance = seance_portee({"tickers": lignes})
    n = sum(1 for t in lignes if (t.get("_meta") or {}).get("prix_asof") == seance)
    sources = Counter((t.get("_meta") or {}).get("source_prix") or "inconnue" for t in lignes)
    masi = data.get("masi") or {}
    return {
        "seance": seance,
        "titres_seance": n,
        "titres": len(lignes),
        "ecrit_a": data.get("updated"),
        "masi_asof": str(masi.get("asof") or "")[:10] or None,
        "sources": dict(sorted(sources.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def cloture_conforme(pub: dict) -> tuple[bool, str]:
    """La publication porte-t-elle la clôture de sa séance ? (verdict, motif)."""
    if not pub.get("seance"):
        return False, "aucune séance lisible"
    motifs = []
    if pub.get("titres_seance", 0) < MIN_TITRES_CLOTURE:
        motifs.append(f"{pub.get('titres_seance', 0)} titres au prix de la séance "
                      f"(minimum {MIN_TITRES_CLOTURE})")
    ecrit = lire_instant(pub.get("ecrit_a"))
    if ecrit is None:
        motifs.append("horodatage illisible")
    elif ecrit < cloture(pub["seance"]):
        motifs.append("écrit avant la clôture de 15h30")
    if pub.get("masi_asof") != pub["seance"]:
        motifs.append(f"MASI daté du {pub.get('masi_asof')}")
    return (not motifs), "; ".join(motifs) or "conforme"


def enregistrer(journal: dict, pub: dict) -> dict:
    """Ajoute une publication au journal. Fonction pure (copie).

    On ne retient, par séance, que la PREMIÈRE publication conforme : c'est
    elle qui dit si la clôture était en ligne avant l'échéance.
    """
    journal = {k: dict(v) for k, v in (journal or {}).items()}
    ok, _ = cloture_conforme(pub)
    s = pub.get("seance")
    if ok and s and s not in journal:
        journal[s] = {"publiee_a": pub["ecrit_a"], "titres": pub["titres_seance"]}
    return journal


# ── Verdicts par séance et compteur ────────────────────────────────────────

def verdicts(journal: dict, depuis, maintenant: datetime) -> list[dict]:
    """Un verdict par jour ouvré, de `depuis` à la dernière séance échue.

    a_temps · hors_delai (publiée après 8h00 J+1) · manquee · en_attente
    (clôture passée, échéance non encore atteinte, rien de publié).
    """
    fin = derniere_seance_echue(maintenant)
    j = _jour(depuis)
    if not jour_ouvre(j):
        j = jour_ouvre_suivant(j)
    sortie = []
    while j <= fin:
        e = journal.get(j.isoformat())
        if e:
            publie = lire_instant(e.get("publiee_a"))
            statut = "a_temps" if publie and publie <= echeance(j) else "hors_delai"
        else:
            statut = "en_attente" if maintenant < echeance(j) else "manquee"
        sortie.append({"seance": j.isoformat(), "statut": statut,
                       **({"publiee_a": e["publiee_a"]} if e else {})})
        j = jour_ouvre_suivant(j)
    return sortie


def compteur(vs: list[dict]) -> dict:
    """Séances à temps consécutives, depuis la plus récente échue."""
    n, rupture = 0, None
    for v in reversed(vs):
        if v["statut"] == "en_attente":
            continue
        if v["statut"] != "a_temps":
            rupture = v
            break
        n += 1
    return {"valeur": n,
            # Toute la fenêtre du journal est à temps : le vrai compte peut
            # être plus long, on ne le sait pas.
            "au_moins": rupture is None and bool(vs),
            "derniere_rupture": ({"seance": rupture["seance"], "statut": rupture["statut"]}
                                 if rupture else None)}


# ── Tâches et sources ──────────────────────────────────────────────────────

def _jjmm(iso) -> str:
    return f"{str(iso)[8:10]}/{str(iso)[5:7]}"


def _statut_tache(nom, derniere, attendue, detail="") -> dict:
    """« à jour » si `derniere` couvre la séance `attendue`, sinon en retard."""
    if not derniere:
        return {"nom": nom, "derniere": None, "en_retard": True,
                "statut": "état inconnu", "detail": detail or "date illisible"}
    if str(derniere)[:10] >= attendue.isoformat():
        return {"nom": nom, "derniere": derniere, "en_retard": False,
                "statut": "à jour", "detail": detail}
    depuis = jour_ouvre_suivant(str(derniere)[:10])
    return {"nom": nom, "derniere": derniere, "en_retard": True,
            "statut": f"en retard depuis le {_jjmm(depuis.isoformat())}", "detail": detail}


def _lire_json(chemin: Path):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def derniere_bougie(dossier: Path) -> str | None:
    """Dernière date portée par au moins MIN_TITRES_CLOTURE fichiers de chandelles."""
    dates = Counter()
    for f in dossier.glob("*.json"):
        serie = _lire_json(f)
        if isinstance(serie, list) and serie and isinstance(serie[-1], dict):
            dates[serie[-1].get("d")] += 1
    ok = [d for d, n in dates.items() if d and n >= MIN_TITRES_CLOTURE]
    return max(ok) if ok else None


def taches(racine: Path, pub: dict, vs: list[dict], echue: date) -> list[dict]:
    """Tâches et sources, chacune « à jour » ou « en retard depuis le JJ/MM »."""
    sortie = []
    # 1. Publication des cours : d'après les verdicts, pas d'après l'heure.
    rompues = [v for v in vs if v["statut"] in ("manquee", "hors_delai")]
    a_temps = [v["seance"] for v in vs if v["statut"] == "a_temps"]
    derniere_ok = a_temps[-1] if a_temps else None
    recentes = [v for v in rompues if not derniere_ok or v["seance"] > derniere_ok]
    sortie.append({
        "nom": "Publication de la clôture (update_bvc)",
        "derniere": derniere_ok, "en_retard": bool(recentes),
        "statut": (f"en retard depuis le {_jjmm(recentes[0]['seance'])}" if recentes else "à jour"),
        "detail": "séance de la dernière clôture publiée à temps"})
    # 2. Indice : daté de la séance que porte data.json.
    if pub.get("seance"):
        sortie.append(_statut_tache("Indice MASI", pub.get("masi_asof"), _jour(pub["seance"]),
                                    "date de l'indice dans data.json"))
    # 3. Chandelles : la dernière séance échue doit y être gravée.
    sortie.append(_statut_tache("Chandelles (pipeline/candles)",
                                derniere_bougie(racine / "pipeline" / "candles"), echue,
                                f"dernière séance portée par au moins {MIN_TITRES_CLOTURE} titres"))
    # 4. Fichiers d'autres tâches : tolérance d'un jour ouvré (écrits le soir).
    veille = jour_ouvre_precedent(echue)
    news = _lire_json(racine / "news.json") or {}
    sortie.append(_statut_tache("Actualités (news.json)", str(news.get("updated") or "")[:10] or None,
                                veille, "date de collecte"))
    bc = _lire_json(racine / "briefing_cloture.json") or {}
    sortie.append(_statut_tache("Briefing de clôture", bc.get("seance"), veille,
                                "séance du dernier briefing de clôture"))
    fd = _lire_json(racine / "financial_data.json") or {}
    sortie.append(_statut_tache("Pipeline v9 (financial_data.json)",
                                str(fd.get("timestamp") or "")[:10] or None, veille,
                                "date d'écriture"))
    # 5. Sources de prix : les replis muets (statique, data.json précédent)
    #    sont un échec de verifier_seance au-delà de 5 titres.
    src = pub.get("sources") or {}
    replis = src.get("static", 0) + src.get("data_json_precedent", 0)
    sortie.append({"nom": "Sources de prix réelles", "derniere": pub.get("seance"),
                   "en_retard": replis > 5,
                   "statut": "à jour" if replis <= 5 else f"{replis} titres sur un repli muet",
                   "detail": " · ".join(f"{k} {v}" for k, v in src.items())})
    # 6. Le contrôle du soir : dit tel quel, non mesuré.
    sortie.append({"nom": "Contrôle du soir (verifier_seance)", "derniere": None,
                   "en_retard": False, "mesure": False, "statut": "non mesuré ici",
                   "detail": "son verdict est le résultat du workflow dans GitHub Actions ; "
                             "il ne commite rien et ne laisse aucun fichier à lire"})
    return sortie


def jours_ouvres_entre(debut, fin) -> int:
    """Jours ouvrés strictement après `debut`, jusqu'à `fin` inclus."""
    n, j = 0, _jour(debut)
    fin = _jour(fin)
    while j < fin:
        j = jour_ouvre_suivant(j)
        if j <= fin:
            n += 1
    return n


def file_comptes(aujourd_hui: date) -> dict:
    """La file des comptes à lire (nombre, plus ancien) ; jamais d'exception."""
    try:
        from pipeline.depots_ammc import charger
        from pipeline.file_attente_comptes import (JEU, charger_integres,
                                                   file_attente_etendue, sortie_json)
        jeu = json.loads(JEU.read_text(encoding="utf-8"))
        f = sortie_json(file_attente_etendue(charger(), jeu, charger_integres()))
    except Exception as ex:  # noqa: BLE001 — la file n'empêche pas l'état
        print(f"etat_service : file des comptes illisible ({type(ex).__name__}: {ex})",
              file=sys.stderr)
        return {"disponible": False, "statut": "état inconnu"}
    a_lire = [e for v in (f.get("a_lire") or {}).values() for e in v]
    a_lire.sort(key=lambda e: str(e.get("date") or ""))
    ancien = a_lire[0] if a_lire else None
    attente = jours_ouvres_entre(ancien["date"], aujourd_hui) if ancien and ancien.get("date") else 0
    return {
        "disponible": True,
        "a_lire": len(a_lire),
        "plus_ancien": ({"ticker": ancien.get("ticker"), "date": ancien.get("date"),
                         "jours_ouvres": attente} if ancien else None),
        "avertissements": len(f.get("avertissements") or []),
        "non_suivis": (f.get("comptes") or {}).get("non_suivis", 0),
        "en_retard": attente > FILE_JOURS_OUVRES_MAX,
        "statut": ("vide" if not a_lire else
                   f"en retard depuis le {_jjmm(ancien['date'])}" if attente > FILE_JOURS_OUVRES_MAX
                   else f"{len(a_lire)} à lire"),
        "seuil_jours_ouvres": FILE_JOURS_OUVRES_MAX,
    }


# ── Assemblage ─────────────────────────────────────────────────────────────

def construire(data: dict, precedent: dict | None, maintenant: datetime,
               racine: Path = RACINE, comptes: dict | None = None) -> dict:
    """L'état complet. `precedent` : le fichier publié au passage d'avant."""
    precedent = precedent if isinstance(precedent, dict) and precedent.get("schema") == SCHEMA else {}
    pub = publication(data)
    journal = enregistrer(precedent.get("journal") or {}, pub)
    # Fenêtre bornée : on garde les JOURNAL_MAX séances les plus récentes, et
    # le début du journal avance avec elles.
    cles = sorted(journal)[-JOURNAL_MAX:]
    journal = {k: journal[k] for k in cles}
    depuis = precedent.get("journal_depuis") or (cles[0] if cles else pub.get("seance"))
    if cles and len(journal) == JOURNAL_MAX and depuis < cles[0]:
        depuis = cles[0]
    echue = derniere_seance_echue(maintenant)
    vs = verdicts(journal, depuis, maintenant) if depuis else []
    cpt = compteur(vs)
    tt = taches(racine, pub, vs, echue)
    ok, motif = cloture_conforme(pub)
    publiees = sorted(journal)
    derniere = publiees[-1] if publiees else None
    retards = [t["nom"] for t in tt if t.get("en_retard")]
    fc = comptes if comptes is not None else file_comptes(echue)
    if fc.get("en_retard"):
        retards.append("File des comptes")
    return {
        "schema": SCHEMA,
        "_quoi": "État du service publié (lots 3.1 et 3.5). Produit par pipeline/etat_service.py "
                 "dans le commit de data.json ; ne pas éditer.",
        "genere_a": heure_maroc(maintenant).isoformat(timespec="seconds"),
        "derniere_publication": {
            "ecrit_a": pub["ecrit_a"], "seance": pub["seance"],
            "titres_seance": pub["titres_seance"], "titres": pub["titres"],
            "cloture": ok, "motif": motif},
        "derniere_cloture": ({"seance": derniere, **journal[derniere]} if derniere else None),
        # Après cet instant sans nouveau fichier, la séance suivante n'est pas
        # publiée à temps : le terminal le dit même si le moteur s'est arrêté.
        "prochaine_echeance": (echeance(jour_ouvre_suivant(derniere)).isoformat()
                               if derniere else None),
        "seance_attendue_ensuite": jour_ouvre_suivant(derniere).isoformat() if derniere else None,
        "statut": "à jour" if not retards else "en retard",
        "en_retard": retards,
        "taches": tt,
        "file_comptes": fc,
        "compteur": {
            "nom": "jours ouvrés consécutifs avec une clôture publiée à temps",
            "definition": DEFINITION_COMPTEUR,
            **cpt,
            "objectif": 30,
            "controle_du_soir": "non mesuré : le verdict de verifier_seance n'est lisible que "
                                "par l'API GitHub",
        },
        "seances": vs[-30:],
        "journal_depuis": depuis,
        "journal": journal,
    }


# ── Amorçage depuis git (local seulement) ──────────────────────────────────

def reconstruire_git(depuis: str, racine: Path = RACINE) -> dict:
    """Rejoue l'historique des data.json commités depuis `depuis`.

    ⚠️ Local seulement : dans GitHub Actions le clone est de profondeur 1.
    """
    shas = subprocess.run(
        ["git", "-C", str(racine), "log", "--reverse", f"--since={depuis}",
         "--format=%H", "origin/main", "--", "data.json"],
        capture_output=True, text=True, check=True).stdout.split()
    journal = {}
    for sha in shas:
        brut = subprocess.run(["git", "-C", str(racine), "show", f"{sha}:data.json"],
                              capture_output=True, check=True).stdout
        try:
            journal = enregistrer(journal, publication(json.loads(brut)))
        except ValueError as ex:
            print(f"etat_service : data.json illisible au commit {sha[:9]} ({ex})", file=sys.stderr)
    return journal


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    maintenant = datetime.now(timezone.utc)
    try:
        data = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as ex:
        print(f"etat_service : data.json illisible ({ex}) — état non produit", file=sys.stderr)
        return 1
    precedent = _lire_json(SORTIE) or {}
    if "--reconstruire-git" in args:
        depuis = args[args.index("--reconstruire-git") + 1]
        precedent = {"schema": SCHEMA, "journal_depuis": depuis,
                     "journal": reconstruire_git(depuis)}
    etat = construire(data, precedent, maintenant)
    texte = json.dumps(etat, ensure_ascii=False, indent=1) + "\n"
    if "--stdout" in args:
        print(texte, end="")
    else:
        SORTIE.write_text(texte, encoding="utf-8")
        c = etat["compteur"]
        print(f"etat_service : {etat['statut']} · compteur {c['valeur']}"
              f"{' (au moins)' if c['au_moins'] else ''} · dernière clôture "
              f"{(etat['derniere_cloture'] or {}).get('seance')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

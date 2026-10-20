#!/usr/bin/env python3
"""Deux contrôles sur le site public de la Bourse de Casablanca — 20/10/2026.

Les relevés viennent de `tools/bourse_casablanca.js` (Chromium, TLS strict) ;
ce module ne fait AUCUNE requête réseau. Il lit deux JSON et le dépôt.

  a. VOLUME — le « volume global » de la dernière séance échue, comparé à la
     somme v × c de nos bougies à cette date.
  b. PUBLICATIONS — les PDF d'émetteurs que la Bourse met en ligne, appariés à
     nos titres et comparés à ce que nous avons déjà intégré.

    python pipeline/controle_bourse.py --accueil A.json --publications P.json --sortie DOSSIER

⚠️ CE CONTRÔLE NE BLOQUE JAMAIS — POUR L'INSTANT (R12)
──────────────────────────────────────────────────────
Nos bougies retrouvent le montant du MARCHÉ CENTRAL à −0,7 % / +0,9 % sur 21
séances (`tests/test_volumes_marche.py`). Mais le « volume global » de la page
d'accueil est une autre grandeur, dont le périmètre n'était pas connu le 20/10 :
marché central seul, ou aussi transferts, apports, augmentations de capital ?
Fixer un seuil sans l'avoir mesuré serait affirmer un chiffre qu'on n'a pas.
Le statut reste donc `observation`, sans code d'échec, tant que
`TOLERANCE_PCT` vaut None. Il ne se renseigne qu'à la main, après au moins
`MIN_SEANCES_TOLERANCE` séances mesurées, relues dans
`datasets/volumes_marche.json › mesures_volume_global`.

Chaque mesure est écrite dans le résumé du workflow et dans l'artefact
(`volumes_marche.json` complété) : le workflow ne commite rien, et c'est
voulu — le quota de publication de Pages est la ressource rare du projet.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

REFERENCE = RACINE / "datasets" / "volumes_marche.json"
CLE_MESURES = "mesures_volume_global"
CANDLES = RACINE / "pipeline" / "candles"

# ⚠️ None = mode observation. Ne pas renseigner sans mesure (voir en tête).
TOLERANCE_PCT: float | None = None
MIN_SEANCES_TOLERANCE = 10

# Au dirham près : l'accueil arrondit le volume à l'unité.
ECART_EGALITE_MAD = 1.0


# ── a. VOLUME ────────────────────────────────────────────────────────────

def montant_bougies(seance: str, dossier: Path | None = None) -> tuple[float, int]:
    """(Σ v × c, nombre de titres échangés) de nos bougies à cette séance."""
    total, n = 0.0, 0
    for chemin in glob.glob(str((dossier or CANDLES) / "*.json")):
        try:
            with open(chemin, encoding="utf-8") as f:
                serie = json.load(f)
        except (OSError, ValueError):
            continue
        serie = serie.get("candles", serie) if isinstance(serie, dict) else serie
        if not isinstance(serie, list):
            continue
        for b in serie:
            if b.get("d") == seance and b.get("v") and b.get("c"):
                total += b["v"] * b["c"]
                n += 1
    return total, n


def ecart_pct(officiel: float | None, nous: float | None) -> float | None:
    """Écart relatif de notre montant au chiffre officiel, en %."""
    if not officiel or nous is None:
        return None
    return round(100.0 * (nous / officiel - 1.0), 3)


def seance_echue(seance: str | None, maintenant: datetime) -> bool:
    """La séance est-elle close ? Même horloge que `verifier_seance.py`."""
    from pipeline.verifier_seance import derniere_cloture_ecoulee
    if not seance:
        return False
    try:
        jour = date.fromisoformat(seance)
    except ValueError:
        return False
    return jour <= derniere_cloture_ecoulee(maintenant).date()


def perimetre(volume_global: float | None, central: float | None,
              autres: dict[str, float]) -> str:
    """Ce que le volume global contient, d'après les chiffres de la séance.

    ⚠️ Un jour sans autre marché que le central ne tranche RIEN : les deux
    hypothèses donnent le même total. On le dit au lieu de conclure.
    """
    if volume_global is None or central is None:
        return "inconnu"
    total = central + sum(autres.values())
    egal_central = abs(volume_global - central) <= ECART_EGALITE_MAD
    egal_total = abs(volume_global - total) <= ECART_EGALITE_MAD
    if egal_central and egal_total:
        return "non discriminant (aucun autre marché ce jour-là)"
    if egal_central:
        return "marché central seul"
    if egal_total:
        return "marché central + " + ", ".join(sorted(autres))
    return "aucun des deux"


def mesurer_volume(accueil: dict, maintenant: datetime, dossier: Path | None = None) -> dict:
    """La mesure du jour. N'émet jamais de verdict bloquant en observation."""
    pv = accueil.get("page_volume") or {}
    seance = pv.get("seance") or accueil.get("date_affichee")
    etat = accueil.get("etat_seance") or ""
    vg = accueil.get("volume_global_mad")
    m = {"seance": seance, "etat_seance": etat or None,
         "volume_global_accueil": vg,
         "volume_global_page_volume": pv.get("volume_global_mad"),
         "sous_marches": pv.get("sous_marches"),
         "releve_le": accueil.get("releve_le"),
         "notre_montant": None, "nos_titres": None,
         "ecart_pct": None, "statut": None, "bloquant": False}
    if not seance_echue(seance, maintenant) or re.search(r"(?i)ouverte", etat):
        m["statut"] = "seance_non_echue"
        return m
    if not vg:
        m["statut"] = "volume_absent"
        return m
    nous, n = montant_bougies(seance, dossier)
    m["notre_montant"], m["nos_titres"] = round(nous, 2), n
    if not n:
        m["statut"] = "bougies_absentes"
        return m
    m["ecart_pct"] = ecart_pct(vg, nous)

    # Périmètre : l'historique officiel de la même séance, s'il est servi.
    hist = [r for r in (accueil.get("historique_volumes") or []) if r.get("seance") == seance]
    central = next((r["volume_mad"] for r in hist if r.get("marche") == "Marché central"), None)
    autres = {r["marche"]: r["volume_mad"] for r in hist
              if r.get("marche") != "Marché central" and r.get("volume_mad") is not None}
    m["historique_marche_central"] = central
    m["historique_autres_marches"] = autres or {}
    m["ecart_pct_vs_marche_central"] = ecart_pct(central, nous)
    m["perimetre_volume_global"] = perimetre(vg, central, autres)

    # Seconde lecture du périmètre, sur la page des volumes du même relevé :
    # « Carnet Central », « Hors Carnet »… Mesuré le 20/10/2026 à 15h37 :
    # 98 262 533,69 + 2 350 156,99 = 100 612 690,68 = le volume global. Le
    # volume global y INCLUT donc le hors carnet (blocs) ce jour-là.
    sous = {x["marche"]: x["volume_mad"] for x in (pv.get("sous_marches") or [])
            if x.get("marche") and x.get("volume_mad") is not None}
    carnet = sous.get("Carnet Central")
    m["carnet_central"] = carnet
    m["ecart_pct_vs_carnet_central"] = ecart_pct(carnet, nous)
    vpv = pv.get("volume_global_mad")
    m["volume_global_somme_des_sous_marches"] = (
        abs(vpv - sum(sous.values())) <= ECART_EGALITE_MAD if sous and vpv is not None else None)
    m["statut"] = "observation" if TOLERANCE_PCT is None else (
        "conforme" if abs(m["ecart_pct"]) <= TOLERANCE_PCT else "hors_tolerance")
    m["bloquant"] = m["statut"] == "hors_tolerance"
    return m


def code_sortie(mesure: dict) -> int:
    """0 en observation, quoi que vaille l'écart. 1 seulement hors tolérance établie."""
    return 1 if TOLERANCE_PCT is not None and mesure.get("bloquant") else 0


MESURE_CHAMPS = ("seance", "volume_global_accueil", "notre_montant", "ecart_pct",
                 "sous_marches", "carnet_central", "ecart_pct_vs_carnet_central",
                 "volume_global_somme_des_sous_marches",
                 "historique_marche_central", "historique_autres_marches",
                 "ecart_pct_vs_marche_central", "perimetre_volume_global", "releve_le")


def ajouter_mesure(reference: dict, mesure: dict) -> dict:
    """La référence complétée de la mesure (une par séance, la plus récente). Pure."""
    ref = dict(reference)
    mesures = list(ref.get(CLE_MESURES) or [])
    # Un passage sans mesure (site muet, bougies absentes) n'efface pas la mesure d'avant.
    if mesure.get("statut") in ("observation", "conforme", "hors_tolerance"):
        mesures = [x for x in mesures if x.get("seance") != mesure.get("seance")]
        mesures.append({k: mesure.get(k) for k in MESURE_CHAMPS})
    ref[CLE_MESURES] = sorted(mesures, key=lambda x: x["seance"])
    return ref


def rapport_volume(m: dict, n_mesures: int) -> str:
    f = lambda x: "—" if x is None else f"{x:,.0f}".replace(",", " ")
    l = [f"## Volume — Bourse de Casablanca, séance du {m['seance']} : `{m['statut']}`", ""]
    if m["statut"] in ("observation", "conforme", "hors_tolerance"):
        l += ["| grandeur | MAD |", "|---|---|",
              f"| volume global (accueil) | {f(m['volume_global_accueil'])} |",
              f"| marché central (historique officiel) | {f(m.get('historique_marche_central'))} |"]
        for k, v in (m.get("historique_autres_marches") or {}).items():
            l.append(f"| {k} (historique officiel) | {f(v)} |")
        for x in m.get("sous_marches") or []:
            l.append(f"| {x.get('marche')} (page des volumes) | {f(x.get('volume_mad'))} |")
        l += [f"| nos bougies, Σ v × c ({m['nos_titres']} titres) | {f(m['notre_montant'])} |", "",
              f"Écart au volume global : **{m['ecart_pct']:+.2f} %**"
              + (f" ; au marché central : {m['ecart_pct_vs_marche_central']:+.2f} %"
                 if m.get("ecart_pct_vs_marche_central") is not None else ""),
              (f"Écart au carnet central (page des volumes) : {m['ecart_pct_vs_carnet_central']:+.2f} %."
               if m.get("ecart_pct_vs_carnet_central") is not None else ""),
              f"Périmètre du volume global ce jour : {m.get('perimetre_volume_global')} ; "
              f"somme des sous-marchés affichés : {m.get('volume_global_somme_des_sous_marches')}."]
    l += ["", f"Mode observation : aucun seuil n'est fixé ({n_mesures} séance(s) mesurée(s), "
              f"{MIN_SEANCES_TOLERANCE} requises avant d'en proposer un). Ce contrôle ne fait pas échouer le workflow."]
    return "\n".join(l) + "\n"


# ── b. PUBLICATIONS ──────────────────────────────────────────────────────

_SEMESTRIEL = re.compile(r"(?i)1er semestre|premier semestre|semestriel|\bS1\b|half[- ]year|interim|30 juin|_s1_")
_ANNUEL = re.compile(r"(?i)annuel|annual|\bRFA\b|exercice 20\d\d|r[ée]sultats (?:financiers )?20\d\d"
                     r"|(?:financial statements|consolidated (?:results|accounts|financial statements)) 20\d\d"
                     r"|20\d\d (?:consolidated )?(?:results|accounts)|comptes (?:annuels|consolid)")
_COMMUNIQUE = re.compile(r"(?i)^cp\b|\bCP\b|communiqu|press release")


def type_presume(titre: str | None, type_site: str | None = None, url: str | None = None) -> str:
    """semestriel / annuel / communiqué / autre — d'après le titre, à défaut le badge du site."""
    t = f"{titre or ''} {Path(url or '').name}"
    if _SEMESTRIEL.search(t):
        return "semestriel"
    if _ANNUEL.search(t):
        return "annuel"
    if _COMMUNIQUE.search(t) or (type_site or "").lower().startswith("communiqu"):
        return "communiqué"
    return "autre"


def apparier(emetteur: str | None) -> tuple[str | None, str, list[str]]:
    """(ticker, méthode, candidats). Plusieurs candidats → ambigu, jamais tranché.

    Les voies sont celles de `depots_ammc.resoudre_emetteur` (code posé par
    l'émetteur entre parenthèses, nom normalisé en correspondance ENTIÈRE,
    code officiel BVC, alias relevés), plus une précaution de
    `tools/comparer_emetteurs.py` : un CODE n'est pas un nom. « SNA » est
    Sonasid chez nous mais Stokvis à la Bourse (`IDB_TICKER_MAP`) ; un code
    qui désigne deux titres selon la convention reste non attribué.
    """
    if not emetteur:
        return None, "sans_emetteur", []
    from bvc_config import COMPANY_NAMES, IDB_TICKER_MAP
    from pipeline.depots_ammc import resoudre_emetteur
    nom = emetteur.strip()
    cands: dict[str, str] = {}
    t = resoudre_emetteur(nom)
    if t:
        cands.setdefault(t, "resolution_ammc")
    officiels = {v: k for k, v in IDB_TICKER_MAP.items() if v}
    if nom in officiels:
        cands.setdefault(officiels[nom], "code_officiel")
    if nom in COMPANY_NAMES:
        cands.setdefault(nom, "notre_code")
    if len(cands) == 1:
        (t, methode), = cands.items()
        return t, methode, [t]
    if len(cands) > 1:
        return None, "ambigu", sorted(cands)
    return None, "non_apparie", []


def _urls(obj, acc: set) -> set:
    if isinstance(obj, dict):
        for v in obj.values():
            _urls(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _urls(v, acc)
    elif isinstance(obj, str) and obj.startswith("http"):
        acc.add(obj.split("?")[0])
    return acc


def charger_connu(racine: Path = RACINE) -> dict:
    """Ce que nous avons déjà : jeu S1, relevés de pièces, faits financiers, dépôts AMMC."""
    def lire(p):
        try:
            return json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    jeu = lire(racine / "datasets" / "resultats_s1_2026.json")
    faits = lire(racine / "pipeline" / "faits_financiers.json")
    urls: set = set()
    _urls(jeu, urls)
    _urls(faits, urls)
    for p in glob.glob(str(racine / "datasets" / "releves" / "*.json")):
        _urls(lire(p), urls)
    try:
        from pipeline.depots_ammc import charger, depots_par_ticker
        ammc = depots_par_ticker(charger())
    except Exception:
        ammc = {}
    return {
        "urls": urls,
        "fichiers": {u.rsplit("/", 1)[-1].lower() for u in urls},
        "s1_integres": set(jeu.get("titres") or {}),
        "s1_ecartes": set(jeu.get("_ecartes") or {}),
        "annuels_2025": {t for t, v in faits.items() if isinstance(v, dict) and v.get("exercice") == 2025},
        "ammc": ammc,
        "depuis": jeu.get("fin_periode") or "2026-06-30",
    }


def classer_publications(pubs: list[dict], connu: dict) -> dict:
    """Répartit les publications. Fonction pure.

    Rend {"nouvelles", "integrees", "ecartees", "non_appariees", "ambigues",
    "archives"} ; une publication appartient à une seule liste.
    """
    out = {k: [] for k in ("nouvelles", "integrees", "ecartees", "non_appariees", "ambigues", "archives")}
    for p in pubs:
        quand = p.get("date") or p.get("fichier_modifie_le")
        t, methode, cands = apparier(p.get("emetteur"))
        e = {"ticker": t, "methode": methode, "date": quand,
             "date_origine": "affichee" if p.get("date") else ("last_modified" if quand else None),
             "emetteur": p.get("emetteur"), "titre": p.get("titre"), "url": p.get("url"),
             "type_presume": type_presume(p.get("titre"), p.get("type_site"), p.get("url"))}
        if quand and quand <= connu["depuis"]:
            out["archives"].append(e)
            continue
        if methode == "ambigu":
            e["candidats"] = cands
            out["ambigues"].append(e)
            continue
        if not t:
            out["non_appariees"].append(e)
            continue
        url = (p.get("url") or "").split("?")[0]
        dep = connu["ammc"].get(t)
        # `depots_par_ticker` ne garde que les dépôts de RÉSULTATS : un communiqué
        # n'a pas d'équivalent à y chercher.
        e["deja_vu_ammc"] = (dep.get("url") if dep and e["type_presume"] in ("semestriel", "annuel")
                             and dep.get("date", "") > connu["depuis"] else None)
        if url in connu["urls"] or url.rsplit("/", 1)[-1].lower() in connu["fichiers"]:
            e["motif"] = "PDF déjà cité dans nos jeux"
            out["integrees"].append(e)
        elif e["type_presume"] == "semestriel" and t in connu["s1_ecartes"]:
            e["motif"] = "écarté dans resultats_s1_2026.json"
            out["ecartees"].append(e)
        elif e["type_presume"] == "semestriel" and t in connu["s1_integres"]:
            e["motif"] = "S1 intégré dans resultats_s1_2026.json"
            out["integrees"].append(e)
        elif e["type_presume"] == "annuel" and t in connu["annuels_2025"]:
            e["motif"] = "exercice 2025 dans faits_financiers.json"
            out["integrees"].append(e)
        else:
            out["nouvelles"].append(e)
    for v in out.values():
        v.sort(key=lambda x: (x.get("date") or "9999", x.get("ticker") or ""), reverse=True)
    return out


def candidats_comptes(classes: dict) -> list[dict]:
    """Les comptes semestriels nouveaux, au format de la file d'attente."""
    return [{"ticker": e["ticker"], "date": e["date"], "titre": e["titre"], "url": e["url"],
             "source": "Bourse de Casablanca"}
            for e in classes["nouvelles"] if e["type_presume"] == "semestriel"]


def rapport_publications(c: dict, n_lues: int) -> str:
    n_app = sum(len(c[k]) for k in ("nouvelles", "integrees", "ecartees"))
    l = [f"## Publications d'émetteurs — Bourse de Casablanca", "",
         f"{n_lues} lues ; {len(c['archives'])} antérieures à la période ; "
         f"{n_app} appariées dont **{len(c['nouvelles'])} nouvelles** ; "
         f"{len(c['non_appariees'])} non appariées ; {len(c['ambigues'])} ambiguës.", ""]
    if c["nouvelles"]:
        l += ["| titre | date | type présumé | publication |", "|---|---|---|---|"]
        for e in c["nouvelles"]:
            vu = " (aussi à l'AMMC)" if e.get("deja_vu_ammc") else ""
            l.append(f"| {e['ticker']} | {e['date'] or '—'} | {e['type_presume']} | [{e['titre']}]({e['url']}){vu} |")
    for cle, titre in (("non_appariees", "Non appariées (jamais attribuées)"), ("ambigues", "Ambiguës (non tranchées)")):
        if c[cle]:
            l += ["", f"{titre} :"]
            l += [f"- {e['date'] or '—'} — [{e['titre']}]({e['url']})"
                  + (f" — candidats {', '.join(e['candidats'])}" if e.get("candidats") else "") for e in c[cle]]
    return "\n".join(l) + "\n"


# ── Entrée ───────────────────────────────────────────────────────────────

def _lire_json(chemin):
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--accueil", help="sortie de `bourse_casablanca.js accueil`")
    ap.add_argument("--publications", help="sortie de `bourse_casablanca.js publications`")
    ap.add_argument("--sortie", help="dossier de l'artefact")
    a = ap.parse_args(argv)
    sortie = Path(a.sortie) if a.sortie else None
    if sortie:
        sortie.mkdir(parents=True, exist_ok=True)
    textes, code = [], 0
    maintenant = datetime.now(timezone.utc)

    acc = _lire_json(a.accueil) if a.accueil else None
    if a.accueil and acc is None:
        textes.append("## Volume — Bourse de Casablanca : relevé indisponible\n")
    elif acc is not None:
        m = mesurer_volume(acc, maintenant)
        ref = ajouter_mesure(_lire_json(REFERENCE) or {}, m)
        n = len(ref.get(CLE_MESURES) or [])
        textes.append(rapport_volume(m, n))
        code = max(code, code_sortie(m))
        if sortie:
            (sortie / "mesure_volume.json").write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            (sortie / "volumes_marche.json").write_text(json.dumps(ref, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    pub = _lire_json(a.publications) if a.publications else None
    if a.publications and pub is None:
        textes.append("## Publications d'émetteurs — Bourse de Casablanca : relevé indisponible\n")
    elif pub is not None:
        pubs = pub.get("publications") or []
        c = classer_publications(pubs, charger_connu())
        textes.append(rapport_publications(c, len(pubs)))
        if sortie:
            (sortie / "publications_classees.json").write_text(json.dumps(c, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            (sortie / "candidats_comptes_bourse.json").write_text(
                json.dumps(candidats_comptes(c), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    texte = "\n".join(textes)
    print(texte)
    resume = os.environ.get("GITHUB_STEP_SUMMARY")
    if resume:
        with open(resume, "a", encoding="utf-8") as h:
            h.write(texte)
    return code


if __name__ == "__main__":
    sys.exit(main())

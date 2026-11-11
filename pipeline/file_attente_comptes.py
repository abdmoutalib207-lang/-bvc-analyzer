#!/usr/bin/env python3
"""File d'attente des comptes à lire — 30/09/2026.

⚠️ POURQUOI CE MODULE
La DÉTECTION des dépôts existe (`depots_ammc.py`, rafraîchie par
`update_bvc`) ; ce qui manquait est l'ÉCART entre ce qui est déposé et ce qui
est intégré dans `datasets/resultats_s1_2026.json`. Au 30/09, sept sociétés
avaient déposé des comptes semestriels que personne n'avait encore lus, sans
que rien ne le signale.

Ce module ne lit aucun PDF et n'écrit aucun chiffre : il dresse la liste, et
la lecture reste un acte relu (agent `lecteur-comptes`, puis PR). Il ne fait
jamais échouer un workflow — une file non vide n'est pas une panne.

    python pipeline/file_attente_comptes.py
    python pipeline/file_attente_comptes.py --bourse candidats_comptes_bourse.json
    python pipeline/file_attente_comptes.py --json    # même contenu, pour une tâche planifiée

ÉLARGISSEMENT — 11/11/2026. La file ne connaissait que le S1 2026, alors que
l'AMMC publie aussi des indicateurs trimestriels (9 du T3 depuis le 15/10) et
publiera les comptes annuels 2026 en mars-avril 2027. Chaque dépôt est classé
par NATURE et PÉRIODE (`classer`, fonction pure : la période se LIT dans le
titre, elle ne se devine pas ; inconnue => « autre »). Ce qui est déjà intégré :
  - S1 2026 : `datasets/resultats_s1_2026.json` (ou la période H1-2026 de
    `datasets/etats_financiers/<TICKER>.json`) ;
  - autres semestres et exercices : périodes `H1-AAAA` / `FYAAAA` de
    `datasets/etats_financiers/<TICKER>.json`, COMPLÈTES au minimum (chiffre
    d'affaires ou PNB, et résultat net part du groupe, non nuls) ;
  - indicateurs trimestriels : RIEN n'est intégré. Ils sont listés à part,
    « publiés, non suivis par le produit », et ne comptent pas comme un retard.
Un classement ne dit pas qu'un chiffre est juste : il dit ce qui reste à lire.

SECONDE SOURCE — 20/10/2026. La Bourse de Casablanca met aussi en ligne des
comptes d'émetteurs (`pipeline/controle_bourse.py` en tire les semestriels
non intégrés). Ils s'AJOUTENT à la file, dans une liste à part, sans jamais
remplacer l'AMMC (R3) : un titre déjà présent côté AMMC n'est pas redoublé.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

JEU = RACINE / "datasets" / "resultats_s1_2026.json"
# Un dépôt SEMESTRIEL : « 1er semestre », « S1 », « RFS » (rapport financier
# semestriel), « 30 juin ». Un avertissement sur résultats annonce des
# comptes, il n'en contient pas : il est listé à part.
_SEMESTRE = re.compile(r"(?i)1er semestre|premier semestre|\bS1\b|\bRFS\b|30 juin|juin 2026")


def file_attente(depots: dict, jeu: dict, depuis: str) -> dict:
    """Répartit les dépôts semestriels postérieurs à `depuis`. Fonction pure.

    Renvoie {"a_lire": [...], "avertissements": [...], "ecartes": [...]},
    chaque entrée {ticker, date, titre, url} ; triée par date.
    """
    integres = set(jeu.get("titres") or {})
    ecartes = set(jeu.get("_ecartes") or {})
    out = {"a_lire": [], "avertissements": [], "ecartes": []}
    for t, d in depots.items():
        if d["date"] <= depuis or not _SEMESTRE.search(d.get("titre") or ""):
            continue
        if t in integres:
            continue
        e = {"ticker": t, "date": d["date"], "titre": d["titre"], "url": d.get("url")}
        if t in ecartes:
            out["ecartes"].append(e)
        elif d.get("avertissement"):
            out["avertissements"].append(e)
        else:
            out["a_lire"].append(e)
    for v in out.values():
        v.sort(key=lambda e: (e["date"], e["ticker"]))
    return out


def ajouter_bourse(f: dict, candidats: list[dict], jeu: dict) -> dict:
    """Ajoute les candidats de la Bourse sous `bourse`, sans toucher aux listes AMMC. Pure.

    Écartés : un titre déjà intégré ou écarté dans le jeu, ou déjà présent dans
    une liste AMMC (celle-ci reste la source première).
    """
    out = {k: list(v) for k, v in f.items()}
    deja = {e["ticker"] for v in f.values() for e in v}
    deja |= set(jeu.get("titres") or {}) | set(jeu.get("_ecartes") or {})
    vus = set()
    out["bourse"] = []
    for c in candidats or []:
        t = c.get("ticker")
        if not t or t in deja or t in vus:
            continue
        vus.add(t)
        out["bourse"].append({"ticker": t, "date": c.get("date"), "titre": c.get("titre"),
                              "url": c.get("url"), "source": "Bourse de Casablanca"})
    out["bourse"].sort(key=lambda e: (e["date"] or "", e["ticker"]))
    return out


def rapport(f: dict) -> str:
    lignes = [f"## Comptes déposés à l'AMMC, pas encore intégrés : {len(f['a_lire'])}", ""]
    for e in f["a_lire"]:
        lignes.append(f"- **{e['ticker']}** — {e['date']} — [{e['titre']}]({e['url']})")
    if f["avertissements"]:
        lignes += ["", "Avertissements sur résultats (pas de comptes) :"]
        lignes += [f"- {e['ticker']} — {e['date']} — {e['titre']}" for e in f["avertissements"]]
    if f["ecartes"]:
        lignes += ["", "Écartés, motif consigné dans le jeu :"]
        lignes += [f"- {e['ticker']} — {e['date']}" for e in f["ecartes"]]
    if "bourse" in f:
        lignes += ["", f"## Seconde source — Bourse de Casablanca, absents côté AMMC : {len(f['bourse'])}", ""]
        lignes += [f"- **{e['ticker']}** — {e['date'] or 'date inconnue'} — [{e['titre']}]({e['url']})"
                   for e in f["bourse"]]
    return "\n".join(lignes) + "\n"


# ── Classement par nature et période (11/11/2026) ───────────────────────

TRIMESTRIELS = "indicateurs_trimestriels"
SEMESTRIELS = "semestriels"
ANNUELS = "annuels"
AVERTISSEMENT = "avertissement"
AUTRE = "autre"
NATURES = (TRIMESTRIELS, SEMESTRIELS, ANNUELS, AVERTISSEMENT, AUTRE)

_ERRATUM = re.compile(r"(?i)\berratum\b")
_AVERT = re.compile(r"(?i)profit warning|avertissement")
_ORDINAL = {"1": 1, "premier": 1, "2": 2, "deuxième": 2, "deuxieme": 2, "second": 2,
            "3": 3, "troisième": 3, "troisieme": 3, "4": 4, "quatrième": 4, "quatrieme": 4}
# « 3ème trimestre 2026 », « 1er trimestre 2027 », « troisième trimestre 2026 »
_TRIMESTRE = re.compile(
    r"(?i)\b(1|2|3|4|premier|deuxi[èe]me|second|troisi[èe]me|quatri[èe]me)\s*(?:er|re|e|[èe]me|nd)?\s+trimestre\s+(20\d\d)")
_TRIM_T = re.compile(r"(?i)\bT([1-4])[\s-]*(20\d\d)\b")
_CONTENU_TRIM = re.compile(r"(?i)indicateurs|chiffre d.affaires|r[ée]sultats|comptes|information financi")
_SEMESTRE_PERIODE = re.compile(
    r"(?i)(?:\b(?:1er|premier)\s+semestre\s+(20\d\d)|\bS1[\s-]*(20\d\d)\b"
    r"|\bRFS\s+(?:de\s+)?juin\s+(20\d\d)|\b30\s+juin\s+(20\d\d))")
_ANNUEL = re.compile(
    r"(?i)comptes annuels|r[ée]sultats annuels|rapport financier annuel|\bRFA\b|[ée]tats de synth[èe]se"
    r"|[ée]tats financiers annuels|r[ée]sultats (?:financiers )?(?:de |du )?(?:l['’]\s*)?exercice"
    r"|comptes de l['’]\s*exercice|publication financi[èe]re annuelle")
_ANNEE = re.compile(r"\b(20\d\d)\b")
# Un titre « autre » qui parle pourtant de résultats : à montrer, pas à classer.
_EVOQUE = re.compile(r"(?i)r[ée]sultats|comptes|semestr|trimestr|annuel|exercice|indicateurs|rapport financier|\bRFS\b|\bRFA\b")
_BRUIT = re.compile(r"(?i)augmentation de capital|dossier d.information|rendement|convocation|prospectus|programme d.[ée]mission")


def _annee_unique(titre: str) -> str | None:
    annees = set(_ANNEE.findall(titre))
    return annees.pop() if len(annees) == 1 else None


def _periode_trimestre(titre: str) -> str | None:
    m = _TRIMESTRE.search(titre)
    if m:
        return f"T{_ORDINAL[m.group(1).lower()]}-{m.group(2)}"
    m = _TRIM_T.search(titre)
    return f"T{m.group(1)}-{m.group(2)}" if m else None


def _periode_semestre(titre: str) -> str | None:
    m = _SEMESTRE_PERIODE.search(titre)
    return f"S1-{next(g for g in m.groups() if g)}" if m else None


def classer(titre: str | None) -> tuple[str, str | None]:
    """(nature, période) d'un titre de dépôt. Fonction pure.

    La période s'écrit `S1-2026`, `T3-2026`, `FY2025`. Elle n'est jamais
    devinée : une année absente ou ambiguë (deux années différentes dans le
    titre) donne `(AUTRE, None)`. Un erratum n'est pas un compte : « autre ».
    Un avertissement sur résultats est reconnu à ses mots, période lue si elle
    figure au titre.
    """
    t = " ".join((titre or "").split())
    if not t or _ERRATUM.search(t):
        return AUTRE, None
    trim, sem = _periode_trimestre(t), _periode_semestre(t)
    if _AVERT.search(t):
        an = _annee_unique(t) if _ANNUEL.search(t) else None
        return AVERTISSEMENT, trim or sem or (f"FY{an}" if an else None)
    if trim:
        # « trimestre » seul ne suffit pas : il faut un contenu financier au titre.
        if _CONTENU_TRIM.search(t) or _TRIM_T.search(t):
            return TRIMESTRIELS, trim
        return AUTRE, None
    if sem:
        return SEMESTRIELS, sem
    if _ANNUEL.search(t):
        an = _annee_unique(t)
        return (ANNUELS, f"FY{an}") if an else (AUTRE, None)
    return AUTRE, None


def classer_depots(entrees: list[dict], resoudre=None) -> list[dict]:
    """Chaque dépôt avec son ticker (None si l'émetteur n'est pas coté), sa nature et sa période."""
    if resoudre is None:
        from pipeline.depots_ammc import emetteur, resoudre_emetteur

        def resoudre(titre):
            return resoudre_emetteur(emetteur(titre))
    out = []
    for e in entrees or []:
        titre = e.get("titre") or ""
        nature, periode = classer(titre)
        out.append({"ticker": resoudre(titre), "date": e.get("date"), "titre": titre,
                    "url": e.get("url"), "nature": nature, "periode": periode})
    return out


def comptes_par_nature(classes: list[dict]) -> dict:
    """{nature: nombre} sur tous les dépôts, émetteurs non cotés compris. Pure."""
    c = {n: 0 for n in NATURES}
    for e in classes:
        c[e["nature"]] += 1
    return c


METRIQUES_REQUISES = ("chiffre_affaires", "resultat_net_part_groupe")


def charger_integres(dossier: Path | None = None) -> dict:
    """{ticker: {périodes}} des `datasets/etats_financiers/<TICKER>.json`.

    Une période compte comme intégrée si elle est COMPLÈTE au minimum : chiffre
    d'affaires (PNB pour une banque) ET résultat net part du groupe portent une
    `valeur_mdh` non nulle. Une période relevée à moitié reste à lire. Un fichier illisible est signalé sur stderr (R5) et
    laissé de côté : la file ne doit pas tomber pour un jeu abîmé.
    """
    dossier = dossier or (RACINE / "datasets" / "etats_financiers")
    out: dict[str, set] = {}
    for f in sorted(dossier.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            periodes = set()
            for k, p in (d.get("periodes") or {}).items():
                donnees = p.get("donnees") or {}
                if all(isinstance(donnees.get(m), dict) and donnees[m].get("valeur_mdh") is not None
                       for m in METRIQUES_REQUISES):
                    periodes.add(k)
            out[d.get("ticker") or f.stem] = periodes
        except (OSError, ValueError, AttributeError) as ex:
            print(f"file_attente_comptes : {f.name} illisible ({ex}), ignoré", file=sys.stderr)
    return out


def _cle_etats(periode: str) -> str | None:
    """Clé `etats_financiers` d'une période : S1-2025 -> H1-2025 ; FY2025 inchangé."""
    if periode.startswith("S1-"):
        return "H1-" + periode[3:]
    return periode if periode.startswith("FY") else None


def _un_par_cle(entrees: list[dict], cle) -> list[dict]:
    """Le dépôt le plus récent pour chaque clé. Pure."""
    best: dict = {}
    for e in entrees:
        k = cle(e)
        if k not in best or e["date"] >= best[k]["date"]:
            best[k] = e
    return sorted(best.values(), key=lambda e: (e["date"], e["ticker"]))


def _public(e: dict) -> dict:
    return {k: e[k] for k in ("ticker", "date", "nature", "periode", "titre", "url")}


def file_attente_etendue(entrees: list[dict], jeu: dict, integres: dict, resoudre=None) -> dict:
    """La file à toutes natures. Fonction pure.

    - `_s1` : sortie historique de `file_attente` (S1 de `jeu["fin_periode"]`),
      calculée sur le dépôt S1 le plus récent de chaque titre (les comptes
      l'emportent sur un avertissement) ;
    - `a_lire` : {"semestriels": [...], "annuels": [...]} — le S1 du jeu, plus
      les autres semestres et les exercices absents d'`etats_financiers` ;
    - `non_suivis` : indicateurs trimestriels, listés sans compter comme retard ;
    - `non_classes` : titres qui évoquent des résultats sans nature reconnue ;
    - `comptes` : dépôts par nature sur TOUTES les entrées.
    """
    classes = classer_depots(entrees, resoudre)
    cotes = [e for e in classes if e["ticker"]]
    fin = jeu.get("fin_periode") or ""
    p_jeu = f"S1-{fin[:4]}" if fin[5:7] == "06" else None

    jeu_eff = dict(jeu)
    jeu_eff["titres"] = dict(jeu.get("titres") or {})
    for t, ps in integres.items():
        if p_jeu and _cle_etats(p_jeu) in ps:
            jeu_eff["titres"].setdefault(t, {})
    s1_depots: dict[str, dict] = {}
    for e in cotes:
        if e["periode"] != p_jeu or e["nature"] not in (SEMESTRIELS, AVERTISSEMENT):
            continue
        d = {"date": e["date"], "titre": e["titre"], "url": e["url"],
             **({"avertissement": True} if e["nature"] == AVERTISSEMENT else {})}
        cur = s1_depots.get(e["ticker"])
        if cur:
            rang_d, rang_c = "avertissement" not in d, "avertissement" not in cur
            if (rang_d, d["date"]) <= (rang_c, cur["date"]):
                continue
        s1_depots[e["ticker"]] = d
    s1 = file_attente(s1_depots, jeu_eff, fin)

    reste = []
    for e in cotes:
        if e["nature"] not in (SEMESTRIELS, ANNUELS) or e["periode"] == p_jeu:
            continue
        cle = _cle_etats(e["periode"])
        if cle and cle in integres.get(e["ticker"], ()):
            continue
        reste.append(e)
    reste = _un_par_cle(reste, lambda e: (e["ticker"], e["periode"]))

    a_lire = {
        SEMESTRIELS: [{**e, "nature": SEMESTRIELS, "periode": p_jeu} for e in s1["a_lire"]]
                     + [_public(e) for e in reste if e["nature"] == SEMESTRIELS],
        ANNUELS: [_public(e) for e in reste if e["nature"] == ANNUELS],
    }
    trim = sorted((e for e in cotes if e["nature"] == TRIMESTRIELS), key=lambda e: (e["date"], e["ticker"]))
    non_classes = sorted(
        (e for e in cotes if e["nature"] == AUTRE and _EVOQUE.search(e["titre"]) and not _BRUIT.search(e["titre"])),
        key=lambda e: (e["date"], e["ticker"]))
    return {
        "schema": "file_attente_comptes/1",
        "depuis": fin,
        "a_lire": a_lire,
        "avertissements": [{**e, "nature": AVERTISSEMENT, "periode": p_jeu} for e in s1["avertissements"]],
        "ecartes": [{**e, "nature": SEMESTRIELS, "periode": p_jeu} for e in s1["ecartes"]],
        "non_suivis": {TRIMESTRIELS: [_public(e) for e in trim]},
        "non_classes": [_public(e) for e in non_classes],
        "comptes": {"depots": len(classes), "emetteurs_non_cotes": len(classes) - len(cotes),
                    "par_nature": comptes_par_nature(classes)},
        "_s1": s1,
    }


def rapport_etendu(f: dict, base: dict | None = None) -> str:
    """Texte : la sortie historique (S1, puis Bourse) INCHANGÉE, puis les ajouts.

    `base` : le dictionnaire de `rapport` (S1, avec `bourse` s'il y a lieu).
    """
    texte = rapport(base if base is not None else f["_s1"])
    lignes = []
    n_s1 = len(f["_s1"]["a_lire"])
    for titre, liste in (("Autres semestres déposés, pas encore intégrés", f["a_lire"][SEMESTRIELS][n_s1:]),
                         ("Comptes annuels déposés, pas encore intégrés", f["a_lire"][ANNUELS])):
        if liste:
            lignes += ["", f"## {titre} : {len(liste)}", ""]
            lignes += [f"- **{e['ticker']}** — {e['date']} — {e['periode']} — [{e['titre']}]({e['url']})"
                       for e in liste]
    tri = f["non_suivis"][TRIMESTRIELS]
    if tri:
        lignes += ["", f"## Publiés, non suivis par le produit (indicateurs trimestriels, pas un retard) : {len(tri)}", ""]
        lignes += [f"- {e['ticker']} — {e['date']} — {e['periode']} — {e['titre']}" for e in tri]
    if f["non_classes"]:
        lignes += ["", f"## Titres qui évoquent des résultats, nature non reconnue : {len(f['non_classes'])}", ""]
        lignes += [f"- {e['ticker']} — {e['date']} — {e['titre']}" for e in f["non_classes"]]
    return texte + ("\n".join(lignes) + "\n" if lignes else "")


def sortie_json(f: dict, base: dict | None = None) -> dict:
    """Structure stable pour une tâche planifiée : `_s1` retiré, `bourse` ajouté s'il existe."""
    out = {k: v for k, v in f.items() if k != "_s1"}
    if base is not None and "bourse" in base:
        out["bourse"] = base["bourse"]
    out["comptes"] = {**out["comptes"],
                      "a_lire": sum(len(v) for v in out["a_lire"].values()),
                      "avertissements": len(out["avertissements"]),
                      "ecartes": len(out["ecartes"]),
                      "non_suivis": sum(len(v) for v in out["non_suivis"].values())}
    return out


def _candidats_bourse(argv: list[str]) -> list[dict] | None:
    """Le fichier passé par `--bourse`, ou None. Absent ou illisible : on s'en passe."""
    if "--bourse" not in argv or argv.index("--bourse") + 1 >= len(argv):
        return None
    try:
        return json.loads(Path(argv[argv.index("--bourse") + 1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as ex:
        print(f"file_attente_comptes : fichier --bourse illisible ({ex}), seconde source ignorée",
              file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    """Toujours 0 : une file non vide, ou un jeu absent, n'est pas une panne de séance.

    L'étape du workflow est en `if: always()` sans `continue-on-error` : une
    exception ici ferait échouer verifier_seance. La cause va sur stderr (R5).
    """
    try:
        return _main(argv)
    except Exception as ex:  # noqa: BLE001 — promesse du module : ne jamais faire échouer le workflow
        print(f"file_attente_comptes : échec ({type(ex).__name__}: {ex}), file non produite",
              file=sys.stderr)
        return 0


def _main(argv: list[str] | None = None) -> int:
    from pipeline.depots_ammc import charger
    args = sys.argv[1:] if argv is None else argv
    jeu = json.loads(JEU.read_text(encoding="utf-8"))
    etendue = file_attente_etendue(charger(), jeu, charger_integres())
    base = etendue["_s1"]
    bourse = _candidats_bourse(args)
    if bourse is not None:
        base = ajouter_bourse(base, bourse, jeu)
    texte = rapport_etendu(etendue, base)
    if "--json" in args:
        print(json.dumps(sortie_json(etendue, base), ensure_ascii=False, indent=2))
    else:
        print(texte)
    resume = os.environ.get("GITHUB_STEP_SUMMARY")
    if resume:
        with open(resume, "a", encoding="utf-8") as h:
            h.write(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Appliquer une série acceptée, et recalculer un cache — sous contrôle.

⚠️ CES DEUX PROGRAMMES ÉCRIVENT DANS LES DONNÉES PUBLIÉES.
Ce sont les seuls du lot à le faire. Ce fichier éprouve ce qui les retient.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))


def test_la_serie_acceptee_est_une_instruction_pas_un_signalement():
    """⚠️ La revue a demandé que la différence soit explicite.

    `datasets/historiques_candidats/` PROPOSE ; `datasets/series_acceptees/`
    INSTRUIT. Le dossier fait la distinction, et le fichier la déclare.
    """
    f = RACINE / "datasets" / "series_acceptees" / "CMT.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    assert "REMPLACEMENT PROPOSÉ" in d["_statut"]
    assert "n'est pas un signalement" in d["_ce_qui_est_propose"].lower() \
        or "N'EST PAS un signalement" in d["_ce_qui_est_propose"]


def test_aucune_bougie_negociee_apres_la_suspension():
    """⚠️ Une séance sans échange ne doit jamais entrer comme bougie : ce
    serait fabriquer une cotation le jour où le titre a cessé d'en avoir."""
    from bvc_config import SUSPENSIONS
    serie = json.loads((RACINE / "pipeline" / "candles" / "CMT.json")
                       .read_text(encoding="utf-8"))
    p = SUSPENSIONS["CMT"][0]
    debut, reprise = p["depuis"], p.get("reprise")

    # ⚠️ LA FENÊTRE EST CELLE DE LA SUSPENSION, PAS « TOUT CE QUI SUIT ». Ce
    # test interdisait toute bougie postérieure au 17/07. La suspension a été
    # levée le 16/09 : le titre cote de nouveau, et lui refuser des bougies
    # reviendrait à le figer pour toujours. Ce qui reste interdit, c'est une
    # bougie PENDANT la suspension — là où le titre ne cotait pas.
    pendant = [b for b in serie
               if b["d"] >= debut and (reprise is None or b["d"] < reprise)]
    assert pendant == [], (
        f"{len(pendant)} bougie(s) pendant la suspension : {[b['d'] for b in pendant][:5]}")
    assert all(b["v"] > 0 for b in serie), (
        "une séance sans échange est entrée comme bougie — ce serait fabriquer "
        "une cotation")


def test_la_serie_publiee_est_bien_celle_qui_a_ete_acceptee():
    """Le graphique lit `pipeline/candles/CMT.json` : c'est CE fichier qui doit
    porter la série réceptionnée, pas seulement le cache."""
    acceptee = json.loads((RACINE / "datasets" / "series_acceptees" / "CMT.json")
                          .read_text(encoding="utf-8"))
    publiee = json.loads((RACINE / "pipeline" / "candles" / "CMT.json")
                         .read_text(encoding="utf-8"))
    # ⚠️ CETTE SÉRIE AVAIT LE DROIT DE GRANDIR, ET ELLE L'A FAIT. Minière
    # Touissit a repris sa cotation le 16/09 — bulletin de l'opérateur à
    # l'appui — après deux mois de suspension pour OPA. Un test qui exige que
    # la série s'arrête au 16/07 n'énonce plus une règle : il interdit au titre
    # de coter.
    #
    # La règle, elle, ne bouge pas : les 681 séances RÉCEPTIONNÉES doivent être
    # intactes, date pour date et clôture pour clôture. Ce qui vient après leur
    # est étranger, et légitime.
    recues = acceptee["serie"]
    assert acceptee["seances_negociees"] == 681
    debut = publiee[:len(recues)]
    assert [b["d"] for b in debut] == [b["d"] for b in recues], (
        "les dates de la série réceptionnée ne sont plus celles publiées")
    assert [b["c"] for b in debut] == [b["c"] for b in recues], (
        "une clôture de la série réceptionnée a été réécrite")
    assert debut[-1]["c"] == 4350.0 and debut[-1]["d"] == "2026-07-16"


def test_le_refus_est_la_regle_si_une_bougie_depasse_la_suspension(tmp_path, monkeypatch):
    """⚠️ Un contrôle qui ne sait pas refuser ne contrôle rien."""
    import appliquer_serie as a
    d = json.loads((RACINE / "datasets" / "series_acceptees" / "CMT.json")
                   .read_text(encoding="utf-8"))
    d["serie"] = d["serie"] + [{"d": "2026-08-03", "o": 1, "h": 1, "l": 1,
                                "c": 1, "v": 10}]
    (tmp_path / "CMT.json").write_text(json.dumps(d), encoding="utf-8")
    monkeypatch.setattr(a, "ACCEPTEES", tmp_path)
    r = a.verifier("CMT")
    assert "refus" in r and "suspension" in r["refus"]


def test_le_cache_recalcule_TOUS_ses_indicateurs():
    """⚠️ Ma première version n'en recalculait que six sur vingt : CMT se
    retrouvait avec un RSI issu des 681 nouvelles bougies à côté d'un `h52w`
    calculé sur l'ancienne série de 514. Une entrée mélangée a l'air à jour."""
    from recalculer_cache import INDICATEURS_COMPLETS
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    champs = {k for k in cache["CMT"] if not k.startswith("_")}
    manquants = champs - set(INDICATEURS_COMPLETS)
    assert manquants == set(), (
        f"ces indicateurs du cache ne sont pas recalculés : {manquants}")


def test_le_cache_de_CMT_decrit_la_serie_qu_il_pretend_decrire():
    """⚠️ RÈGLE DE COHÉRENCE, ET NON PLUS RELEVÉ DE SEPT CONSTANTES.

    Ce test épinglait `rsi == 42.0`, `n_candles == 681`, `last_date ==
    "2026-07-16"`. Ces valeurs sont justes : ce sont celles du lot réceptionné.
    Mais un test qui fige un instantané cesse de vérifier quoi que ce soit dès
    que le travail avance — et ici il ferait pire. CMT a repris sa cotation le
    16/09 ; le cache sera un jour recalculé, et ce test refuserait alors la
    publication d'une séance parfaitement valide. On s'y est repris huit fois
    dans ce projet.

    Ce qui ne vieillit pas : le cache doit décrire LA SÉRIE QU'IL DIT DÉCRIRE.
    Son `last_date`, son `last_close` et son `n_candles` doivent se retrouver
    dans les chandelles arrêtées à cette même date. Un cache qui annonce une
    date et compte les séances d'une autre est une entrée mélangée — le défaut
    exact que le test précédent attrape indicateur par indicateur.
    """
    cache = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))["CMT"]
    serie = json.loads((RACINE / "pipeline" / "candles" / "CMT.json")
                       .read_text(encoding="utf-8"))
    jusqu_ici = [b for b in serie if b["d"] <= cache["last_date"]]
    assert jusqu_ici, f"le cache annonce le {cache['last_date']}, absent de la série"
    assert cache["n_candles"] == len(jusqu_ici), (
        f"le cache compte {cache['n_candles']} séances jusqu'au "
        f"{cache['last_date']}, la série en compte {len(jusqu_ici)}")
    assert cache["last_close"] == jusqu_ici[-1]["c"]

    # Et tant que le cache s'arrête à la réception, il en porte les valeurs —
    # celles qui ont été vérifiées une à une lors du lot du 14/09.
    if cache["last_date"] == "2026-07-16":
        assert (cache["rsi"], cache["ma20"], cache["ma50"], cache["h52w"]) == (
            42.0, 4624.45, 4769.04, 5940.0), "le cache réceptionné a été altéré"
        assert cache["n_candles"] == 681


def test_le_recalcul_n_interroge_aucune_source():
    """⚠️ « Ne pas relancer un import général pour obtenir ce recalcul. »
    Le programme relit les chandelles du dépôt ; il ne doit atteindre ni le
    réseau, ni les sources."""
    # ⚠️ ON CHERCHE DES APPELS, PAS DES CHAÎNES. Ma première version cherchait
    # le mot « bvcscrap » dans le fichier et le trouvait dans le NOM DU MODULE
    # importé — une mention n'est pas un accès. Quatrième fois que ce piège se
    # présente dans ce projet ; on lit l'arbre syntaxique.
    import ast
    src = (RACINE / "pipeline" / "recalculer_cache.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)

    reseau = {"requests", "urllib", "http", "socket", "httpx", "aiohttp"}
    for n in ast.walk(arbre):
        noms = []
        if isinstance(n, ast.Import):
            noms = [a.name.split(".")[0] for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module:
            noms = [n.module.split(".")[0]]
        for nom in noms:
            assert nom not in reseau, f"le recalcul importe « {nom} » (ligne {n.lineno})"

    # Aucun appel aux fonctions de COLLECTE du collecteur.
    # ⚠️ `main` et `run` sont exclus de la liste : ce module a les siens, et
    # les y inclure faisait échouer le test sur son propre point d'entrée.
    collecte = {"fetch_bvcscrap_extension", "load_xlsx", "load_export",
                "save_candle_file", "adjust_splits_df"}
    for n in ast.walk(arbre):
        if isinstance(n, ast.Call):
            cible = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
            if cible in collecte:
                raise AssertionError(
                    f"le recalcul appelle « {cible} » (ligne {n.lineno}) : "
                    f"il relancerait une collecte")
    # Et il ne doit appeler du collecteur QUE `compute_indicators`.
    depuis_collecteur = {getattr(n.func, "attr", None) for n in ast.walk(arbre)
                         if isinstance(n, ast.Call)
                         and getattr(getattr(n.func, "value", None), "id", None) == "m"}
    # ⚠️ Deux fonctions, et deux seulement : `compute_indicators` pour le
    # recalcul complet, `calc_rsi` pour le recalcul RSI seul. Tout autre appel
    # au collecteur rouvrirait une collecte.
    assert depuis_collecteur <= {"compute_indicators", "calc_rsi"}, (
        f"le recalcul appelle autre chose : {depuis_collecteur}")


def test_la_selection_des_lignes_n_est_pas_generalisee():
    """⚠️ « Absence de quantité renseignée ne prouve pas absence d'échange. »

    Les 18 lignes anciennes sans quantité sont exclues DE CETTE sélection, et
    le fichier doit le dire — sans en faire une règle générale.
    """
    d = json.loads((RACINE / "datasets" / "series_acceptees" / "CMT.json")
                   .read_text(encoding="utf-8"))
    s = d["_selection"]
    assert "ne prouve pas" in s
    assert "n'est pas généralisée" in s or "pas généralisée" in s


# ═══ UN RECALCUL RSI SEUL NE TOUCHE À RIEN D'AUTRE ════════════════════════

def _copie_bac(tmp_path, tickers):
    """Un cache et des chandelles jetables.

    ⚠️ LE CACHE VIENT DE `origin/main`, PAS DU DÉPÔT COURANT.
    Ma première version copiait le cache déjà corrigé : le recalcul rendait
    alors la même valeur, aucune écriture n'avait lieu, et le test ne
    démontrait rien — la mutation ne le faisait pas tomber. Un bac de test doit
    partir de l'état d'AVANT.
    """
    import shutil
    import subprocess
    (tmp_path / "pipeline" / "candles").mkdir(parents=True)
    try:
        cache = json.loads(subprocess.check_output(
            ["git", "show", "origin/main:pipeline/historical_data.json"],
            text=True, cwd=RACINE, stderr=subprocess.DEVNULL))
    except subprocess.CalledProcessError:
        pytest.skip("origin/main absent de ce clone")
    garde = {k: v for k, v in cache.items() if k.startswith("_") or k in tickers}
    # ⚠️ ON FORCE LE CHEMIN D'ÉCRITURE POUR CHAQUE TITRE DU BAC.
    # Le recalcul sort avant d'écrire quand le RSI ne change pas. SOT est dans
    # ce cas — et c'est précisément SOT qui doit démontrer que `h52w` n'est pas
    # touché. Sans cette perturbation, la mutation qui transforme le recalcul
    # RSI en recalcul complet passait inaperçue : le test ne l'atteignait pas.
    for t in tickers:
        if t in garde:
            garde[t] = dict(garde[t])
            garde[t]["rsi"] = -1.0       # valeur impossible : l'écriture aura lieu
    (tmp_path / "pipeline" / "historical_data.json").write_text(
        json.dumps(garde, ensure_ascii=False), encoding="utf-8")
    for t in tickers:
        shutil.copy(RACINE / "pipeline" / "candles" / f"{t}.json",
                    tmp_path / "pipeline" / "candles" / f"{t}.json")
    return tmp_path / "pipeline" / "historical_data.json"


def test_un_recalcul_rsi_seul_ne_modifie_aucun_autre_champ(tmp_path, monkeypatch):
    """⚠️ LE CONTRÔLE DEMANDÉ PAR LA REVUE DU 12/09, ET IL PORTE SUR SOT.

    Mon recalcul COMPLET, appliqué à tous les titres, faisait passer
    `SOT.h52w` de **380** à **1 700**. La valeur venait de la bougie du
    05/05/2026 — `o = h = 1700`, `l = c = 369` — qui mêle deux bases de prix,
    avant et après le split 1:5.

    Rien dans le correctif du RSI ne justifiait de toucher à `h52w`. Un
    recalcul n'assainit pas une donnée : il la relit, anomalie comprise.
    L'assainissement de Sothema est un lot distinct.
    """
    import recalculer_cache as rc

    # ⚠️ LA LISTE COMPTE, ET MA PREMIÈRE VERSION ÉTAIT AVEUGLE.
    # Elle ne contenait que SOT, SGTM et ADH — trois titres dont le RSI ne
    # change PAS. La boucle sortait donc avant d'écrire, et la mutation qui
    # transformait ce recalcul en recalcul complet ne faisait pas tomber le
    # test : il n'empruntait jamais le chemin d'écriture.
    #
    # AKD, ALU et CIM ont un RSI qui bouge : c'est sur eux que la garantie
    # « un seul champ » se démontre. SOT reste, pour la démonstration inverse.
    tickers = ["AKD", "ALU", "CIM", "SOT", "SGTM"]
    cache_f = _copie_bac(tmp_path, tickers)
    monkeypatch.setattr(rc, "CACHE", cache_f)
    monkeypatch.setattr(rc, "CANDLES", tmp_path / "pipeline" / "candles")

    avant = json.loads(cache_f.read_text(encoding="utf-8"))
    r = rc.recalculer(complets=[], rsi_seul=tickers)
    apres = r["_nouveau"]

    for t in tickers:
        modifies = {k for k in set(avant[t]) | set(apres[t])
                    if avant[t].get(k) != apres[t].get(k)}
        assert modifies <= {"rsi"}, (
            f"{t} : un recalcul RSI seul a modifié {sorted(modifies - {'rsi'})}")

    # Le chemin d'écriture est bien emprunté, sinon le test ne prouve rien.
    ecrits = [t for t in tickers if avant[t].get("rsi") != apres[t].get("rsi")]
    assert set(ecrits) == set(tickers), (
        f"le chemin d'écriture n'est pas emprunté pour tous : {ecrits}")

    # ⚠️ La démonstration nommée : 1 700 ne revient pas.
    #
    # ⚠️ ET ELLE NE FIGE PLUS DE VALEUR LITTÉRALE. Elle exigeait
    # `h52w == 380.0` — l'état d'AVANT la réparation de Sothema du 15/09/2026.
    # Ce lot a porté l'extremum à 389,60, légitimement : la série était à une
    # échelle 23 fois trop basse. Le test est alors devenu rouge EN CI
    # SEULEMENT, parce qu'en local la copie de référence vient d'`origin/main`,
    # qui portait encore l'ancienne valeur. Un test dont le verdict dépend de
    # l'instant où on le lance ne décrit rien.
    #
    # Ce qui est DURABLE, c'est la règle : un recalcul RSI SEUL laisse `h52w`
    # exactement là où il était, quelle que soit sa valeur.
    assert apres["SOT"]["h52w"] == avant["SOT"]["h52w"], (
        "le recalcul RSI seul a touché à h52w")
    assert apres["SOT"]["h52w"] != 1700.0, (
        "l'anomalie de la bougie du 05/05 est revenue")
    assert apres["SGTM"]["l52w"] == avant["SGTM"]["l52w"]


def test_le_recalcul_complet_est_reserve_aux_series_remplacees(tmp_path, monkeypatch):
    """⚠️ La contre-épreuve : un recalcul COMPLET relit la bougie telle quelle.

    Ce n'est pas un défaut du calcul — c'est ce que la bougie contient. C'est
    précisément pourquoi le mode complet ne doit viser que les titres dont la
    série a été remplacée : sur des chandelles inchangées, il rejoue les
    anomalies déjà présentes au lieu de les corriger.

    ⚠️ CETTE DÉMONSTRATION NE S'APPUIE PLUS SUR SOT.
    Elle lisait la vraie série de Sothema, dont la bougie du 05/05/2026 mêlait
    les deux bases du regroupement — o=h=1700 avant, l=c=369 après — et elle
    exigeait que le recalcul complet en ressorte `h52w = 1700`. Cette bougie est
    CORRIGÉE depuis le 15/09/2026 : l'objet de la démonstration a disparu avec
    le défaut. La contre-épreuve travaille donc sur une série FABRIQUÉE pour
    l'occasion, ce qui la rend indépendante de l'état des données publiées —
    elle ne pourra plus s'éteindre parce qu'on a réparé ailleurs.
    """
    import recalculer_cache as rc

    cache_f = _copie_bac(tmp_path, ["SOT"])
    monkeypatch.setattr(rc, "CACHE", cache_f)
    candles = tmp_path / "pipeline" / "candles"
    monkeypatch.setattr(rc, "CANDLES", candles)

    # Une série saine à 100, puis UNE bougie qui mêle deux bases de prix :
    # un plus-haut de 1 700 hérité de l'ancienne échelle, une clôture de 369
    # sur la nouvelle. C'est exactement la forme qu'avait SOT au 05/05.
    serie = [{"d": f"2026-01-{j:02d}", "o": 100.0, "h": 101.0, "l": 99.0,
              "c": 100.0, "v": 10} for j in range(1, 29)]
    serie.append({"d": "2026-02-02", "o": 1700.0, "h": 1700.0,
                  "l": 369.0, "c": 369.0, "v": 613})
    (candles / "SOT.json").write_text(json.dumps(serie), encoding="utf-8")

    r = rc.recalculer(complets=["SOT"], rsi_seul=[])
    assert r["_nouveau"]["SOT"]["h52w"] == 1700.0, (
        "la contre-épreuve ne démontre plus rien : le mode complet ne reprend "
        "plus le plus-haut de la bougie mixte")
    # ⚠️ Et le mode RSI SEUL, lui, ne doit PAS toucher à cet extremum.
    r2 = rc.recalculer(complets=[], rsi_seul=["SOT"])
    assert "h52w" not in (r2["changements_rsi"][0] if r2["changements_rsi"] else {})


def test_les_deux_operations_sont_nommees_separement():
    """Le programme doit exposer deux portées distinctes, pas un seul mode."""
    import recalculer_cache as rc
    assert rc.INDICATEUR_RSI == ("rsi",)
    assert len(rc.INDICATEURS_COMPLETS) > 10
    src = (RACINE / "pipeline" / "recalculer_cache.py").read_text(encoding="utf-8")
    assert "--complet" in src and "--rsi-seul" in src


def _titres_dont_la_serie_a_change() -> set:
    """Les titres qu'un recalcul COMPLET a le droit de déplacer.

    ⚠️ Cette liste se LIT dans le dépôt, elle ne se recopie pas. Écrite en dur,
    elle disait « CMT » — et il aurait fallu y ajouter MSA à la main le jour de
    sa correction, c'est-à-dire modifier le contrôle pour faire passer la
    livraison. C'est précisément ce qu'il ne faut pas faire.

    Trois dossiers, trois portées :
      · `series_acceptees/`      la série ENTIÈRE est remplacée ET le titre est
                                 figé face aux imports (CMT, suspendu)
      · `corrections_acceptees/` des séances NOMMÉES sont réécrites (MSA, qui
                                 cote tous les jours)
      · `historiques_importes/`  la série entière vient d'un export de
                                 l'opérateur, sans figer le titre (AKD, HAL,
                                 MUT, TMA, TQA — ajouté le 16/09/2026)
      · `seances_retirees/`      des séances NOMMÉES sont retirées, faute de
                                 pouvoir les corriger (ATL, MRL — 17/09/2026)

    Dans les trois cas, les anciennes valeurs décrivaient une autre série. Pour
    tous les autres titres, seul `rsi` peut bouger.

    ⚠️ LE TROISIÈME DOSSIER A ÉTÉ AJOUTÉ PARCE QUE CE TEST A ROUGI, et c'est la
    seule façon acceptable de le faire taire. Il n'a pas rougi à tort : cinq
    caches avaient bougé sans qu'aucun dossier du dépôt ne l'autorise. La
    réponse n'est pas d'élargir l'exception à la main — ce serait modifier le
    contrôle pour faire passer la livraison — mais d'écrire l'instruction qui
    manquait, avec sa provenance, son empreinte et sa période. Le test continue
    de LIRE le dépôt ; c'est le dépôt qui dit désormais ce qui a été réceptionné.
    """
    dossiers = (RACINE / "datasets" / "series_acceptees",
                RACINE / "datasets" / "corrections_acceptees",
                RACINE / "datasets" / "historiques_importes",
                RACINE / "datasets" / "seances_retirees")
    return {f.stem for d in dossiers if d.exists() for f in d.glob("*.json")}


def _series_modifiees_dans_cette_livraison() -> set:
    """Les titres dont le fichier de chandelles diffère de `origin/main`.

    ⚠️ C'est la mesure de ce que la livraison FAIT, et non de ce que le dépôt
    a déjà reçu. Sans elle, l'exemption ne fait que grandir.
    """
    import subprocess
    try:
        sortie = subprocess.check_output(
            ["git", "diff", "--name-only", "origin/main", "--", "pipeline/candles"],
            text=True, cwd=RACINE, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return set()
    return {Path(l).stem for l in sortie.split() if l.endswith(".json")}


def test_hors_series_corrigees_le_cache_livre_ne_differe_que_par_le_rsi():
    """⚠️ Le contrôle sur la LIVRAISON elle-même, pas sur un bac de test."""
    import subprocess
    try:
        base = json.loads(subprocess.check_output(
            ["git", "show", "origin/main:pipeline/historical_data.json"],
            text=True, cwd=RACINE, stderr=subprocess.DEVNULL))
    except subprocess.CalledProcessError:
        pytest.skip("origin/main absent de ce clone")
    livre = json.loads((RACINE / "pipeline" / "historical_data.json")
                       .read_text(encoding="utf-8"))
    # ⚠️ LES REGISTRES SONT CUMULATIFS, LE CONTRÔLE NE DOIT PAS L'ÊTRE.
    #
    # Ce test comparait le cache livré au cache de `origin/main` et exemptait
    # TOUS les titres jamais inscrits dans un registre. Au 17/09 ils étaient
    # vingt-cinq sur soixante-quinze — exactement le tiers que le garde-fou
    # refuse — et le contrôle s'est arrêté. Il avait raison de s'arrêter, et la
    # réponse n'est pas de desserrer le seuil.
    #
    # Un titre corrigé le 15/09 n'a aucune raison d'être exempté le 17. Ce qui
    # a le droit de bouger dans CETTE livraison, ce sont les titres dont la
    # SÉRIE a changé dans cette livraison ET qui portent une instruction écrite.
    # Les deux conditions, pas l'une ou l'autre.
    #
    # C'est un RESSERREMENT : l'exemption passe de vingt-cinq titres à ceux que
    # la livraison touche réellement.
    bouges = _series_modifiees_dans_cette_livraison()
    exceptions = _titres_dont_la_serie_a_change() & bouges

    # ⚠️ Et le seuil porte désormais sur ce que la livraison FAIT, pas sur ce
    # que l'histoire contient. Toucher un tiers des séries d'un coup est une
    # opération de masse : elle doit être refusée ici, quelle que soit la
    # qualité des instructions qui l'accompagnent.
    univers = len([k for k in base if not k.startswith("_")])
    assert len(bouges) < univers / 3, (
        f"cette livraison modifie {len(bouges)} séries sur {univers} "
        f"— opération de masse : {sorted(bouges)}")
    fautifs = {}
    for t in (k for k in base if not k.startswith("_") and k not in exceptions):
        d = {k for k in set(base[t]) | set(livre.get(t, {}))
             if base[t].get(k) != livre.get(t, {}).get(k)}
        if d - {"rsi"}:
            fautifs[t] = sorted(d - {"rsi"})
    assert fautifs == {}, (
        f"champs hors rsi modifiés sur des titres dont la série n'a pas "
        f"changé : {fautifs}")

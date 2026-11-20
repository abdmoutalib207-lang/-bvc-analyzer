"""État du service publié — lots 3.1 et 3.5 (20/11/2026).

Quatre familles :
  1. le COMPTEUR, sur des historiques fabriqués : séance manquée, publiée hors
     délai, week-end, férié, séance en attente — et les contrôles négatifs ;
  2. le FICHIER : forme de `construire()`, et `etat_service.json` publié ;
  3. le TERMINAL lecteur : lien depuis l'accueil, état indisponible, aucune
     couleur de variation, retard recalculé à la lecture (exécuté sous node) ;
  4. le WORKFLOW : aucun cron, aucun `workflow_run`, aucun commit de plus.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from pipeline import etat_service as es  # noqa: E402

UTC = timezone.utc
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
WF = RACINE / ".github" / "workflows" / "update_bvc.yml"


def _t(iso: str) -> datetime:
    """Instant à l'heure du Maroc (UTC+0 depuis le 20/09/2026)."""
    return datetime.fromisoformat(iso).replace(tzinfo=UTC)


def _journal(seances, heure="15:56:10"):
    return {s: {"publiee_a": f"{s}T{heure}+0000", "titres": 66} for s in seances}


# Jours ouvrés du 02 au 19/11/2026 : le 06 (Marche Verte) et le 18 (Indépendance)
# sont fériés, les 07-08 et 14-15 un week-end.
OUVRES = ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-09",
          "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-16",
          "2026-11-17", "2026-11-19"]
MAINTENANT = _t("2026-11-20T11:00:00")


# ── 1. Calendrier et compteur ──────────────────────────────────────────────

def test_seuils_identiques_a_verifier_seance():
    from pipeline import verifier_seance as vs
    assert es.MIN_TITRES_CLOTURE == vs.MIN_PRIX_DU_JOUR
    assert es.HEURE_CLOTURE == vs.HEURE_CLOTURE


@pytest.mark.parametrize("jour,attendu", [
    ("2026-11-19", True),    # jeudi ordinaire
    ("2026-11-21", False),   # samedi
    ("2026-11-22", False),   # dimanche
    ("2026-11-06", False),   # Marche Verte (férié fixe)
    ("2026-11-18", False),   # Fête de l'Indépendance
    ("2026-09-17", False),   # séance annulée par la Bourse
    ("2026-07-30", False),   # séance sans cotation inscrite au registre
])
def test_jour_ouvre(jour, attendu):
    assert es.jour_ouvre(jour) is attendu


def test_echeance_le_jour_ouvre_suivant_a_8h():
    assert es.jour_ouvre_suivant("2026-11-05").isoformat() == "2026-11-09"
    assert es.echeance("2026-11-13") == _t("2026-11-16T08:00:00")   # vendredi → lundi
    assert es.echeance("2026-11-17") == _t("2026-11-19T08:00:00")   # le 18 est férié
    # Avant le 20/09/2026 le Maroc était à UTC+1 : l'échéance suit le registre.
    assert es.echeance("2026-09-15").utcoffset() == timedelta(hours=1)


def test_compteur_historique_complet():
    vs = es.verdicts(_journal(OUVRES), "2026-11-02", MAINTENANT)
    assert [v["seance"] for v in vs] == OUVRES
    c = es.compteur(vs)
    assert c["valeur"] == 12 and c["au_moins"] and c["derniere_rupture"] is None


def test_week_end_et_ferie_ne_rompent_pas():
    vs = es.verdicts(_journal(OUVRES), "2026-11-02", MAINTENANT)
    vus = {v["seance"] for v in vs}
    assert not vus & {"2026-11-06", "2026-11-07", "2026-11-08", "2026-11-14",
                      "2026-11-15", "2026-11-18"}


def test_seance_manquee_rompt_le_compteur():
    j = _journal([s for s in OUVRES if s != "2026-11-12"])
    c = es.compteur(es.verdicts(j, "2026-11-02", MAINTENANT))
    assert c["valeur"] == 4            # 13, 16, 17, 19
    assert not c["au_moins"]
    assert c["derniere_rupture"] == {"seance": "2026-11-12", "statut": "manquee"}


def test_publication_hors_delai_rompt_le_compteur():
    j = _journal(OUVRES)
    j["2026-11-16"]["publiee_a"] = "2026-11-17T08:30:00+0000"
    c = es.compteur(es.verdicts(j, "2026-11-02", MAINTENANT))
    assert c["valeur"] == 2 and c["derniere_rupture"]["statut"] == "hors_delai"


def test_publication_juste_avant_8h_est_a_temps():
    # Le cas réel du 16/11 (JET ENERGY) : clôture publiée le 17 à 07h50.
    j = _journal(OUVRES)
    j["2026-11-16"]["publiee_a"] = "2026-11-17T07:50:41+0000"
    assert es.compteur(es.verdicts(j, "2026-11-02", MAINTENANT))["valeur"] == 12


def test_seance_en_attente_ne_compte_ni_ne_rompt():
    j = _journal(OUVRES)
    vs = es.verdicts(j, "2026-11-02", _t("2026-11-20T16:00:00"))
    assert vs[-1] == {"seance": "2026-11-20", "statut": "en_attente"}
    assert es.compteur(vs)["valeur"] == 12
    # Avant la clôture, la séance du jour n'est même pas évaluée.
    assert es.verdicts(j, "2026-11-02", _t("2026-11-20T15:00:00"))[-1]["seance"] == "2026-11-19"


def test_echeance_depassee_sans_publication_devient_manquee():
    vs = es.verdicts(_journal(OUVRES), "2026-11-02", _t("2026-11-23T08:01:00"))
    assert vs[-1] == {"seance": "2026-11-20", "statut": "manquee"}
    assert es.compteur(vs)["valeur"] == 0


def test_ferie_lunaire_non_inscrit_compte_comme_manque():
    """Contrôle négatif assumé : une date absente du registre n'est pas devinée."""
    vs = es.verdicts({}, "2026-11-19", _t("2026-11-20T11:00:00"))
    assert vs == [{"seance": "2026-11-19", "statut": "manquee"}]


# ── Publication et conformité ──────────────────────────────────────────────

def _data(seance="2026-11-19", n=60, ecrit="2026-11-19T15:56:00+0000", masi=None, autres=10):
    lignes = [{"symbol": f"T{i}", "_meta": {"prix_asof": seance, "source_prix": "cdg"}} for i in range(n)]
    lignes += [{"symbol": f"V{i}", "_meta": {"prix_asof": "2026-11-10", "source_prix": "candles"}}
               for i in range(autres)]
    return {"updated": ecrit, "tickers": lignes, "masi": {"asof": masi or seance}}


def test_cloture_conforme_et_motifs():
    assert es.cloture_conforme(es.publication(_data())) == (True, "conforme")
    ok, motif = es.cloture_conforme(es.publication(_data(ecrit="2026-11-19T11:00:00+0000")))
    assert not ok and "avant la clôture" in motif
    ok, motif = es.cloture_conforme(es.publication(_data(n=49, autres=0)))
    assert not ok and "49 titres" in motif
    ok, motif = es.cloture_conforme(es.publication(_data(masi="2026-11-18")))
    assert not ok and "MASI" in motif


def test_journal_retient_la_premiere_publication_conforme():
    j = es.enregistrer({}, es.publication(_data(ecrit="2026-11-19T12:00:00+0000")))
    assert j == {}                                   # cours de séance : rien
    j = es.enregistrer(j, es.publication(_data(ecrit="2026-11-19T15:56:00+0000")))
    j = es.enregistrer(j, es.publication(_data(ecrit="2026-11-19T18:00:00+0000", n=70)))
    assert j == {"2026-11-19": {"publiee_a": "2026-11-19T15:56:00+0000", "titres": 60}}


def test_lire_instant_formats():
    assert es.lire_instant("2026-11-20T09:55:58+0000") == _t("2026-11-20T09:55:58")
    assert es.lire_instant("2026-11-20T09:55:58.98+00:00").minute == 55
    assert es.lire_instant("n'importe quoi") is None and es.lire_instant(None) is None


# ── 2. Le fichier ──────────────────────────────────────────────────────────

COMPTES = {"disponible": True, "a_lire": 0, "plus_ancien": None, "en_retard": False, "statut": "vide"}


def _racine(tmp_path, news="2026-11-19T20:00:00+00:00", bougie="2026-11-19"):
    (tmp_path / "pipeline" / "candles").mkdir(parents=True)
    for i in range(55):
        (tmp_path / "pipeline" / "candles" / f"T{i}.json").write_text(
            json.dumps([{"d": bougie, "o": 1, "h": 1, "l": 1, "c": 1}]))
    (tmp_path / "news.json").write_text(json.dumps({"updated": news}))
    (tmp_path / "briefing_cloture.json").write_text(json.dumps({"seance": "2026-11-18"}))
    (tmp_path / "financial_data.json").write_text(json.dumps({"timestamp": "2026-11-19T22:26:07Z"}))
    return tmp_path


def test_construire_forme_et_compteur(tmp_path):
    prec = {"schema": es.SCHEMA, "journal_depuis": "2026-11-02",
            "journal": _journal(OUVRES[:-1])}
    e = es.construire(_data(), prec, MAINTENANT, racine=_racine(tmp_path), comptes=COMPTES)
    json.dumps(e)                                     # sérialisable
    for cle in ("schema", "genere_a", "derniere_publication", "derniere_cloture",
                "prochaine_echeance", "statut", "taches", "file_comptes", "compteur",
                "seances", "journal_depuis", "journal"):
        assert cle in e
    assert e["derniere_cloture"]["seance"] == "2026-11-19"
    assert e["prochaine_echeance"] == "2026-11-23T08:00:00+00:00"
    assert e["compteur"]["valeur"] == 12
    assert e["statut"] == "à jour", e["en_retard"]
    # Le compteur dit ce qu'il mesure : il ne se présente pas comme le
    # verdict de verifier_seance, qu'il ne peut pas lire.
    assert "verifier_seance" not in e["compteur"]["nom"]
    assert "n'est lisible que" in e["compteur"]["controle_du_soir"]
    ctrl = [t for t in e["taches"] if "verifier_seance" in t["nom"]][0]
    assert ctrl["mesure"] is False and ctrl["statut"] == "non mesuré ici"


def test_tache_en_retard_dite_avec_sa_date(tmp_path):
    racine = _racine(tmp_path, news="2026-11-12T20:00:00+00:00")
    e = es.construire(_data(), {}, MAINTENANT, racine=racine, comptes=COMPTES)
    news = [t for t in e["taches"] if t["nom"].startswith("Actualités")][0]
    assert news["en_retard"] and news["statut"] == "en retard depuis le 13/11"
    assert e["statut"] == "en retard" and "Actualités (news.json)" in e["en_retard"]


def test_precedent_d_un_autre_schema_ignore(tmp_path):
    e = es.construire(_data(), {"schema": "autre", "journal": _journal(OUVRES)},
                      MAINTENANT, racine=_racine(tmp_path), comptes=COMPTES)
    assert list(e["journal"]) == ["2026-11-19"] and e["journal_depuis"] == "2026-11-19"


def test_journal_borne(tmp_path):
    seances, j = [], es._jour("2026-01-05")
    while len(seances) < es.JOURNAL_MAX + 10:
        seances.append(j.isoformat())
        j = es.jour_ouvre_suivant(j)
    prec = {"schema": es.SCHEMA, "journal_depuis": seances[0], "journal": _journal(seances)}
    e = es.construire(_data(), prec, MAINTENANT, racine=_racine(tmp_path), comptes=COMPTES)
    assert len(e["journal"]) == es.JOURNAL_MAX
    assert e["journal_depuis"] == min(e["journal"])


def test_file_des_comptes_reelle_lisible():
    fc = es.file_comptes(es._jour("2026-11-20"))
    assert fc["disponible"] is True
    assert isinstance(fc["a_lire"], int) and fc["a_lire"] >= 0


def test_fichier_publie_conforme():
    """Données publiées : etat_service.json à la racine servie par Pages.

    ⚠️ On ne compare pas à data.json : dans le workflow, les tests passent
    AVANT que l'état ne soit régénéré pour le data.json du passage.
    """
    chemin = RACINE / "etat_service.json"
    if not chemin.exists():
        pytest.skip("etat_service.json pas encore publié")
    e = json.loads(chemin.read_text(encoding="utf-8"))
    assert e["schema"] == es.SCHEMA
    c = e["compteur"]
    assert isinstance(c["valeur"], int) and c["valeur"] >= 0
    assert c["definition"] == es.DEFINITION_COMPTEUR
    assert e["statut"] in ("à jour", "en retard")
    assert e["journal_depuis"] <= min(e["journal"] or [e["journal_depuis"]])
    for v in e["seances"]:
        assert v["statut"] in ("a_temps", "hors_delai", "manquee", "en_attente")


# ── 3. Le terminal ─────────────────────────────────────────────────────────

def _bloc_terminal() -> str:
    return SRC[SRC.index("const ETAT_SCHEMA="):SRC.index("const Header=")]


def test_terminal_lien_depuis_l_accueil():
    accueil = SRC[SRC.index("const Accueil="):SRC.index("const ETAT_SCHEMA=")]
    assert 'setTab("etat")' in accueil and "État du service" in accueil
    assert '"etat"' in SRC[SRC.index("const VUES_CONNUES="):SRC.index("const EtatDonnees=")]
    assert '{tab==="etat"     &&<EtatService/>}' in SRC
    # Lisible même quand data.json manque.
    vues = SRC[SRC.index("const VUES_SUR_DONNEES="):SRC.index("const VUES_CONNUES=")]
    assert '"etat"' not in vues


def test_terminal_lit_le_fichier_et_dit_indisponible():
    bloc = _bloc_terminal()
    assert 'fetch("etat_service.json?t="' in bloc
    assert "État indisponible" in bloc
    assert f'const ETAT_SCHEMA="{es.SCHEMA}"' in bloc


def test_terminal_sans_couleur_de_variation_ni_mot_d_action():
    bloc = _bloc_terminal()
    for couleur in ("#00e5a0", "#ff4f5a", "rgba(0,229,160", "rgba(255,79,90", "VC("):
        assert couleur not in bloc, couleur
    for mot in ("ACHETER", "VENDRE", "ÉVITER", "SURVEILLER", "acheter", "vendre"):
        assert mot not in bloc, mot


@pytest.mark.skipif(not shutil.which("node"), reason="node absent")
def test_terminal_recalcule_le_retard_a_la_lecture():
    """Exécute `lireEtatService` (JS pur, sans JSX) sous node."""
    bloc = _bloc_terminal()
    fonctions = bloc[:bloc.index("const EtatService=")]
    etat = {"schema": es.SCHEMA, "statut": "à jour", "en_retard": [], "taches": [],
            "compteur": {"valeur": 3}, "prochaine_echeance": "2026-11-23T08:00:00+00:00",
            "seance_attendue_ensuite": "2026-11-20"}
    script = fonctions + f"""
const e={json.dumps(etat)};
const avant=lireEtatService(e,Date.parse("2026-11-23T07:59:00Z"));
const apres=lireEtatService(e,Date.parse("2026-11-23T08:01:00Z"));
const retardFichier=lireEtatService({{...e,statut:"en retard",en_retard:["Indice MASI"]}},0);
console.log(JSON.stringify([avant,apres,retardFichier,lireEtatService(null,0),
  lireEtatService({{schema:"autre"}},0)]));
"""
    sortie = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert sortie.returncode == 0, sortie.stderr
    avant, apres, fichier, absent, autre = json.loads(sortie.stdout)
    assert avant == {"statut": "à jour", "retard": False, "depasse": False}
    assert apres == {"statut": "en retard depuis le 20/11", "retard": True, "depasse": True}
    assert fichier["retard"] and "Indice MASI" in fichier["statut"]
    assert absent is None and autre is None


# ── 4. Le workflow ─────────────────────────────────────────────────────────

CRONS_UPDATE_BVC = ["0 10 * * 1-5", "0 12 * * 1-5", "45 15 * * 1-5", "0 18 * * 1-5",
                    "25,55 8-18 * * 1-5"]


def _wf():
    return yaml.safe_load(WF.read_text(encoding="utf-8"))


def test_workflow_aucun_cron_ni_declencheur_ajoute():
    on = _wf().get("on") or _wf().get(True)
    assert [c["cron"] for c in on["schedule"]] == CRONS_UPDATE_BVC
    assert on["workflow_run"]["workflows"] == ["BVC Financial Data Pipeline v9"]
    # Aucun autre workflow n'écrit ni ne lit l'état.
    autres = [f for f in (RACINE / ".github" / "workflows").glob("*.yml")
              if f != WF and "etat_service" in f.read_text(encoding="utf-8")]
    assert autres == []


def test_workflow_etat_dans_le_commit_existant_jamais_seul():
    etapes = _wf()["jobs"]["update-bvc-data"]["steps"]
    avec = [s for s in etapes if "etat_service" in (s.get("run") or "")]
    assert len(avec) == 1, "l'état doit vivre dans une seule étape"
    run = avec[0]["run"]
    assert "git commit" in run, "l'état doit partir dans l'étape qui commite data.json"
    texte = WF.read_text(encoding="utf-8")
    assert texte.count("git commit") == 1, "aucun commit de plus"
    vide = run.index("git diff --cached --quiet")
    appel = run.index("python3 pipeline/etat_service.py")
    ajout = run.index("git add etat_service.json")
    commit = run.index("git commit")
    # Écrit APRÈS le constat qu'autre chose part : jamais un commit à lui seul.
    assert vide < appel < ajout < commit
    # Un échec de l'état n'empêche pas data.json.
    assert re.search(r"if python3 pipeline/etat_service\.py; then\s+git add etat_service\.json\s+else",
                     run)


def test_module_bibliotheque_standard_seulement():
    """R4 : aucune dépendance tierce dans etat_service.py."""
    src = (RACINE / "pipeline" / "etat_service.py").read_text(encoding="utf-8")
    imports = set(re.findall(r"^\s*(?:from|import) ([a-zA-Z_]+)", src, re.M))
    tiers = imports - {"__future__", "json", "re", "subprocess", "sys", "collections",
                       "datetime", "pathlib", "bvc_config", "pipeline"}
    assert not tiers, tiers

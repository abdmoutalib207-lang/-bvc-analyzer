"""L'audit de la chaîne (tools/audit_chaine.py) : de la pièce à l'affichage.

Demandé par un relecteur externe (16/10/2026) : prouver, titre par titre, que la
note, les alertes et la fiche lisent les MÊMES valeurs.

Trois familles dans ce fichier, à ne pas confondre :

1. CELLE QUI RELIT LES DONNÉES PUBLIÉES (`test_data_json_publie…`). Un échec peut
   vouloir dire « le moteur n'a pas encore tourné ». Si le data.json jugé est
   antérieur (historique du dépôt) à une de ses entrées, le test SAUTE en disant
   lequel ; sinon il échoue. Le 16/10/2026, il sautait : data.json (21:14 UTC le
   15/10) précédait les fusions #269 et #270 (22:53 et 23:07, +01:00) qui ont
   complété la note de MSA, VCNE, TMA, BAL, MOX et UNI.

2. CELLE QUI JUGE UN FICHIER ÉCRIT PAR LE CODE ACTUEL (`regenere`) : le dépôt est
   COPIÉ dans un dossier temporaire, le moteur y tourne en essai à blanc
   (`run(dry_run=True)`), hors réseau, IDBourse servie par les cours du
   data.json de la copie. Aucune ambiguïté « périmé ou défaut » : un échec ici
   est un défaut. Rien n'est écrit dans le dépôt.

3. CELLE QUI DÉCRIT LE CODE : des cas FABRIQUÉS à partir du fichier régénéré,
   qui DOIVENT échouer (note divergente, signal incohérent, confiance mal
   sommée, grandeur contestée utilisée, alerte incomplète, composant du
   terminal qui lit une seconde source).
"""
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tools"))

import audit_chaine as A  # noqa: E402
from conftest import chemin_data_json  # noqa: E402

PILOTE = '''
import socket, sys, json
sys.path.insert(0, ".")

def _refus(*a, **k):
    raise OSError("réseau interdit dans ce test")
socket.socket.connect = _refus
socket.getaddrinfo = _refus
import update_data as u

data = json.load(open("data.json"))
lignes = [{"name": t["symbol"], "url": "https://idbourse.invalid/instruments/" + u.IDB_TICKER_MAP.get(t["symbol"], t["symbol"]),
           "dernier_cours": t["price"], "variation": t["chg"], "volume_en_titres": str(t["vol"]),
           "ouverture": str(t.get("open") or ""), "capitalisation_boursiere": str((t.get("cap") or 0) * 1e6),
           "updated_at": ((t.get("_meta") or {}).get("prix_asof") or "2026-10-09") + "T00:00:00"}
          for t in data["tickers"]]
u.idb_get = lambda endpoint, timeout=10: lignes if endpoint == "/api/proxy/get_all_data" else None
sortie = u.run(dry_run=True, push=False)
json.dump(sortie, open("regenere.json", "w", encoding="utf-8"), ensure_ascii=False)
print("RUN_TERMINE")
'''


def _lire(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def regenere(tmp_path_factory):
    """(dossier de travail, data.json écrit par le code ACTUEL en essai à blanc)."""
    dossier = tmp_path_factory.mktemp("regen") / "depot"
    shutil.copytree(RACINE, dossier, ignore=shutil.ignore_patterns(
        ".git", "node_modules", "__pycache__", ".pytest_cache", ".claude"))
    (dossier / "_pilote.py").write_text(PILOTE, encoding="utf-8")
    r = subprocess.run([sys.executable, "_pilote.py"], cwd=dossier, capture_output=True, text=True, timeout=600)
    assert "RUN_TERMINE" in r.stdout and (dossier / "regenere.json").exists(), \
        f"la régénération à blanc a échoué :\n{r.stdout[-800:]}\n{r.stderr[-1500:]}"
    return dossier, _lire(dossier / "regenere.json")


@pytest.fixture(scope="module")
def entrees(regenere):
    dossier, _ = regenere
    ch = A.charger(dossier)
    return ch["fondamentaux"], ch["faits"], ch["bpa"]


@pytest.fixture
def audit(regenere, entrees):
    """auditer() sur une COPIE de la fiche modifiée : renvoie les contrôles levés."""
    _, data = regenere
    fo, faits, bpa = entrees

    def _audit(sym, modifie):
        d = copy.deepcopy(data)
        t = next(x for x in d["tickers"] if x["symbol"] == sym)
        modifie(t)
        return {i["controle"] for i in A.auditer({"tickers": [t]}, fo, faits, bpa) if i["gravite"] == A.ERREUR}
    return _audit


def _premier(data, pred):
    return next(t["symbol"] for t in data["tickers"] if pred(t))


# ═══ 1. Le fichier écrit par le code actuel est cohérent ═══════════════════

def test_le_fichier_regenere_passe_l_audit(regenere, entrees):
    _, data = regenere
    fo, faits, bpa = entrees
    erreurs = [i for i in A.auditer(data, fo, faits, bpa) if i["gravite"] == A.ERREUR]
    assert not erreurs, "chaîne incohérente sur un fichier écrit par le code actuel :\n" + \
        "\n".join(f"  {i['titre']} {i['controle']} : {i['message']} (publié={i['publie']!r}, attendu={i['attendu']!r})"
                  for i in erreurs[:25])


def test_les_80_titres_sont_audites(regenere):
    _, data = regenere
    assert len(data["tickers"]) == 80


def test_titre_non_cote_variation_et_ouverture_nulles(regenere):
    """R9 (audit du 22/10/2026) : un cours antérieur à la séance de référence
    n'a ni variation ni ouverture du jour — `null`, pas 0,00 % ni la clôture.
    Le volume, lui, est mesuré (0) et motivé."""
    _, data = regenere
    asofs = [(t.get("_meta") or {}).get("prix_asof") for t in data["tickers"]]
    seance = max(a for a in asofs if a)
    non_cotes = [t for t in data["tickers"]
                 if (t["_meta"].get("prix_asof") or seance) < seance]
    assert non_cotes, "aucun titre non coté : le contrôle ne teste rien"
    fautes = [f"{t['symbol']} chg={t['chg']} open={t['open']} vol={t['vol']} "
              f"motif={t['_meta'].get('motif_vol')}"
              for t in non_cotes
              if t["chg"] is not None or t["open"] is not None or t["vol"] != 0
              or not t["_meta"].get("motif_vol") or not t["_meta"].get("stale")]
    assert not fautes, "\n".join(fautes)
    cotes = [t for t in data["tickers"] if t["_meta"].get("prix_asof") == seance]
    assert cotes and all(t["chg"] is not None and t["open"] is not None
                         and t["_meta"].get("motif_vol") is None for t in cotes)


def test_l_audit_n_est_pas_vide_de_sens(regenere, entrees):
    """Garde contre un audit qui passerait faute de matière : il existe des titres
    contestés, des couvertures partielles, des alertes et des titres sans note."""
    _, data = regenere
    fo, faits, _ = entrees
    assert A.contestations(fo, faits), "aucune grandeur contestée : le contrôle « contestée » ne teste rien"
    sigs = {t["sig"] for t in data["tickers"]}
    assert {"Couverture partielle", "Données insuffisantes"} <= sigs
    assert any(t["alertes"]["liste"] for t in data["tickers"])


# ═══ 2. Le data.json PUBLIÉ ═════════════════════════════════════════════════

def test_data_json_publie_passe_l_audit():
    chemin = chemin_data_json()
    ch = A.charger(RACINE, chemin)
    erreurs = [i for i in A.auditer(ch["data"], ch["fondamentaux"], ch["faits"], ch["bpa"])
               if i["gravite"] == A.ERREUR]
    if not erreurs:
        return
    retard = A.entrees_plus_recentes(RACINE, ch["data"])
    titres = sorted({i["titre"] for i in erreurs})
    if retard:
        pytest.skip(
            f"data.json publié ({ch['data'].get('updated')}) antérieur à ses entrées "
            f"{[f for f, _ in retard]} : {len(erreurs)} écart(s) sur {titres}. Le moteur n'a pas encore "
            "régénéré le fichier ; le même audit sur le fichier régénéré (test_le_fichier_regenere_passe_l_audit) "
            "est, lui, strict.")
    pytest.fail(f"{len(erreurs)} incohérence(s) sur le data.json publié, qui n'est PAS antérieur à ses entrées "
                f"— défaut réel. Titres : {titres}\n" +
                "\n".join(f"  {i['titre']} {i['controle']} : {i['message']}" for i in erreurs[:25]))


# ═══ 3. Cas FABRIQUÉS qui doivent échouer ═══════════════════════════════════

def test_note_divergente(audit, regenere):
    sym = _premier(regenere[1], lambda t: t["note_fond"]["note"] is not None)
    assert "note.recalcul" in audit(sym, lambda t: t["note_fond"].update(note=round(t["note_fond"]["note"] + 1, 2)))


def test_score_fond_different_de_la_note(audit, regenere):
    sym = _premier(regenere[1], lambda t: t["note_fond"]["note"] is not None)
    assert "note.score_fond" in audit(sym, lambda t: t.update(score_fond=round(t["score_fond"] + 0.5, 2)))


def test_composante_affichee_avec_une_autre_valeur(audit, regenere):
    sym = _premier(regenere[1], lambda t: (t["note_fond"]["composantes"]["valorisation"]["note"] is not None))
    assert "composante.valorisation.note" in audit(
        sym, lambda t: t["note_fond"]["composantes"]["valorisation"].update(note=1.0))
    assert "composante.valorisation.mesure" in audit(
        sym, lambda t: t["note_fond"]["composantes"]["valorisation"].update(mesure="PER 3"))


def test_reserve_effacee_de_l_affichage(audit, regenere):
    sym = _premier(regenere[1], lambda t: any(c.get("reserve") for c in t["note_fond"]["composantes"].values()))
    def efface(t):
        for c in t["note_fond"]["composantes"].values():
            c.pop("reserve", None)
    assert any(c.endswith(".reserve") for c in audit(sym, efface))


def test_couverture_gonflee(audit, regenere):
    # Une couverture RÉELLEMENT partielle : depuis la règle B (27/10/2026), une
    # foncière à couverture pleine peut aussi porter « Couverture partielle ».
    sym = _premier(regenere[1], lambda t: t["sig"] == "Couverture partielle"
                   and (t["note_fond"].get("couverture_applicable") or 1) < 0.75)
    assert "note.couverture" in audit(sym, lambda t: t["note_fond"].update(couverture=1.0))


def test_signal_incoherent_avec_la_couverture(audit, regenere):
    sym = _premier(regenere[1], lambda t: t["sig"] == "Couverture partielle")
    assert "signal.couverture" in audit(sym, lambda t: t.update(sig="ACHETER ★★"))
    ok = _premier(regenere[1], lambda t: t["sig"] in ("ACHETER ★★", "SURVEILLER ★"))
    assert "signal.couverture" in audit(ok, lambda t: t.update(sig="Couverture partielle"))


def test_signal_incoherent_avec_la_confiance(audit, regenere):
    sym = _premier(regenere[1], lambda t: t["sig"] == "Données insuffisantes" and t["_meta"]["confidence"] <= 1)
    assert "signal.confiance" in audit(sym, lambda t: t.update(sig="ÉVITER FORT"))
    assert "signal.sans_donnees" in audit(sym, lambda t: t.update(sig="ATTENDRE"))


def test_regle_a_signal_et_champ_non_comparables_vont_ensemble(audit, regenere):
    """Règle A (27/10/2026, accord R8) : un verdict sur un titre très peu liquide,
    un champ `_meta.non_comparable` effacé ou décalé, un libellé sans condition —
    chacun doit être refusé."""
    nc = "Non comparable (liquidité)"
    sym = _premier(regenere[1], lambda t: t["sig"] == nc)
    assert "signal.non_comparable" in audit(sym, lambda t: t.update(sig="SURVEILLER ★"))
    assert "signal.non_comparable_meta" in audit(sym, lambda t: t["_meta"].pop("non_comparable"))
    assert "signal.non_comparable_meta" in audit(
        sym, lambda t: t["_meta"]["non_comparable"].update(montant_median_dh=1))
    ok = _premier(regenere[1], lambda t: t["sig"] in ("ACHETER ★★", "SURVEILLER ★") and not t.get("technique_neutralise"))
    assert "signal.non_comparable" in audit(ok, lambda t: t.update(sig=nc))


def test_regle_b_fonciere_sans_note_metier(audit, regenere):
    """Règle B (27/10/2026) : foncière sans note par métier → « Couverture partielle »."""
    sym = _premier(regenere[1], lambda t: (t.get("note_fond_metier") or {}).get("famille") == "fonciere"
                   and (t.get("note_fond_metier") or {}).get("note") is None
                   and t["sig"] == "Couverture partielle")
    assert "signal.couverture" in audit(sym, lambda t: t.update(sig="ATTENDRE"))


def test_suspendu_sans_signal_suspendu(audit, regenere):
    sym = _premier(regenere[1], lambda t: t["_meta"].get("suspendu"))
    assert "signal.suspendu" in audit(sym, lambda t: t.update(sig="ATTENDRE"))


def test_v53_non_recomposable(audit, regenere):
    sym = _premier(regenere[1], lambda t: t["v53"] is not None and not t.get("bonus"))
    assert "v53.recomposition" in audit(sym, lambda t: t.update(v53=round(min(10.0, t["v53"] + 1.5), 2)))
    sans = _premier(regenere[1], lambda t: t["v53"] is None)
    assert "v53.sans_note" in audit(sans, lambda t: t.update(v53=5.0))


def test_confiance_mal_sommee(audit, regenere):
    sym = _premier(regenere[1], lambda t: t["_meta"]["confidence"] == 5)
    assert "confiance.somme" not in audit(sym, lambda t: None)

    def gonfle(t):
        t["_meta"]["garanties"][4]["ok"] = False          # une garantie tombe, la confiance reste
    assert "confiance.plafond_ignore" in audit(sym, gonfle)

    def sur_somme(t):
        t["_meta"]["garanties"] = [dict(g, ok=False) for g in t["_meta"]["garanties"]]
    assert "confiance.somme" in audit(sym, sur_somme)


def test_confiance_plus_basse_que_ses_garanties_sans_plafond(audit, regenere):
    sym = _premier(regenere[1], lambda t: t["_meta"]["confidence"] == 5)
    assert "confiance.plafond_inexplique" in audit(sym, lambda t: t["_meta"].update(confidence=3))


def test_garantie_qui_ment(audit, regenere):
    sym = _premier(regenere[1], lambda t: t["_meta"]["confidence"] == 5)
    def ment(t):
        t["_meta"]["stale"] = True
    assert "garantie.cours" in audit(sym, ment)


def test_grandeur_contestee_utilisee_dans_la_note(audit, regenere, entrees):
    fo, faits, _ = entrees
    contestes = A.contestations(fo, faits)
    sym = _premier(regenere[1], lambda t: t["symbol"] in contestes
                   and t["note_fond"]["composantes"]["qualite"]["note"] is None
                   and t["note_fond"]["composantes"]["bilan"]["note"] is None)
    def utilise(t):
        c = t["note_fond"]["composantes"]
        c["qualite"] = {"note": 8.5, "poids": 0.4, "mesure": "ROIC 20.2 % − WACC 10"}
        c["bilan"] = {"note": 7.0, "poids": 0.1, "mesure": "dette nette / EBITDA 0.95"}
    levees = audit(sym, utilise)
    assert "contestee.mesuree" in levees and "contestee.mesure_citee" in levees


def test_alerte_sur_grandeur_contestee(audit, regenere, entrees):
    fo, faits, _ = entrees
    contestes = A.contestations(fo, faits)
    sym = sorted(contestes)[0]
    def alerte(t):
        t["alertes"]["liste"].append({"niveau": "critique", "theme": "Structure financière",
                                      "raison": "Dette nette très élevée", "valeur": "5.5× l'EBITDA",
                                      "seuil": "alerte au-delà de 4×", "source": "calculé sur les comptes publiés",
                                      "date": "2025-12-31"})
    levees = audit(sym, alerte)
    assert "contestee.alerte" in levees and "alertes.recalcul" in levees


def test_alerte_incomplete_ou_sans_date(audit, regenere):
    sym = _premier(regenere[1], lambda t: t["alertes"]["liste"])
    assert "alerte.champs" in audit(sym, lambda t: t["alertes"]["liste"][0].pop("seuil"))
    assert "alerte.date" in audit(sym, lambda t: t["alertes"]["liste"][0].pop("date"))
    assert "alerte.champs" in audit(sym, lambda t: t["alertes"]["liste"][0].update(source=""))


def test_alerte_qui_ne_dit_pas_comme_la_note(audit, regenere):
    sym = _premier(regenere[1], lambda t: any(a["raison"].startswith("Dette nette") for a in t["alertes"]["liste"]))
    def autre_chiffre(t):
        for a in t["alertes"]["liste"]:
            if a["raison"].startswith("Dette nette"):
                a["valeur"] = "9.99× l'EBITDA"
    levees = audit(sym, autre_chiffre)
    assert "alertes.recalcul" in levees and "alerte.vs_note" in levees


def test_meta_absent(audit, regenere):
    assert "meta.absent" in audit(regenere[1]["tickers"][0]["symbol"], lambda t: t.pop("_meta"))


# ═══ 4. L'affichage, vérifié STATIQUEMENT ═══════════════════════════════════
# ⚠️ LIMITE : ces contrôles lisent du texte. Ils prouvent que les composants ne
# lisent que les champs publiés ; ils ne prouvent pas que l'écran se rend.

SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def _erreurs_affichage(src):
    return [i for i in A.auditer_affichage(src) if i["gravite"] == A.ERREUR]


def test_le_terminal_ne_lit_que_les_champs_publies():
    assert _erreurs_affichage(SRC) == []


def test_les_cinq_composants_sont_trouves_et_lisent_note_fond():
    for nom in A.COMPOSANTS_AFFICHAGE:
        assert A._corps(SRC, nom), nom
    assert "r.note_fond" in A._corps(SRC, "ResumeNote") and "r.note_fond" in A._corps(SRC, "PourquoiNote")


def test_un_composant_qui_lit_une_seconde_source_est_refuse():
    corps = A._corps(SRC, "PourquoiNote")
    faux = SRC.replace(corps, corps.replace("r.note_fond", "r.note_fond_metier", 1))
    assert any(i["controle"] == "affichage.seconde_source" for i in _erreurs_affichage(faux))


def test_un_champ_hors_liste_est_refuse():
    corps = A._corps(SRC, "ResumeNote")
    faux = SRC.replace(corps, corps.replace("const dfr=", "const x=r.score_nlp;const dfr=", 1))
    assert any(i["controle"] == "affichage.champ_hors_liste" for i in _erreurs_affichage(faux))


def test_le_transport_data_json_vers_la_fiche_est_surveille():
    faux = SRC.replace("note_fond:t.note_fond,", "note_fond:t.note_fond_metier,")
    assert any(i["controle"] == "affichage.transport" for i in _erreurs_affichage(faux))


def test_le_seuil_de_couverture_affiche_suit_la_config(monkeypatch):
    import bvc_config
    monkeypatch.setattr(bvc_config, "COUVERTURE_VERDICT_MIN", 0.80)
    assert any(i["controle"] == "affichage.seuil" for i in A.auditer_affichage(SRC, bvc_config))


def test_le_seuil_de_non_comparabilite_affiche_suit_la_config(monkeypatch):
    import bvc_config
    monkeypatch.setattr(bvc_config, "SEUIL_NON_COMPARABLE_DH", 150_000)
    assert any(i["controle"] == "affichage.seuil" for i in A.auditer_affichage(SRC, bvc_config))
    faux = SRC.replace("m.non_comparable", "m.autre_champ")
    assert any(i["controle"] == "affichage.non_comparable" for i in _erreurs_affichage(faux))


# ═══ 5. Le code de l'audit lui-même ═════════════════════════════════════════

def test_per_identique_a_celui_du_moteur(ud):
    for p, b in [(90.98, 6.07), (100, 0), (100, -3), (None, 5), (0, 5), (33.4, 2.7)]:
        assert A._per(p, b) == ud._per(p, b)


def test_contestations_identiques_a_celles_du_moteur(entrees):
    from pipeline.smart_money import fond_score as F
    fo, faits, _ = entrees
    avant = dict(F.CONTESTES)
    attendu = A.contestations(fo, faits)
    assert F.CONTESTES == avant, "l'audit ne doit pas toucher au registre du moteur"
    try:
        assert F.charger_contestations(fo, faits) == attendu
    finally:
        F.CONTESTES.clear()
        F.CONTESTES.update(avant)


def test_l_audit_restaure_le_registre_des_contestations(regenere, entrees):
    from pipeline.smart_money import fond_score as F
    _, data = regenere
    fo, faits, bpa = entrees
    F.CONTESTES["ZZZ"] = "sentinelle"
    try:
        A.auditer({"tickers": data["tickers"][:5]}, fo, faits, bpa)
        assert F.CONTESTES == {"ZZZ": "sentinelle"}
    finally:
        F.CONTESTES.pop("ZZZ", None)


def test_cli_code_de_sortie_et_json(regenere, tmp_path):
    dossier, data = regenere
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, str(RACINE / "tools" / "audit_chaine.py"), "--racine", str(dossier),
                        "--data", str(ok), "--json"], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-1500:]
    assert json.loads(r.stdout)["erreurs"] == 0

    mauvais = copy.deepcopy(data)
    mauvais["tickers"][0]["note_fond"]["note"] = 9.99
    ko = tmp_path / "ko.json"
    ko.write_text(json.dumps(mauvais, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, str(RACINE / "tools" / "audit_chaine.py"), "--racine", str(dossier),
                        "--data", str(ko), "--json"], capture_output=True, text=True, timeout=300)
    assert r.returncode == 1
    sortie = json.loads(r.stdout)
    assert sortie["erreurs"] >= 1 and sortie["incoherences"][0]["titre"] == mauvais["tickers"][0]["symbol"]


def test_l_audit_n_ecrit_rien(regenere):
    import hashlib
    dossier, _ = regenere
    avant = {p: hashlib.sha256((dossier / p).read_bytes()).hexdigest()
             for p in ("data.json", "fondamentaux.json", "bpa.json")}
    subprocess.run([sys.executable, str(RACINE / "tools" / "audit_chaine.py"), "--racine", str(dossier),
                    "--data", str(dossier / "regenere.json")], capture_output=True, text=True, timeout=300)
    assert avant == {p: hashlib.sha256((dossier / p).read_bytes()).hexdigest() for p in avant}


# ═══ 6. Défaut LATENT trouvé par l'audit (code, pas données) ════════════════

@pytest.mark.xfail(strict=True, reason=(
    "DÉFAUT LATENT, établi le 16/10/2026 : l'alerte de surchauffe RSI n'a pas de `date`, et le terminal écrit "
    "« comptes au <date de l'alerte> » (ResumeNote) : « comptes au date inconnue » pour un chiffre calculé sur "
    "nos chandelles. Invisible aujourd'hui (aucun RSI > seuil dans data.json). Corriger = donner une date à "
    "l'alerte (séance du dernier cours) et un libellé qui ne dise pas « comptes »."))
def test_l_alerte_rsi_porte_sa_date(ud):
    f = json.loads((RACINE / "fondamentaux.json").read_text(encoding="utf-8"))["ADI"]
    liste = ud.detecter_alertes(f, 85.0, "ADI")["liste"]
    rsi = [a for a in liste if a["theme"] == "Technique"]
    assert rsi, "l'alerte RSI devait se déclencher à RSI 85"
    assert rsi[0].get("date")

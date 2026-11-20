"""Cours de séance dits comme tels — feuille de route 9/10, lot 1.2 (20/11/2026).

« Pendant la séance : « Cours de séance · 14h56 · différé » ; après la
clôture : « Clôture du JJ/MM ». Critère : plus aucun « J+1 » ni « clôture »
sur un cours de séance. »

Constat d'origine (mesuré au navigateur, horloge simulée, data.json du 20/11
relevé à 09h55) : la fiche disait « relevé à 09h55, séance en cours » à 15h45
et le samedi encore — l'heure du relevé était lue, pas l'horloge ; la légende
du graphique marquait « C » (clôture) sur la bougie d'un cours de 9h55 ; le
guide écrivait « Données J+1 ».

Règle : UNE fonction, `libelleCours(meta, generated_at, maintenant)`, qui
croise trois sources — la date du cours (`_meta.prix_asof`), l'heure du
relevé (`generated_at`) et l'horloge de Casablanca (lundi–vendredi,
9h30–15h30, registre DECALAGES_MAROC) :
- séance ouverte, cours du jour relevé pendant la séance → « Cours de séance
  · HHhMM · différé » ;
- cours relevé pendant sa séance, séance close, clôture pas encore publiée →
  « Cours de séance du JJ/MM · HHhMM · clôture non publiée » (jamais
  « Clôture du ») ;
- sinon (relevé à partir de 15h30, week-end, férié, cours périmé) →
  « Clôture du JJ/MM », date DU COURS.

Affichage seulement : ni moteur, ni données, ni Score BVC. Le texte des
garanties de la fiabilité vient du moteur (`_meta.garanties`) et reste tel
quel ; le terminal ajoute dessous la précision.

Contrôle négatif : sur origin/main (avant ce lot), `libelleCours` n'existe
pas et ce fichier échoue.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
SRC = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
COMPILE = (RACINE / "index.html").read_text(encoding="utf-8")


def _entre(s: str, debut: str, fin: str) -> str:
    i = s.index(debut)
    return s[i:s.index(fin, i)]


def _sans_commentaires(s: str) -> str:
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    s = re.sub(r"\{/\*.*?\*/\}", " ", s, flags=re.S)
    return re.sub(r"(?<![:\"'])//[^\n]*", " ", s)


def _composant(nom: str) -> str:
    i = SRC.index(f"const {nom}=")
    j = SRC.find("\nconst ", i + 1)
    return _sans_commentaires(SRC[i:j if j > 0 else len(SRC)])


def _executer(appels: str):
    if not shutil.which("node"):
        pytest.skip("node absent")
    horloge = _entre(SRC, "const DECALAGES_MAROC=", "async function fetchChart")
    fonctions = _entre(SRC, "function horodatage(iso)", "\n// ── MASI INDEX")
    garantie = _entre(SRC, "const precisionGarantie=", "const DetailConfiance=")
    code = horloge + fonctions + garantie + "\nconsole.log(JSON.stringify(" + appels + "));"
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _lc(asof, releve, maintenant, stale=False):
    a = "null" if asof is None else f'"{asof}"'
    return (f'libelleCours({{prix_asof:{a},stale:{str(stale).lower()}}},'
            f'"{releve}",new Date("{maintenant}"))')


# Maroc à UTC+0 depuis le 20/09/2026 : en novembre, heure UTC = heure de Casablanca.
CAS = {
    # séance ouverte, cours du jour relevé à 09h55 (le data.json du 20/11)
    "seance_ouverte": (("2026-11-20", "2026-11-20T09:55:38+00:00", "2026-11-20T11:00:00Z"),
                       "seance", "Cours de séance · 09h55 · différé"),
    # 15h45 : la séance est close, le passage de clôture n'est pas publié
    "close_sans_cloture": (("2026-11-20", "2026-11-20T09:55:38+00:00", "2026-11-20T15:45:00Z"),
                           "attente", "Cours de séance du 20/11 · 09h55 · clôture non publiée"),
    # relevé du jour fait après 15h30
    "releve_apres_1530": (("2026-11-20", "2026-11-20T15:52:00+00:00", "2026-11-20T16:10:00Z"),
                          "cloture", "Clôture du 20/11"),
    # relevé pile à 15h30 : déjà la clôture
    "releve_a_1530": (("2026-11-20", "2026-11-20T15:30:00+00:00", "2026-11-20T15:31:00Z"),
                      "cloture", "Clôture du 20/11"),
    # samedi, données du vendredi soir
    "week_end": (("2026-11-20", "2026-11-20T18:05:00+00:00", "2026-11-21T11:00:00Z"),
                 "cloture", "Clôture du 20/11"),
    # samedi, le dernier passage publié est celui de 09h55 : pas une clôture,
    # mais plus un cours « différé » de séance ouverte non plus
    "week_end_sans_cloture": (("2026-11-20", "2026-11-20T09:55:00+00:00", "2026-11-21T11:00:00Z"),
                              "attente", "Cours de séance du 20/11 · 09h55 · clôture non publiée"),
    # 18/11 (fête de l'Indépendance), en pleine heure de séance : un relevé
    # du jour qui porte le cours du 17/11
    "ferie": (("2026-11-17", "2026-11-18T10:00:00+00:00", "2026-11-18T11:00:00Z"),
              "cloture", "Clôture du 17/11"),
    # cours périmé en pleine séance : clôture de SA date
    "perime": (("2026-11-19", "2026-11-20T09:55:38+00:00", "2026-11-20T11:00:00Z", True),
               "cloture", "Clôture du 19/11"),
    # avant l'ouverture, données de la veille au soir
    "avant_ouverture": (("2026-11-19", "2026-11-19T18:05:00+00:00", "2026-11-20T09:00:00Z"),
                        "cloture", "Clôture du 19/11"),
    # heure d'été (UTC+1, registre DECALAGES_MAROC) : 09h30 UTC = 10h30
    "heure_d_ete": (("2026-07-10", "2026-07-10T09:30:00Z", "2026-07-10T10:00:00Z"),
                    "seance", "Cours de séance · 10h30 · différé"),
    # sans date de cours
    "date_inconnue": ((None, "2026-11-20T09:55:38+00:00", "2026-11-20T11:00:00Z"),
                      "inconnu", "Date du cours inconnue"),
}


@pytest.fixture(scope="module")
def resultats():
    noms = list(CAS)
    r = _executer("[" + ",".join(_lc(*CAS[n][0]) for n in noms) + "]")
    return dict(zip(noms, r))


@pytest.mark.parametrize("nom", list(CAS))
def test_libelle_par_cas(resultats, nom):
    _, etat, texte = CAS[nom]
    assert resultats[nom]["etat"] == etat, resultats[nom]
    assert resultats[nom]["texte"] == texte


def test_jamais_cloture_ni_j1_sur_un_cours_de_seance(resultats):
    """Le critère du lot : un cours relevé pendant sa séance ne se dit jamais
    « Clôture du » ni « J+1 », sous aucune de ses formes."""
    for nom, x in resultats.items():
        if x["etat"] in ("seance", "attente"):
            for forme in ("texte", "complet", "court"):
                assert not x[forme].startswith("Clôture"), (nom, forme, x[forme])
                assert "clôture du" not in x[forme].lower(), (nom, forme, x[forme])
                assert "J+1" not in x[forme], (nom, forme, x[forme])
            assert "différé" in x["texte"] or "clôture non publiée" in x["texte"]


def test_la_fiche_garde_l_annee(resultats):
    assert resultats["seance_ouverte"]["complet"] == "Cours de séance du 20/11/2026 · 09h55 · différé"
    assert resultats["week_end"]["complet"] == "Clôture du 20/11/2026"


def test_trois_sources_jamais_une_seule():
    """Même horloge et même relevé, une date de cours différente change le
    libellé ; même date et même relevé, l'horloge le change aussi."""
    r = _executer("[" + ",".join([
        _lc("2026-11-20", "2026-11-20T10:00:00Z", "2026-11-20T11:00:00Z"),
        _lc("2026-11-19", "2026-11-20T10:00:00Z", "2026-11-20T11:00:00Z"),
        _lc("2026-11-20", "2026-11-20T10:00:00Z", "2026-11-20T15:40:00Z"),
        _lc("2026-11-20", "2026-11-20T15:35:00Z", "2026-11-20T15:40:00Z"),
    ]) + "]")
    assert [x["etat"] for x in r] == ["seance", "cloture", "attente", "cloture"]


def test_libelle_du_marche_sur_la_derniere_seance_cotee():
    """Bandeau et en-tête du classement : la plus récente des dates de cours,
    et l'heure du relevé la plus récente si data.json n'en donne pas."""
    lignes = json.dumps([
        {"_meta": {"prix_asof": "2026-11-19", "stale": True, "generated_at": "2026-11-20T09:55:38+00:00"}},
        {"_meta": {"prix_asof": "2026-11-20", "stale": False, "generated_at": "2026-11-20T09:55:38+00:00"}},
        {},
    ])
    r = _executer(f'[derniereSeance({lignes}),libelleMarche({lignes},null,new Date("2026-11-20T11:00:00Z")).texte,'
                  f'libelleMarche([],null,new Date())]')
    assert r == ["2026-11-20", "Cours de séance · 09h55 · différé", None]


# ── Une seule fonction, branchée partout ────────────────────────────────────

def test_une_seule_fonction_pour_dater_un_cours():
    code = _sans_commentaires(SRC)
    assert code.count("function libelleCours(") == 1
    for ancien in ("etatSeance(", "heureReleve", "dernière valeur relevée à ${h}",
                   "relevé à {h}, séance en cours", "cours de clôture du ${jjmm(m.asof)}"):
        assert ancien not in code, ancien
    assert "const coursDe=r=>{const m=meta(r);return libelleCours(m,m.generated_at,new Date());};" in code


def test_bandeau():
    entete = _sans_commentaires(_entre(SRC, "const Header=(", "\n};\n"))
    assert "libelleCours({prix_asof:seance||masi.asof},ts,new Date())" in entete
    assert "{lc.texte}" in entete and 'id="cours_seance"' in entete
    assert "seance={seanceCotee}" in SRC and "derniereSeance(rows)" in SRC


def test_fiche_en_bref():
    f = _composant("EnTeteEssentiel")
    assert "const lc=coursDe(r);" in f and "{lc.complet}" in f
    assert 'prefixe={lc.etat==="cloture"?"clôture du ":"cours du "}' in f
    assert "heureCours(r)" in f                      # le survol suit la même règle
    assert "const heureCours=r=>coursDe(r).complet;" in SRC


def test_classement():
    c = _sans_commentaires(_entre(SRC, "const Ranking=(", "\n// ──"))
    assert "libelleMarche(rows,null,new Date())" in c
    assert '<Terme id="cours_seance">{lcMarche.court}</Terme>' in c


def test_legende_du_graphique():
    """La dernière bougie d'un cours de séance n'a pas de clôture : « C »
    devient « Dernier » et le libellé est écrit sous la légende."""
    code = _sans_commentaires(SRC)
    assert 'lab(enSeance?"Dernier":"C")' in code
    assert "const lc=coursDe(r),enSeance=k===n-1&&" in code
    assert "${lc.texte}</div>" in code


def test_garanties_texte_du_moteur_inchange_precision_dessous():
    """Le critère vient d'update_data.py (_meta.garanties) : rendu tel quel
    ({x.critere}). La précision du terminal suit libelleCours."""
    d = _composant("DetailConfiance")
    assert "{x.critere}" in d and "precisionGarantie(x.critere,lc)" in d
    moteur = (RACINE / "update_data.py").read_text(encoding="utf-8")
    assert '("Cours de la dernière séance cotée", not stale)' in moteur
    r = _executer('[precisionGarantie("Cours de la dernière séance cotée",'
                  + _lc("2026-11-20", "2026-11-20T09:55:38+00:00", "2026-11-20T11:00:00Z") + '),'
                  'precisionGarantie("Cours de la dernière séance cotée",'
                  + _lc("2026-11-20", "2026-11-20T09:55:38+00:00", "2026-11-20T15:45:00Z") + '),'
                  'precisionGarantie("Cours de la dernière séance cotée",'
                  + _lc("2026-11-20", "2026-11-20T15:52:00+00:00", "2026-11-20T16:10:00Z") + '),'
                  'precisionGarantie("Comptes déposés à l\'AMMC et relevés",'
                  + _lc("2026-11-20", "2026-11-20T09:55:38+00:00", "2026-11-20T11:00:00Z") + ')]')
    assert r == ["cours de la séance, relevé à 09h55 (différé)",
                 "cours de la séance du 20/11, relevé à 09h55 : clôture non publiée", None, None]


# ── Glossaire et guide ──────────────────────────────────────────────────────

def test_une_entree_du_glossaire_sans_doublon():
    g = _entre(SRC, "const GLOSSAIRE={", "\n};\n")
    assert g.count("cours_seance:{") == 1
    e = re.search(r'cours_seance:\{g:"(\w+)",terme:"([^"]+)",def:"([^"]+)"\}', g)
    assert e and e.group(1) == "seance"
    assert "Cours de séance" in e.group(2) and "Clôture" in e.group(2)
    d = e.group(3)
    for mot in ("9h30", "15h30", "Casablanca", "différé", "clôture"):
        assert mot in d, mot
    # la définition n'est écrite qu'une fois dans tout le source
    assert SRC.count(d) == 1


def test_le_guide_ne_dit_plus_donnees_j1():
    code = _sans_commentaires(SRC)
    assert "Données J+1" not in code
    assert "« Cours de séance · HHhMM · différé »" in code and "« Clôture du JJ/MM »" in code


# ── Compilation ─────────────────────────────────────────────────────────────

def test_index_compile_a_jour():
    for x in ("function libelleCours(", "precisionGarantie", "cours_seance"):
        assert x in COMPILE, x
    assert "Donn\\xE9es J+1" not in COMPILE and "Données J+1" not in COMPILE

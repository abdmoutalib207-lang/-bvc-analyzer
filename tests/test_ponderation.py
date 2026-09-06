"""WeightEngine : les deux régimes de marché qui n'ont jamais pu s'activer.

Signalé par l'audit externe du 05/09/2026, puis vérifié dans le code avant
toute correction :

    update_data.py:1981    "masi_ytd":  masi["chg"]      ← variation DU JOUR
    update_data.py:1560    if masi_ytd < -5:  ...        ← seuil ANNUEL
    update_data.py:1980    "has_results": False          ← figé, jamais vrai

Les seuils de -5 % et +10 % décrivent une performance depuis le 1er janvier.
La variation d'une séance vaut typiquement ±1 % et la BVC la plafonne à ±10 %
par titre. Le mode défensif de marché baissier ne pouvait donc s'armer que le
jour d'un krach de l'indice entier, et le mode haussier jamais. Ces deux
régimes étaient du code mort depuis l'origine du projet.

⚠️ CE QUE CE CORRECTIF NE FAIT PAS. Il ne calcule pas le vrai YTD : le projet
ne conservait aucun historique de l'indice. `pipeline/masi_history.py`
commence à l'enregistrer, et `performance_ytd()` répond `None` tant que la
série ne remonte pas à la clôture de l'année précédente. `None` neutralise le
bloc — ce qui est la bonne réponse à « nous ne savons pas ». Un `0` aurait
affirmé « marché plat ».

⚠️ R8 — la formule 47/28/25 n'est pas touchée. C'est l'entrée du moteur qui
était fausse, pas la pondération.
"""

import json

from update_data import get_weights
from masi_history import enregistrer, performance_ytd, profondeur, MIN_SEANCES

BASE = {"technique": 0.25, "fondamental": 0.47, "comportemental": 0.28}


# ── get_weights ──────────────────────────────────────────────────────────

def test_masi_ytd_inconnu_ne_change_rien():
    """`None` doit neutraliser le bloc, pas se comporter comme un zéro."""
    assert get_weights({"masi_ytd": None}) == get_weights({})


def test_masi_ytd_absent_vaut_inconnu():
    """Ne pas fournir la clé revient à dire « je ne sais pas »."""
    assert get_weights({}) == get_weights({"masi_ytd": None})


def test_marche_baissier_arme_le_mode_defensif():
    """Le régime qui n'a jamais pu s'activer doit s'activer.

    Avec l'ancienne alimentation, `masi_ytd` valait la variation du jour :
    atteindre -5 % aurait demandé que l'indice entier perde 5 % en une séance.
    """
    w = get_weights({"masi_ytd": -12.0})
    assert w["fondamental"] > BASE["fondamental"]
    assert w["comportemental"] < BASE["comportemental"]


def test_marche_haussier_favorise_le_technique():
    w = get_weights({"masi_ytd": 18.0})
    assert w["technique"] > BASE["technique"]


def test_les_seuils_sont_annuels_pas_quotidiens():
    """Une variation de séance plausible ne doit armer aucun régime.

    C'est le cœur du défaut : ±1 % un jour ordinaire, et la BVC plafonne de
    toute façon à ±10 % par titre. Passer ces valeurs comme si elles étaient
    annuelles rendait les deux régimes inatteignables.
    """
    neutre = get_weights({"masi_ytd": None})
    for variation_du_jour in (-1.04, -0.3, 0.0, 0.44, 1.9, 4.9):
        assert get_weights({"masi_ytd": variation_du_jour}) == neutre


def test_les_poids_somment_toujours_a_un():
    for ctx in ({}, {"masi_ytd": -30.0}, {"masi_ytd": 40.0},
                {"has_results": True}, {"hype_spike": True, "masi_ytd": -9.0},
                {"smart_money_active": True, "ticker_coverage": 12}):
        assert abs(sum(get_weights(ctx).values()) - 1.0) < 1e-6


def test_le_bloc_resultats_reste_fonctionnel():
    """Il n'est plus alimenté, mais il ne doit pas être cassé pour autant.

    `has_results` n'est branché sur aucun calendrier — l'ancien `False` écrit
    en dur faisait passer cette absence pour une décision. Le jour où un
    calendrier existera, ce test garantit que la branche répond encore.
    """
    assert get_weights({"has_results": True})["fondamental"] > BASE["fondamental"]


# ── masi_history ─────────────────────────────────────────────────────────

def _fichier(tmp_path):
    return tmp_path / "masi_history.json"


def test_une_seance_deja_connue_n_est_pas_reecrite(tmp_path):
    """L'indice de midi ne doit pas remplacer celui déjà enregistré.

    Quatre runs par jour ouvré déposent la même date. Sans cette garde, la
    dernière valeur écrite gagnerait — y compris celle d'un run de milieu de
    séance. C'est exactement le défaut corrigé le 10/08 sur les bougies.
    """
    f = _fichier(tmp_path)
    assert enregistrer(18710.31, "2026-09-03", f) is True
    assert enregistrer(18999.99, "2026-09-03", f) is False
    assert json.loads(f.read_text())["seances"]["2026-09-03"] == 18710.31


def test_valeurs_aberrantes_refusees(tmp_path):
    f = _fichier(tmp_path)
    for v, d in ((0, "2026-09-03"), (-1, "2026-09-03"), (None, "2026-09-03"),
                 ("x", "2026-09-03"), (18000, ""), (18000, "2026")):
        assert enregistrer(v, d, f) is False
    assert profondeur(f) == 0


def test_ytd_indisponible_sans_ancrage_sur_l_annee_precedente(tmp_path):
    """Sans clôture de l'an passé, il n'y a rien depuis quoi mesurer.

    C'est l'état réel du projet au 05/09/2026 : la série commence
    aujourd'hui, donc le YTD reste `None` jusqu'en janvier prochain — ou
    jusqu'à ce qu'on saisisse une clôture d'ancrage datée et sourcée.
    """
    f = _fichier(tmp_path)
    for i in range(1, 21):
        enregistrer(18000 + i, f"2026-09-{i:02d}", f)
    assert profondeur(f) == 20
    assert performance_ytd("2026-09-20", f) is None


def test_ytd_indisponible_si_la_serie_est_trop_courte(tmp_path):
    f = _fichier(tmp_path)
    enregistrer(15000, "2025-12-31", f)
    for i in range(1, MIN_SEANCES):
        enregistrer(16000, f"2026-01-{i:02d}", f)
    assert performance_ytd("2026-01-09", f) is None


def test_ytd_calcule_quand_l_ancrage_existe(tmp_path):
    """+20 % depuis la clôture du 31/12, et c'est bien ce qui doit sortir."""
    f = _fichier(tmp_path)
    enregistrer(15000, "2025-12-31", f)
    for i in range(1, 16):
        enregistrer(18000, f"2026-01-{i:02d}", f)
    assert performance_ytd("2026-01-15", f) == 20.0


def test_ytd_ignore_les_seances_posterieures_a_la_date_demandee(tmp_path):
    """Pas de regard sur le futur : un backtest doit rester honnête."""
    f = _fichier(tmp_path)
    enregistrer(15000, "2025-12-31", f)
    for i in range(1, 16):
        enregistrer(16500, f"2026-01-{i:02d}", f)
    enregistrer(30000, "2026-02-01", f)
    assert performance_ytd("2026-01-15", f) == 10.0


def test_fichier_absent_ne_plante_pas(tmp_path):
    assert performance_ytd("2026-09-05", tmp_path / "rien.json") is None
    assert profondeur(tmp_path / "rien.json") == 0


def test_import_ne_recouvre_jamais_une_seance_deja_connue(tmp_path):
    """⚠️ Une source extérieure ne doit pas contredire en silence notre mesure.

    L'import est rejouable, et une divergence entre investing.com et notre
    chaîne doit se voir plutôt que se résoudre par ordre d'écriture. C'est la
    même règle que le cliquet de séance du 28/08 : ce qu'on sait déjà ne se
    laisse pas remplacer sans arbitrage explicite.
    """
    from masi_history import importer
    f = _fichier(tmp_path)
    enregistrer(18710.3128, "2026-09-03", f)
    n = importer({"2026-09-03": 99999.0, "2026-09-04": 18792.25},
                 source="test", chemin=f)
    assert n == 1, "seule la date inconnue doit entrer"
    seances = json.loads(f.read_text())["seances"]
    assert seances["2026-09-03"] == 18710.3128
    assert seances["2026-09-04"] == 18792.25


def test_import_journalise_sa_provenance(tmp_path):
    """Toute valeur importée doit pouvoir être rattachée à sa source."""
    from masi_history import importer
    f = _fichier(tmp_path)
    importer({"2026-09-03": 18710.31, "2026-09-04": 18792.25},
             source="investing.com", url="https://exemple", chemin=f)
    ap = json.loads(f.read_text())["_apports"]
    assert ap[0]["source"] == "investing.com" and ap[0]["n"] == 2
    assert ap[0]["depuis"] == "2026-09-03" and ap[0]["jusqu_au"] == "2026-09-04"


def test_import_ecarte_les_valeurs_inutilisables(tmp_path):
    from masi_history import importer
    f = _fichier(tmp_path)
    n = importer({"2026-09-04": 18792.25, "2026-09-05": 0, "2026-09-06": None,
                  "2026-09-07": "x", "mauvaise": 18000}, source="test", chemin=f)
    assert n == 1


# ── le fichier versionné lui-même ────────────────────────────────────────

def test_historique_masi_versionne_est_sain():
    """Contrôle du fichier réellement livré, pas d'un cas fabriqué.

    Il porte des valeurs venues d'une source extérieure : elles doivent
    rester vérifiables. Un saut de plus de 10 % en une séance sur l'INDICE
    serait extraordinaire — la BVC plafonne déjà chaque titre à ±10 % (R10),
    et l'indice est une moyenne pondérée : il ne peut pas bouger plus que ses
    composantes. Un tel saut signalerait une valeur corrompue à l'import.
    """
    from datetime import date
    from pathlib import Path
    chemin = Path(__file__).resolve().parent.parent / "pipeline" / "masi_history.json"
    if not chemin.exists():
        return  # la série se construit ; son absence n'est pas une régression
    d = json.loads(chemin.read_text(encoding="utf-8"))
    seances = d["seances"]
    assert seances, "fichier présent mais vide"
    assert d.get("_apports"), "toute valeur doit être rattachable à son apport"

    jours = sorted(seances)
    for j in jours:
        assert len(j) == 10 and j[4] == "-" and j[7] == "-", f"date mal formée : {j}"
        assert float(seances[j]) > 0, f"valeur non positive au {j}"

    def _d(s):
        a, m, jj = (int(x) for x in s.split("-"))
        return date(a, m, jj)

    for prec, suiv in zip(jours, jours[1:]):
        if (_d(suiv) - _d(prec)).days > 4:
            continue  # trou assumé dans la série, pas deux séances voisines
        var = abs(seances[suiv] / seances[prec] - 1) * 100
        assert var <= 10, f"saut de {var:.1f} % entre {prec} et {suiv}"


def test_le_ytd_reste_plausible_ou_indisponible():
    """Si l'ancrage existe, la performance annuelle doit rester crédible.

    Ce test ne fixe pas une valeur — elle bouge chaque jour. Il vérifie que
    le calcul ne produit pas d'aberration, et qu'il répond `None` plutôt
    qu'un nombre douteux quand la série ne le permet pas.
    """
    from datetime import date
    y = performance_ytd(date.today().isoformat())
    assert y is None or -80 < y < 200, f"YTD aberrant : {y}"

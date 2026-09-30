"""« À surveiller aujourd'hui » : des critères mesurés, pas des poids — 30/09/2026.

Les attendus sont écrits à la main ; aucun n'est produit par la fonction testée.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.briefing import a_surveiller  # noqa: E402

S = "2026-09-29"


def _t(sym, chg=0.0, cote=True, stale=False, **kw):
    x = {"symbol": sym, "name": sym, "chg": chg, "price": 100.0,
         "echange_dh": kw.pop("dh", 1000.0),
         "_meta": {"prix_asof": S if cote else "2026-09-28", "stale": stale}}
    x.update(kw)
    return x


def _tous(r):
    return {z["symbol"]: z for z in r["a_publie"] + r["a_bouge"]}


def test_un_titre_sans_critere_n_entre_pas():
    r = a_surveiller({}, [_t("AAA", 0.2)], S)
    # Seule hausse de la séance : il entre par la variation, et par elle seule.
    assert [c["code"] for c in _tous(r)["AAA"]["criteres"]] == ["variation"]
    r = a_surveiller({}, [_t("AAA", 0.0)], S)
    assert _tous(r) == {}


def test_une_forte_variation_sans_actualite_entre():
    titres = [_t("GROS", 5.96)] + [_t(f"T{i}", 0.1 * i) for i in range(1, 6)]
    r = a_surveiller({}, titres, S)
    assert "GROS" in _tous(r)


def test_un_titre_qui_n_a_pas_cote_ne_bouge_jamais():
    # Rediffusion (famille 24) : daté de la séance mais déclaré périmé.
    titres = [_t("FANT", 9.0, stale=True), _t("VRAI", 1.0)]
    r = a_surveiller({}, titres, S)
    assert "FANT" not in _tous(r)


def test_une_publication_entre_meme_sans_cotation():
    b = {"depots": {"titres": [{"ticker": "PUB", "url": "u"}]}}
    r = a_surveiller(b, [_t("PUB", cote=False)], S)
    z = _tous(r)["PUB"]
    assert r["a_publie"][0]["symbol"] == "PUB"
    assert z["cote"] is False and z["chg"] is None
    assert z["criteres"][0]["url"] == "u"


def test_le_seuil_est_celui_du_titre_pas_dix_pour_cent():
    # Référence 1 091 ; seuils publiés à ±6 % : 1 156 / 1 026.
    x = _t("OUL", 5.96, price=1156.0, reference=1091.0,
           seuil_haut=1156.0, seuil_bas=1026.0)
    r = a_surveiller({}, [x], S)
    textes = [c["texte"] for c in _tous(r)["OUL"]["criteres"]]
    assert "au seuil haut de la séance (+6 %)" in textes


def test_rang_par_nombre_de_criteres_puis_montant():
    b = {"volumes": [{"symbol": "DEUX", "facteur": 4.0}]}
    titres = [_t("UN", 3.0, dh=9e9), _t("DEUX", 2.0, dh=1.0)]
    r = a_surveiller(b, titres, S)
    # DEUX : volume + variation (2 critères) passe devant UN (1 critère),
    # malgré un montant échangé bien moindre.
    assert [z["symbol"] for z in r["a_bouge"]][:2] == ["DEUX", "UN"]


def test_la_liste_est_courte():
    titres = [_t(f"T{i}", 1.0 + i) for i in range(20)]
    b = {"volumes": [{"symbol": f"T{i}", "facteur": 3.5} for i in range(20)]}
    r = a_surveiller(b, titres, S)
    assert len(r["a_publie"]) + len(r["a_bouge"]) == 8
    assert r["n_candidats"] == 20

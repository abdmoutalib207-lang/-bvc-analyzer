"""La note ne dépend pas de l'heure du run — 03/11/2026, accord R8 d'Abd Moutalib.

CE QUI ÉTAIT FAUX
─────────────────
`get_weights()` ajoutait +0,05 au fondamental et −0,05 au technique quand
`market_status` valait CLOSED ou PRE_MARKET. Constaté sur MNG suspendu, aucune
donnée ne bougeant (cours 1 490, fond 7,2, tech 5,2) : v53 = 6,63 aux runs en
séance et 6,76 aux runs après clôture, les 30/10 et 02/11. Même situation,
deux notes, selon l'horloge.

DÉCISION : la pondération « marché fermé » — celle du bulletin J+1 du soir —
s'applique partout. La note du soir ne change pas ; celles des runs en séance
s'y alignent. Mesuré par quatre essais à blanc simultanés (main / branche ×
séance / fermé) : fermé 80/80 identiques ; en séance, la branche rend
exactement la note du soir de main sur 80/80.

Ce test est une INVARIANCE : même entrée, statut ouvert ou fermé → mêmes
poids et même note. Il ne fige aucun chiffre, sauf la base, qui est la
décision elle-même.
"""
import itertools

import pytest

import update_data as u

STATUTS = ["OPEN", "CLOSED", "PRE_MARKET", None]

# Les modulateurs qui restent : chacun seul et combinés.
MODULATEURS = [
    {},
    {"masi_ytd": -6.0},
    {"masi_ytd": 11.0},
    {"masi_ytd": 2.0},
    {"has_results": True},
    {"tech_non_fiable": {"motif": "fixing"}},
    {"masi_ytd": -6.0, "has_results": True},
    {"masi_ytd": 11.0, "tech_non_fiable": True},
]

# (score_tech, score_fond) — dont le cas MNG du 30/10 et du 02/11.
NOTES = [(5.2, 7.2), (9.5, 9.8), (2.0, 1.5), (6.0, 6.0), (7.2, 1.9)]


def _ctx(mod, statut):
    c = dict(mod)
    if statut is not None:
        c["market_status"] = statut
    return c


@pytest.mark.parametrize("mod", MODULATEURS)
def test_memes_poids_quel_que_soit_le_statut(mod):
    poids = [u.get_weights(_ctx(mod, s)) for s in STATUTS]
    assert all(p == poids[0] for p in poids), (mod, poids)


@pytest.mark.parametrize("mod,notes", list(itertools.product(MODULATEURS, NOTES)))
def test_meme_note_et_meme_signal_quel_que_soit_le_statut(mod, notes):
    st, sf = notes
    sorties = [u.compute_v53("ZZTEST", st, sf, 0, 0, _ctx(mod, s)) for s in STATUTS]
    for s in sorties[1:]:
        assert (s["v53"], s["sig"], s["poids"]) == (
            sorties[0]["v53"], sorties[0]["sig"], sorties[0]["poids"]), mod


def test_la_base_est_celle_du_marche_ferme():
    """0,52/0,72 et 0,20/0,72 : l'ancien chemin « fermé », à toute heure."""
    assert u.get_weights({}) == {"technique": 0.2778, "fondamental": 0.7222}


def test_cas_mng_du_30_octobre():
    """Fond 7,2 · tech 5,2 · MASI < −5 % : 6,76, la note du soir, en séance aussi."""
    for s in STATUTS:
        r = u.compute_v53("MNG", 5.2, 7.2, 0, 0, _ctx({"masi_ytd": -6.0}, s))
        assert r["v53"] == 6.76, s


def test_le_moteur_ne_lit_plus_le_statut_pour_ponderer():
    import inspect
    src = inspect.getsource(u.get_weights)
    code = "\n".join(l.split("#")[0] for l in src.split('"""')[-1].splitlines())
    assert "market_status" not in code

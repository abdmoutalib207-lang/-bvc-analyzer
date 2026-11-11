"""La fiche du terminal : « Dernier semestre » et « À savoir » — 09/11/2026.

Le moteur publie `comptes_s1` et `a_savoir` (pipeline/fiche_comptes.py,
tests/test_fiche_comptes.py). Ici, l'écran : les deux champs traversent la
fusion, la fiche dit « Non relevé » et « Rien de particulier… », montre les
réserves et les sources, écrit les nombres en format français et n'emploie
aucun mot d'action.
"""
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
ECRAN = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


def _composant(nom, suivant):
    i = ECRAN.index(f"const {nom}=")
    return ECRAN[i:ECRAN.index(suivant, i)]


def test_terminal_lit_les_deux_champs_jusque_dans_la_fusion():
    i = ECRAN.find("d.tickers.forEach(t=>{m[t.symbol]={")
    fusion = ECRAN[i:ECRAN.find("};});", i)]
    assert "comptes_s1:t.comptes_s1" in fusion and "a_savoir:t.a_savoir" in fusion
    assert "<DernierSemestre c={r.comptes_s1}/>" in ECRAN and "<ASavoir items={r.a_savoir}/>" in ECRAN


def test_terminal_textes_attendus_et_aucun_mot_d_action():
    sem = _composant("DernierSemestre", "const ASavoir=")
    sav = _composant("ASavoir", "// ── TICKER NEWS")
    assert "Non relevé" in sem and "Dernier semestre" in sem and "S1 2025" in sem
    assert "Rien de particulier à signaler pour lire les comptes." in sav and "À savoir" in sav
    assert "c.reserves" in sem and "c.sources" in sem          # réserves et sources affichées
    for mot in ("ACHETER", "VENDRE", "ÉVITER", "acheter", "vendre", "renforcer", "alléger",
                "va monter", "va baisser", "objectif de cours"):
        assert mot not in sem and mot not in sav, mot
    # format français : nombres par nfr (espace, virgule), dates JJ/MM/AAAA
    assert "valeurS1(" in sem and "variationFr(" in sem
    aides = ECRAN[ECRAN.index("const dateFait="):ECRAN.index("const DernierSemestre=")]
    assert aides.count("nfr(") >= 3 and 'split("-").reverse().join("/")' in aides


def test_champ_absent_rien_plutot_qu_un_faux_rien_a_signaler():
    """Un data.json antérieur au 09/11 n'a pas `a_savoir` : la carte ne doit pas
    affirmer « rien à signaler » sur une vérification qui n'a pas été faite."""
    sav = _composant("ASavoir", "// ── TICKER NEWS")
    assert "if(!Array.isArray(items)) return null;" in sav
    assert "if(!c) return null;" in _composant("DernierSemestre", "const ASavoir=")


def test_index_compile_contient_les_blocs():
    idx = (RACINE / "index.html").read_text(encoding="utf-8")
    assert "Rien de particulier \\xE0 signaler pour lire les comptes." in idx          # Babel échappe « à »
    assert "comptes_s1: t.comptes_s1" in idx or "comptes_s1:t.comptes_s1" in idx

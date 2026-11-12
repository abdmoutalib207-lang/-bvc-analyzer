"""Le volume publié est celui du MARCHÉ CENTRAL, et il le dit (audit du 12/11/2026).

Constat établi sur le bulletin de la cote de la Bourse de Casablanca
(« Physionomie des transactions ») : le 11/11/2026, notre « volume global »
de 134 765 180,59 DH est exactement le MARCHÉ CENTRAL ; le TOTAL GÉNÉRAL vaut
1 071 747 430,59 DH (bloc Managem de 936 940 000 DH, transferts 42 250 DH).
Le 12/11 : marché central 65 370 886,66, total 65 800 609,76. Nos sources
(synthèse de séance d'une société de bourse, somme des fiches) ne donnent ni
les blocs ni les transferts : le chiffre publié se nomme donc « marché central ».

Même audit : le MASI 20 n'est pas « les vingt plus grosses capitalisations »
mais les vingt plus liquides parmi les quarante plus grandes capitalisations
flottantes (fiche signalétique des indices de la Bourse de Casablanca).
"""
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
ECRAN = (RACINE / "terminal.src.html").read_text(encoding="utf-8")
BRIEFING = (RACINE / "pipeline" / "briefing.py").read_text(encoding="utf-8")


def test_le_volume_publie_ne_se_dit_plus_global():
    for texte, ou in ((ECRAN, "terminal.src.html"), (BRIEFING, "pipeline/briefing.py")):
        lignes = [l for l in texte.splitlines()
                  if "olume global" in l and not l.lstrip().startswith(("#", "//", "*"))
                  and '"""' not in l]
        affiches = [l for l in lignes if any(m in l for m in ('title=', ' l="', 'P.append', 'f"'))]
        assert not affiches, f"{ou} affiche encore « volume global » : {affiches[:2]}"
    assert "volume du marché central" in BRIEFING
    assert 'l="Marché central"' in ECRAN and "hors blocs et transferts" in ECRAN


def test_l_infobulle_du_masi_20_dit_sa_regle():
    assert "plus grosses capitalisations" not in ECRAN
    assert "les vingt valeurs les plus liquides parmi les quarante plus grandes capitalisations flottantes" in ECRAN

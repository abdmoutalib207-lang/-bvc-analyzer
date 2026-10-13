"""Fonds propres part du groupe au 31/12/2024 — la colonne N-1 des rapports 2025.

POURQUOI (13/10/2026) : le ROE d'exercice se calcule sur des fonds propres MOYENS
(31/12/2024 et 31/12/2025). Jusqu'ici le 31/12/2024 n'était cité qu'en texte
libre dans la note du fait 2025 ; il est désormais un FAIT STRUCTURÉ,
`capitaux_propres_part_groupe_2024`, avec les mêmes champs que celui de 2025 :
valeur (MMAD), `valeur_au_rapport`, `unite_au_rapport`, `colonne_exercice_precedent`,
page, et une citation de la ligne entre guillemets.

RÈGLE : colonne LUE ou rien. Aucune valeur n'est déduite (ni du 2025 moins le
résultat, ni d'un tableau de variation incomplet). Un titre dont la colonne N-1
n'est pas lisible n'a pas le fait, et le dit dans `_fonds_propres_2024_non_releves`.

⚠️ CES TESTS NE LISENT PAS LE PDF. Ils vérifient que tout ce qu'il faut pour
recontrôler la lecture est là, et que le fait est cohérent avec celui de 2025.
"""

import json
import re
from pathlib import Path

import pytest

import test_fonds_propres as tfp  # noqa: E402  (mêmes outils d'analyse de citation)

RACINE = Path(__file__).resolve().parent.parent
CLE = "capitaux_propres_part_groupe_2024"
PLANCHER = 50     # titres couverts au 13/10/2026 : le relevé progresse, il ne recule pas


@pytest.fixture(scope="module")
def faits():
    return json.loads((RACINE / "pipeline" / "faits_financiers.json").read_text(encoding="utf-8"))


def _fp24(faits):
    return {t: e["faits"][CLE] for t, e in faits.items()
            if not t.startswith("_") and isinstance(e, dict) and CLE in (e.get("faits") or {})}


def test_le_releve_2024_couvre_au_moins_le_plancher_et_dit_ses_manquants(faits):
    cp = _fp24(faits)
    assert len(cp) >= PLANCHER, f"{len(cp)} titres couverts, plancher {PLANCHER}"
    manq = faits["_ratios_2025"].get("_fonds_propres_2024_non_releves")
    assert isinstance(manq, dict) and manq, "les manquants doivent être listés avec leur motif"
    avec_2025 = {t for t, e in faits.items() if not t.startswith("_") and isinstance(e, dict)
                 and "capitaux_propres_part_groupe" in (e.get("faits") or {})}
    # Tout titre qui a le fait 2025 a soit le 2024, soit un motif. Aucun silence.
    assert avec_2025 <= set(cp) | set(manq), sorted(avec_2025 - set(cp) - set(manq))
    assert not (set(cp) & set(manq)), "un titre ne peut être à la fois relevé et manquant"
    assert set(cp) <= avec_2025, "un 2024 sans fait 2025 : le ROE moyen n'a pas de sens"


def test_la_conversion_se_refait_sans_rouvrir_le_pdf(faits):
    for t, f in sorted(_fp24(faits).items()):
        assert "valeur_au_rapport" in f, t
        u = f.get("unite_au_rapport")
        assert u in tfp.VERS_MMAD, f"{t} : unité {u!r} inconnue"
        attendu = f["valeur_au_rapport"] * tfp.VERS_MMAD[u]
        assert abs(f["valeur"] - attendu) <= max(1e-6, abs(attendu) * 1e-9), (
            f"{t} : {f['valeur']} MMAD publié, {f['valeur_au_rapport']} {u} font {attendu}")


def test_chaque_fait_porte_page_colonne_citation_et_date(faits):
    for t, f in sorted(_fp24(faits).items()):
        assert isinstance(f.get("page"), int) and 0 < f["page"] <= faits[t]["pages_document"], t
        col = f.get("colonne_exercice_precedent")
        assert isinstance(col, int) and 1 <= col <= 10, f"{t} : rang {col!r}"
        note = f.get("note") or ""
        assert "«" in note and "»" in note, f"{t} : la note ne cite pas la ligne du rapport"
        assert re.search(r"capitaux\s+propres|fonds\s+propres|CAPITAUX", note, re.I), t
        assert f.get("releve_le") == "2026-10-13", t


def test_la_valeur_retenue_est_celle_de_la_colonne_declaree(faits):
    """Même contrôle que pour 2025 : le nombre publié occupe, dans la ligne citée,
    le rang déclaré. Sans lui, une colonne 2025 prise pour 2024 passerait."""
    applique = 0
    for t, f in sorted(_fp24(faits).items()):
        nombres = tfp._nombres_cites(f.get("note"))
        col = f["colonne_exercice_precedent"]
        if nombres is None or len(nombres) < col:
            continue
        applique += 1
        assert nombres[col - 1] == pytest.approx(f["valeur_au_rapport"], rel=1e-9), (
            f"{t} : la colonne {col} de la ligne citée porte {nombres[col - 1]}, "
            f"mais le fait retient {f['valeur_au_rapport']}")
    assert applique >= 35, f"le contrôle ne s'est appliqué qu'à {applique} titres"


def test_la_colonne_2024_n_est_pas_celle_de_2025(faits):
    """Une inversion de colonnes publie 2025 sous la date de 2024 : les deux valeurs
    seraient identiques. Elles ne le sont jamais (sauf mention explicite)."""
    for t, f in sorted(_fp24(faits).items()):
        f25 = faits[t]["faits"]["capitaux_propres_part_groupe"]
        if abs(f["valeur"] - f25["valeur"]) < 1e-9:
            assert "identique" in (f.get("note") or "").lower(), (
                f"{t} : fonds propres 2024 = 2025 sans explication — colonnes confondues ?")


def test_l_ecart_2024_2025_reste_dans_une_plage_defendable(faits):
    """Filet contre l'erreur d'unité et la colonne d'un autre exercice : les fonds
    propres d'une société ne varient pas de ×4 ou ÷4 en un an sans que la note
    le dise (augmentation de capital, IPO, perte)."""
    for t, f in sorted(_fp24(faits).items()):
        f25 = faits[t]["faits"]["capitaux_propres_part_groupe"]["valeur"]
        if f["valeur"] <= 0 or f25 <= 0:
            continue
        r = f25 / f["valeur"]
        if not 0.25 <= r <= 4:
            assert "⚠" in (f.get("note") or ""), (
                f"{t} : fonds propres ×{r:.2f} en un an sans note ⚠ qui l'explique")


def test_les_fonds_propres_negatifs_s_ecrivent_entre_parentheses_dans_la_citation(faits):
    for t, f in sorted(_fp24(faits).items()):
        if f["valeur"] < 0:
            nombres = tfp._nombres_cites(f.get("note"))
            assert nombres and min(nombres) < 0, f"{t} : négatif sans parenthèses dans la citation"

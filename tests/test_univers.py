"""L'univers des titres, et les affirmations que la page a le droit de porter.

Deux familles de contrôles, nées de l'audit externe du 05/09/2026.

1. UN SEUL UNIVERS
   Le front portait sa propre table de repli `STATIC` (77 titres) et la
   fusionnait avec `data.json` (80). L'union en affichait 81, l'en-tête en
   annonçait 77, et le classement en listait 81 — trois compteurs pour une
   seule réalité. Surtout, `TIM` n'existait que dans la table du front :
   un titre visible à l'écran, absent des données, sur lequel aucun prix
   ni score n'était calculable.

   ⚠️ TIM est RADIÉ, et ce n'est pas une supposition : le référentiel
   Maroclear des valeurs ACTIVES, relevé le 05/09/2026, ne contient ni le
   symbole ni son ISIN `MA0000011686`. Le doute traînait depuis le 02/07.

2. AUCUNE AFFIRMATION QUE LE DÉPÔT NE PEUT PAS ÉTAYER
   La page annonçait 83 % de réussite et +38,3 % de rendement à 12 mois,
   écrits en dur dans le HTML, sans qu'aucun artefact du dépôt permette de
   refaire le calcul. Elle appelait « probabilité de surperformance » un
   nombre qui vaut `score composite ÷ 100 × 0,7` — vérifié à moins de 0,002
   près sur les lignes de `final_rankings.csv`.

   Ces deux tests sont des garde-fous d'HONNÊTETÉ, pas de correction. Ils
   échoueront si quelqu'un remet ces chiffres sans le backtest reproductible
   qui les justifie. C'est exactement leur rôle.
"""

import json
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FRONT = RACINE / "index.html"


def _static_du_front():
    m = re.search(r"const STATIC = \[(.*?)\n\];", FRONT.read_text(encoding="utf-8"), re.S)
    assert m, "bloc STATIC introuvable dans index.html"
    return set(re.findall(r'symbol:"([A-Z0-9]+)"', m.group(1)))


def _symboles_data():
    d = json.loads((RACINE / "data.json").read_text(encoding="utf-8"))
    return {t["symbol"] for t in d["tickers"]}


# ── 1. un seul univers ───────────────────────────────────────────────────

def test_aucun_titre_fantome_dans_le_front():
    """Un symbole affiché doit exister dans les données. Sinon il n'a ni prix,
    ni score, ni date — c'est une ligne vide qui se fait passer pour un titre.
    """
    fantomes = _static_du_front() - _symboles_data()
    assert not fantomes, (
        f"{len(fantomes)} titre(s) présents dans la table du front mais absents "
        f"de data.json : {sorted(fantomes)}. Vérifier d'abord s'ils sont radiés "
        f"(référentiel Maroclear) avant de les rajouter aux données.")


def test_l_univers_affiche_egale_l_univers_des_donnees():
    """Le classement affiche l'union des deux tables. Elle ne doit rien
    ajouter à ce que les données contiennent réellement."""
    assert len(_static_du_front() | _symboles_data()) == len(_symboles_data())


def test_tim_est_absent_car_radie():
    """Garde-fou nommé : le doute sur TIM a traîné du 02/07 au 05/09.

    Maroclear ne le liste pas parmi les valeurs actives, et son ISIN
    `MA0000011686` n'apparaît nulle part dans ce référentiel. Le rajouter
    demanderait une preuve, pas une habitude.
    """
    assert "TIM" not in _static_du_front()
    import sys
    sys.path.insert(0, str(RACINE))
    from bvc_config import TICKERS_ALL
    assert "TIM" not in TICKERS_ALL


# ── 2. affirmations non étayées ──────────────────────────────────────────

def test_le_front_ne_republie_pas_un_backtest_irreproductible():
    """83 % et +38,3 % ne reviennent qu'avec de quoi les refaire.

    Le dépôt ne contient ni jeu de données figé, ni commande, ni journal
    permettant de retrouver ces valeurs. Tant que c'est le cas, les écrire
    dans la page est une affirmation, pas un résultat.
    """
    texte = FRONT.read_text(encoding="utf-8")
    # On ignore les lignes de commentaire : le code d'origine y est conservé
    # exprès, pour que le chantier reparte de quelque chose.
    vivant = "\n".join(l for l in texte.split("\n")
                       if not l.lstrip().startswith("//"))
    for motif in (r'"83%"', r'\+38\.3%', r'Win rate 83'):
        assert not re.search(motif, vivant), (
            f"« {motif} » réapparaît dans index.html. Ces chiffres ne peuvent "
            f"être republiés qu'avec un backtest reproductible : commande "
            f"unique, séries réelles figées, frais de la place, vrai MASI en "
            f"référence, nombre de signaux et intervalle de confiance.")


def test_le_mot_probabilite_ne_qualifie_plus_le_champ_heuristique():
    """`win` vaut `score ÷ 100 × 0,7`, pas une fréquence observée.

    Le champ était présenté « probabilité de surperformance 1 mois » dans la
    légende, « WIN RATE 6M » sur la fiche, et alimenté par
    `p_outperform_12m` : trois horizons pour un seul nombre.
    """
    texte = FRONT.read_text(encoding="utf-8")
    vivant = "\n".join(l for l in texte.split("\n")
                       if not l.lstrip().startswith("//"))
    assert "probabilité de surperformance" not in vivant
    assert "Win rate 6M" not in vivant


def test_le_champ_heuristique_porte_le_meme_nom_partout():
    """Un même nombre, un même libellé. La contradiction d'horizon était le
    défaut le plus trompeur des trois."""
    texte = FRONT.read_text(encoding="utf-8")
    assert texte.count("SM~") >= 2, "le libellé unique SM~ doit être utilisé"

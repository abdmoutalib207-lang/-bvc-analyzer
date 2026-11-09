#!/usr/bin/env python3
"""Ce que le moteur calcule doit se voir — sinon il ne sert à personne.

⚠️ LE DÉFAUT QUE CES TESTS EMPÊCHENT DE REVENIR
───────────────────────────────────────────────
Au 25/09/2026, quatre blocs étaient calculés à chaque run et **invisibles à
l'écran** : le rang sectoriel, le montant échangé, la cohérence du flux et la
largeur de marché. Le moteur les publiait dans `data.json`, le terminal ne les
lisait pas.

C'est exactement le reproche qu'une lecture extérieure faisait au score
composite : les notes par pilier existaient dans le flux depuis des mois sans
jamais être montrées. Le même défaut s'est reproduit quatre fois en deux jours,
à mesure que le moteur gagnait des mesures.

⚠️ CE N'EST PAS UNE QUESTION D'ESTHÉTIQUE
Deux de ces blocs **justifient une décision du moteur** :

  · le montant échangé explique pourquoi la confiance est plafonnée à 2 sur
    27 titres — un plafond qu'on ne peut pas vérifier ne se discute pas ;
  · le rang sectoriel répond à « un P/B de 2,16 ne veut rien dire seul », et
    sans lui le chiffre nu laisse le lecteur faire une comparaison que
    personne ne fait de tête sur quatre-vingts titres.

Un moteur qui décide sans montrer sur quoi il décide demande qu'on lui fasse
confiance. Ce projet fait l'inverse.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

ECRAN = (RACINE / "terminal.src.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def flux():
    f = RACINE / "data.json"
    if not f.exists():
        pytest.skip("data.json absent de ce clone")
    return json.loads(f.read_text(encoding="utf-8"))


# ── ⚠️ Ce que le moteur calcule, l'écran le lit ────────────────────────────

@pytest.mark.parametrize("champ,pourquoi", [
    ("echange_median_dh", "c'est ce qui plafonne la confiance de 27 titres"),
    ("rang_secteur", "un ratio nu ne se compare pas d'un secteur à l'autre"),
    ("reprise_recente", "sinon un titre repris affiche « Données insuffisantes »"),
    ("fond_age_jours", "la moitié du poids de la note vient de chiffres de juin"),
])
def test_le_terminal_lit_ce_que_le_moteur_publie(champ, pourquoi):
    assert champ in ECRAN, f"`{champ}` est calculé mais invisible — {pourquoi}"


# ⚠️ Les champs publiés à la RACINE d'un ticker. Ceux qui vivent dans `_meta`
# voyagent avec lui et n'ont pas besoin d'y figurer.
CHAMPS_RACINE = [
    ("rang_secteur", "le rang sectoriel, publié le 24/09"),
    ("niveaux", "les niveaux et leurs bornes réglementaires, publiés le 25/09"),
    ("note_fond", "la note fondamentale et ses composantes (score_fond retiré le 06/11/2026)"),
    ("score_bvc", "le score affiché, avec ses facteurs"),
    ("note_fond_metier", "la note par famille, publiée à côté de la note actuelle (comparaison, 11/10)"),
    ("comptes_s1", "le « Dernier semestre » de la fiche, relevé sur pièce (09/11/2026)"),
    ("a_savoir", "les faits datés des registres, « À savoir » de la fiche (09/11/2026)"),
]


@pytest.mark.parametrize("champ,quoi", CHAMPS_RACINE)
def test_le_champ_traverse_la_fusion_et_pas_seulement_le_fichier(champ, quoi):
    """⚠️ LE DÉFAUT QUE LE TEST PRÉCÉDENT NE VOYAIT PAS — trouvé le 25/09/2026.

    Le terminal ne passe pas `data.json` tel quel aux composants : il le
    recopie champ par champ dans une **énumération nommée** d'une quarantaine
    d'entrées. Un champ absent de cette liste n'atteint jamais l'écran, quand
    bien même le composant qui l'affiche existe.

    C'est arrivé à `rang_secteur` : livré le 24/09, affiché nulle part
    pendant une journée entière. Le test qui devait l'empêcher cherchait la
    chaîne « rang_secteur » DANS index.html — elle y était, dans le composant.
    **Il ne vérifiait pas le chemin de données, et c'est le seul endroit où la
    rupture se produit.**

    Le commentaire du code annonçait le risque mot pour mot : « une
    énumération de quarante champs cache ce qui lui manque ».
    """
    i = ECRAN.find("d.tickers.forEach(t=>{m[t.symbol]={")
    assert i > 0, "l'énumération de fusion est introuvable — a-t-elle été renommée ?"
    fin = ECRAN.find("};});", i)
    fusion = ECRAN[i:fin]

    # Un champ traverse en écriture directe (`champ:t.champ`). La seconde
    # forme, la liste nommée `CHAMPS_SCORE` qui portait `score_tech` et
    # `score_fond`, est retirée avec la note v5.3 (06/11/2026, lot 2).
    assert f"{champ}:t.{champ}" in fusion, (
        f"`{champ}` n'est pas recopié par la fusion : {quoi} n'atteindra "
        f"jamais l'écran, même si le composant qui l'affiche existe")


# ⚠️ 06/11/2026 — retrait du producteur de la note v5.3 (lot 2). Le moteur ne
# publie plus ces champs ; les transporter ferait voyager des `undefined` et
# laisserait croire à un composant qu'ils existent encore.
CHAMPS_V53 = ("v53", "sig", "score_fond", "score_tech", "poids", "bonus", "setup",
              "verdict_plafonne", "score_version")


def _fusion():
    i = ECRAN.find("d.tickers.forEach(t=>{m[t.symbol]={")
    return ECRAN[i:ECRAN.find("};});", i)]


@pytest.mark.parametrize("champ", CHAMPS_V53)
def test_la_fusion_ne_transporte_plus_la_note_v53(champ):
    import re
    assert not re.search(rf"\b{champ}:t\.{champ}\b", _fusion()), f"`{champ}` encore transporté"
    assert "t[c]" not in _fusion() and "CHAMPS_SCORE" not in _fusion()


def test_la_liste_champs_score_est_retiree():
    assert "const CHAMPS_SCORE" not in ECRAN and "CHAMPS_SCORE.map" not in ECRAN


def test_la_comparaison_par_metier_quitte_la_fiche_mais_traverse_la_fusion():
    """11/10/2026 : la note par famille était publiée à côté de la note v5.3,
    en comparaison (« non retenue dans la note »). 06/11/2026 : la note v5.3
    quitte le terminal et le Score BVC devient le score unique (décision
    d'Abd Moutalib) — une seconde note sur 10, comparée à une note qui n'est
    plus affichée, n'a plus sa place sur la fiche. Le moteur la publie
    toujours ; elle traverse encore la fusion (`roeSansObjet` en lit le
    critère de rentabilité pour dire qu'un ROE est sans objet)."""
    assert "<NoteFond" not in ECRAN and "const NoteFond=" not in ECRAN
    assert "note_fond_metier:t.note_fond_metier" in ECRAN
    assert "note_fond_metier" in ECRAN[ECRAN.index("const roeSansObjet="):][:300]
    # Les libellés d'état des critères (ETATS_NOTE_LIB) partent avec le composant.
    assert "const ETATS_NOTE_LIB" not in ECRAN


def test_la_largeur_de_marche_est_affichee():
    """⚠️ Le 24/09, le MASI perdait 0,95 % et DEUX TITRES SUR TROIS
    reculaient — 16 hausses contre 42 baisses. La variation seule ne le dit
    pas : un indice peut monter porté par trois grosses capitalisations."""
    assert "masi.hausses" in ECRAN and "masi.baisses" in ECRAN, (
        "la largeur de marché est collectée mais n'apparaît pas dans l'en-tête")


# ── Le flux porte bien ce que l'écran attend ───────────────────────────────

def test_le_masi_annuel_est_affiche():
    """⚠️ LE YTD ÉTAIT COLLECTÉ ET INVISIBLE — corrigé le 25/09.

    Pire que l'invisibilité : le `WeightEngine` déclarait `masi_ytd` « non
    calculable » et neutralisait deux régimes de pondération DEPUIS L'ORIGINE
    DU PROJET, alors que la source le sert sous `VariationAnneeP`.

    Un lecteur qui voit « −0,95 % » ne sait pas si le marché est en hausse ou
    en baisse sur l'année — c'est pourtant ce qui décide du régime.
    """
    assert "masi.ytd_pct" in ECRAN, (
        "la variation annuelle de l'indice est collectée mais pas affichée")


def test_le_ytd_est_publie_dans_le_flux(flux):
    m = flux.get("masi") or {}
    assert m.get("ytd_pct") is not None, (
        "l'en-tête afficherait du vide — `_etat_marche()` ne remonte pas le YTD")


def test_le_flux_publie_la_largeur(flux):
    m = flux.get("masi") or {}
    # ⚠️ 14/10/2026 : dans les premières minutes, la source compte des
    # transactions sans servir la largeur. Le moteur publie alors une absence
    # DÉCLARÉE — jamais « 0 hausse, 0 baisse ». Seule cette forme est admise.
    if m.get("synthese_partielle"):
        assert m.get("hausses") is None and m.get("baisses") is None
        assert "pas encore consolidée" in ((m.get("largeur") or {}).get("_lecture") or "")
        return
    assert m.get("hausses") is not None, "l'en-tête afficherait du vide"
    assert m.get("baisses") is not None
    assert (m.get("largeur") or {}).get("ratio") is not None


def test_le_flux_publie_le_montant_echange(flux):
    t = flux.get("tickers") or []
    avec = [x for x in t if (x.get("_meta") or {}).get("echange_median_dh") is not None]
    assert len(avec) >= len(t) * 0.8, (
        f"{len(avec)}/{len(t)} titres seulement portent leur montant échangé")


def test_le_flux_publie_un_rang_sectoriel_utile(flux):
    """⚠️ Pas pour tous : les secteurs de moins de quatre comparables n'en ont
    pas, et c'est voulu — un « rang 1 sur 1 » n'informe de rien."""
    t = flux.get("tickers") or []
    avec = [x for x in t if x.get("rang_secteur")]
    assert len(avec) >= 30, (
        f"seulement {len(avec)} titres situés dans leur secteur — la table "
        f"COMPANY_SECTORS est-elle intacte ?")


# ── ⚠️ Ce que l'affichage ne doit pas faire ────────────────────────────────

def test_le_rang_n_est_pas_affiche_sans_pairs():
    """Le composant doit rendre `null` quand le titre n'a pas de rang, et non
    un « — » qui ressemblerait à une donnée manquante alors que c'est une
    mesure volontairement absente."""
    i = ECRAN.find("r.rang_secteur")
    assert i > 0
    bloc = ECRAN[i:i + 300]
    assert "if(!e) return null" in bloc, (
        "un titre sans comparables afficherait un rang vide")


def test_le_plafond_de_liquidite_est_annonce_a_l_ecran():
    """⚠️ Le chiffre seul ne suffit pas : il faut dire ce qu'il entraîne. Un
    lecteur qui voit « 6 309 DH » sans explication ne fait pas le lien avec la
    confiance de 2 sur 5 qui s'affiche ailleurs."""
    assert "confiance plafonnée" in ECRAN, (
        "le montant échangé est affiché sans dire qu'il plafonne la confiance")


def test_l_ecart_au_secteur_porte_son_sens():
    """Pour le PER et le P/B, au-dessus de la médiane signifie PLUS CHER ; pour
    le dividende, c'est l'inverse. Une couleur unique pour les trois dirait le
    contraire de la vérité une fois sur trois."""
    i = ECRAN.find("r.rang_secteur")
    bloc = ECRAN[i:i + 600]
    assert 'ratio==="div"' in bloc, (
        "le sens de lecture du dividende n'est pas distingué de celui du PER")


# ── ⚠️ `meta()` ne doit plus être une liste blanche ────────────────────────

def _champs_lus_via_meta() -> set:
    """Les champs que l'écran lit à travers le helper `meta(...)`."""
    import re
    lus = set(re.findall(r"meta\([^)]*\)\.([a-zA-Z_]\w*)", ECRAN))
    # la forme `const m=meta(r)` puis `m.champ` plus loin
    lus |= set(re.findall(r"const m=meta\([^)]*\)[,;].{0,400}?m\.([a-zA-Z_]\w*)",
                          ECRAN, re.S))
    return lus


def _champs_rendus_par_meta() -> set:
    """Ce que `meta()` renvoie réellement."""
    import re
    i = ECRAN.find("const meta=r=>")
    j = ECRAN.find(";", ECRAN.find("suspMotif:null}", i))
    corps = ECRAN[i:j]
    rendus = set(re.findall(r"(\w+):", corps))
    # ⚠️ `{...m}` étale TOUT `_meta` : le helper cesse d'être une liste
    # blanche, et c'est la seule forme qui survit à un ajout de champ.
    if "{...m," in corps or "{ ...m," in corps:
        rendus.add("*")
    return rendus


def test_meta_livre_tout_ce_que_l_ecran_lit():
    """⚠️ QUATRE FONCTIONNALITÉS TUÉES EN SILENCE, découvertes le 25/09/2026.

    `meta()` était une LISTE BLANCHE de sept champs normalisés. L'écran en
    lisait cinq autres, tous jetés :

        fond_age_jours          la puce de fraîcheur des fondamentaux
        echange_median_dh       le bloc de liquidité
        reprise_recente         la puce « reprise de cotation »
        seances_depuis_reprise  idem
        comptes_plus_recents    l'avertissement de comptes plus récents

    Conséquence mesurée : la puce de fraîcheur affichait « date inconnue » sur
    **les quatre-vingts titres** depuis sa livraison du 24/09 — pas seulement
    sur les quatre réellement sans date. Le bloc de liquidité n'a jamais été
    rendu une seule fois.

    ⚠️ **Un composant qui rend `null` ne laisse aucune trace.** Ni erreur, ni
    case vide : rien. C'est pourquoi personne ne l'a vu, et pourquoi seule
    une capture d'écran l'a révélé.

    ⚠️ Troisième liste nommée de la journée à perdre ce qu'on ajoute à côté
    d'elle, après l'énumération de la fusion et le `git add` du workflow.
    """
    rendus = _champs_rendus_par_meta()
    if "*" in rendus:
        return                     # `{...m}` : tout passe, par construction
    manquants = sorted(_champs_lus_via_meta() - rendus)
    assert not manquants, (
        f"`meta()` ne livre pas ces champs, les composants qui les lisent "
        f"rendront `null` en silence : {manquants}")


def test_meta_etale_le_bloc_plutot_que_de_l_enumerer():
    """⚠️ La forme compte autant que le contenu. Réparer en AJOUTANT les cinq
    champs à la liste blanche marcherait aujourd'hui et retomberait au
    prochain ajout. L'étalement est la seule forme qui survit."""
    i = ECRAN.find("const meta=r=>")
    corps = ECRAN[i:i + 600]
    assert "{...m," in corps or "{ ...m," in corps, (
        "`meta()` est redevenue une liste blanche — elle perdra le prochain "
        "champ ajouté à `_meta`")

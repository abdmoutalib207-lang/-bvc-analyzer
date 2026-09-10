"""Un titre suspendu ne reçoit ni signal, ni chandelle.

CE QUI S'EST PASSÉ
──────────────────
Le 09/09/2026, le terminal affichait **ACHETER ★★** sur CMT — une valeur du
MASI 1 dont la cotation est suspendue depuis le 17/07/2026, dans l'attente
d'une offre publique d'achat obligatoire. Le moteur recommandait d'acheter un
titre que personne n'a le droit d'acheter.

Il avait en outre écrit 28 chandelles pour des séances qui n'ont pas eu lieu,
du 17/07 au 01/09, toutes au même cours de 4 350 DH et toutes à volume nul.

POURQUOI AUCUN GARDE-FOU N'A JOUÉ
─────────────────────────────────
Trois s'en sont approchés :

  · **R9** (`chg=0` ET `vol=0`) a bien reconnu la donnée — c'est exactement sa
    signature. Mais elle conclut « stale », c'est-à-dire « pas rafraîchi ». Le
    titre était marqué stale ET portait un signal d'achat : les deux verdicts
    coexistaient sans se contredire, parce qu'ils ne parlent pas de la même
    chose.
  · **le plafond de liquidité du 01/09** a ramené la confiance à 2, le volume
    médian étant nul. Mais le garde-fou d'affichage se déclenche à 1.
  · **l'étape 6c** refuse d'écrire une bougie depuis un prix stale, et elle a
    joué — les 28 bougies datent d'avant, quand la source estampillait encore
    le cours du jour.

Aucun ne pouvait conclure, et c'est le point : **une suspension ne se déduit
pas des cours.** Un titre suspendu et un titre délaissé produisent exactement
les mêmes nombres — volume nul, variation nulle, cours immobile. La différence
est juridique, publiée par le régulateur, et elle doit entrer par un registre
tenu à la main. C'est le même raisonnement que `SPLITS` : un fait extérieur que
la série ne porte pas.

CE QUE CES TESTS PROTÈGENT
──────────────────────────
Que le registre existe, qu'il soit lu aux trois endroits qui comptent — le
bloc `_meta`, le signal, l'écriture des chandelles — et que la série de CMT ne
reparte pas en séances fantômes.
"""

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from bvc_config import SUSPENSIONS, est_suspendu

RACINE = Path(__file__).resolve().parent.parent


# ── le registre ──────────────────────────────────────────────────────────

def test_le_registre_declare_cmt():
    assert "CMT" in SUSPENSIONS, (
        "CMT est suspendue depuis le 17/07/2026 — avis AMMC DO/EM/07/2026")


@pytest.mark.parametrize("ticker,periodes", SUSPENSIONS.items())
def test_chaque_suspension_est_sourcee(ticker, periodes):
    """Une suspension sans source est une affirmation. Le registre en porte
    l'avis du régulateur, comme SPLITS porte la date d'effet."""
    for p in periodes:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", p["depuis"]), \
            f"{ticker} : date de début mal formée ({p['depuis']!r})"
        assert p.get("motif"), f"{ticker} : suspension sans motif"
        assert p.get("source"), f"{ticker} : suspension sans source"
        if p.get("reprise") is not None:
            assert p["reprise"] > p["depuis"], \
                f"{ticker} : reprise antérieure à la suspension"


def test_la_veille_le_titre_cotait_encore():
    """La borne est inclusive du premier jour, exclusive de la veille."""
    assert est_suspendu("CMT", "2026-07-16") is None
    assert est_suspendu("CMT", "2026-07-17") is not None


def test_un_titre_normal_n_est_jamais_suspendu():
    for t in ("ATW", "IAM", "ADI", "MNG"):
        assert est_suspendu(t) is None, f"{t} n'est pas suspendu"


def test_sans_date_la_fonction_repond_pour_aujourdhui():
    """⚠️ Ce test a attrapé un vrai défaut : `datetime` n'était pas importé
    dans bvc_config.py. La fonction marchait avec une date explicite et levait
    NameError sans — c'est-à-dire dans son usage par défaut."""
    r = est_suspendu("CMT")
    assert r is None or isinstance(r, dict)  # ne doit pas lever
    assert est_suspendu("CMT", datetime.now().strftime("%Y-%m-%d")) is not None


def test_une_reprise_lève_la_suspension():
    """Le registre doit savoir refermer une période, sinon il ment dès que
    l'AMMC autorise la reprise."""
    from bvc_config import SUSPENSIONS as reg
    sauve = reg.get("_TEST")
    reg["_TEST"] = [{"depuis": "2026-01-05", "reprise": "2026-02-10",
                     "motif": "essai", "source": "essai"}]
    try:
        assert est_suspendu("_TEST", "2026-01-04") is None
        assert est_suspendu("_TEST", "2026-01-20") is not None
        assert est_suspendu("_TEST", "2026-02-10") is None, \
            "le jour de la reprise, le titre cote de nouveau"
    finally:
        reg.pop("_TEST", None)
        if sauve is not None:
            reg["_TEST"] = sauve


# ── le moteur lit-il le registre ? ───────────────────────────────────────

def _moteur():
    return (RACINE / "update_data.py").read_text(encoding="utf-8")


def test_le_meta_porte_la_suspension():
    s = _moteur()
    assert '"suspendu":' in s and '"suspendu_depuis":' in s, (
        "le bloc _meta n'expose pas la suspension : le frontend ne peut pas "
        "la distinguer d'une simple donnée périmée")


def test_le_signal_devient_suspendu():
    assert re.search(r'"sig":\s*\("SUSPENDU" if est_suspendu\(', _moteur()), (
        "LE test qui compte : sans lui, le moteur recommande d'acheter un "
        "titre qu'on ne peut pas acheter")


def test_l_ecriture_de_chandelle_est_refusee():
    assert re.search(r'if _m\.get\("suspendu"\):\s*\n\s*continue', _moteur()), (
        "l'étape 6c écrira de nouveau des séances fantômes")


def test_la_confiance_tombe_a_zero():
    assert re.search(r"suspension = est_suspendu\(ticker, prix_asof\)\s*\n\s*if suspension:\s*\n\s*confiance = 0",
                     _moteur()), (
        "un titre suspendu doit tomber à 0 : la première garantie du score de "
        "confiance est « prix de la dernière séance cotée », et c'est "
        "précisément elle qui manque")


# ── le frontend ──────────────────────────────────────────────────────────

def test_le_frontend_nomme_la_suspension():
    """« Données insuffisantes » serait un contresens : les données ne
    manquent pas, le titre ne cote plus."""
    s = (RACINE / "index.html").read_text(encoding="utf-8")
    assert "meta(r).susp" in s, "le frontend ne lit pas le drapeau"
    assert 'label="SUSPENDU"' in s, "le classement n'affiche pas l'état"
    assert "SUSPENDU depuis le ${jjmm(meta(r).suspDepuis)}" in s, (
        "la fiche n'annonce pas depuis quand")
    # ⚠️ Comparer les PREMIÈRES occurrences dans tout le fichier ne marche
    # pas : `meta(r).conf<=1` sert aussi, plus haut, à griser le score. Il
    # faut regarder l'ordre DANS chacune des deux cellules de signal, seules
    # concernées — c'est ce qu'a montré la première version de ce test, qui
    # échouait sur du code pourtant correct.
    cellules = [c for c in re.findall(
        r"meta\(r\)\.susp\s*\n?\s*\?[\s\S]{0,400}?meta\(r\)\.conf<=1", s)]
    assert len(cellules) == 2, (
        f"{len(cellules)} cellule(s) où la suspension précède la confiance ; "
        "il en faut deux — le classement et la fiche. Ailleurs, un titre "
        "suspendu s'afficherait « Données insuffisantes »")


# ── les données publiées ─────────────────────────────────────────────────

def test_aucune_chandelle_apres_la_suspension():
    """La série de CMT s'arrête au 16/07, dernière séance portant un volume."""
    for ticker, periodes in SUSPENSIONS.items():
        f = RACINE / "pipeline" / "candles" / f"{ticker}.json"
        if not f.exists():
            continue
        serie = json.loads(f.read_text(encoding="utf-8"))
        for p in periodes:
            fin = p.get("reprise") or "9999-12-31"
            fantomes = [b["d"] for b in serie if p["depuis"] <= b["d"] < fin]
            assert not fantomes, (
                f"{ticker} : {len(fantomes)} chandelle(s) pendant la "
                f"suspension ({fantomes[0]} → {fantomes[-1]})")


# ── ce que le dry-run a révélé (09/09, demandé par Abd Moutalib) ─────────
#
# Lancer `update_data.py --dry-run` après le nettoyage a montré trois défauts
# qu'aucun test ne voyait, dont deux que le nettoyage lui-même avait CRÉÉS.

def test_la_variation_d_un_titre_suspendu_est_nulle_aux_trois_endroits():
    """CMT affichait −3,35 % par jour sur un titre qui n'échange plus rien.

    L'écart venait de la comparaison entre le cours diffusé (4 350) et la
    dernière séance échangée (4 501 le 16/07). Tant que les 28 bougies
    fantômes étaient là, elle donnait 4 350 contre 4 350 — zéro par accident.
    **Retirer une donnée fausse a mis au jour un calcul qui s'appuyait
    dessus.**

    Il a fallu trois gardes : la boucle principale, le repli Médias24, et
    `recalculer_variation`. Cette dernière est la plus instructive — c'est le
    remède de R9, et appliqué à une suspension il FABRIQUE le défaut qu'il
    croit corriger, parce que `chg=0` + `vol=0` y est la vérité, pas un
    symptôme.
    """
    s = _moteur()
    assert "if price and est_suspendu(ticker, IDB_ASOF):" in s, (
        "boucle principale : la variation se recalcule encore depuis la "
        "dernière clôture")
    assert "and not est_suspendu(ticker, prix_asof):" in s, (
        "repli Médias24 : idem")
    assert re.search(r"if est_suspendu\(ticker, seance\):\s*\n\s*return 0\.0", s), (
        "recalculer_variation : le correctif de R9 fabrique une variation sur "
        "un titre qui n'a pas coté")


def test_le_journal_annonce_le_signal_reellement_publie():
    """Le dry-run affichait « ACHETER ★★ » sur CMT pendant que le fichier
    écrivait « SUSPENDU » : le journal imprimait `v53['sig']`, calculé avant
    la substitution. Un journal qui contredit le fichier qu'il décrit est pire
    qu'un journal muet — c'est là qu'on va vérifier quand on doute."""
    s = _moteur()
    assert '_sig_publie = "SUSPENDU" if est_suspendu(ticker, prix_asof) else v53["sig"]' in s
    assert "{_sig_publie}\")" in s, "la ligne de journal n'utilise pas le signal publié"


def test_le_dry_run_n_ecrit_rien():
    """`--dry-run` promet « aperçu sans écrire » et enregistrait pourtant le
    MASI dans masi_history.json à chaque appel. Un mode d'essai qui modifie
    l'état n'est pas un mode d'essai — et c'est précisément l'outil qu'on
    emploie pour vérifier sans risque."""
    s = _moteur()
    assert re.search(r"if dry_run:\s*\n\s*logger\.info\(f\"  \[DRY RUN\] MASI", s), (
        "le dry-run écrit encore masi_history.json")


def test_les_champs_derives_suivent_la_serie_purgee():
    """⚠️ Piège du 14/08, retombé dedans : `n_candles` décrivait encore 542
    bougies pour une série qui n'en compte plus que 222."""
    import json as _j
    h = _j.loads((RACINE / "pipeline" / "historical_data.json").read_text(encoding="utf-8"))
    for t in SUSPENSIONS:
        e = h.get(t)
        if not isinstance(e, dict) or "candles" not in e:
            continue
        # ⚠️ PAS d'égalité avec len(candles) : `n_candles` décrit la série
        # SOURCE, la liste stockée est tronquée à 250 points. Exiger l'égalité
        # est précisément l'erreur commise le 09/09 — 222 inscrits pour une
        # série de 514. On vérifie seulement qu'il reste plausible.
        assert e.get("n_candles") is None or e["n_candles"] >= len(e["candles"]), (
            f"{t} : n_candles={e.get('n_candles')} inférieur à la liste stockée "
            f"({len(e['candles'])}) — la série source ne peut pas être plus "
            "courte que sa propre troncature")
        assert e.get("last_date") == e["candles"][-1]["d"], f"{t} : last_date périmé"
        assert e.get("last_close") == e["candles"][-1]["c"], f"{t} : last_close périmé"


def test_les_deux_magasins_de_chandelles_sont_purges():
    """Le premier nettoyage n'avait touché que pipeline/candles/. Trois
    écrivains alimentent les chandelles (journal du 14/08) et
    historical_data.json est un instantané dérivé, à purger aussi."""
    import json as _j
    for t, periodes in SUSPENSIONS.items():
        h = _j.loads((RACINE / "pipeline" / "historical_data.json").read_text(encoding="utf-8"))
        e = h.get(t) or {}
        for p in periodes:
            fin = p.get("reprise") or "9999-12-31"
            reste = [b["d"] for b in e.get("candles", []) if p["depuis"] <= b["d"] < fin]
            assert not reste, f"{t} : historical_data.json garde {len(reste)} fantôme(s)"


def test_cmt_garde_sa_derniere_seance_reelle():
    """Retirer les fantômes ne doit pas amputer l'historique réel."""
    serie = json.loads((RACINE / "pipeline" / "candles" / "CMT.json")
                       .read_text(encoding="utf-8"))
    assert len(serie) > 500, f"série tronquée : {len(serie)} bougies"
    assert serie[-1]["d"] == "2026-07-16"
    assert serie[-1]["v"] > 0, (
        "la dernière séance conservée doit porter un volume réel — sinon "
        "c'est encore un fantôme")

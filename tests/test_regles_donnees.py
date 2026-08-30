"""Les règles R1 à R10 transformées en tests exécutables sur `data.json`.

Ces tests portent sur le fichier RÉELLEMENT PUBLIÉ. Un `data.json` dégradé qui
arriverait dans le dépôt fait rougir l'intégration continue — c'est le filet
que le projet n'avait pas, et qui lui a coûté deux régressions en une semaine.

⚠️ Les seuils sont des invariants du marché ou du produit, jamais les chiffres
exacts d'un jour donné. Un test calé sur la valeur du jour échouerait le
lendemain, et une alarme peu fiable finit ignorée.
"""

import pytest

NB_TICKERS = 81          # R1 — l'univers complet
NB_MASI1 = 19            # R1 — les valeurs suivies en priorité
LIMITE_VARIATION = 10.0  # R10 — plafond réglementaire BVC, ±10 %/séance


# ── R1 : aucune régression sur la couverture ────────────────────────────────

def test_r1_univers_complet(titres):
    assert len(titres) == NB_TICKERS


def test_r1_masi1_present_et_cote(config, titres):
    assert len(config.TICKERS_ACTIFS) == NB_MASI1
    sans_prix = [t for t in config.TICKERS_ACTIFS
                 if not (titres.get(t, {}).get("price") or 0) > 0]
    assert not sans_prix, f"MASI 1 sans prix : {sans_prix}"


def test_r1_tout_titre_a_un_prix(titres):
    sans = [s for s, x in titres.items() if not (x.get("price") or 0) > 0]
    assert not sans, f"titres sans prix : {sans}"


# ── R10 : le plafond de variation est un invariant réglementaire ────────────

def test_r10_aucune_variation_hors_limite(titres):
    """Au-delà de ±10 %, c'est une erreur de source, jamais un mouvement réel."""
    hors = {s: x["chg"] for s, x in titres.items()
            if abs(x.get("chg") or 0) > LIMITE_VARIATION}
    assert not hors, f"variations impossibles : {hors}"


# ── R8 : le scoring v5.3 est sacré ─────────────────────────────────────────

def test_r8_les_ponderations_somment_a_cent(titres):
    """Technique + Fondamental + NLP = 100 %, quelle que soit l'adaptation.

    Le WeightEngine module la répartition selon le contexte, mais la somme est
    un invariant. L'ancienne documentation annonçait 47 + 36 + 25 = 108 % —
    mathématiquement impossible, et personne ne l'avait vu.
    """
    faux = {s: p for s, x in titres.items()
            if (p := x.get("poids")) and sum(p.values()) != 100}
    assert not faux, f"pondérations qui ne somment pas à 100 : {faux}"


def test_r8_score_dans_l_intervalle(titres):
    hors = {s: x["v53"] for s, x in titres.items()
            if x.get("v53") is not None and not 0 <= x["v53"] <= 10}
    assert not hors, f"scores v5.3 hors [0, 10] : {hors}"


def test_r8_aucun_score_manquant(titres):
    assert not [s for s, x in titres.items() if x.get("v53") is None]


# ── Le bloc `_meta` : sans lui, le frontend ne peut pas dire ce qu'il sait ──

def test_meta_present_sur_chaque_titre(titres):
    """Anti-pattern documenté : un ticker sans `_meta` masque au frontend le

    fait que sa donnée est périmée. Le frontend suppose alors le pire —
    `stale: true`, `confidence: 0` — mais il vaut mieux que le cas n'arrive pas.
    """
    sans = [s for s, x in titres.items() if not x.get("_meta")]
    assert not sans, f"titres sans _meta : {sans}"


def test_confiance_dans_l_echelle(titres):
    hors = {s: (x.get("_meta") or {}).get("confidence") for s, x in titres.items()
            if not 0 <= ((x.get("_meta") or {}).get("confidence") or 0) <= 5}
    assert not hors, f"scores de confiance hors [0, 5] : {hors}"


def test_source_du_prix_declaree_et_connue(titres):
    """Une source inconnue signale un chemin de repli non documenté."""
    connues = {"cdg", "bmce", "idbourse", "medias24", "candles",
               "idbourse_perime", "historical", "data_json_precedent",
               "financial", "static"}
    vues = {(x.get("_meta") or {}).get("source_prix") for x in titres.values()}
    assert vues <= connues, f"sources non documentées : {vues - connues}"


def test_masi1_pas_massivement_perime(config, titres):
    """Le produit promet la dernière clôture fiable sur ses valeurs phares.

    Seuil à 5 sur 19 : au-delà, ce n'est plus un titre non coté, c'est une
    collecte défaillante.
    """
    perimes = [t for t in config.TICKERS_ACTIFS
               if (titres.get(t, {}).get("_meta") or {}).get("stale")]
    assert len(perimes) <= 5, f"trop de MASI 1 périmés : {perimes}"


# ── R9 : chg=0 ET vol=0 ⇒ donnée suspecte ──────────────────────────────────

def test_r9_titres_suspects_bornes(titres):
    """⚠️ QUESTION OUVERTE, volontairement bornée plutôt que bloquante.

    R9 dit qu'un titre à `chg=0` ET `vol=0` porte une donnée périmée. Or 8 titres
    dans cet état ne sont PAS marqués `stale` — ils n'ont simplement pas coté de
    la séance, et leur prix est le cours de référence.

    Faut-il les marquer périmés ? La question mérite l'avis de `gardien-donnees`
    et n'est pas tranchée. En attendant, ce test empêche la dérive : si leur
    nombre double, c'est que la collecte se dégrade.
    """
    suspects = [s for s, x in titres.items()
                if not (x.get("chg") or 0) and not (x.get("vol") or 0)
                and not (x.get("_meta") or {}).get("stale")]
    assert len(suspects) <= 16, (
        f"{len(suspects)} titres à chg=0 et vol=0 non marqués périmés "
        f"(référence du 28/08 : 8) — {suspects}")


# ── Le MASI ────────────────────────────────────────────────────────────────

def test_masi_coherent(data):
    masi = data.get("masi") or {}
    assert masi.get("value"), "l'indice ne doit jamais valoir 0 ou être absent"
    assert 5_000 < float(masi["value"]) < 50_000, \
        f"MASI hors de toute plage plausible : {masi.get('value')}"
    assert abs(float(masi.get("chg") or 0)) <= LIMITE_VARIATION


@pytest.mark.parametrize("cle", ["updated", "tickers", "masi", "market_status"])
def test_cles_racine_presentes(data, cle):
    assert cle in data, f"clé racine absente de data.json : {cle}"

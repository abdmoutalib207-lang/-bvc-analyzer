#!/usr/bin/env python3
"""Un score qui ne se vérifie pas lui-même ne peut pas être calibré.

⚠️ D'OÙ VIENT CE MODULE
───────────────────────
D'une lecture extérieure du terminal, transmise par Abd Moutalib le 24/09/2026.
Trois reproches y étaient faits, et le troisième portait :

    « Le RSI à 29 et à 41, l'ADX "range" avec un "setup contrarié", la
      pondération annoncée puis contredite : ces contradictions se détectent
      automatiquement. Un score qui ne se vérifie pas lui-même ne peut pas être
      calibré. »

C'est exact, et c'est réparable. Ce module énonce ce qu'un titre publié doit
respecter pour être **interne­ment cohérent**, et le vérifie sur chaque ligne.

⚠️ CE QU'IL FAIT, ET CE QU'IL NE FAIT PAS
Il ne juge pas si un chiffre est VRAI — c'est le rôle du recoupement au
bulletin CDG, qui compare à l'extérieur. Il juge si les chiffres publiés
peuvent coexister. Une série peut être entièrement fausse et parfaitement
cohérente ; l'inverse, non : une incohérence prouve qu'au moins un chiffre est
faux, sans dire lequel.

C'est pour cela qu'il **signale** sans corriger. Devant « RSI 29 ici et 41 là »,
rien ne permet de choisir, et choisir au hasard reviendrait à effacer le
symptôme en gardant la maladie.

⚠️ POURQUOI PAS UN SIMPLE TEST
Un test tourne à la livraison ; ceci tourne à chaque run et publie son verdict
dans `data.json`. Un lecteur peut alors voir qu'une fiche se contredit, au
moment où il la lit — pas trois jours plus tard dans un journal de CI.
"""

from __future__ import annotations

# Écart relatif toléré entre deux expressions d'une même grandeur. Deux
# décimales publiées de part et d'autre, des arrondis à chaque étape : 1 %
# absorbe la représentation et rien d'autre.
TOLERANCE = 0.01

# ⚠️ 06/11/2026 : `ADX_SANS_TENDANCE` (20) n'est plus lu — il ne servait qu'au
# contrôle 6, retiré avec le champ `setup`.

# Bornes des indicateurs, par construction mathématique. Un RSI hors [0, 100]
# n'est pas un RSI extrême : c'est un calcul faux.
BORNES = {
    "rsi": (0, 100), "stoch_k": (0, 100), "stoch_d": (0, 100),
    "adx": (0, 100), "adx_pdi": (0, 100), "adx_mdi": (0, 100),
    "bvc": (0, 10),
    # ⚠️ 06/11/2026 : plus de bornes `v53`, `score_fond`, `score_tech` — le
    # producteur de la note v5.3 est retiré (lot 2) et ces champs ne sont plus
    # publiés. Le Score BVC a ses bornes dans `controler_score_bvc`.
    # ⚠️ 29/10/2026 : plus de bornes `score_nlp`, `nlp`, `nlp_corpus`,
    # `nlp_news` — le pilier NLP est retiré du moteur (lot 2) et ces champs ne
    # sont plus publiés depuis le lot 1 ; leurs bornes ne s'armaient plus.
}

# ⚠️ 06/11/2026 : `SETUPS_DIRECTIONNELS` est retiré avec le champ `setup`
# (étiquette déduite de la note v5.3, plus publiée) et le contrôle 6.


def _nb(v):
    """Le nombre, ou None. Un booléen n'est pas un nombre ici."""
    if isinstance(v, bool) or v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def controler(t: dict) -> list[dict]:
    """Les incohérences d'UN titre publié. Liste vide = rien à signaler.

    Fonction pure : elle ne lit ni disque ni réseau, et ne modifie pas `t`.
    Chaque anomalie porte un `code` stable — c'est lui qui permet de compter
    les récurrences d'un run à l'autre, pas le libellé.
    """
    a = []

    def dire(code, quoi, gravite="avertissement"):
        a.append({"code": code, "quoi": quoi, "gravite": gravite})

    # ── 1. Les bornes mathématiques ────────────────────────────────────────
    for champ, (lo, hi) in BORNES.items():
        v = _nb(t.get(champ))
        if v is not None and not (lo <= v <= hi):
            dire("hors_bornes", f"{champ} = {v}, hors [{lo}, {hi}]", "erreur")

    # ── 2. et 3. (retirés le 06/11/2026) ───────────────────────────────────
    # « poids_somme » et « score_irreproductible » vérifiaient que la note v5.3
    # se refaisait à la main depuis `score_fond`, `score_tech` et `poids`. Le
    # producteur est retiré (lot 2) : plus aucun de ces champs n'est publié.
    # Le Score BVC se refait à la main au contrôle 10. Numérotation conservée.

    # ── 4. L'invariant OHLC du jour ────────────────────────────────────────
    c = _nb(t.get("close"))
    hi, lo = _nb(t.get("h52w")), _nb(t.get("l52w"))
    if all(x is not None for x in (hi, lo)) and lo > hi:
        dire("extremes_inverses",
             f"plus-bas 52 s. ({lo:g}) au-dessus du plus-haut ({hi:g})",
             "erreur")
    if c is not None and hi is not None and c > hi * (1 + TOLERANCE):
        dire("cours_hors_extremes",
             f"cours {c:g} au-dessus du plus-haut 52 semaines {hi:g}")
    if c is not None and lo is not None and c < lo * (1 - TOLERANCE):
        dire("cours_hors_extremes",
             f"cours {c:g} sous le plus-bas 52 semaines {lo:g}")

    # ── 5. Les moyennes mobiles encadrent le cours, ou presque ─────────────
    # Pas une règle : un titre en tendance franche s'écarte de sa MA200. Mais
    # un facteur 3 signale un ISIN croisé — le cours d'une société mariée à
    # l'historique d'une autre. Le moteur a déjà ce soupçon ailleurs ; il est
    # dit ici aussi, parce que c'est ici qu'un lecteur le voit.
    for ma in ("ma20", "ma50", "ma200"):
        m = _nb(t.get(ma))
        if m and c and (m > c * 3 or m * 3 < c):
            dire("ma_hors_echelle",
                 f"{ma} = {m:g} pour un cours de {c:g} — facteur supérieur à 3",
                 "erreur")

    # ── 6. (retiré le 06/11/2026) ──────────────────────────────────────────
    # « direction_sans_tendance » opposait le `setup` (étiquette déduite de la
    # note v5.3) à un ADX sans tendance. Le champ n'est plus publié.

    # ── 7. (retiré le 29/10/2026) ──────────────────────────────────────────
    # « nlp_decompose_faux » vérifiait nlp = corpus + news. Les trois champs
    # ne sont plus publiés depuis le 28/10 et le pilier est retiré du moteur :
    # le contrôle était devenu inerte. Numérotation conservée pour la trace.

    # ── 8. (retiré le 06/11/2026) ──────────────────────────────────────────
    # « signal_sans_confiance » refusait un ACHETER / ÉVITER à confiance ≤ 1.
    # Le signal n'est plus publié (lot 2) ; la règle « confiance ≤ 1 →
    # Données insuffisantes » vit désormais à l'écran, qui lit
    # `_meta.confidence` (classement et fiche du terminal).
    meta = t.get("_meta") or {}

    # ── 9. ⚠️ LA FRAÎCHEUR, PAR BRIQUE ─────────────────────────────────────
    # Ce n'est pas une incohérence : c'est une asymétrie qu'un lecteur ne peut
    # pas deviner. Un cours du jour et des fondamentaux de juin cohabitent dans
    # la même note sans que rien ne le dise.
    # ⚠️ 06/11/2026 : la phrase citait « X % du poids de la note » — le poids
    # fondamental de la note v5.3, que le terminal n'affiche plus. L'âge porte
    # sur les fondamentaux dont dépend la note fondamentale publiée
    # (`note_fond`) ; le code et le seuil sont inchangés.
    age = _nb(meta.get("fond_age_jours"))
    if age is not None and age > 180:
        dire("fondamentaux_perimes",
             f"fondamentaux vieux de {age:.0f} jours ({meta.get('fond_asof')}) "
             f"sous la note fondamentale publiée")
    elif age is None and meta.get("source_fond") == "bpa_calcule":
        dire("fondamentaux_sans_date",
             "ratios calculés sur des fondamentaux dont la date est inconnue")

    # ── 10. ⚠️ LE SCORE BVC DOIT SE REFAIRE À LA MAIN — 06/11/2026 ──────────
    # Le score publié est le Score BVC (lot 1 du retrait de la note v5.3). Le
    # même principe que le contrôle 3 : ce que la fiche affiche — facteurs,
    # points, poids — doit redonner la valeur. Aucun bloc : rien à dire ici
    # (la panne du calcul est un contrôle du soir, `verifier_seance.py`).
    a.extend(controler_score_bvc(t))

    return a


ETATS_BVC = {"CALCULABLE", "PARTIEL", "NON_CALCULABLE"}


def controler_score_bvc(t: dict) -> list[dict]:
    """Les incohérences du bloc `score_bvc` d'un titre. Fonction pure.

    Contrat de `pipeline/score_bvc.py::score_bvc` :
      · CALCULABLE ⇔ une valeur ; PARTIEL et NON_CALCULABLE n'en ont pas ;
      · valeur et couverture dans [0, 100] ; CALCULABLE ⇒ couverture ≥ seuil ;
      · couverture = somme des poids des facteurs DISPONIBLES (ceux dont les
        points sont mesurés, zéro compris ; `points: None` = indisponible) ;
      · valeur = points ÷ couverture × 100, arrondie à 2 décimales ;
      · titre suspendu ou cours périmé ⇒ NON_CALCULABLE.
    """
    out = []
    b = t.get("score_bvc")
    if not isinstance(b, dict):
        return out

    def dire(code, quoi, gravite="erreur"):
        out.append({"code": code, "quoi": quoi, "gravite": gravite})

    etat, v, couv = b.get("etat"), b.get("valeur"), b.get("couverture_pct")
    if etat not in ETATS_BVC:
        dire("score_bvc_etat", f"Score BVC à l'état inconnu « {etat} »")
        return out
    if (v is not None) != (etat == "CALCULABLE"):
        dire("score_bvc_etat", f"Score BVC {etat} avec une valeur {v!r} — "
                               "seul CALCULABLE porte une valeur")
    vn, cn = _nb(v), _nb(couv)
    if v is not None and (vn is None or not 0 <= vn <= 100):
        dire("hors_bornes", f"score_bvc.valeur = {v!r}, hors [0, 100]")
    if cn is None or not 0 <= cn <= 100:
        dire("hors_bornes", f"score_bvc.couverture_pct = {couv!r}, hors [0, 100]")
    meta = t.get("_meta") or {}
    if (meta.get("suspendu") or meta.get("stale")) and etat != "NON_CALCULABLE":
        dire("score_bvc_sur_cours_perime",
             f"Score BVC {etat} sur un titre "
             f"{'suspendu' if meta.get('suspendu') else 'au cours périmé'}")
    if etat == "NON_CALCULABLE" or cn is None:
        return out
    try:
        from pipeline.score_bvc import COUVERTURE_MIN
    except ImportError:                                   # lancé hors de la racine
        from score_bvc import COUVERTURE_MIN              # type: ignore
    if etat == "CALCULABLE" and cn < COUVERTURE_MIN:
        dire("score_bvc_couverture",
             f"Score BVC calculé sur {cn:g} % du poids, sous le seuil de {COUVERTURE_MIN} %")
    fac = b.get("facteurs") or {}
    dispo = [f for f in fac.values() if isinstance(f, dict) and _nb(f.get("points")) is not None]
    somme_poids = sum(_nb(f.get("poids")) or 0 for f in dispo)
    if abs(somme_poids - cn) > 1e-6:
        dire("score_bvc_irreproductible",
             f"couverture publiée {cn:g} % ≠ somme des poids des facteurs disponibles "
             f"{somme_poids:g} %")
    elif vn is not None and cn > 0:
        attendu = sum(_nb(f.get("points")) for f in dispo) / cn * 100
        if abs(attendu - vn) > 0.01:
            dire("score_bvc_irreproductible",
                 f"Score BVC = {vn:g} alors que ses facteurs donnent {attendu:.2f}")
    return out


def controler_tous(tickers: list[dict]) -> dict:
    """Le relevé de tout un flux : par titre, et le décompte par code."""
    par_titre, compte = {}, {}
    for t in tickers or []:
        if not isinstance(t, dict):
            continue
        anomalies = controler(t)
        if anomalies:
            par_titre[t.get("symbol") or "?"] = anomalies
            for x in anomalies:
                compte[x["code"]] = compte.get(x["code"], 0) + 1
    erreurs = sum(1 for v in par_titre.values() for x in v
                  if x["gravite"] == "erreur")
    return {
        "titres_controles": len(tickers or []),
        "titres_avec_anomalie": len(par_titre),
        "erreurs": erreurs,
        "par_code": dict(sorted(compte.items(), key=lambda kv: -kv[1])),
        "detail": par_titre,
    }


def main() -> int:
    import json
    import sys
    from pathlib import Path

    chemin = Path(sys.argv[1] if len(sys.argv) > 1
                  else Path(__file__).resolve().parent.parent / "data.json")
    flux = json.loads(chemin.read_text(encoding="utf-8"))
    r = controler_tous(flux.get("tickers") or [])
    print(json.dumps(r, ensure_ascii=False, indent=2))
    # ⚠️ Sortie 0 même en présence d'anomalies : ce module RELÈVE, il ne
    # bloque pas. C'est un test dédié qui décide ce qui empêche de publier —
    # sinon toute anomalie nouvelle arrêterait le bulletin du matin.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

# En dessous, l'ADX dit qu'il n'y a PAS de tendance. Seuil usuel, et celui que
# le terminal affiche déjà comme « range ».
ADX_SANS_TENDANCE = 20

# Bornes des indicateurs, par construction mathématique. Un RSI hors [0, 100]
# n'est pas un RSI extrême : c'est un calcul faux.
BORNES = {
    "rsi": (0, 100), "stoch_k": (0, 100), "stoch_d": (0, 100),
    "adx": (0, 100), "adx_pdi": (0, 100), "adx_mdi": (0, 100),
    "score_fond": (0, 10), "score_tech": (0, 10),
    "v53": (0, 10), "bvc": (0, 10),
    # ⚠️ 29/10/2026 : plus de bornes `score_nlp`, `nlp`, `nlp_corpus`,
    # `nlp_news` — le pilier NLP est retiré du moteur (lot 2) et ces champs ne
    # sont plus publiés depuis le lot 1 ; leurs bornes ne s'armaient plus.
}

# Les setups qui affirment une DIRECTION. Les opposer à un ADX qui dit
# « pas de tendance » n'est pas une contradiction logique — l'ADX mesure la
# force, pas le sens — mais c'est une conviction directionnelle posée sur un
# terrain que notre propre indicateur déclare sans direction. Le lecteur doit
# le savoir.
SETUPS_DIRECTIONNELS = {"MOMENTUM CONFIRME", "PULLBACK HAUSSIER",
                        "CONTRARIEN", "FAIBLESSE"}


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

    # ── 2. La somme des poids ──────────────────────────────────────────────
    p = t.get("poids") or {}
    # ⚠️ Deux piliers depuis le 28/10/2026 : fondamental et technique. Le
    # pilier NLP (`n`) est retiré ; s'il réapparaissait avec un poids non nul,
    # la somme f + t ne ferait plus 100 et ce contrôle le dirait.
    parts = [_nb(p.get(k)) for k in ("f", "t")]
    if all(x is not None for x in parts):
        total = sum(parts)
        if abs(total - 100) > 1:
            dire("poids_somme", f"les poids totalisent {total:g} % et non 100",
                 "erreur")

    # ── 3. ⚠️ LE SCORE DOIT SE REFAIRE À LA MAIN ───────────────────────────
    # Le contrôle central. Si la note affichée ne se retrouve pas depuis les
    # deux notes et les deux poids publiés, alors l'un des cinq chiffres est
    # faux — et le lecteur qui refait le calcul le verra avant nous.
    #
    # La note v5.3 porte en plus des bonus/malus ; on ne vérifie donc que
    # l'écart au socle, et on ne s'alarme qu'au-delà de ce que les bonus
    # documentés peuvent produire (±1,5 point au total).
    notes = [_nb(t.get(k)) for k in ("score_fond", "score_tech")]
    if all(x is not None for x in parts) and all(x is not None for x in notes):
        socle = sum(n * w for n, w in zip(notes, parts)) / 100.0
        v53 = _nb(t.get("v53"))
        if v53 is not None and abs(v53 - socle) > 1.5:
            dire("score_irreproductible",
                 f"v53 = {v53:g} alors que fond×f + tech×t donne "
                 f"{socle:.2f} — écart {abs(v53 - socle):.2f}, au-delà de ce "
                 f"que les bonus/malus peuvent expliquer", "erreur")

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

    # ── 6. ⚠️ LA CONVICTION DIRECTIONNELLE SANS TENDANCE ───────────────────
    adx = _nb(t.get("adx"))
    setup = (t.get("setup") or "").strip().upper()
    if adx is not None and adx < ADX_SANS_TENDANCE and setup in SETUPS_DIRECTIONNELS:
        dire("direction_sans_tendance",
             f"setup « {setup} » alors que l'ADX vaut {adx:g} — sous "
             f"{ADX_SANS_TENDANCE}, notre propre indicateur dit qu'il n'y a "
             f"pas de tendance à suivre")

    # ── 7. (retiré le 29/10/2026) ──────────────────────────────────────────
    # « nlp_decompose_faux » vérifiait nlp = corpus + news. Les trois champs
    # ne sont plus publiés depuis le 28/10 et le pilier est retiré du moteur :
    # le contrôle était devenu inerte. Numérotation conservée pour la trace.

    # ── 8. Un signal exige de la confiance ─────────────────────────────────
    meta = t.get("_meta") or {}
    conf = _nb(meta.get("confidence"))
    sig = (t.get("sig") or "").upper()
    if conf is not None and conf <= 1 and any(
            m in sig for m in ("ACHAT", "ACHETER", "ÉVITER", "EVITER")):
        dire("signal_sans_confiance",
             f"signal « {t.get('sig')} » avec une confiance de {conf:g}/5",
             "erreur")

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

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
    "score_fond": (0, 10), "score_tech": (0, 10), "score_nlp": (0, 10),
    "v53": (0, 10), "bvc": (0, 10),
    "nlp": (-1, 1), "nlp_corpus": (-1, 1), "nlp_news": (-1, 1),
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
    parts = [_nb(p.get(k)) for k in ("f", "n", "t")]
    if all(x is not None for x in parts):
        total = sum(parts)
        if abs(total - 100) > 1:
            dire("poids_somme", f"les poids totalisent {total:g} % et non 100",
                 "erreur")

    # ── 3. ⚠️ LE SCORE DOIT SE REFAIRE À LA MAIN ───────────────────────────
    # Le contrôle central. Si la note affichée ne se retrouve pas depuis les
    # trois notes et les trois poids publiés, alors l'un des sept chiffres est
    # faux — et le lecteur qui refait le calcul le verra avant nous.
    #
    # La note v5.3 porte en plus des bonus/malus ; on ne vérifie donc que
    # l'écart au socle, et on ne s'alarme qu'au-delà de ce que les bonus
    # documentés peuvent produire (±1,5 point au total).
    notes = [_nb(t.get(k)) for k in ("score_fond", "score_nlp", "score_tech")]
    if all(x is not None for x in parts) and all(x is not None for x in notes):
        socle = sum(n * w for n, w in zip(notes, parts)) / 100.0
        v53 = _nb(t.get("v53"))
        if v53 is not None and abs(v53 - socle) > 1.5:
            dire("score_irreproductible",
                 f"v53 = {v53:g} alors que fond×f + nlp×n + tech×t donne "
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

    # ── 7. Le sentiment publié doit correspondre à ses composantes ─────────
    nlp, corpus, news = (_nb(t.get(k)) for k in ("nlp", "nlp_corpus", "nlp_news"))
    if all(x is not None for x in (nlp, corpus, news)):
        if abs(nlp - (corpus + news)) > 0.02:
            dire("nlp_decompose_faux",
                 f"nlp = {nlp:g} alors que corpus ({corpus:g}) + news "
                 f"({news:g}) donne {corpus + news:g}")

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
    age = _nb(meta.get("fond_age_jours"))
    if age is not None and age > 180:
        dire("fondamentaux_perimes",
             f"fondamentaux vieux de {age:.0f} jours ({meta.get('fond_asof')}) "
             f"pour {p.get('f', '?')} % du poids de la note")
    elif age is None and meta.get("source_fond") == "bpa_calcule":
        dire("fondamentaux_sans_date",
             "ratios calculés sur des fondamentaux dont la date est inconnue")

    return a


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

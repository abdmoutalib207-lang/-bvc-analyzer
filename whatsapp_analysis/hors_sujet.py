"""
Détection du hors-sujet dans le corpus WhatsApp — football en particulier.

POURQUOI
────────
Le groupe est un groupe d'investisseurs, mais c'est aussi un groupe de gens :
on y parle de football. Le vocabulaire des deux mondes se recouvre
dangereusement — on « achète » un joueur, une équipe « monte » ou « descend »,
un club « vaut » tant. Un message enthousiaste sur un transfert ne doit pas se
lire comme un signal haussier sur le titre cité dans la phrase d'à côté.

CE QUE LA MESURE DIT (corpus 919 372 messages, 2020-09 → 2026-07)
──────────────────────────────────────────────────────────────────
    messages mentionnant un ticker      48 832   ← seuls ceux-là sont scorés
    messages de football avérés          2 195
    messages QUI SONT LES DEUX              79   ← le bruit réellement nuisible

Soit 0,16 % des messages scorés. Pollution médiane par titre : 0,20 %. Aucun
titre suivi n'est matériellement affecté.

⚠️ Le filtre est donc CORRECT mais PEU RENTABLE. Il est écrit quand même
parce que le coût est nul et que la règle est juste ; il ne faut pas en
attendre un changement de score visible.

POURQUOI LE FILTRE EST ÉTROIT ET LE RESTERA
────────────────────────────────────────────
La tentation est d'élargir aux mots « évidents ». Mesuré, chacun est un piège —
part de ces occurrences qui relèvent vraiment du football :

    « but » / « buts »      893 occurrences →   2,8 %   (« dans le but de »)
    « match »               784 occurrences →   8,0 %   (« ça match avec »)
    « transfert »           284 occurrences →   1,1 %   (virement bancaire !)
    « stade »               400 occurrences →   5,2 %   (« au stade actuel »)
    « CAN »                 497 occurrences →   6,8 %   (anglais, darija)
    « CAF »                  65 occurrences →   9,2 %

Les retenir supprimerait ~2 900 messages pour n'en écarter que ~150 de
football : on détruirait dix-neuf messages financiers légitimes pour un
message de foot. **Ne pas élargir ce filtre sans refaire cette mesure.**

Aucun sigle de club marocain ou européen ne collide avec un ticker BVC ni avec
un code officiel BVC — vérifié sur les 110 sigles (RCA, WAC, MAS, FAR, FUS,
RSB, PSG, RMA…). Ils peuvent donc figurer ici sans risque.

ON MARQUE, ON NE SUPPRIME PAS
──────────────────────────────
Conformément à la méthode du projet (archiver plutôt que supprimer), la
fonction pose un drapeau. Le message reste dans le corpus, consultable et
recomptable ; il est simplement écarté de l'agrégation par titre.
"""

import re

# ── Noyau non ambigu ────────────────────────────────────────────────────────
# Chaque terme doit être IMPOSSIBLE à rencontrer dans une discussion boursière
# de bonne foi. Au moindre doute, il n'entre pas.

_CLUBS_MAROCAINS = (
    r"raja|wydad|difaa|hassania|renaissance berkane|moghreb|"
    r"maghreb de f[eè]s|olympique de safi|olympique de khouribga|"
    r"chabab mohamm[ée]dia|ittihad de tanger"
)

_CLUBS_ETRANGERS = (
    r"bar[çc]a|barcelone|real madrid|atl[ée]tico|s[ée]ville|valence cf|"
    r"psg|paris s\.?g|marseille|lyon|monaco fc|"
    r"liverpool|chelsea|arsenal|manchester|tottenham|newcastle|"
    r"bayern|dortmund|juventus|milan ac|naples|inter milan|"
    r"ajax|benfica|porto fc"
)

_COMPETITIONS = (
    r"botola|coupe du tr[oô]ne|"
    r"fifa|uefa|caf\b(?=.*\b(?:football|foot|club|[ée]quipe))|"
    r"mondial|coupe du monde|"
    r"ligue des champions|champions league|europa league|"
    r"premier league|la liga|serie a|bundesliga|ligue 1"
)

_JOUEURS_ET_SELECTION = (
    r"hakimi|ziyech|amrabat|bounou|en[- ]?nesyri|ounahi|"
    r"amine adli|brahim d[ií]az|regragui|renard\b(?=.*s[ée]lection)|"
    r"messi|ronaldo|mbapp[ée]|neymar|haaland|benzema|"
    r"lions de l['’ ]atlas|s[ée]lection nationale|[ée]quipe nationale"
)

_LEXIQUE_PROPRE_AU_FOOT = (
    r"penalty|carton rouge|carton jaune|hors[- ]jeu|coup franc|"
    r"mi[- ]temps|gardien de but|but v[ai]inqueur|"
    r"marqu[ée] un but|gagn[ée] le match|"
    r"mercato|derby\b|supporters?\b|tribune|"
    r"footballistique|\bfoot(?:ball)?\b"
)

_MOTIFS = {
    "clubs_marocains": _CLUBS_MAROCAINS,
    "clubs_etrangers": _CLUBS_ETRANGERS,
    "competitions": _COMPETITIONS,
    "joueurs": _JOUEURS_ET_SELECTION,
    "lexique": _LEXIQUE_PROPRE_AU_FOOT,
}

RX_FOOTBALL = re.compile(
    r"\b(?:" + "|".join(_MOTIFS.values()) + r")", re.IGNORECASE
)

# ⚠️ Délibérément ABSENTS — mesurés majoritairement hors football.
#    Les toucher demande de refaire la mesure documentée en tête de fichier.
TERMES_ECARTES_A_DESSEIN = frozenset(
    {"but", "buts", "match", "matchs", "stade", "can", "caf", "transfert",
     "equipe", "joueur", "score", "victoire", "defaite", "champion"}
)


def est_hors_sujet(texte) -> bool:
    """Vrai si le message relève manifestement du football.

    Tolère None et les valeurs non textuelles : le parseur produit des lignes
    médias et système dont le corps peut être vide.
    """
    if not texte or not isinstance(texte, str):
        return False
    return RX_FOOTBALL.search(texte) is not None


def motif_hors_sujet(texte):
    """Renvoie la catégorie qui a déclenché, ou None. Sert au journal et aux
    tests : un filtre dont on ne peut pas expliquer une décision n'est pas
    auditable."""
    if not texte or not isinstance(texte, str):
        return None
    for nom, motif in _MOTIFS.items():
        if re.search(r"\b(?:" + motif + r")", texte, re.IGNORECASE):
            return nom
    return None

"""Détection de séance fantôme — le 14/08/2026, férié, 114 bougies écrites.

IDBourse et Médias24 ont rediffusé la clôture du 13 en l'estampillant du 14.
`updated_at` étant notre seule autorité sur la date de séance, les trois
écrivains de chandelles ont suivi.

⚠️ La règle R9 (`chg=0` ET `vol=0`) ne détecte PAS ce cas : la source rediffuse
aussi les variations, donc 67 titres sur 77 portaient un `chg` non nul. Le
signal n'existe qu'à l'échelle du marché — une séance réelle ne reproduit jamais
toutes les clôtures au centime près. Mesuré : 71/71 identiques le 14/08 (férié)
contre 6/44 le 13/08 (séance cotée). La marge est telle qu'un seuil à 95 % ne
peut pas se tromper de côté.

⚠️ Aucun calendrier de fériés n'entre dans ce test : les fêtes marocaines sont
en partie lunaires. Le signal se déduit des données, et c'est ce qui le rend
durable.
"""

from seance import derniere_seance_connue, purger_seance_fantome


def _serie(veille, jour, close_veille, close_jour):
    return [{"d": veille, "o": close_veille, "h": close_veille,
             "l": close_veille, "c": close_veille, "v": 100},
            {"d": jour, "o": close_jour, "h": close_jour,
             "l": close_jour, "c": close_jour, "v": 0}]


def test_purge_une_seance_entierement_rediffusee(dossier_chandelles):
    """Le cas du 14/08 : toutes les clôtures identiques à la veille."""
    series = {f"T{i:02d}": _serie("2026-08-13", "2026-08-14", 100 + i, 100 + i)
              for i in range(30)}
    d = dossier_chandelles(series)
    jour, n = purger_seance_fantome(candles_dir=d)
    assert jour == "2026-08-14"
    assert n == 30, "les 30 bougies fictives doivent être retirées"
    assert derniere_seance_connue(candles_dir=d) == "2026-08-13"


def test_ne_purge_pas_une_vraie_seance(dossier_chandelles):
    """Séance cotée : les cours bougent, rien ne doit être touché."""
    series = {f"T{i:02d}": _serie("2026-08-12", "2026-08-13", 100 + i, 101 + i)
              for i in range(30)}
    d = dossier_chandelles(series)
    jour, n = purger_seance_fantome(candles_dir=d)
    assert jour is None and n == 0
    assert derniere_seance_connue(candles_dir=d) == "2026-08-13"


def test_ne_purge_pas_sous_le_nombre_minimum_de_titres(dossier_chandelles):
    """Trop peu de titres : la statistique n'est pas significative.

    Sans ce garde-fou, trois petites capitalisations inchangées suffiraient à
    faire disparaître une séance réelle.
    """
    series = {f"T{i}": _serie("2026-08-13", "2026-08-14", 100, 100) for i in range(5)}
    d = dossier_chandelles(series)
    jour, n = purger_seance_fantome(candles_dir=d)
    assert jour is None and n == 0


def test_le_mode_essai_ne_modifie_rien(dossier_chandelles):
    series = {f"T{i:02d}": _serie("2026-08-13", "2026-08-14", 100 + i, 100 + i)
              for i in range(30)}
    d = dossier_chandelles(series)
    jour, n = purger_seance_fantome(candles_dir=d, dry_run=True)
    assert jour == "2026-08-14"
    assert derniere_seance_connue(candles_dir=d) == "2026-08-14", \
        "dry_run doit signaler sans écrire"


def test_seuil_partiel_ne_declenche_pas(dossier_chandelles):
    """80 % d'identiques : sous le seuil de 95 %, on ne purge pas.

    Une séance très calme sur un marché peu liquide reste une séance.
    """
    series = {}
    for i in range(30):
        bouge = i < 6                       # 6/30 = 20 % de titres qui bougent
        series[f"T{i:02d}"] = _serie("2026-08-13", "2026-08-14",
                                     100 + i, (101 + i) if bouge else (100 + i))
    d = dossier_chandelles(series)
    jour, n = purger_seance_fantome(candles_dir=d)
    assert jour is None and n == 0

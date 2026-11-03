"""Le cache daté du jour décrit le jour pour TOUS les titres (03/11/2026).

Passé minuit, `update_data` réécrivait `_updated` à la date du jour mais ne
recalculait que les titres cotés du run : les autres gardaient les extrêmes de
la veille. SNA gardait un plus-haut de 52 semaines (2 600, séance du
03/11/2025) sorti de la fenêtre, et le contrôle bloquant
`test_import_sna_stk` refusait la publication.
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pipeline"))

import update_data as ud  # noqa: E402


def _b(d, h, l=None):
    return {"d": d, "o": h, "h": h, "l": l if l is not None else h, "c": h, "v": 10}


def _cache():
    bougies = [_b("2025-11-03", 2600.0)] + [_b(f"2026-{m:02d}-15", 1800.0) for m in range(1, 11)] \
        + [_b("2026-11-02", 1551.0)]
    return {"_updated": "2026-11-02T23:11:16+00:00",
            "SNA": {"candles": bougies, "n_candles": len(bougies),
                    "h52w": 2600.0, "l52w": 1551.0, "h90": 1800.0, "l90": 1551.0}}


def test_un_plus_haut_sorti_de_la_fenetre_est_recale_a_la_date_du_cache():
    c = _cache()
    assert ud.reancrer_extremes_du_cache(c, "2026-11-02T23:11:16+00:00") == []
    assert c["SNA"]["h52w"] == 2600.0, "la veille, la séance du 03/11/2025 est dans la fenêtre"
    modifies = ud.reancrer_extremes_du_cache(c, "2026-11-03T00:50:23+00:00")
    assert modifies == ["SNA"] and c["SNA"]["h52w"] == 1800.0


def test_le_recalage_est_branche_la_ou_l_horodatage_est_ecrit():
    src = (RACINE / "update_data.py").read_text(encoding="utf-8")
    i = src.index('_hd_all["_updated"] = datetime.now(timezone.utc).isoformat()')
    assert "reancrer_extremes_du_cache(_hd_all, _hd_all[\"_updated\"])" in src[i:i + 1500]

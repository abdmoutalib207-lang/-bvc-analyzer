"""Tout skill cité par le projet est versionné (ERRORS.md, famille 31).

La ligne `.claude/skills/*` de .gitignore écarte sans bruit un skill qui n'a pas
son exception `!.claude/skills/<nom>/`. Le 11/11/2026, le skill
`releve-etats-financiers` a été annoncé fusionné (PR #337) sans l'être, et
l'agent du lot 2 a travaillé sans lui.

Ce test lit les textes qui renvoient à un skill (agents, mémoire, skills,
CLAUDE.md) et exige que chaque `.claude/skills/<nom>/SKILL.md` cité soit SUIVI
par git — pas seulement présent sur le disque, où un fichier ignoré passerait.
"""
import re
import subprocess
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CITE = re.compile(r"\.claude/skills/([a-z0-9][a-z0-9-]*)/SKILL\.md")


def _suivis():
    sortie = subprocess.run(["git", "ls-files"], cwd=RACINE, capture_output=True, text=True, check=True)
    return set(sortie.stdout.splitlines())


def _textes(suivis):
    for f in sorted(suivis):
        if f == "CLAUDE.md" or (f.startswith((".claude/agents/", ".claude/memory/", ".claude/skills/")) and f.endswith(".md")):
            yield f, (RACINE / f).read_text(encoding="utf-8")


def _citations(suivis):
    cites = {}
    for f, texte in _textes(suivis):
        for nom in CITE.findall(texte):
            cites.setdefault(nom, set()).add(f)
    return cites


def test_tout_skill_cite_est_versionne():
    suivis = _suivis()
    cites = _citations(suivis)
    assert "releve-etats-financiers" in cites, "le renvoi de l'agent lecteur-comptes au skill a disparu"
    manquants = {n: sorted(src) for n, src in cites.items() if f".claude/skills/{n}/SKILL.md" not in suivis}
    assert not manquants, f"skills cités mais non versionnés (exception .gitignore manquante ?) : {manquants}"


def test_temoin_un_skill_non_suivi_est_detecte():
    suivis = _suivis() - {".claude/skills/releve-etats-financiers/SKILL.md"}
    cites = _citations(_suivis())
    manquants = [n for n in cites if f".claude/skills/{n}/SKILL.md" not in suivis]
    assert manquants == ["releve-etats-financiers"]

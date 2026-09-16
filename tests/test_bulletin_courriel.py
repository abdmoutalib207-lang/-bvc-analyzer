#!/usr/bin/env python3
"""Un secret absent n'est pas une panne — et ne doit pas sonner comme telle.

LE DÉFAUT, ET SA MESURE
───────────────────────
« Il y a un problème concernant les run de 9h45, toujours la même chose, il se
déclenche, c'est très pénalisant » (Noure, 16/09/2026).

Relevé le 16/09 sur la TOTALITÉ des exécutions du workflow « Bulletin quotidien
par courriel » depuis sa création le 02/09 :

    20 exécutions · 20 échecs · 0 courriel envoyé

Toutes s'arrêtaient au même endroit — l'étape qui vérifie la configuration —
sur un `exit 1`, parce que les secrets `MAIL_TO`, `MAIL_USERNAME` et
`MAIL_PASSWORD` ne sont pas renseignés dans le dépôt. Chaque `exit 1` envoie au
propriétaire un courriel « workflow failed ». Deux par matinée ouvrée, arrivant
entre 9h et 11h à Casablanca : ce sont les « run de 9h45 ».

Le reste fonctionne : l'étape « Composer le bulletin » réussit à chaque fois.
Le bulletin est produit, complet ; seul l'envoi manque.

CE QUE CE FICHIER PROTÈGE
─────────────────────────
**Un état de configuration ne se signale pas par un échec.** Il ne se répare
pas en réessayant, et il ne changera pas parce qu'on aura crié vingt fois. Ce
que produit un `exit 1` répété n'est pas une alerte, c'est un bruit quotidien —
et ce bruit NOIE les échecs qui, eux, demandent une intervention. Le dépôt
documente ce piège depuis le 18/08 : « une alerte toujours allumée n'alerte
plus », et la même leçon a coûté le drapeau `stale` du 14/08.

⚠️ La règle inverse compte autant : ce qui reste bloquant, c'est l'ENVOI. Le
jour où les trois secrets existeront, un refus du serveur SMTP devra de nouveau
faire échouer le job. Un test ci-dessous l'exige, pour qu'en supprimant le bruit
on ne supprime pas aussi l'alarme.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / ".github" / "workflows" / "bulletin_mail.yml"

SECRETS = ("MAIL_TO", "MAIL_USERNAME", "MAIL_PASSWORD")


@pytest.fixture(scope="module")
def workflow():
    if not FICHIER.exists():
        pytest.skip("bulletin_mail.yml absent")
    return yaml.safe_load(FICHIER.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def etapes(workflow):
    return workflow["jobs"]["envoyer"]["steps"]


def _etape(etapes, morceau):
    for e in etapes:
        if morceau.lower() in (e.get("name") or "").lower():
            return e
    raise AssertionError(f"étape « {morceau} » introuvable")


def test_la_verification_de_configuration_ne_fait_pas_echouer_le_job(etapes):
    """Le cœur du correctif : plus de `exit 1` sur un secret absent.

    ⚠️ C'est ce `exit 1` qui a produit vingt courriels d'alerte en dix jours
    ouvrés sans rien réparer. Le remettre ferait repartir le bruit à la
    prochaine matinée.
    """
    e = _etape(etapes, "Vérifier la configuration")
    script = e["run"]
    assert "exit 1" not in script, (
        "l'étape échoue encore quand un secret manque — c'est exactement ce "
        "qui envoyait deux courriels d'alerte par matinée pour un état qui ne "
        "se répare pas en réessayant")
    assert "::error::" not in script, (
        "une annotation d'erreur marque le run comme fautif : utiliser "
        "`::notice::` pour un état de configuration")


def test_la_configuration_manquante_se_dit_quand_meme(etapes):
    """Vert ne veut pas dire muet. « Une absence se dit, elle ne se comble pas. »

    Sans cette exigence, le correctif troquerait un bruit permanent contre un
    silence permanent — et le bulletin ne partirait jamais sans que rien ne
    l'indique nulle part.
    """
    script = _etape(etapes, "Vérifier la configuration")["run"]
    assert "GITHUB_STEP_SUMMARY" in script, "rien n'est écrit dans le résumé du run"
    for s in SECRETS:
        assert s in script, f"le résumé ne nomme pas le secret {s}"
    assert re.search(r"Settings\s*→\s*Secrets", script), (
        "le résumé ne dit pas OÙ poser les secrets — une alerte qu'on ne sait "
        "pas interpréter n'est pas une alerte")
    assert "::notice::" in script, (
        "rien n'apparaît dans les annotations du run")


def test_aucun_envoi_n_est_tenté_sans_configuration(etapes):
    """L'étape d'envoi est conditionnée à la présence des trois secrets.

    Sans cette condition, l'action d'envoi repartirait avec des champs vides et
    échouerait sur « At least one of 'to', 'cc' or 'bcc' must be specified » —
    le message d'origine, celui que personne ne savait interpréter.
    """
    e = _etape(etapes, "Envoyer")
    cond = e.get("if") or ""
    assert "configuree" in cond, (
        f"l'envoi n'est pas conditionné à la configuration : if = {cond!r}")
    assert "compose.outputs.envoyer" in cond, (
        "l'envoi n'est plus conditionné à la composition du bulletin")


def test_la_verification_publie_son_verdict(etapes):
    """La condition ci-dessus n'a de sens que si quelqu'un produit la sortie."""
    e = _etape(etapes, "Vérifier la configuration")
    assert e.get("id") == "config", (
        "l'étape n'a pas d'identifiant : sa sortie est inatteignable")
    assert "configuree=true" in e["run"] and "configuree=false" in e["run"], (
        "les deux verdicts ne sont pas émis")


def test_un_refus_du_serveur_reste_un_echec(etapes):
    """⚠️ LA RÈGLE INVERSE. En supprimant le bruit, ne pas supprimer l'alarme.

    Une fois les secrets posés, un refus SMTP est un vrai incident : le
    bulletin du matin n'est pas parti, et personne ne le saura autrement. Cette
    étape ne doit donc jamais devenir tolérante.
    """
    e = _etape(etapes, "Envoyer")
    assert not e.get("continue-on-error"), (
        "l'envoi est devenu tolérant : un refus du serveur passerait inaperçu")


def test_le_resume_distingue_composé_de_envoyé(etapes):
    """Trois situations, trois phrases.

    « Non composé » (collecte insuffisante), « composé mais envoi en attente »,
    « envoyé ». L'ancien résumé n'en connaissait que deux et annonçait
    « Envoyé » dès que le bulletin était composé — y compris les vingt fois où
    rien n'était parti.
    """
    script = _etape(etapes, "Résumé")["run"]
    assert "configuree" in script, (
        "le résumé ne regarde pas si l'envoi a réellement eu lieu")
    assert script.count("GITHUB_STEP_SUMMARY") >= 3, (
        "le résumé ne distingue pas les trois situations")
    assert re.search(r"attente", script, re.I), (
        "le cas « composé mais non envoyé » n'est pas nommé")


def test_le_bulletin_reste_compose_avant_toute_question_d_envoi(etapes):
    """L'ordre compte : composer, puis regarder si l'on peut envoyer.

    C'est ce qui permet de dire « le bulletin est bon, seul l'envoi manque » —
    et c'est vrai : les vingt exécutions ont toutes composé correctement.
    """
    noms = [(e.get("name") or "") for e in etapes]
    i_compose = next(i for i, n in enumerate(noms) if "Composer" in n)
    i_config = next(i for i, n in enumerate(noms) if "configuration" in n.lower())
    i_envoi = next(i for i, n in enumerate(noms) if n.strip() == "Envoyer")
    assert i_compose < i_config < i_envoi, (
        f"ordre des étapes inattendu : {noms}")


def test_le_workflow_ne_commite_rien(workflow):
    """Le quota de reconstruction de Pages est la ressource rare du projet."""
    assert workflow.get("permissions", {}).get("contents") == "read", (
        "le workflow a obtenu le droit d'écrire : il n'en a pas besoin")
    script_complet = "\n".join(e.get("run", "") for e in
                               workflow["jobs"]["envoyer"]["steps"])
    assert "git push" not in script_complet, "le workflow pousse un commit"

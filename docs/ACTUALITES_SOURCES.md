# Actualités : intégration du 20 septembre 2026

Le collecteur horaire existant reste le propriétaire de `news.json`.
Les prix, indicateurs, pondérations et corpus WhatsApp ne sont pas modifiés.

## Collecte directe

L'index des communiqués d'émetteurs AMMC fournit le titre, l'horodatage publié
et le lien direct du PDF. Le statut `listed_officially` signifie que le
document est référencé par l'AMMC, pas que son contenu financier a été analysé
ou certifié par notre moteur. Pas de téléchargement/republication du PDF.
L'heure de collecte et la première observation restent distinctes.

Une erreur ou un changement de structure est enregistré dans `source_health`
et signalé dans le radar. L'archive antérieure reste disponible
dans sa fenêtre de sept jours. Cette fenêtre est éditoriale : elle ne marque
pas l'expiration juridique ou économique des événements.

## Alertes indirectes

Ajout de neuf recherches Google News limitées aux domaines : MEF, Maroclear,
Attijariwafa IR, Maroc Telecom, LabelVie, Managem, Akdital, Cosumar, TGCC.
Bourse, BAM, HCP et les principaux médias étaient déjà collectés.
Ces relais portent `classification=SIGNAL`, `validation_status=unverified` et
le domaine ciblé. Leur présence dans la configuration ne garantit pas une
publication récente : le compte de résultats est conservé par collecte.
Zéro résultat est marqué `no_items_or_error`, sans prétendre distinguer un
flux vide d'une panne. Les doublons de lien PDF natif/RSS sont éliminés.

## Affichage et limites

Le radar distingue « Document officiel référencé » et « Alerte à recouper ».
Le terminal existant affiche la source « AMMC documents » pour les liens
issus de l'index officiel. Les articles portent `usable_for_score=false` ; aucun
branchement au score n'est ajouté. Les publications institutionnelles sont
neutres : le vocabulaire du titre ne devient pas une recommandation.
Une date absente n'est plus remplacée par l'heure actuelle dans le RSS.
Le compteur d'audience tiers du radar est retiré : aucune télémétrie vers ce
service n'est nécessaire au fil d'actualités. Le code du terminal principal
n'est pas republié dans ce lot ; ses contenus WhatsApp restent à traiter.
Les collectes RSS indépendantes sont parallélisées (huit connexions au maximum)
pour rester dans le délai du workflow existant.

Restent à développer : lecture financière des PDF, déduplication sémantique
entre éditeurs, suivi des versions, collecte directe des autres institutions
et émetteurs, vérification contractuelle source par source. Aucun compte X ni
service d'IA tiers n'est connecté. L'index AMMC couvre ici sa première page ;
une panne longue peut nécessiter un rattrapage des pages antérieures.

## Vérifications

Tests sans réseau : publication datée, exclusion des URL externes et dates
invalides/futures, distinction relais/document, panne avec conservation de
l'archive et première observation, absence de date artificielle.
Collecte réelle et compilation JSX/JavaScript réalisées avant livraison.

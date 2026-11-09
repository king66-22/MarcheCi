# MarchéCI — Réseaux et communications

Cette page décrit les réseaux définis dans `compose.yaml` et les appels réellement visibles dans le code.

## 1. Réseaux Docker

| Réseau | Membres | Accès publié |
|---|---|---|
| `front` | Nginx Gateway et les quatre API | Seule Gateway publie le port hôte (`GATEWAY_PORT`, 80 par défaut) |
| `back` | Les quatre API, PostgreSQL, Redis et RabbitMQ | Aucun port publié |
| `monitoring` | Services Zabbix et sa base PostgreSQL | Interface Web liée à `MON_WEB_BIND` (`127.0.0.1` par défaut) et `MON_WEB_PORT` (8090 par défaut) |

La pile Zabbix rejoint aussi les réseaux Compose `marcheci_front` et `marcheci_back` comme réseaux externes. Elle suppose donc que la pile principale a déjà créé ces réseaux.

Les API se trouvent sur les deux réseaux `front` et `back`; cette configuration permet à Gateway de les joindre et aux services de joindre leurs dépendances. Elle donne aussi aux API l’accès au réseau `front`, un choix d’isolation perfectible. La base et les brokers ne sont accessibles que depuis `back`.

## 2. Appels et événements

| Origine | Destination | Usage | Comportement en cas de panne |
|---|---|---|---|
| Navigateur | Gateway | SPA et API sous `/api/{service}/` | Nginx renvoie une réponse HTTP d’indisponibilité |
| Gateway | Catalogue | Liste, détail, catégories; DNS Docker pour répartir les répliques | Erreur JSON de Gateway |
| Gateway | Commandes, Utilisateurs, Notifications | API HTTP du service correspondant | Erreur JSON de Gateway |
| Commandes | Catalogue | Lire produits, prix et stock; ajuster le stock | La commande est refusée ou compensée si l’opération échoue |
| Commandes | Utilisateurs | Authentifier le compte système `svc.commandes` pour obtenir un JWT d’appel interne | La création de commande ne peut pas continuer |
| Commandes | RabbitMQ | Publier `order.created` depuis la table outbox | L’événement reste en attente et le worker retente environ toutes les deux secondes |
| Notifications | RabbitMQ | Consommer l’événement, persister la notification, acquitter le message | Trois files de reprise à TTL croissant, puis DLQ |
| Catalogue | Redis | Cache des listes de produits | Redis est facultatif; Catalogue continue sans cache |
| Utilisateurs | Redis | Limitation des tentatives de connexion | Le mode dégradé dépend de la configuration; la limite distribuée n’est plus assurée si Redis est coupé |

Les services utilisent des appels HTTP synchrones seulement lorsqu’une vérification immédiate est requise, par exemple la validation du prix et du stock. La notification est asynchrone.

### Flux d’une commande

1. Le navigateur conserve le panier dans `localStorage` et envoie les identifiants de produits et quantités.
2. Commandes récupère les produits actifs et leurs prix auprès de Catalogue; les montants envoyés par le navigateur ne font pas autorité.
3. Commandes vérifie puis ajuste le stock auprès de Catalogue et enregistre les prix comme instantanés.
4. La commande et l’événement outbox sont validés dans la même base et la même transaction.
5. Le worker publie l’événement à RabbitMQ avec confirmation. Une interruption du broker ne supprime donc pas l’événement enregistré.
6. Notifications persiste une notification au statut `SIMULE_ENVOYE`, puis acquitte l’événement. Aucun fournisseur réel d’e-mail ou de SMS n’est configuré.

RabbitMQ utilise une file durable, trois files de reprise (`order.created.retry.1..3`) à TTL 2, 4 et 8 secondes par défaut, et une dead-letter queue `order.created.dlq`. Le rejeu DLQ est exposé par une route réservée à `ADMIN`.

## 3. Authentification des appels

Utilisateurs émet les JWT signés en HS256. Les services valident le même secret, l’émetteur et l’audience. Pour ajuster le stock, Commandes utilise un compte système `svc.commandes` configuré au bootstrap avec le rôle `ADMIN`.

Ce compte système simplifie l’authentification entre services mais partage des privilèges d’administration. Un rôle de service à privilèges minimaux serait préférable avant un déploiement exposé.

## 4. Gateway et santé

- Nginx écoute sur le port 8080 du conteneur; le port hôte est configurable par `GATEWAY_PORT`.
- Gateway sert la SPA, route les API sous `/api/` et expose les interfaces OpenAPI sous `/docs/{service}/`.
- Le résolveur Docker `127.0.0.11` avec validité de 5 secondes permet de redécouvrir les répliques du Catalogue sans redémarrer Nginx.
- Les timeouts de connexion et de lecture sont configurés; les erreurs 500–504 sont remplacées par une réponse JSON générique.
- `GET /health` de Gateway confirme uniquement que Nginx répond. Chaque API expose également son propre contrôle de santé; les scripts de lancement vérifient ces routes via Gateway.
- PostgreSQL, Redis, RabbitMQ et les API ne publient pas de ports hôtes dans la pile principale.

## 5. Volumes persistants

| Volume Compose | Contenu |
|---|---|
| `pgdata` | Données des quatre bases logiques PostgreSQL |
| `rabbitdata` | Données RabbitMQ et files durables |
| `zabbixdb` (pile facultative) | Base de supervision |

Redis n’a pas de volume persistant dans le Compose principal : il contient un cache recalculable. La commande d’arrêt du launcher utilise `docker compose down` sans `--volumes`, donc elle conserve les volumes de données.

## 6. Secrets et configuration

- `.env` contient les variables nécessaires à l’interpolation Compose; il est ignoré par Git.
- `scripts/sync_secrets.py` génère les fichiers locaux ignorés par Git que Compose monte sous `/run/secrets/`.
- Le mode `--missing-only` du launcher crée uniquement les fichiers absents afin de préserver ceux déjà présents.
- Les fichiers montés par Compose restent des fichiers locaux; ils ne forment pas un coffre de secrets chiffré.

# MarchéCI — Spécification des API (Étape 1, niveau contractuel)

Version détaillée complétée en Étape 7 (OpenAPI par service, auto-découverte via `/docs` FastAPI).
Conventions globales : JSON ; timestamps ISO 8601 UTC ; erreurs `{"detail": "..."}` ;
authentification `Authorization: Bearer <JWT>` ; montants en FCFA entiers.

## 1. Service catalogue — `/api/catalogue`

| Méth | Route | Auth | Entrée | Sortie | Erreurs |
|---|---|---|---|---|---|
| GET | `/health` | — | — | `{"status":"ok/down","components":{"database":"up/down","cache":"up/degraded"}}` | 503 si PostgreSQL est indisponible; Redis dégradé n’arrête pas Catalogue |
| GET | `/products` | — | query : `q`, `category`, `ids` (interne), `page`, `page_size`, `in_stock` | page `items[]`, `total`, `page`, `page_size` | 422 |
| GET | `/products/{id}` | — | — | produit complet, `images[]` (galerie ordonnée), `owner_id` | 404 |
| GET | `/products/mine` | COMMERCANT (+ ADMIN) | query `page`, `page_size` | produits du commerçant, y compris désactivés | 401, 403 |
| GET | `/categories` | — | — | liste catégories | — |
| POST | `/categories` | ADMIN | `{slug, name}` | 201 catégorie | 401, 403, 409 |
| POST | `/products` | COMMERCANT ou ADMIN | `{slug, name, description?, price_xof, category_id?, stock?, image_url?}` | 201 produit (`owner_id` = commerçant) | 401, 403, 409, 422 |
| PUT | `/products/{id}` | ADMIN ou COMMERCANT propriétaire | produit partiel | produit mis à jour | 401, 403, 404, 422 |
| DELETE | `/products/{id}` | ADMIN ou COMMERCANT propriétaire | — | soft-delete `is_active=false` | 401, 403, 404 |
| POST | `/products/{id}/images` | ADMIN ou COMMERCANT propriétaire | multipart `file` (JPEG/PNG/WebP, ≤ 8 Mo) | 201 `{id, url, position}` ; première photo = couverture | 401, 403, 404, 409 (10 photos max), 413, 422 |
| DELETE | `/products/{id}/images/{image_id}` | ADMIN ou COMMERCANT propriétaire | — | photo supprimée ; couverture reportée sur la suivante | 401, 403, 404 |
| POST | `/products/{id}/images/{image_id}/cover` | ADMIN ou COMMERCANT propriétaire | — | définit `image_url` du produit | 401, 403, 404 |
| POST | `/products/{id}/adjust-stock` | service→service (JWT users) | `{delta: -3}` | nouveau stock | 409 si stock < 0 |

Cache Redis : clé `products:list:<q>:<cat>:<page>` TTL **60 s** ; invalidation des
clés `products:*` à chaque POST/PUT/DELETE et à chaque ajout/suppression de photo.

Photos : stockées dans le volume `media_data` (`MEDIA_ROOT=/data/media`), servies
par la gateway sous `/media/products/<fichier>` avec un cache navigateur d’un jour.
Le contenu est vérifié par Pillow, redressé selon l’EXIF et converti en JPEG
(côté le plus long ramené à 1 600 px).

## 2. Service commandes — `/api/commandes`

| Méth | Route | Auth | Entrée | Sortie | Erreurs |
|---|---|---|---|---|---|
| GET | `/health` | — | — | `{"status":"ok/down","components":{"database":"up/down","rabbitmq":"up/down","catalogue":"reachable/unreachable/broken"}}` | 503 si une dépendance critique est indisponible |
| POST | `/orders` | CLIENT+ | `{items:[{product_id, quantity}], delivery_address, delivery_phone}` | 201 `order` (prix calculés serveur via catalogue) | 400 stock/catalogue indisponible, 401, 422 |
| GET | `/orders` | CLIENT+ (ADMIN : toutes) | query `status`, `page` | historique paginé | 401 |
| GET | `/orders/{id}` | propriétaire ou ADMIN | — | détail + lignes | 401, 403, 404 |
| PATCH | `/orders/{id}/status` | ADMIN | `{status}` | commande mise à jour | 401, 403, 404, 409 transition invalide |
| POST | `/orders/{id}/cancel` | propriétaire (si EN_ATTENTE/CONFIRMEE), ADMIN | — | commande ANNULÉE + restitution stock | 401, 403, 404 |

Transitions de statut autorisées :
EN_ATTENTE → CONFIRMEE → EN_PREPARATION → EXPEDIEE → LIVREE ;
EN_ATTENTE/CONFIRMEE → ANNULEE (restitution stock).

## 3. Service utilisateurs — `/api/utilisateurs`

| Méth | Route | Auth | Entrée | Sortie | Erreurs |
|---|---|---|---|---|---|
| GET | `/health` | — | — | `{"status":"ok/down","components":{"database":"up/down"}}` | 503 |
| POST | `/auth/register` | — | `{email, password, full_name, phone?, role?}` (`role` = `CLIENT` ou `COMMERCANT`, défaut `CLIENT`) | 201 `{id, email, role}` | 409 email, 422 |
| POST | `/auth/login` | — | `{email, password}` | `{access_token, token_type, expires_in, role}` | 401 (message générique), 429 rate-limit |
| GET | `/users/me` | JWT | — | profil (jamais de hash) | 401 |
| PUT | `/users/me` | JWT | `{full_name?, phone?, current_password?, new_password?}` (`current_password` requis pour changer le mot de passe) | profil | 401, 422 |
| GET | `/users` | ADMIN | query `page`, `page_size` | liste paginée des profils | 401, 403 |
| PATCH | `/users/{id}/role` | ADMIN | `{role: "CLIENT"\|"COMMERCANT"}` | profil mis à jour | 401, 403, 404, 422 ; le rôle ADMIN est protégé |

JWT : HS256, expiration configurable (défaut 60 min), émetteur et audience vérifiés; le payload comprend notamment `sub`, `role`, `iss`, `aud` et `exp`.
Limitation des tentatives : 5 échecs par fenêtre et par adresse e-mail (Redis). Si Redis est absent ou désactivé, la limite distribuée n’est pas assurée.

## 4. Service notifications — `/api/notifications`

| Méth | Route | Auth | Entrée | Sortie | Erreurs |
|---|---|---|---|---|---|
| GET | `/health` | — | — | `{"status":"ok/down","components":{"database":"up/down","rabbitmq":"up/down","consumer":"up/down"}}` | 503 si une dépendance critique est indisponible |
| GET | `/notifications` | ADMIN | query `page`, `page_size` | historique paginé (`items`, `total`, `page`, `page_size`) | 401, 403 |
| POST | `/internal/replay-dlq` | ADMIN | query `limit` (1–100, défaut 20) | `{replayed, limit}` | 401, 403, 503 |

Consommation RabbitMQ (hors HTTP) :
- File principale `order.created` durable, exchange direct durable `marcheci`, DLQ durable `order.created.dlq`.
- Retry : trois files durables `order.created.retry.1..3`, TTL par défaut 2/4/8 s; expiration vers la file principale; les erreurs permanentes et les tentatives épuisées vont dans la DLQ.
- Les publications utilisent les confirmations RabbitMQ et des messages persistants. Commandes inscrit chaque événement dans `outbox_events` avec la commande, puis un worker le publie après commit.
- Rejeu DLQ manuel : `POST /api/notifications/internal/replay-dlq` (ADMIN); un message de la DLQ est acquitté seulement après confirmation de republication.
- Le consommateur ignore un événement déjà traité pour le même `order_id`, afin de limiter les doublons après une reprise.
- Le statut `SIMULE_ENVOYE` identifie explicitement l'absence de fournisseur réel.

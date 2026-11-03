# MarchéCI — Spécification des API (Étape 1, niveau contractuel)

Version détaillée complétée en Étape 7 (OpenAPI par service, auto-découverte via `/docs` FastAPI).
Conventions globales : JSON ; timestamps ISO 8601 UTC ; erreurs `{"detail": "..."}` ;
authentification `Authorization: Bearer <JWT>` ; montants en FCFA entiers.

## 1. Service catalogue — `/api/catalogue`

| Méth | Route | Auth | Entrée | Sortie | Erreurs |
|---|---|---|---|---|---|
| GET | `/health` | — | — | `{"status":"ok"}` | 503 (Redis/PG KO) |
| GET | `/products` | — | query : `q`, `category_slug`, `page`, `page_size`, `in_stock` | panier paginé `items[]`, `total`, `page` | 422 |
| GET | `/products/{id}` | — | — | produit complet | 404 |
| GET | `/categories` | — | — | liste catégories | — |
| POST | `/categories` | ADMIN | `{slug, name}` | 201 catégorie | 401, 403, 409 |
| PUT | `/products/{id}` | ADMIN | produit partiel | produit mis à jour | 401, 403, 404, 422 |
| DELETE | `/products/{id}` | ADMIN | — | soft-delete `is_active=false` | 401, 403, 404 |
| POST | `/products/{id}/adjust-stock` | service→service (JWT users) | `{delta: -3}` | nouveau stock | 409 si stock < 0 |

Cache Redis : clé `products:list:<q>:<cat>:<page>` TTL **60 s** ; invalidation des
clés `products:*` à chaque POST/PUT/DELETE.

## 2. Service commandes — `/api/commandes`

| Méth | Route | Auth | Entrée | Sortie | Erreurs |
|---|---|---|---|---|---|
| GET | `/health` | — | — | `{"status":"ok","rabbitmq":"up/down"}` | 503 |
| POST | `/orders` | CLIENT+ | `{items:[{product_id, quantity}], delivery_address, delivery_phone}` | 201 `order` (prix calculés serveur via catalogue) | 400 stock/katalogue KO, 401, 422 |
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
| GET | `/health` | — | — | `{"status":"ok"}` | 503 |
| POST | `/auth/register` | — | `{email, password, full_name, phone?}` | 201 `{id, email, role}` | 409 email, 422 |
| POST | `/auth/login` | — | `{email, password}` | `{access_token, token_type, expires_in, role}` | 401 (message générique), 429 rate-limit |
| GET | `/users/me` | JWT | — | profil (jamais de hash) | 401 |
| PUT | `/users/me` | JWT | `{full_name?, phone?, password? (current_password requis)} | profil | 401, 422 |
| GET | `/users` | ADMIN | query `page` | liste profils | 401, 403 |

JWT : HS256, expération configurable (défaut 60 min), payload {sub, role, exp}.
Limitation anti-brute-forcement : 5 échecs/5 min/email (Redis).

## 4. Service notifications — `/api/notifications`

| Méth | Route | Auth | Entrée | Sortie | Erreurs |
|---|---|---|---|---|---|
| GET | `/health` | — | — | `{"status":"ok","consumer":"up/down"}` | 503 |
| GET | `/notifications` | ADMIN | query `page`, `status` | historique paginé | 401, 403 |

Consommation RabbitMQ (hors HTTP) :
- File principale `order.created` (durable, quorum queue simple), DL `order.created.dlq`.
- Retry : 3 tentatives, backoff 5 s/20 s/60 s, puis DLQ.
- Rejeu DLQ manuel : `POST /api/notifications/internal/replay-dlq` (ADMIN).
- Le statut **SIMULÉ_ENVOYÉ** identifie explicitement l'absence de fournisseur réel.

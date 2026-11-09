# MarchéCI — Architecture technique (Étape 1)

> Statut : validée le 2026-11-03. Sert de référence contractuelle pour Étapes 2 à 7.
> Contrainte source : sujet « Projets Cloud Native — Projet 1 : MarchéCI » (PDF, version apprenant).

## 1. Vue d'ensemble

Plateforme e-commerce en **microservices conteneurisés**, point d'entrée unique Nginx,
une base de données logique par service, cache Redis, messagerie RabbitMQ,
supervision Zabbix. Le Compose est conçu pour un serveur Linux; le budget et un
démarrage complet en moins de deux minutes restent des objectifs à mesurer.

```
                         Internet (hôte :80 via gateway)
                                   │
                      ┌────────────▼─────────────┐
                      │   gateway (Nginx 1.27)   │ routage "/", /api/*
                      └──┬──────┬──────┬──────┬──┘
             réseau FRONT│      │      │      │
     ┌───────────────────▼┐ ┌───▼──────┐ ┌▼─────────────┐ ┌▼──────────────┐
     │ catalogue (×1 à ×3)│ │ commandes│ │ utilisateurs │ │ notifications │
     │ FastAPI, stateless │ │ FastAPI  │ │ FastAPI+JWT  │ │ consommateur  │
     └──────┬─────────────┘ └──┬───────┘ └──────┬───────┘ └───┬───────────┘
            │ réseau BACK      │HTTP→catalogue  │             │
     ┌──────▼─────┐ ┌──────────▼────────────┐ ┌─▼─────────────┐
     │ Redis 7.4  │ │ PostgreSQL 16 (4 bases│ │ RabbitMQ 3.13 │
     │ cache 60 s │ │ logiques, 4 comptes)  │ │ file + DLQ    │
     └────────────┘ └───────────────────────┘ └───────────────┘
```

## 2. Rôle et limites de responsabilité de chaque composant

| Composant | Responsabilité exclusive | Interdits |
|---|---|---|
| **catalogue** | Produits, catégories, stock, recherche, filtres, images (URL), prix master | Ne connaît ni commandes ni clients |
| **commandes** | Commandes, statuts, montants, lignes avec instantanés de prix et table outbox | Le panier reste dans le navigateur ; ne modifie jamais les tables Catalogue et ajuste le stock via son API |
| **utilisateurs** | Comptes, mots de passe hachés, émission/validation JWT, rôles CLIENT, ADMIN | Ne connaît ni produits ni commandes |
| **notifications** | Consommation `order.created`, historique des notifications, envoi simulé clairement marqué | Ne lit aucune autre base |
| **gateway** | Routage, limitation des chemins exposés, timeouts, round-robin catalogue | Aucune logique métier |
| **frontend** | SPA React/TS, panier utilisateur (localStorage), formulaires | Aucun prix inventé : tout vient des APIs |
| **PostgreSQL** | 4 bases logiques, 4 comptes SQL, un serveur (optimisation VM 4 Go) | Isolation stricte par compte (`GRANT` sur une seule base chacun) |
| **Redis** | Cache 60 s de la liste produits, invalidation à l'écriture | Aucune donnée source de vérité |
| **RabbitMQ** | Événements asynchrones commandes → notifications | Aucun appel synchrone critique ne dépend d'un broker |
| **Outbox Commandes** | Rend durable la publication après le commit de commande | Livraison exactement une fois non garantie; consommation idempotente par commande |

## 3. Flux de panier → commande (exigence prix validés serveur)

1. Le client compose un panier (local, résumé revalidé à la validation de commande).
2. `POST /orders` (JWT client) → **Commandes** appelle Catalogue `GET /products?ids=…`
   pour reconstituer les prix réels (jamais ceux du navigateur).
3. Copie (`snapshot`) prix + nom produit dans `order_items` (résistance à la modification
   ultérieure du catalogue).
4. Contrôle du stock : refus si stock insuffisant. Décrément par appel catalogue
   `POST /products/{id}/adjust-stock` — en cas d'échec, la commande passe à `ANNULÉE`
   (limitation documentée : pas de saga distribuée complète dans ce périmètre).
5. La commande et `order.created` sont écrits dans la même transaction locale
   PostgreSQL (`orders`, `order_items`, `outbox_events`). Un worker Commandes
   publie ensuite l’événement avec confirmation RabbitMQ. Si le broker est
   indisponible, la commande reste enregistrée et l’événement reste en attente
   dans l’outbox jusqu’à sa publication.
6. Notifications consomme le message durable, persiste la notification puis
   accuse réception. Une reprise peut livrer un doublon; le service vérifie
   l’existence d’une notification par `order_id` avant insertion.

## 4. Décisions techniques justifiées

| Décision | Justification |
|---|---|
| FastAPI + Pydantic | Exigence du sujet, validation serveur, OpenAPI natif |
| 1 serveur PostgreSQL / 4 bases | VM 4 Go : 4 serveurs séparés dépasseraient le budget mémoire ; isolation équivalente via comptes et `GRANT`s séparés |
| `resolver 127.0.0.11` Nginx | Découverte dynamique des répliques (`--scale catalogue=3`) sans redémarrage |
| JWT HS256, secrets hors Git | Simplicité adaptée au périmètre ; secrets via compose `secrets:` / `.env` |
| CAPTCHA, authentification à deux facteurs, rotation des jetons de renouvellement | Non implémentés dans le périmètre actuel; limites à réévaluer avant un déploiement public |
| E-mail/SMS simulé | Aucun fournisseur réel intégré : marqué explicitement « simulation » |
| Paiement non intégré | Aucun faux paiement ; CLI passe commande « à régler au marché », architecture prête (champ `payment_status` + interface future) |

## 5. Limites mémoire Compose

Les valeurs ci-dessous sont des plafonds de conteneur, pas des mesures d’usage ni une preuve qu’une VM de 4 Go suffit. Le plafond théorique cumulé dépasse 2 Go pour le socle avec trois répliques Catalogue, avant le système et les pointes de consommation. Le profil réel doit être mesuré sur l’hôte cible.

| Conteneur | Limite mem | Note |
|---|---|---|
| PostgreSQL 16 | 400 Mo | shared_buffers 128 Mo |
| Redis 7.4 | 128 Mo | |
| RabbitMQ 3.13 | 256 Mo | |
| catalogue ×3 | 3 × 128 Mo | |
| commandes, utilisateurs, notifications | 3 × 128 Mo | |
| gateway + frontend | 64 + 32 Mo | |
| Zabbix (pile séparée) | ~500 Mo activable | `compose.monitoring.yaml`, optionnel |

Le rapport technique du 4 novembre signale une dégradation temporaire des contrôles de santé pendant un test de charge. Ne pas lancer les scénarios de charge ou de panne sur une pile partagée.

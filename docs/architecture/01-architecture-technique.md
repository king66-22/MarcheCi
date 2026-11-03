# MarchéCI — Architecture technique (Étape 1)

> Statut : validée le 2026-11-03. Sert de référence contractuelle pour Étapes 2 à 7.
> Contrainte source : sujet « Projets Cloud Native — Projet 1 : MarchéCI » (PDF, version apprenant).

## 1. Vue d'ensemble

Plateforme e-commerce en **microservices conteneurisés**, point d'entrée unique Nginx,
une base de données logique par service, cache Redis, messagerie RabbitMQ,
supervision Zabbix. Livrable sur un serveur Linux par `docker compose up -d`
(démarrage complet < 2 min sur VM 4 Go).

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
| **commandes** | Panier serveur, commandes, statuts, montants, lignes de commande SNAPSHOT prix | Ne modifie jamais les tables catalogue ; décrémente le stock via API catalogue |
| **utilisateurs** | Comptes, mots de passe hachés, émission/validation JWT, rôles CLIENT, ADMIN | Ne connaît ni produits ni commandes |
| **notifications** | Consommation `order.created`, historique des notifications, envoi simulé clairement marqué | Ne lit aucune autre base |
| **gateway** | Routage, limitation des chemins exposés, timeouts, round-robin catalogue | Aucune logique métier |
| **frontend** | SPA React/TS, panier utilisateur (localStorage), formulaires | Aucun prix inventé : tout vient des APIs |
| **PostgreSQL** | 4 bases logiques, 4 comptes SQL, un serveur (optimisation VM 4 Go) | Isolation stricte par compte (`GRANT` sur une seule base chacun) |
| **Redis** | Cache 60 s de la liste produits, invalidation à l'écriture | Aucune donnée source de vérité |
| **RabbitMQ** | Événements asynchrones commandes → notifications | Aucun appel synchrone critique ne dépend d'un broker |

## 3. Flux de panier → commande (exigence prix validés serveur)

1. Le client compose un panier (local, résumé revalidé à la validation de commande).
2. `POST /orders` (JWT client) → **commandes** appelle catalogue `GET /products/{ids}`
   pour reconstituer les prix réels (jamais ceux du navigateur).
3. Copie (`snapshot`) prix + nom produit dans `order_items` (résistance à la modification
   ultérieure du catalogue).
4. Contrôle du stock : refus si stock insuffisant. Décrément par appel catalogue
   `POST /products/{id}/adjust-stock` — en cas d'échec, la commande passe à `ANNULÉE`
   (limitation documentée : pas de saga distribuée complète dans ce périmètre).
5. Publication `order.created` dans RabbitMQ + commit BDD ; notifications consomme.

## 4. Décisions techniques justifiées

| Décision | Justification |
|---|---|
| FastAPI + Pydantic | Exigence du sujet, validation serveur, OpenAPI natif |
| 1 serveur PostgreSQL / 4 bases | VM 4 Go : 4 serveurs séparés dépasseraient le budget mémoire ; isolation équivalente via comptes et `GRANT`s séparés |
| `resolver 127.0.0.11` Nginx | Découverte dynamique des répliques (`--scale catalogue=3`) sans redémarrage |
| JWT HS256, secrets hors Git | Simplicité adaptée au périmètre ; secrets via compose `secrets:` / `.env` |
| WAVES : captcha, 2FA, refresh-rotating | Hors périmètre (3 semaines) — inscrits dans limites de sécurité |
| E-mail/SMS simulé | Aucun fournisseur réel intégré : marqué explicitement « simulation » |
| Paiement non intégré | Aucun faux paiement ; CLI passe commande « à régler au marché », architecture prête (champ `payment_status` + interface future) |

## 5. Budget mémoire cible (VM 4 Go)

| Conteneur | Limite mem | Note |
|---|---|---|
| PostgreSQL 16 | 400 Mo | shared_buffers 128 Mo |
| Redis 7.4 | 128 Mo | |
| RabbitMQ 3.13 | 256 Mo | |
| catalogue ×3 | 3 × 128 Mo | |
| commandes, utilisateurs, notifications | 3 × 128 Mo | |
| gateway + frontend | 64 + 32 Mo | |
| Zabbix (pile séparée) | ~500 Mo activable | `compose.monitoring.yaml`, optionnel |

Total socle ≈ 1,4 Go ; socle + Zabbix ≈ 1,9 Go — compatible 4 Go.

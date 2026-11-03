# MarchéCI — Réseaux, communications et sécurité infrastructure (Étape 1)

## 1. Réseaux Docker

```
Réseau front (bridge marcheci_front)           Réseau back (bridge marcheci_back)
────────────────────────────────               ──────────────────────────────────
gateway (nginx:1.27, :80.published)            postgres (postgres:16-alpine)
catalogue (×1..3)                              redis (redis:7.4-alpine)
commandes                                      rabbitmq (rabbitmq:3.13-management-alpine)
utilisateurs                                   + tous les servicesfony (accèss données)
notifications
frontend (build Vite, servi par gateway)
```

| Nécessité | Cible | Justification |
|---|---|---|
| gateway | front | expose 80 |
| tous services | front + back | échangent entre eux (HTTP) et accèdent aux données |
| postgres, redis, rabbitmq | back uniquement | jamais exposés |
| frontend | front uniquement | servi par gateway |

Attaché : les services applicatifs doivent communiquer entre eux via le réseau front
(catalogue ← commandes), les données administrateur via back. Nginx de routage
listener sur front pour parler à services.

## 2. Communications inter-services (liste exhaustive)

| De | À | Protocole | Objet | Échec résilient ? |
|---|---|---|---|---|
| navigateur | gateway | HTTP :80 | tout | — |
| gateway | catalogue ×3 | HTTP, round-robin DNS docker | /api/catalogue/* | 502 géré nginx |
| gateway | commandes/utilisateurs/notifications | HTTP | /api/* | 502 géré |
| commandes | catalogue | HTTP `GET /products?ids=…` | prix serveur à la création de commande | NO — commande refusée (422/503) |
| commandes | catalogue | HTTP `POST /products/{id}/adjust-stock` | décrément STOCK à confirmation | compensation (annulation ou restock) |
| commandes | RabbitMQ | AMQP publish | event `order.created` | NO : publication avant commit du « statut EN_ATTENTE », retry applicatif |
| notifications | RabbitMQ | AMQP consume | idem | retry + DLQ |
| utilisateurs | (aucun) | — | source JWT partagée aux services (`JWT_SECRET` secret compose) | — |
| catalogue/utilisateurs | Redis | TCP | cache ; rate-limit login | dégradé (cache off / rate-limit off) |

## 3. Authentification inter-services

Un JWT se voit émis par utilisateurs (via login admin ou MCP) et peut authonifier
les appels service→service. Pour le décrément stock (commandes→catalogue), un
compte de type `svc:commandes` (API key interne stockée en secret) est préféré ?

### Décision (simple et defendable)
Le décrément stock via catalogue exige le rôle ADMIN (JWT). Le service commandes
obtient ce JWT via login du compte système `svc_commandes` administrateur, secrets
fournis par `.env`/compose. BUT : documenté comme pònt de sécurité ; l'alternative
`API key header X-INTERNAL-KEY` est documentée mais non retenue (lecture Nginx du
header dépend du network isolation), pour garder un seul mécanisme JWT.

## 4. Timeouts et erreurs gateway

- `proxy_read_timeout 30s` (catalogue 10 s), `proxy_connect_timeout 5s`.
- Page d'erreur JSON propre (`{"detail":"service indisponible"}`), pas d'HTML brut.
- Nginx `resolver 127.0.0.11 valid=5s` + upstream variable ⇒ découverte dynamique
  des répliques `catalogue` (scale) sans redémarrage du container gateway.
- Aucun port de postgres/redis/rabbitmq publié.
- ports services applicatifs non publiés non plus (accès uniquement via gateway).

## 5. Volumes persistants

| Volume | Monté sur | Contenu |
|---|---|---|
| pg_data | /pg/postgres/data | toutes les bases (postgreSQL serveur unique) |
| redis_data | /data | AOF cache (option saturable) |
| rabbitmq_data | /var/lib/rabbitmq | files durables |
| (zabbix_db dans compose.monitoring) | | si activé |

Sauvegardes : script `scripts/backup.sh` (pg_dump par base, 7 rétentions) — documenté Étape 7.

## 6. Secrets

- `.env` Git-ignoré, `.env.example` sans valeurs réelles.
- `compose.yaml` référence `env_file` + `secrets` (jwt, postgres users, rabbitmq).
- Jamais de mot de passe dans les logs, images ou variables publicité.

# MarchéCI

Plateforme e-commerce en microservices pour la coopérative des commerçants
d’Adjamé (Abidjan). Le dépôt contient quatre API FastAPI, une SPA React/TypeScript,
une passerelle Nginx, PostgreSQL, Redis, RabbitMQ et une pile Zabbix facultative.

## Architecture et limites connues

```
Internet
   │ :80 (seul port publié sur l'hôte)
┌──▼──────────────────────────────┐
│ gateway (Nginx)                 │
│  "/"      → SPA React           │
│  "/api/*" → services            │
└──┬──────────────────────────────┘
   │ réseau front
┌──▼───────┬──────────┬────────────┬───────────────┐
│catalogue │commandes │utilisateurs│ notifications │
│ ×1 à ×3  │          │            │               │
└──┬───────┴────┬─────┴──────┬─────┴───────┬───────┘
   │ réseau back│            │             │
┌──▼─────┐ ┌────▼────────────▼──┐ ┌────────▼──────┐
│ Redis  │ │ PostgreSQL 16      │ │ RabbitMQ 3.13 │
│ cache  │ │ 4 bases logiques   │ │ file + retry  │
│ 60 s   │ │ 4 comptes SQL      │ │ + DLQ         │
└────────┘ └────────────────────┘ └───────────────┘
```

- **Catalogue** : produits, catégories, prix et stock; cache Redis à TTL 60 s avec
  invalidation après écriture. Si Redis est indisponible, le service fonctionne
  sans cache et l’indique dans son healthcheck.
- **Commandes** : vérifie les prix et stocks via Catalogue, enregistre des
  instantanés de prix, et compense les réductions de stock si l’écriture échoue.
- **Utilisateurs** : inscription, connexion, rôles et JWT; les mots de passe sont
  hachés et les routes privées exigent un token.
- **Notifications** : consomme les événements de commande; les notifications
  sont persistées. Leur état `SIMULE_ENVOYE` signifie qu’aucun fournisseur
  d’e-mail/SMS réel n’est configuré.
- Le modèle d’accès comprend les rôles `CLIENT` et `ADMIN`. L’API et le frontend
  ne proposent pas d’espace commerçant ni de propriétaire vendeur pour les
  produits; les écritures de catalogue sont réservées à l’administration.
- Le panier vit dans le navigateur. Les prix et le stock sont contrôlés côté
  serveur au passage de commande. Le paiement en ligne, l’envoi réel de
  notifications et le téléversement d’images ne sont pas intégrés.
- Les migrations ne créent pas de catalogue métier de démonstration. Sur une
  base neuve, un administrateur doit créer les catégories et produits avant que
  la boutique affiche des articles.
- Chaque microservice possède une base logique PostgreSQL et un compte SQL dédiés.
  Les quatre bases partagent le même serveur PostgreSQL pour respecter le budget
  de ressources de la VM.
- La table `outbox_events` est écrite dans la même transaction que la commande.
  Un worker publie ensuite l’événement confirmé par RabbitMQ; une interruption
  temporaire du broker laisse l’événement en attente, puis le worker le retente.
  Les reprises sont au moins une fois; Notifications ignore les événements dont
  la commande a déjà une notification.
- RabbitMQ utilise une file durable, trois files de reprise à TTL croissant
  (2, 4 et 8 secondes par défaut), et `order.created.dlq`. Un administrateur peut
  rejouer jusqu’à 100 messages via `POST /api/notifications/internal/replay-dlq`.
- La gateway sert le frontend et expose les API sous `/api/{service}/`. Nginx
  tourne avec l’UID non privilégié 101 et le port 8080 dans le conteneur.
- Le tableau de bord Zabbix est une pile séparée; son port hôte est limité à
  `127.0.0.1:8090` par défaut.

## Prérequis

- Docker Desktop et Docker Compose v2.
- Python 3.12+ est requis par le launcher pour vérifier `.env` et créer les
  fichiers secrets manquants. Node.js sert aux tests et au développement du
  frontend; il n’est pas requis pour utiliser la boutique via Docker.
- Les ports hôte 80 et 8090 libres pour l’installation standard.

## Démarrage guidé

Le point d’entrée conseillé est le dossier `launcher/`. Sur Windows, après avoir
installé et démarré Docker Desktop, double-cliquez `launcher/start.bat`. Si `.env`
n’existe pas encore, le script crée une copie de `.env.example` et s’arrête pour
que vous puissiez remplacer les valeurs `CHANGE_ME`. Il vérifie ensuite Docker,
la configuration, les secrets, les services et l’accès au frontend.

Sur Linux ou macOS, ouvrez un terminal dans le dossier MarchéCI et lancez
`sh launcher/start.sh`. Le dossier `launcher/` contient aussi les scripts
d’arrêt, d’état, de journaux et de supervision facultative. La commande d’arrêt
conserve les volumes de données. Les détails pour une première installation
sont dans [GUIDE_DE_LANCEMENT.md](GUIDE_DE_LANCEMENT.md).

Le launcher démarre une instance Catalogue par défaut. Le passage à trois
répliques est une mesure de scalabilité optionnelle; le dernier test de charge
historique a dépassé son seuil de latence et le bénéfice de trois répliques doit
être remesuré sur un hôte dédié avant toute conclusion.

## Configuration et démarrage

1. Créer `.env` depuis `.env.example`; remplacer chaque valeur `CHANGE_ME` par un
   secret fort, unique et non partagé.
2. Générer les fichiers secrets ignorés par Git :

   ```powershell
   .\.venv\Scripts\python.exe scripts\sync_secrets.py
   ```

   Relancer cette commande après toute rotation d’un secret. Les fichiers locaux
   montés par Compose ne sont pas un coffre-fort chiffré; protégez les accès au
   poste ou à la VM qui les héberge.
3. Démarrer les services et trois instances du Catalogue :

   ```powershell
   docker compose up -d --build --scale catalogue=3
   docker compose ps
   ```

   La commande unique `docker compose up -d --build` démarre aussi les migrations
   et l’amorçage administrateur. Les images externes de l’infrastructure et les
   bases d’image sont référencées par digest.
4. Démarrer Zabbix si nécessaire :

   ```powershell
   docker compose -f monitoring/zabbix/compose.yaml up -d
   .\.venv\Scripts\python.exe monitoring\zabbix\configure_zabbix_admin.py
   $env:ZABBIX_API_URL = 'http://127.0.0.1:8090/api_jsonrpc.php'
   .\.venv\Scripts\python.exe monitoring\zabbix\provisioning.py verify
   ```

   L’interface est disponible sur `http://127.0.0.1:8090` avec les paramètres
   `ZABBIX_ADMIN_PASSWORD` de `.env` (le compte initial est `Admin`). Sur
   Windows, le launcher `launcher/monitoring.bat` automatise ces étapes.

## Comptes de test

Les comptes techniques sont créés automatiquement au premier démarrage par
`docker/bootstrap/init_admins.py` (idempotent). Aucun mot de passe n'est écrit
dans le dépôt : ils proviennent de `.env` et des fichiers `secrets/`.

| Compte | Rôle | Usage | Mot de passe |
|---|---|---|---|
| `admin@marcheci.ci` | `ADMIN` | Administration : produits, catégories, commandes, utilisateurs, notifications | variable `ADMIN_PASSWORD` de `.env` |
| `svc.commandes@marcheci.ci` | `ADMIN` technique | Appels internes Commandes → Catalogue (`adjust-stock`) | variable `SVC_COMMANDES_PASSWORD` de `.env` |
| Compte client | `CLIENT` | Créé via `/inscription` ou `POST /api/utilisateurs/auth/register` | choisi à l'inscription |

Pour une présentation, utilisez le fichier `.env` de démonstration fourni hors
dépôt, ou remplacez les valeurs `CHANGE_ME` avant le premier démarrage.

## Accès API

Les documentations OpenAPI sont accessibles via la gateway :

- `/docs/catalogue/`
- `/docs/commandes/`
- `/docs/utilisateurs/`
- `/docs/notifications/`

Routes principales :

| Service | Routes principales |
| --- | --- |
| Catalogue | `GET /api/catalogue/products`, `GET /api/catalogue/products/{id}`, `GET /api/catalogue/categories`; écritures ADMIN sur produits/catégories; ajustement interne du stock |
| Commandes | `POST /api/commandes/orders`, historique et détail, transition ADMIN, annulation |
| Utilisateurs | `POST /api/utilisateurs/auth/register`, `POST /api/utilisateurs/auth/login`, `GET/PUT /api/utilisateurs/users/me`, `GET /api/utilisateurs/users` ADMIN |
| Notifications | `GET /api/notifications/notifications` ADMIN; `POST /api/notifications/internal/replay-dlq` ADMIN |

Chaque service expose `/health`. Commandes et Notifications retournent HTTP 503
si PostgreSQL, RabbitMQ, Catalogue ou le consommateur dont ils dépendent sont
indisponibles. Catalogue traite Redis comme un cache facultatif et signale son
état séparément.

## Tests et vérifications

Lancer les suites de service (les tests Commandes, Utilisateurs et Notifications
importent aussi `conftest.py` depuis `tests/`) :

```powershell
Set-Location services/catalogue
..\..\.venv\Scripts\pytest.exe -q -p no:cacheprovider
Set-Location ../commandes
$env:PYTHONPATH = (Join-Path (Get-Location) 'tests')
..\..\.venv\Scripts\pytest.exe -q -p no:cacheprovider
Set-Location ../utilisateurs
$env:PYTHONPATH = (Join-Path (Get-Location) 'tests')
..\..\.venv\Scripts\pytest.exe -q -p no:cacheprovider
Set-Location ../notifications
$env:PYTHONPATH = (Join-Path (Get-Location) 'tests')
..\..\.venv\Scripts\pytest.exe -q -p no:cacheprovider
Set-Location ../..
```

Les tests HTTP en processus séparés sont dans `tests/integration/`; ils utilisent
des bases temporaires SQLite et désactivent RabbitMQ. Pour valider la vraie
chaîne Docker, y compris RabbitMQ et la persistance de Notifications, utiliser un
projet Compose isolé (bases et réseaux propres) :

```powershell
$env:GATEWAY_PORT = '8181'
docker compose -p marcheci-e2e up -d --build --scale catalogue=1
$env:MARCHECI_BASE_URL = 'http://localhost:8181'
.\.venv\Scripts\python.exe tests\smoke_docker.py
.\.venv\Scripts\python.exe tests\smoke_rabbit_recovery.py
.\.venv\Scripts\python.exe tests\smoke_service_resilience.py
docker compose -p marcheci-e2e down
```

Le scénario de reprise arrête puis redémarre RabbitMQ uniquement dans le projet
isolé `marcheci-e2e`. La commande `down` conserve le volume de test; ces actions
de reprise et de résilience arrêtent des composants seulement dans le projet
isolé; elles ne touchent pas aux données du projet `marcheci`.

Build et lint frontend :

```powershell
Set-Location frontend
npm ci
npm run build
npm run lint
```

Le build de production et le lint ont été réexécutés le 6 novembre 2026; le
build réussit et `npm run lint` termine sans avertissement. Le dossier technique
du 4 novembre conserve les résultats et limites observés lors de cette revue
antérieure.

## Supervision, scalabilité et rapports

- `monitoring/zabbix/provisioning.py verify` provisionne les sondes HTTP et vérifie
  leur collecte. Le mode `alerte` arrête volontairement toutes les répliques du
  Catalogue; ne le lancer que sur un environnement de démonstration isolé.
- Les scénarios k6 sont dans `tests/load/`. Ils lisent Catalogue, mais
  l’orchestrateur fourni arrête Commandes pendant le test de résilience et lance
  les variations d’échelle sur le projet Compose courant. Exécuter ces scénarios
  uniquement avec un projet de test dédié.
- `docs/reports/load_1replica.json`, `docs/reports/load_3replicas.json` et
  `docs/reports/resilience.json` sont des résumés historiques. Le run isolé du
  04/11/2026 à 50 VU a dépassé les seuils de latence et rendu les conteneurs du
  laboratoire unhealthy; ses données détaillées sont conservées dans
  `docs/reports/raw/e2e_load_1replica_raw.json`. Ce résultat n'est pas présenté comme une
  performance acceptable ni comparé directement aux anciens résumés.

## Documentation technique

- [Architecture et choix techniques](docs/architecture/01-architecture-technique.md)
- [Modèles de données](docs/architecture/02-modeles-de-donnees.md)
- [Contrats des API](docs/api/specifications-api.md)
- [Réseaux et communications](docs/architecture/04-reseaux-et-communications.md)
- [Analyse et plan de réalisation](docs/architecture/05-risques-et-plan.md)
- [Rapport d’analyse](docs/reports/rapport_audit_final.md)
- [Rapport de validation](docs/reports/rapport_tests_reels.md)
- [Points ouverts](docs/reports/problemes_restants.md)
- [Autres rapports et livrables](docs/reports/)

Les livrables de présentation sont `docs/reports/rapport_technique_MarcheCI.pdf` et
`docs/reports/Diaporama_présentation_MarcheCI.pptx`. Ils distinguent les résultats
vérifiés des éléments restant à démontrer, notamment la charge à trois
répliques, l’alerte de panne Zabbix et le déploiement sur la pile principale.

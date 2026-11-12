# MarchéCI

Plateforme e-commerce en microservices pour la coopérative des commerçants
d’Adjamé (Abidjan). Le dépôt contient quatre API FastAPI, une SPA React/TypeScript,
une passerelle Nginx, PostgreSQL, Redis, RabbitMQ et une pile Zabbix facultative.

## Architecture

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
- **Photos produits** : un commerçant téléverse ses photos (galerie, appareil photo
  du téléphone ou glisser-déposer). Les fichiers sont redimensionnés et stockés
  dans le volume Docker `media_data`, puis servis par la gateway sous `/media/`.
  Contraintes par défaut : 8 Mo par photo, 10 photos par produit.
- **Commandes** : vérifie les prix et stocks via Catalogue, enregistre des
  instantanés de prix, et compense les réductions de stock si l’écriture échoue.
- **Utilisateurs** : inscription, connexion, rôles et JWT; les mots de passe sont
  hachés et les routes privées exigent un token.
- **Notifications** : consomme les événements de commande; les notifications
  sont persistées. Leur état `SIMULE_ENVOYE` signifie qu’aucun fournisseur
  d’e-mail/SMS réel n’est configuré.
- Le modèle d’accès comprend les rôles `CLIENT`, `COMMERCANT` et `ADMIN`. Un
  commerçant dispose de l’espace `/commercant` : il crée ses produits et gère
  leurs photos. Un produit appartient à un seul commerçant (`owner_id`) ; les
  produits historiques restent sans propriétaire et sont gérés par l’ADMIN.
  Un client peut être promu commerçant par l’administration.
- Le panier vit dans le navigateur. Les prix et le stock sont contrôlés côté
  serveur au passage de commande. Le paiement en ligne et l’envoi réel de
  notifications ne sont pas intégrés.
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
répliques s’effectue avec `--scale catalogue=3`, après validation des ressources
de l’hôte et des paramètres de la passerelle.

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
   .\.venv\Scripts\python.exe monitoring\zabbix\dashboard.py
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
| Compte commerçant | `COMMERCANT` | Créé via `/inscription` (choix « Vendre mes produits ») ou promu par un ADMIN ; accès à `/commercant` | choisi à l'inscription |

Pour une démonstration, utilisez le fichier `.env` de démonstration fourni hors
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
| Catalogue | `GET /api/catalogue/products`, `GET /api/catalogue/products/{id}`, `GET /api/catalogue/categories`; `GET /api/catalogue/products/mine` (commerçant); écritures ADMIN ou COMMERCANT propriétaire; photos `POST/DELETE /api/catalogue/products/{id}/images`; ajustement interne du stock |
| Commandes | `POST /api/commandes/orders`, historique et détail, transition ADMIN, annulation |
| Utilisateurs | `POST /api/utilisateurs/auth/register` (`role` = `CLIENT` ou `COMMERCANT`), `POST /api/utilisateurs/auth/login`, `GET/PUT /api/utilisateurs/users/me`, `GET /api/utilisateurs/users` et `PATCH /api/utilisateurs/users/{id}/role` ADMIN |
| Notifications | `GET /api/notifications/notifications` ADMIN; `POST /api/notifications/internal/replay-dlq` ADMIN |

Chaque service expose `/health`. Commandes et Notifications retournent HTTP 503
si PostgreSQL, RabbitMQ, Catalogue ou le consommateur dont ils dépendent sont
indisponibles. Catalogue traite Redis comme un cache facultatif et signale son
état séparément.

## Tests et vérifications

Lancer les suites unitaires depuis la racine du dépôt. Chaque suite importe le
code du service (`services/<service>`) et son `conftest.py`
(`tests/unit/<service>`) via `PYTHONPATH` :

```powershell
$env:PYTHONPATH = "services\catalogue;tests\unit\catalogue"
.\.venv\Scripts\python.exe -m pytest tests\unit\catalogue -q

$env:PYTHONPATH = "services\commandes;tests\unit\commandes"
.\.venv\Scripts\python.exe -m pytest tests\unit\commandes -q

$env:PYTHONPATH = "services\utilisateurs;tests\unit\utilisateurs"
.\.venv\Scripts\python.exe -m pytest tests\unit\utilisateurs -q

$env:PYTHONPATH = "services\notifications;tests\unit\notifications"
.\.venv\Scripts\python.exe -m pytest tests\unit\notifications -q

Remove-Item Env:PYTHONPATH
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

Le build de production et le lint ont été réexécutés le 6 novembre 2026 : le
build réussit et `npm run lint` termine sans avertissement.

## Supervision et scalabilité

- `monitoring/zabbix/provisioning.py verify` provisionne les sondes HTTP et vérifie
  leur collecte. Le mode `alerte` arrête volontairement toutes les répliques du
  Catalogue; ne le lancer que sur un environnement de démonstration isolé.
- `monitoring/zabbix/dashboard.py` crée ou met à jour le tableau de bord
  « MarcheCI - Supervision » : liste des problèmes actifs et une tuile par sonde.
  À exécuter après le provisionnement lorsque l’hôte et les items existent.
- Les scénarios k6 sont dans `tests/load/`. Ils lisent Catalogue, mais
  l’orchestrateur fourni arrête Commandes pendant le test de résilience et lance
  les variations d’échelle sur le projet Compose courant. Exécuter ces scénarios
  uniquement avec un projet de test dédié.
- Les résultats de référence sont conservés dans `docs/reports/`
  (`load_1replica.json`, `load_3replicas.json`, `resilience.json`) et les données
  détaillées dans `docs/reports/raw/`.
- Le [rapport de test de charge](docs/reports/rapport_test_charge.md) consigne le
  protocole, les tableaux requêtes/s et latence p95 pour une et trois répliques du
  Catalogue, l’analyse et les optimisations retenues.
- Les captures de supervision sont dans `docs/screenshots/` : tableau de bord
  nominal (`06_tableau_de_bord_zabbix.jpeg`), problème détecté à l’arrêt du
  Catalogue (`06_problem_actif_dashboard.jpeg`,
  `06_problem_actif_catalogue.jpeg`) et résolution automatique au redémarrage
  (`06_problems_resolus_auto.jpeg`).

## Documentation technique

- [Architecture et choix techniques](docs/architecture/01-architecture-technique.md)
- [Modèles de données](docs/architecture/02-modeles-de-donnees.md)
- [Contrats des API](docs/api/specifications-api.md)
- [Réseaux et communications](docs/architecture/04-reseaux-et-communications.md)
- [Rapport de test de charge](docs/reports/rapport_test_charge.md)
- [Dossier technique (PDF)](docs/reports/Dossier_technique_MarcheCI.pdf)

# MarchéCI — Modèles de données

Chaque service écrit dans sa base logique et utilise son propre compte PostgreSQL. Les quatre bases résident sur le même serveur PostgreSQL Compose : cette séparation limite les accès croisés, mais ne protège pas contre une panne commune du serveur.

Les champs et contraintes ci-dessous résument les modèles SQLAlchemy et les migrations Alembic présents dans le dépôt.

## 1. Catalogue (`marcheci_catalogue`)

### `categories`

| Champ | Type | Règle |
|---|---|---|
| `id` | Integer | Clé primaire |
| `slug` | String(80) | Unique, non nul, indexé |
| `name` | String(120) | Non nul |

### `products`

| Champ | Type | Règle |
|---|---|---|
| `id` | Integer | Clé primaire |
| `slug` | String(160) | Unique, non nul, indexé |
| `name` | String(200) | Non nul |
| `description` | Text | Non nul, chaîne vide par défaut |
| `price_xof` | BigInteger | Montant entier en FCFA, non négatif selon le schéma API |
| `category_id` | Integer | Référence locale à `categories.id`, nullable |
| `stock` | Integer | Stock courant, entier non négatif selon le schéma API |
| `image_url` | String(500) | URL facultative; aucun dépôt de fichier n’est implémenté |
| `is_active` | Boolean | Vrai par défaut; faux après désactivation administrative |
| `created_at`, `updated_at` | DateTime | Horodatages UTC |

L’index composite `is_active, category_id` sert les listes publiques. Les produits sont triés du plus récent au plus ancien. Les filtres de texte, de catégorie et de disponibilité sont appliqués par Catalogue.

## 2. Utilisateurs (`marcheci_utilisateurs`)

### `users`

| Champ | Type | Règle |
|---|---|---|
| `id` | Integer | Clé primaire |
| `email` | String(255) | Unique, non nul |
| `password_hash` | String(255) | Hachage Argon2; jamais retourné par l’API |
| `full_name` | String(150) | Non nul |
| `phone` | String(30) | Facultatif |
| `role` | String(10) | `CLIENT` par défaut; comptes `ADMIN` créés au bootstrap |
| `is_active` | Boolean | Vrai par défaut |
| `created_at`, `updated_at` | DateTime | Horodatages UTC |

Le code et les contrats exposent les rôles `CLIENT` et `ADMIN` uniquement. Il n’existe pas de rôle commerçant, de rattachement produit-commerçant ou d’espace de gestion autonome pour un vendeur.

## 3. Commandes (`marcheci_commandes`)

### `orders`

| Champ | Type | Règle |
|---|---|---|
| `id` | Integer | Clé primaire |
| `user_id` | Integer | Identifiant logique; aucun lien SQL entre bases |
| `status` | String(20) | `EN_ATTENTE`, `CONFIRMEE`, `EN_PREPARATION`, `EXPEDIEE`, `LIVREE` ou `ANNULEE` |
| `total_xof` | BigInteger | Total recalculé côté serveur, en FCFA entier |
| `delivery_address` | Text | Adresse de livraison, non nulle |
| `delivery_phone` | String(30) | Téléphone de livraison, non nul |
| `payment_status` | String(20) | `A_REGIER` par défaut; aucun paiement en ligne n’est intégré |
| `created_at`, `updated_at` | DateTime | Horodatages UTC |

### `order_items`

Chaque ligne conserve `product_id`, `product_name`, `unit_price_xof` et `quantity`. Le nom et le prix sont copiés au moment de la commande : l’historique ne dépend pas des changements ultérieurs du catalogue. Seul `order_id` possède une clé étrangère, vers la commande dans la même base.

### `outbox_events`

La commande, ses lignes et son événement `order.created` sont enregistrés dans une même transaction PostgreSQL. Le worker Commandes publie les événements en attente à RabbitMQ avec confirmation, puis renseigne `published_at`. Les tentatives et la dernière erreur restent enregistrées pour le diagnostic. La livraison est au moins une fois, pas exactement une fois.

## 4. Notifications (`marcheci_notifications`)

### `notifications`

Les lignes conservent `order_id`, `user_id`, `channel` (`EMAIL` ou `SMS`), `recipient`, `template`, le `payload` JSON, le nombre de tentatives et la date de création. `order_id` et `user_id` sont des identifiants logiques sans clé étrangère entre bases. Le statut `SIMULE_ENVOYE` désigne une notification persistée mais non remise par un fournisseur réel; l’autre statut métier est `ECHEC`.

## 5. Intégrité entre services

- Aucun service ne lit directement la base d’un autre.
- Commandes récupère nom, prix et disponibilité auprès de Catalogue par HTTP, puis enregistre les instantanés de commande.
- Les changements de stock passent par l’API Catalogue. Une compensation tente de restaurer le stock si la création ou l’annulation de commande échoue.
- Les identifiants d’utilisateur, de produit et de commande partagés dans les événements sont des références logiques.
- Le panier frontend est conservé dans le navigateur (`localStorage`). Les prix et le stock sont revalidés par les services à la création de commande.
- Les migrations Alembic sont séparées par service; Compose les exécute avant le démarrage des API.

## 6. Limites du modèle métier observé

Le modèle actuel couvre un catalogue commun administré par `ADMIN` et des commandes client. Il ne permet pas d’isoler les produits par commerçant, les droits d’un vendeur, ses images ou ses commandes. La conformité de ce choix au cahier des charges officiel reste à confirmer, car le sujet source n’est pas présent dans le dépôt.

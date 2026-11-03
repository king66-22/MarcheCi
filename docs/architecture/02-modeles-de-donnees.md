# MarchéCI — Modèles de données (Étape 1)

Une base logique par service, un compte SQL par service. Aucune shared table.
Migrations Alembic par service, autogénérées puis relues.

## 1. marcheci_catalogue

### categories
| Colonne | Type | Contraintes |
|---|---|---|
| id | INT | PK, identity |
| slug | VARCHAR(80) | UNIQUE, NOT NULL |
| name | VARCHAR(120) | NOT NULL |

### products
| Colonne | Type | Contraintes |
|---|---|---|
| id | INT | PK, identity |
| slug | VARCHAR(160) | UNIQUE, NOT NULL |
| name | VARCHAR(200) | NOT NULL |
| description | TEXT | NOT NULL DEFAULT '' |
| price_xof | BIGINT | NOT NULL, >= 0 (montant en FCFA entiers, pas de flottant) |
| category_id | INT | FK → categories.id, nullable (produit sans catégorie) |
| stock | INT | NOT NULL, >= 0 |
| image_url | VARCHAR(500) | nullable |
| is_active | BOOL | NOT NULL DEFAULT true |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL |

Index : `slug (unique)`, `category_id`, trigram `name` (recherche), partial index
`WHERE is_active` sur la liste publique.

> Prix stockés en **entiers FCFA** (ex. 12500) — jamais de `float` monétaire.

## 2. marcheci_commandes

### orders
| Colonne | Type | Contraintes |
|---|---|---|
| id | INT | PK, identity |
| user_id | INT | NOT NULL (idém for `utilisateurs`, pas de FK cross-DB) |
| status | VARCHAR(20) | NOT NULL, CHECK dans {EN_ATTENTE, CONFIRMEE, EN_PREPARATION, EXPEDIEE, LIVREE, ANNULEE} |
| total_xof | BIGINT | NOT NULL, calculé serveur |
| delivery_address | VARCHAR(400) | NOT NULL |
| delivery_phone | VARCHAR(30) | NOT NULL |
| payment_status | VARCHAR(20) | NOT NULL DEFAULT 'A_REGIER' (adapter pour intégration future) |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL |

Index : `(user_id, created_at DESC)`, `status`.

### order_items
| Colonne | Type | Contraintes |
|---|---|---|
| id | INT | PK |
| order_id | INT | FK → orders.id, ON DELETE CASCADE |
| product_id | INT | NOT NULL (ref logique catalogue) |
| product_name | VARCHAR(200) | NOT NULL (snapshot) |
| unit_price_xof | BIGINT | NOT NULL (snapshot serveur, prix catalogue au moment de la commande) |
| quantity | INT | NOT NULL, > 0 |

## 3. marcheci_utilisateurs

### users
| Colonne | Type | Contraintes |
|---|---|---|
| id | INT | PK |
| email | VARCHAR(255) | UNIQUE, NOT NULL |
| password_hash | VARCHAR(255) | NOT NULL (Argon2id) |
| full_name | VARCHAR(150) | NOT NULL |
| phone | VARCHAR(30) | nullable |
| role | VARCHAR(10) | NOT NULL, CHECK dans {CLIENT, ADMIN} |
| is_active | BOOL | NOT NULL DEFAULT true |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL |

Le hash de mot de passe n'est JAMAIS retourné par l'API.

## 4. marcheci_notifications

### notifications
| Colonne | Type | Contraintes |
|---|---|---|
| id | INT | PK |
| order_id | INT | nullable |
| user_id | INT | nullable |
| channel | VARCHAR(10) | CHECK dans {EMAIL, SMS} |
| recipient | VARCHAR(255) | NOT NULL |
| template | VARCHAR(50) | NOT NULL |
| status | VARCHAR(15) | CHECK dans {SIMULÉ_ENVOYÉ, ÉCHEC} |
| payload | JSONB | NOT NULL (corps de l'événement d'origine) |
| attempts | INT | NOT NULL DEFAULT 1 |
| created_at | TIMESTAMPTZ | NOT NULL |

## 5. Règles d'intégrité cross-services

- Pas de FK cross-BD : cohérence par id + snapshots (`product_name`, `unit_price_xof`).
- Stock : source de volution **catalogue uniquement** ; commandes agit via API et annule sa commande en cas d'échec (journalisé).
- Suppression produit : le sujet impose DELETE ; catalogage soft-delete (`is_active=false`) recommandé pour ne pas briser l'historique commandes — DELETE physique refusé si le produit a déjà été commandé (API catalogue expose `/products/{id}/has-been-ordered` ? Non : coommanages exposent nombres pour éviter le couplage inverse → décision : DELETE systématiquement converti en soft-delete, documenté).

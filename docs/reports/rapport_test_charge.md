# Rapport de test de charge — Catalogue

## 1. Objectif

Mesurer l'impact du passage de **1 à 3 répliques** du service Catalogue sur le
débit et la latence, en conservant une charge identique et un trafic passant
exclusivement par la passerelle Nginx (`http://localhost/api/catalogue/`).

## 2. Protocole

| Paramètre | Valeur |
| --- | --- |
| Scénario k6 | `tests/load/load_catalogue.js` |
| Charge | montée en 20 s jusqu'à 50 utilisateurs virtuels, palier de 40 s, descente de 10 s |
| Répartition du trafic | 70 % liste page 1 (chemin cache Redis), 30 % recherches uniques (chemin PostgreSQL) |
| Cible | passerelle Nginx → service Catalogue |
| Image k6 | `grafana/k6:1.0.0` |
| Seuils d'acceptation | cache p95 < 800 ms, base p95 < 1500 ms, checks > 99 % |

L'orchestrateur `tests/load/orchestrateur.py` applique `docker compose up -d
--scale catalogue=<n>` puis attend la stabilisation avant chaque exécution.

## 3. Résultats

| Indicateur | 1 réplique | 3 répliques | Écart |
| --- | ---: | ---: | ---: |
| Requêtes totales | 2 268 | 2 664 | +17 % |
| Débit (requêtes/s) | 32,0 | 37,8 | +18 % |
| p95 global (ms) | 672 | 89 | −87 % |
| p95 cache Redis (ms) | 653 | 71 | −89 % |
| p95 PostgreSQL (ms) | 697 | 115 | −83 % |
| Erreurs | 0 | 0 | — |

### Détail par chemin

| Chemin | Requêtes | p50 (ms) | p95 (ms) | Max (ms) |
| --- | ---: | ---: | ---: | ---: |
| Cache Redis — 1 réplique | 1 591 | 132 | 653 | 892 |
| Cache Redis — 3 répliques | 1 852 | 26 | 71 | 346 |
| PostgreSQL — 1 réplique | 677 | 196 | 697 | 910 |
| PostgreSQL — 3 répliques | 812 | 43 | 115 | 493 |

## 4. Analyse

- Les deux configurations respectent les seuils : le p95 du chemin cache reste
  sous 800 ms et celui du chemin base sous 1 500 ms.
- La répartition sur trois répliques divise le p95 global par plus de sept et
  absorbe 18 % de requêtes supplémentaires sur la même fenêtre de test.
- Les deux chemins progressent : la latence du cache chute de 89 %, celle de la
  base de 83 %. Le gain ne provient donc pas uniquement du cache mais bien de la
  parallélisation du traitement applicatif.
- Aucune erreur HTTP n'a été enregistrée dans les deux configurations.

## 5. Optimisations appliquées avant la mesure

Deux corrections ont été nécessaires pour que le test mesure le service et non
la passerelle :

1. **Passerelle Nginx** : les `proxy_pass` avec variable ouvraient une connexion
   TCP vers l'amont à chaque requête. Le routage utilise désormais des
   `upstream` avec `server ... resolve` et `keepalive`, ce qui conserve la
   découverte dynamique des répliques (scaling à chaud) tout en réutilisant les
   connexions.
2. **Service Catalogue** : le client Redis était instancié à chaque requête et
   exécutait un `PING` de contrôle avant chaque lecture. Le client est désormais
   unique par processus, avec le pool de connexions thread-safe de `redis-py`.

## 6. Reproduction

```powershell
# Pile démarrée et stabilisée
docker compose up -d

# Comparaison 1 vs 3 répliques
.\.venv\Scripts\python.exe tests\load\orchestrateur.py charge
```

Les résultats bruts sont écrits dans `docs/reports/load_1replica.json`,
`docs/reports/load_3replicas.json` et `docs/reports/comparatif_machines.json`.

## 7. Environnement de mesure

| Élément | Valeur |
| --- | --- |
| Processeur | Intel Core i7-10510U (4 cœurs / 8 threads) |
| Mémoire allouée à Docker | 8 Go |
| Système | Windows, Docker Desktop |
| Date de l'exécution | 11 novembre 2026 |

Les valeurs restent dépendantes de la machine hôte : elles servent à comparer
les deux configurations entre elles, pas à établir une capacité absolue.

# Guide de lancement MarchéCI

Ce guide s’adresse à une personne qui découvre le projet. Il explique comment lancer la boutique sur un ordinateur, vérifier qu’elle répond, puis l’arrêter sans supprimer les données.

## Ce qu’il faut installer

Pour lancer MarchéCI sur un ordinateur, préparez :

1. **Docker Desktop** sur Windows ou macOS, ou Docker Engine avec le plugin Docker Compose v2 sur Linux. Le moteur Docker doit être démarré.
2. **Python 3.12 ou plus récent**. Le launcher l’utilise pour vérifier `.env` et préparer les fichiers secrets la première fois.
3. Un accès Internet au premier démarrage pour télécharger les images et construire les conteneurs.

Node.js n’est pas nécessaire pour utiliser la boutique lancée par Docker. Il sert au développement du frontend.

Le port `80` doit être libre. Si un autre programme l’utilise, modifiez `GATEWAY_PORT` dans `.env`, par exemple en `8080`. L’interface Zabbix facultative utilise le port `8090` par défaut.

## Première configuration

1. Ouvrez le dossier **MarchéCI** dans l’Explorateur de fichiers ou le Finder.
2. Si le fichier `.env` n’est pas présent, lancez une première fois le script de démarrage décrit ci-dessous. Il copie `.env.example` vers `.env`, affiche un message de configuration requise, puis s’arrête.
3. Ouvrez `.env` avec un éditeur de texte, par exemple Notepad, TextEdit ou VS Code.
4. Remplacez chaque valeur `CHANGE_ME...` par un secret privé. Enregistrez le fichier. Ne publiez pas son contenu et ne l’envoyez pas dans un rapport.
5. Gardez le dossier du projet complet : le fichier `.env`, le dossier `secrets/`, `compose.yaml` et les sous-dossiers `services/` doivent rester ensemble.

Le launcher crée automatiquement les fichiers secrets qui manquent, uniquement après avoir validé `.env`. Il préserve les fichiers secrets déjà présents.

## Démarrer sous Windows

1. Ouvrez **Docker Desktop** depuis le menu Démarrer.
2. Attendez que Docker Desktop indique que le moteur est démarré (*Running*).
3. Dans le dossier `MarchéCI`, ouvrez `launcher`.
4. Double-cliquez sur **`start.bat`**.
5. Une fenêtre affiche la progression. Au premier lancement, Docker télécharge et construit les images : cela peut prendre plusieurs minutes.
6. Attendez les lignes `[OK] Catalogue opérationnel`, `[OK] Commandes opérationnel`, `[OK] Utilisateurs opérationnel`, `[OK] Notifications opérationnel`, `[OK] Frontend accessible`, puis `STATUT : APPLICATION DÉMARRÉE`.
7. Ouvrez l’adresse affichée, généralement **http://localhost/**.

Le compte administrateur est initialisé avec les valeurs `ADMIN_EMAIL` et `ADMIN_PASSWORD` de `.env`. Pour vous connecter, ouvrez **http://localhost/connexion**. Conservez ces valeurs privées.

## Démarrer sous Linux ou macOS

1. Démarrez Docker Desktop sur macOS ou Docker Engine sur Linux.
2. Ouvrez un terminal dans le dossier **MarchéCI**. Dans la plupart des gestionnaires de fichiers, clic droit sur le dossier puis **Ouvrir dans un terminal**.
3. Lancez le script fourni :

   ```sh
   sh launcher/start.sh
   ```

4. Suivez les lignes `[OK]`, puis ouvrez l’adresse imprimée, généralement **http://localhost/**.

Si le terminal indique qu’il ne peut pas exécuter Docker, démarrez Docker Desktop ou le service Docker puis relancez le même script.

## Ce que fait le démarrage

Le launcher vérifie Docker, Docker Compose, la configuration et les secrets, valide les fichiers Compose, construit les images puis démarre la base de données, Redis, RabbitMQ, les migrations, les comptes de démarrage, les quatre API et la passerelle web. Il attend les contrôles de santé puis interroge les routes HTTP des quatre API et la page du frontend.

Le launcher démarre une instance Catalogue. Le réglage de plusieurs répliques est une étape facultative de mesure de charge; le dernier résultat historique ne démontre pas encore un gain satisfaisant.

## Adresses utiles

Avec la configuration par défaut :

| Usage | Adresse |
|---|---|
| Boutique | `http://localhost/` |
| Connexion | `http://localhost/connexion` |
| Catalogue | `http://localhost/catalogue` |
| API (via Nginx) | `http://localhost/api/` |
| Santé de Gateway | `http://localhost/health` |
| Documentation API Catalogue | `http://localhost/docs/catalogue/` |
| Documentation API Commandes | `http://localhost/docs/commandes/` |
| Documentation API Utilisateurs | `http://localhost/docs/utilisateurs/` |
| Documentation API Notifications | `http://localhost/docs/notifications/` |

Si `GATEWAY_PORT` a été modifié, remplacez le port dans ces adresses. Par exemple, avec `GATEWAY_PORT=8080`, utilisez `http://localhost:8080/`.

## Démarrer Zabbix (facultatif)

Lancez d’abord MarchéCI. Sous Windows, double-cliquez ensuite sur `launcher/monitoring.bat`. Sous Linux/macOS, lancez `sh launcher/monitoring.sh` depuis la racine du projet. Le script remplace le mot de passe initial Zabbix avec la valeur privée de `.env`, crée les sondes et attend leur collecte; prévoyez environ une minute de plus. Quand le contrôle est réussi, ouvrez **http://127.0.0.1:8090/**.

Le compte initial reste `Admin`; son mot de passe vient de `ZABBIX_ADMIN_PASSWORD` dans `.env`. L’interface est liée à l’ordinateur local par défaut; elle n’est pas publiée sur Internet.

## Vérifier l’état et lire les journaux

Sous Windows, ouvrez les fichiers dans `launcher/` :

- `status.bat` affiche les conteneurs et vérifie les quatre API.
- `logs.bat` affiche les derniers journaux. Pour un service précis, lancez `logs.bat catalogue`, `logs.bat commandes`, `logs.bat utilisateurs` ou `logs.bat notifications`.

Sous Linux/macOS, depuis le dossier MarchéCI :

```sh
sh launcher/status.sh
sh launcher/logs.sh
sh launcher/logs.sh catalogue
```

Les journaux des services Zabbix sont accessibles avec `sh launcher/logs.sh zabbix-web` (ou `logs.bat zabbix-web`).

## Arrêter MarchéCI

- **Windows :** double-cliquez sur `launcher/stop.bat`.
- **Linux/macOS :** lancez `sh launcher/stop.sh` depuis la racine.

L’arrêt ferme les conteneurs et les réseaux. Il conserve les volumes PostgreSQL, RabbitMQ et Zabbix. Il n’existe pas de bouton de suppression des données dans le launcher; ne supprimez pas manuellement les volumes Docker si vous souhaitez conserver les commandes et les comptes.

## Dépannage

### Le démarrage dit que Docker ne répond pas

Ouvrez Docker Desktop, attendez l’état *Running* puis relancez `start.bat` ou `sh launcher/start.sh`. Sur Linux, vérifiez que Docker Engine et Compose v2 sont installés et que votre compte peut utiliser Docker.

### Le script demande de corriger `.env`

Ouvrez `.env`, remplacez les valeurs `CHANGE_ME...`, enregistrez, puis relancez le démarrage. Le script ne révèle jamais les valeurs de configuration qu’il vérifie.

### Le port 80 ou 8090 est déjà utilisé

Changez `GATEWAY_PORT` ou `MON_WEB_PORT` dans `.env`. Relancez ensuite le script concerné. La boutique est accessible sur le port choisi; Zabbix reste local par défaut.

### Un service ne devient pas opérationnel

Lisez l’état avec `launcher/status.bat` ou `sh launcher/status.sh`, puis ses journaux avec `launcher/logs.bat nom-du-service` ou `sh launcher/logs.sh nom-du-service`. Les noms sont `postgres`, `redis`, `rabbitmq`, `catalogue`, `commandes`, `utilisateurs`, `notifications` et `gateway`. Corrigez le problème signalé, puis relancez `start.bat` ou `sh launcher/start.sh`.

### L’interface s’ouvre mais le catalogue est vide

Une base neuve ne contient pas de produits de démonstration. Connectez-vous comme administrateur, ouvrez `/admin/categories` pour créer des rayons, puis `/admin/produits` pour créer les articles. Les images utilisent une URL; le projet ne téléverse pas de fichiers.

### Je veux ouvrir MarchéCI sur un téléphone connecté au même Wi-Fi

`localhost` sur le téléphone désigne le téléphone lui-même. Pour un essai sur le réseau local, ouvrez dans le navigateur du téléphone l’adresse IP locale de l’ordinateur qui héberge Docker, suivie du port de `GATEWAY_PORT`, par exemple `http://192.168.1.20/`. Le pare-feu de l’ordinateur et le réseau doivent autoriser cette connexion. Cette adresse locale ne constitue pas un déploiement sécurisé sur Internet.

## Utiliser MarchéCI depuis plusieurs appareils

Le launcher démarre les services sur un ordinateur qui exécute Docker. Pour un téléphone, une tablette ou un autre ordinateur, les services doivent être déployés sur un serveur accessible; l’utilisateur ouvre alors l’adresse web de ce serveur dans son navigateur. Docker et les microservices restent sur le serveur : ils ne s’installent pas sur Android, iPhone/iPad, Windows, macOS ou Linux utilisés comme clients.

Le dépôt contient la configuration Docker locale, mais pas un déploiement Internet prêt à l’emploi, de domaine ou de certificat TLS. Ne publiez pas directement cette configuration de démonstration sur Internet sans sécuriser l’hébergement, HTTPS, les comptes et les secrets.

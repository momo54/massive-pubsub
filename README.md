# Massive Queue - GAE Social Likes (minimal)

Application minimale sur Google App Engine qui gère des posts et des likes via une file Pub/Sub et un worker pull qui incrémente un compteur dans Firestore.

## Architecture
- Service web (App Engine Standard, Python 3.11):
  - `POST /posts` crée un post (Firestore)
  - `GET /posts` liste les posts
  - `POST /posts/{id}/like` publie un message dans Pub/Sub (`post-likes`)
- Service worker (App Engine Standard, Python 3.11, service séparé `worker`):
  - Endpoint `/tasks/drain` lancé par cron qui consomme la subscription `post-likes-sub` et met à jour le compteur `likes` dans Firestore (transaction).

## Prérequis
- gcloud SDK installé et connecté
- Un projet GCP et les rôles suffisants (Pub/Sub, Firestore, App Engine Admin)
- Firestore en mode natif initialisé

## Déploiement rapide
1. Initialiser App Engine (si pas encore fait):
   ```sh
   gcloud app create --region=europe-west3
   ```
2. Activer les APIs requises (si besoin):
   ```sh
   gcloud services enable appengine.googleapis.com firestore.googleapis.com pubsub.googleapis.com
   ```
3. Créer le topic et la subscription:
   ```sh
   gcloud pubsub topics create post-likes
   gcloud pubsub subscriptions create post-likes-sub --topic=post-likes
   ```
4. Déployer les services (web + worker) et le cron:
   ```sh
   gcloud app deploy app.yaml worker/app.yaml cron.yaml --quiet
   ```

## Test
- Créer un post:
  ```sh
  export APP_URL="https://<votre-app>.appspot.com"
  curl -X POST "$APP_URL/posts" -H 'Content-Type: application/json' -d '{"title":"Hello","content":"world"}'
  ```
- Liker un post (remplacez <ID>):
  ```sh
  curl -X POST "$APP_URL/posts/<ID>/like"
  ```
- Lister les posts:
  ```sh
  curl "$APP_URL/posts"
  ```

Le worker consommera les messages et mettra à jour `likes` en quelques secondes.

## Exécution locale (optionnel)
Pour tester en local (les clients GCP utilisent les identifiants par défaut):
```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_CLOUD_PROJECT=<votre-projet>
export PUBSUB_TOPIC=post-likes
FLASK_APP=main:app flask run -p 8080
# Dans un autre terminal, lancer le worker en mode drain
export GOOGLE_CLOUD_PROJECT=<votre-projet>
export PUBSUB_SUBSCRIPTION=post-likes-sub
curl -X POST http://localhost:8080/tasks/drain || python worker/worker.py
```

Notes:
- En local, assurez-vous d'avoir des identifiants d'application: `gcloud auth application-default login`.
- En prod, App Engine fournit automatiquement GOOGLE_CLOUD_PROJECT.

## Nettoyage
```sh
gcloud pubsub subscriptions delete post-likes-sub
gcloud pubsub topics delete post-likes
```

## Licence
MIT

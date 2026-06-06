# Agent RAG avec FastAPI, PostgreSQL et Hugging Face

Auteur: Yacouba Berthe

## Presentation

Ce projet est une API backend permettant a un utilisateur d'uploader des documents PDF, de les indexer dans une base vectorielle locale, puis de poser des questions a un assistant RAG.

L'objectif du projet est de montrer une architecture backend moderne autour de FastAPI, PostgreSQL, Alembic, Docker et Hugging Face, avec une base de deploiement compatible Railway.

Ce repository est pense comme un projet personnel de portfolio. Il n'est pas presente comme une solution enterprise complete, mais comme une application backend structuree, deployable et progressivement durcie avec les bonnes pratiques de production.

## Fonctionnalites Actuelles

- Authentification utilisateur avec JWT.
- Creation de compte utilisateur.
- Connexion avec OAuth2 Password Flow.
- Hash des mots de passe avec bcrypt via Passlib.
- Upload de fichiers PDF authentifie.
- Limite actuelle de 10 fichiers PDF par requete.
- Limite actuelle de 10 MB par fichier PDF.
- Extraction des PDF avec `pypdf`.
- Decoupage leger des PDF en chunks.
- Stockage des chunks dans PostgreSQL.
- Recherche documentaire simple par utilisateur.
- Metadata ajoutees aux chunks: nom du fichier, page et utilisateur.
- Sources fournies au contexte RAG avec nom du fichier et page.
- Generation de reponse via l'API Hugging Face.
- Persistance des conversations en PostgreSQL.
- Endpoints pour consulter les conversations et messages.
- Endpoint de suppression d'une conversation.
- Migrations de base de donnees avec Alembic.
- Dockerfile pour lancer l'API.
- Docker Compose pour lancer l'API avec PostgreSQL en local.
- Configuration Railway avec `railway.json`.
- Endpoint de sante `/health`.

## Stack Technique

- Python
- FastAPI
- Uvicorn
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic
- Passlib
- python-jose
- Hugging Face
- Docker
- Docker Compose

## Architecture

```text
Client
  |
  v
FastAPI
  |
  |-- Auth JWT
  |-- Upload PDF
  |-- Chat RAG
  |
  |--> PostgreSQL
  |      |-- users
  |      |-- chat_sessions
  |      |-- chat_messages
  |      |-- document_chunks
  |
  |--> Hugging Face
         |-- modele de generation
```

## Structure Du Projet

```text
.
|-- alembic/
|   |-- versions/
|   |   `-- 0001_initial_schema.py
|   |-- env.py
|   `-- script.py.mako
|-- routers/
|   |-- auth_router.py
|   |-- chat_router.py
|   |-- upload_router.py
|   `-- user_router.py
|-- classes.py
|-- config.py
|-- database.py
|-- main.py
|-- rag.py
|-- tablebase.py
|-- alembic.ini
|-- Dockerfile
|-- docker-compose.yml
|-- railway.json
|-- requirements.txt
|-- .env.example
`-- README.md
```

## Variables D'environnement

Les variables attendues sont definies dans `.env.example`.

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/database

HF_TOKEN=

JWT_SECRET_KEY=
JWT_ALGO=HS256

ALLOWED_ORIGINS=
```

### Description Des Variables

| Variable | Description |
| --- | --- |
| `DATABASE_URL` | URL de connexion PostgreSQL utilisee par SQLAlchemy et Alembic. |
| `HF_TOKEN` | Token Hugging Face utilise pour acceder aux services Hugging Face si necessaire. |
| `JWT_SECRET_KEY` | Cle secrete utilisee pour signer les tokens JWT. |
| `JWT_ALGO` | Algorithme de signature JWT, par defaut `HS256`. |
| `ALLOWED_ORIGINS` | Liste d'origines autorisees pour CORS, separees par des virgules. Exemple: `http://localhost:3000,https://mon-front.com`. |

Important: le fichier `.env` ne doit jamais etre pousse sur GitHub.

## Installation Locale

### 1. Cloner le projet

```bash
git clone <url-du-repository>
cd <nom-du-repository>
```

### 2. Creer un environnement virtuel

```bash
python -m venv .venv
```

### 3. Activer l'environnement virtuel

Sur Windows:

```bash
.venv\Scripts\activate
```

Sur macOS/Linux:

```bash
source .venv/bin/activate
```

### 4. Installer les dependances

```bash
pip install -r requirements.txt
```

Pour installer aussi les outils de developpement:

```bash
pip install -r requirements-dev.txt
```

### 5. Configurer les variables d'environnement

Creer un fichier `.env` a partir du modele:

```bash
cp .env.example .env
```

Puis remplir les valeurs necessaires.

Sur Windows PowerShell, la copie peut se faire avec:

```powershell
Copy-Item .env.example .env
```

### 6. Lancer les migrations

```bash
alembic upgrade head
```

### 7. Lancer l'API

```bash
uvicorn main:app --reload
```

L'API sera disponible par defaut sur:

```text
http://127.0.0.1:8000
```

## Lancement Avec Docker Compose

Le fichier `docker-compose.yml` permet de lancer l'API avec une base PostgreSQL locale.

```bash
docker compose up --build
```

L'API sera disponible sur:

```text
http://localhost:8000
```

Endpoint de sante:

```text
GET /health
```

Le `Dockerfile` utilise:

- une image Python slim;
- `PYTHONDONTWRITEBYTECODE=1`;
- `PYTHONUNBUFFERED=1`;
- un utilisateur non-root `appuser`;
- la variable `PORT` pour rester compatible Railway.

## Deploiement Railway

Le projet contient un `Dockerfile` compatible avec Railway.

Le projet contient aussi un fichier `railway.json` pour versionner la configuration Railway minimale:

```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "healthcheckPath": "/health",
    "healthcheckTimeout": 300,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

Railway fournit une variable d'environnement `PORT`. Le `Dockerfile` lance Uvicorn avec cette variable:

```dockerfile
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

Sur Railway, il faut configurer:

- un service PostgreSQL;
- la variable `DATABASE_URL`;
- les variables Hugging Face;
- les variables JWT.

Healthcheck recommande:

```text
/health
```

### Etapes Railway Recommandees

1. Creer un nouveau projet Railway.
2. Ajouter un service PostgreSQL.
3. Deployer ce repository depuis GitHub.
4. Verifier que Railway detecte le `Dockerfile`.
5. Configurer les variables d'environnement du service API.
6. Verifier que `DATABASE_URL` pointe vers le PostgreSQL Railway.
7. Lancer les migrations Alembic sur l'environnement Railway.
8. Verifier que `/health` retourne `200`.
9. Tester l'inscription, la connexion, l'upload et le chat.

### Variables Railway A Configurer

```env
DATABASE_URL=
HF_TOKEN=
JWT_SECRET_KEY=
JWT_ALGO=HS256
ALLOWED_ORIGINS=
```

`DATABASE_URL` doit venir du service PostgreSQL Railway.

Avec SQLAlchemy et `psycopg`, le format recommande est:

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/database
```

`ALLOWED_ORIGINS` doit contenir l'URL du frontend si un frontend est connecte a l'API.

Exemple:

```env
ALLOWED_ORIGINS=https://mon-frontend.com
```

### Migrations Railway

Avant un deploiement public, les migrations Alembic doivent etre executees sur la base Railway:

```bash
alembic upgrade head
```

Cette etape n'est pas encore automatisee dans `railway.json`. Le choix est volontaire pour eviter de lancer automatiquement des migrations destructives pendant la phase portfolio.

### Notes Railway Importantes

- Railway utilise le `Dockerfile` present a la racine du projet.
- L'API doit ecouter sur `0.0.0.0`.
- L'API doit utiliser la variable `PORT` fournie par Railway.
- Le healthcheck est configure sur `/health`.
- La recherche documentaire actuelle est volontairement legere pour faciliter Docker/Railway. Pour une recherche semantique avancee, il faudrait ajouter un moteur vectoriel externe.

## Endpoints Principaux

### Sante

```http
GET /health
```

Retour attendu:

```json
{
  "status": "ok"
}
```

### Authentification

```http
POST /auth/register
```

Cree un utilisateur.

```http
POST /auth/login
```

Retourne un token JWT.

### Chat RAG

```http
POST /chat_ask/
```

Pose une question a l'assistant RAG.

Authentification requise.

### Upload De Documents

```http
POST /upload/upload_document
```

Upload un ou plusieurs PDF pour indexation vectorielle.

Authentification requise.

### Utilisateur Et Conversations

```http
PUT /user/update_password
```

Met a jour le mot de passe de l'utilisateur connecte.

```http
GET /user/conversation
```

Liste les conversations de l'utilisateur connecte.

```http
GET /user/messages/{session_id}
```

Liste les messages d'une conversation.

```http
DELETE /user/messages/{session_id}
```

Supprime une conversation et ses messages associes.

## Base De Donnees

Les tables applicatives actuelles sont:

- `users`
- `chat_sessions`
- `chat_messages`
- `document_chunks`

Contraintes et index importants:

- email utilisateur unique;
- username utilisateur unique et indexe;
- relation obligatoire entre une conversation et un utilisateur;
- relation obligatoire entre un message et une conversation;
- unicite `(user_id, thread_id)` pour eviter les conversations dupliquees;
- index sur `chat_sessions.user_id`;
- index sur `chat_sessions.thread_id`;
- index sur `chat_messages.session_id`;
- index sur `document_chunks.user_id`;
- cascade configuree au niveau des cles etrangeres.

Les migrations sont gerees avec Alembic.

Migrations actuelles:

```text
alembic/versions/0001_initial_schema.py
alembic/versions/0002_strengthen_constraints_and_indexes.py
alembic/versions/0003_add_document_chunks.py
```

## Qualite Code

Le projet utilise `ruff` pour le lint et le formatage.

Verifier le code:

```bash
ruff check .
```

Formatter le code:

```bash
ruff format .
```

La configuration se trouve dans:

```text
pyproject.toml
```

La CI GitHub Actions execute aussi cette verification automatiquement.

## Tests

Le projet est configure pour utiliser `pytest`.

Lancer les tests:

```bash
pytest
```

Les tests seront ajoutes dans le dossier:

```text
tests/
```

La CI GitHub Actions execute les tests automatiquement a chaque push sur `main` ou `master`, et a chaque pull request.

Tests actuellement presents:

- verification de `/health`;
- creation d'un utilisateur;
- connexion et generation d'un token JWT;
- refus d'une route protegee sans authentification;
- refus d'un upload non PDF;
- appel de `/chat_ask/` avec agent RAG mocke.

## RAG

Le RAG fonctionne actuellement avec:

- extraction des PDF avec `pypdf`;
- decoupage leger en chunks;
- stockage des chunks dans PostgreSQL;
- recherche simple par mots dans les chunks de l'utilisateur;
- metadata sur les chunks: `filename`, `page`, `user_id`;
- contexte RAG formate avec les sources disponibles;
- generation de reponse via l'API Hugging Face.

Le modele actuellement configure dans le code est:

```text
Qwen/Qwen3-32B
```

## Securite Actuelle

Le projet contient deja:

- hash des mots de passe;
- authentification JWT;
- routes protegees par token;
- configuration CORS par variable d'environnement;
- rate limiting simple en memoire sur auth, chat et upload;
- verification basique des fichiers PDF;
- limite de taille des fichiers;
- `.gitignore` pour eviter de pousser `.env`, `.venv`, caches et bases locales.

## Limites Connues Actuelles

Ces limites sont connues et seront traitees progressivement dans la roadmap:

- README initialement vide avant cette documentation.
- Tests minimum des endpoints critiques ajoutes.
- CI GitHub Actions ajoutee.
- Configuration `ruff` ajoutee.
- Le lint global passe avec `ruff check .`.
- Rate limiting simple ajoute. Il est en memoire et adapte a un projet portfolio, mais pas a un usage multi-replicas.
- Configuration CORS ajoutee via `ALLOWED_ORIGINS`.
- Les erreurs principales RAG, upload et DB sont loggees.
- Les ecritures DB principales gerent maintenant un rollback en cas d'erreur.
- Le streaming RAG utilise encore la session DB dans le generateur.
- Les embeddings sont recrees a plusieurs endroits au lieu d'etre centralises.
- La recherche actuelle est plus legere qu'une recherche vectorielle semantique.
- Les chunks contiennent les metadata principales: fichier, page et utilisateur.
- Les sources sont fournies au contexte RAG. La reponse reste un flux texte simple.
- Le Dockerfile utilise maintenant un utilisateur non-root.
- Contraintes et index DB principaux renforces.

## Roadmap Production-Ready Portfolio

Cette roadmap correspond aux etapes prevues avant publication finale du projet sur GitHub.

### 1. Documentation

- Rediger un README complet.
- Documenter l'installation locale.
- Documenter Docker.
- Documenter Railway.
- Documenter les endpoints.
- Documenter les limites connues.

### 2. Qualite Code

- `pyproject.toml` ajoute.
- `ruff` configure.
- `pytest` configure.
- Base de tooling developpement ajoutee avec `requirements-dev.txt`.

### 3. Tests

- Tests minimum des endpoints critiques ajoutes.
- `/health` teste.
- Inscription testee.
- Connexion testee.
- Route protegee sans token testee.
- Upload invalide teste.
- Chat teste avec un RAG mocke.

### 4. CI GitHub Actions

- Workflow CI ajoute.
- Lint lance avec `ruff check .`.
- Tests lances avec `pytest`.

### 5. Logs Et Robustesse DB

- Logs ajoutes sur les erreurs principales.
- Rollbacks ajoutes sur les ecritures DB principales.
- Erreurs RAG mieux journalisees.
- Refactor complet du streaming encore a faire si le projet doit monter en charge.

### 6. Securite API

- CORS configure par environnement avec `ALLOWED_ORIGINS`.
- Rate limiting simple ajoute sur auth, chat et upload.
- Renforcer les validations Pydantic.

### 7. Railway

- Documentation Railway ajoutee.
- Configuration Railway ajoutee avec `railway.json`.
- Strategie de migrations documentee.

### 8. RAG

- Metadata ajoutees aux documents.
- Sources ajoutees au contexte RAG.
- Remplacement des embeddings locaux lourds par une recherche PostgreSQL legere.
- Ameliorer la recherche documentaire si besoin avec un moteur externe.

### 9. Base De Donnees

- Contraintes plus strictes ajoutees.
- Index utiles ajoutes.
- Contrainte unique `(user_id, thread_id)` ajoutee.
- Relations et suppressions renforcees avec `ondelete="CASCADE"`.

### 10. Docker

- Dockerfile durci.
- Utilisateur non-root ajoute.
- Image preparee pour un deploiement portfolio Railway/Docker.

## Etat Actuel Du Projet

Le projet est actuellement en phase de durcissement avant publication GitHub.

Etat:

- API fonctionnelle en local.
- Dockerfile present.
- Docker Compose present.
- Dockerfile durci avec utilisateur non-root.
- Configuration Railway presente avec `railway.json`.
- Alembic configure.
- Auth JWT presente.
- Upload PDF present.
- RAG present.
- Documentation en cours.
- Tests a ajouter.
- CI a ajouter.
- Durcissement production portfolio en cours.

## Licence

Licence a definir avant publication finale sur GitHub.

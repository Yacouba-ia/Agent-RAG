# Agent RAG avec FastAPI, PostgreSQL et OpenAI

API backend de portfolio pour uploader des PDF, stocker les chunks dans PostgreSQL, interroger un assistant RAG et tracer les executions avec LangSmith.

En bref: une demo backend qui montre de bout en bout l'authentification, l'upload de documents, la recherche documentaire, la reponse RAG, les traces LangSmith, Docker, Railway et les tests automatiques.

## Presentation

Projet developpe par Yacouba Berthe, developpeur backend Python/FastAPI oriente API, IA appliquee, RAG, Docker, PostgreSQL et deploiement cloud.

Ce projet est une API backend permettant a un utilisateur d'uploader des documents PDF, de stocker leurs chunks dans PostgreSQL, puis de poser des questions a un assistant RAG.

L'objectif du projet est de montrer une architecture backend moderne autour de FastAPI, PostgreSQL, Alembic, Docker, OpenAI et Railway.

Ce repository est pense comme un projet personnel de portfolio. Il n'est pas presente comme une solution enterprise complete, mais comme une application backend structuree, deployable et durcie avec des pratiques proches de la production.

Ce qui compte ici, c'est la preuve visible que l'API fonctionne pour de vrai, qu'elle peut etre testee publiquement, et qu'elle est assez propre pour inspirer confiance a un recruteur ou a un client.

## Ce Que Le Projet Montre

- Authentification JWT.
- Gestion de comptes utilisateurs.
- Upload de PDF authentifie.
- Stockage des documents et des conversations dans PostgreSQL.
- Pipeline RAG simple, lisible et documente.
- Trace LangSmith sur les parties importantes du workflow.
- Docker et Docker Compose.
- Deploiement compatible Railway.
- Tests automatises et lint.

## Fonctionnalites Actuelles

- Authentification utilisateur avec JWT.
- Creation de compte utilisateur.
- Connexion avec OAuth2 Password Flow.
- Hash des mots de passe avec bcrypt via Passlib.
- Upload de fichiers PDF authentifie.
- Limite de 10 fichiers PDF par requete.
- Limite de 10 MB par fichier PDF.
- Extraction des PDF avec `pypdf`.
- Decoupage leger des PDF en chunks.
- Stockage des chunks dans PostgreSQL.
- Liste des PDF indexes par utilisateur.
- Suppression des PDF indexes par utilisateur.
- Recherche documentaire simple par utilisateur.
- Metadata ajoutees aux chunks: nom du fichier, page et utilisateur.
- Sources fournies au contexte RAG avec nom du fichier et page.
- Generation de reponse streamee via l'API OpenAI.
- Gestion propre des erreurs temporaires du service IA.
- Observabilite et tracing RAG avec LangSmith.
- Persistance des conversations en PostgreSQL.
- Endpoints pour consulter les conversations et messages.
- Endpoint de suppression d'une conversation.
- Rate limiting persistant en base.
- Logs HTTP simples avec statut et duree.
- Migrations de base de donnees avec Alembic.
- Dockerfile pour lancer l'API.
- Docker Compose pour lancer l'API avec PostgreSQL en local.
- Configuration Railway avec `railway.json`.
- Endpoint de sante `/health`.
- Endpoint de readiness `/ready`.

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
- OpenAI
- LangSmith
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
  |-- Logs HTTP
  |
  |--> PostgreSQL
  |      |-- users
  |      |-- chat_sessions
  |      |-- chat_messages
  |      |-- document_chunks
  |      |-- rate_limit_events
  |
  |--> OpenAI
  |      |-- modele de generation
  |
  |--> LangSmith
         |-- tracing RAG
         |-- observabilite
```

## Structure Du Projet

```text
.
|-- alembic/
|   |-- versions/
|   |   |-- 0001_initial_schema.py
|   |   |-- 0002_strengthen_constraints_and_indexes.py
|   |   |-- 0003_add_document_chunks.py
|   |   `-- 0004_rate_limit_events.py
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
|-- rate_limit.py
|-- tablebase.py
|-- alembic.ini
|-- Dockerfile
|-- docker-compose.yml
|-- railway.json
|-- requirements.txt
|-- requirements-dev.txt
|-- .env.example
`-- README.md
```

## Variables D'environnement

Les variables attendues sont definies dans `.env.example`.

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/database

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=1600

LANGCHAIN_API_KEY=
LANGCHAIN_TRACING_V2=false
LANGCHAIN_PROJECT=rag-fastapi-openai-api

JWT_SECRET_KEY=
JWT_ALGO=HS256

ALLOWED_ORIGINS=
```

### Description Des Variables

| Variable | Description |
| --- | --- |
| `DATABASE_URL` | URL de connexion PostgreSQL utilisee par SQLAlchemy et Alembic. |
| `OPENAI_API_KEY` | Cle API OpenAI utilisee pour generer les reponses RAG. |
| `OPENAI_MODEL` | Modele OpenAI utilise pour la generation, par defaut `gpt-4o-mini`. |
| `OPENAI_MAX_OUTPUT_TOKENS` | Limite maximale de tokens de sortie OpenAI, par defaut `1600`. |
| `LANGCHAIN_API_KEY` | Cle LangSmith utilisee pour tracer les executions RAG. |
| `LANGCHAIN_TRACING_V2` | Active ou desactive le tracing LangSmith. |
| `LANGCHAIN_PROJECT` | Nom du projet LangSmith utilise pour organiser les traces. |
| `JWT_SECRET_KEY` | Cle secrete utilisee pour signer les tokens JWT. |
| `JWT_ALGO` | Algorithme de signature JWT, par defaut `HS256`. |
| `ALLOWED_ORIGINS` | Liste d'origines autorisees pour CORS, separees par des virgules. |
| `TRUST_PROXY_HEADERS` | Active la lecture des headers de proxy pour recuperer la vraie IP cliente en production. |

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

Sur Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Puis remplir les valeurs necessaires.

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

Endpoints utilitaires:

```text
GET /health
GET /ready
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
- les variables OpenAI `OPENAI_API_KEY`, `OPENAI_MODEL` et `OPENAI_MAX_OUTPUT_TOKENS`;
- les variables JWT;
- `ALLOWED_ORIGINS` si un frontend est connecte.
- `TRUST_PROXY_HEADERS=true`.

### Notes Railway Importantes

- Railway utilise le `Dockerfile` present a la racine du projet.
- L'API doit ecouter sur `0.0.0.0`.
- L'API doit utiliser la variable `PORT` fournie par Railway.
- Le healthcheck est configure sur `/health`.
- Les migrations ne sont pas automatisees au deploy.
- La recherche documentaire actuelle reste legere pour garder le projet simple a deployer.

### Verification Deploiement Public

Quand le projet est en ligne, un testeur peut verifier:

1. `GET /health` pour confirmer que l'API repond.
2. `GET /ready` pour confirmer que PostgreSQL repond.
3. `POST /auth/register` puis `POST /auth/login` pour valider l'authentification.
4. `POST /upload/upload_document` avec un vrai PDF pour valider l'indexation.
5. `POST /chat_ask/` pour verifier la lecture du contexte et la reponse RAG.

### Ce Que La Demo Montre

- une API qui demarre et repond proprement;
- une base PostgreSQL reliee a l'application;
- un flux utilisateur complet: inscription, connexion, upload, question, reponse;
- un RAG trace avec LangSmith;
- un comportement propre en cas d'indisponibilite temporaire du service IA.

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

### Readiness

```http
GET /ready
```

Retour attendu quand PostgreSQL repond:

```json
{
  "status": "ready",
  "database": "ok"
}
```

### Authentification

```http
POST /auth/register
POST /auth/login
```

### Chat RAG

```http
POST /chat_ask/
```

Authentification requise.

### Upload De Documents

```http
POST /upload/upload_document
GET /upload/documents
DELETE /upload/documents/{filename}
```

Authentification requise.

### Utilisateur Et Conversations

```http
PUT /user/update_password
GET /user/conversation
GET /user/messages/{session_id}
DELETE /user/messages/{session_id}
```

## Base De Donnees

Les tables applicatives actuelles sont:

- `users`
- `chat_sessions`
- `chat_messages`
- `document_chunks`
- `rate_limit_events`

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
- index sur `rate_limit_events.scope`;
- index sur `rate_limit_events.client_key`;
- index sur `rate_limit_events.created_at`;
- cascade configuree au niveau des cles etrangeres.

Les migrations sont gerees avec Alembic.

Migrations actuelles:

```text
alembic/versions/0001_initial_schema.py
alembic/versions/0002_strengthen_constraints_and_indexes.py
alembic/versions/0003_add_document_chunks.py
alembic/versions/0004_rate_limit_events.py
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

La configuration se trouve dans `pyproject.toml`.

## Tests

Le projet utilise `pytest`.

Lancer les tests:

```bash
pytest
```

Tests actuellement presents:

- verification de `/health`;
- verification de `/ready`;
- creation d'un utilisateur;
- connexion et generation d'un token JWT;
- rate limiting auth;
- refus d'une route protegee sans authentification;
- refus d'un upload non PDF;
- appel de `/chat_ask/` avec agent RAG mocke;
- streaming OpenAI mocke, sauvegarde de la reponse finale et gestion propre des erreurs.

## RAG

Le RAG fonctionne actuellement avec:

- extraction des PDF avec `pypdf`;
- decoupage leger en chunks;
- stockage des chunks dans PostgreSQL;
- recherche simple par mots dans les chunks de l'utilisateur;
- metadata sur les chunks: `filename`, `page`, `user_id`;
- contexte RAG formate avec les sources disponibles;
- generation de reponse en streaming via l'API OpenAI;
- limite de sortie configurable avec `OPENAI_MAX_OUTPUT_TOKENS`;
- sauvegarde de la reponse assistant complete en PostgreSQL apres la fin du streaming;
- gestion propre des erreurs temporaires de l'API OpenAI;
- tracing LangSmith sur la recherche documentaire, l'appel OpenAI et l'execution RAG globale.

Le modele de generation se configure avec la variable d'environnement:

```text
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=1600
```

## Securite Actuelle

Le projet contient deja:

- hash des mots de passe;
- authentification JWT;
- routes protegees par token;
- configuration CORS par variable d'environnement;
- rate limiting persistant en base sur auth, chat et upload;
- verification basique des fichiers PDF;
- limite de taille des fichiers;
- validation de la disponibilite base avec `/ready`;
- logs HTTP simples pour mieux diagnostiquer les requetes;
- `.gitignore` pour eviter de pousser `.env`, `.venv`, caches et bases locales.

## Observabilite

Le projet integre LangSmith pour tracer les parties importantes du pipeline RAG:

- recuperation des chunks documentaires;
- construction du contexte;
- appel au modele OpenAI;
- execution globale de la reponse RAG;
- journalisation des requetes HTTP avec leur duree et leur statut.

Le tracing est configurable via les variables d'environnement:

```env
LANGCHAIN_API_KEY=
LANGCHAIN_TRACING_V2=false
LANGCHAIN_PROJECT=rag-fastapi-openai-api
```

En local ou en CI, le tracing peut rester desactive avec `LANGCHAIN_TRACING_V2=false`.
En environnement de demonstration, il suffit d'ajouter une cle LangSmith valide et d'activer le tracing.

## Limites Connues Actuelles

Ces limites sont connues et sont traitees progressivement:

- La recherche documentaire reste volontairement legere et lexicale.
- L'appel OpenAI depend toujours de la disponibilite du service externe.
- Le streaming utilise une reponse texte simple compatible avec le frontend actuel.
- Les migrations Railway ne sont pas automatisees.
- Il n'y a pas encore de frontend dans ce repository.

## Etat Actuel Du Projet

Le projet est en phase de durcissement final avant publication GitHub.

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
- Tracing LangSmith present.
- Logs HTTP presents.
- Endpoint `/ready` present.
- Documentation complete pour portfolio.
- Tests automatises presents.
- CI GitHub Actions presente.
- Base technique propre pour une presentation GitHub serieuse.

## Licence

Licence a definir avant publication finale sur GitHub.

## Auteur

Yacouba Berthe.

Developpeur backend Python/FastAPI avec un focus sur les API REST, les systemes RAG, l'integration IA, Docker, PostgreSQL et le deploiement cloud.

Ce projet fait partie de mon portfolio technique pour demontrer ma capacite a concevoir, structurer, tester, documenter et deployer une API backend orientee IA.

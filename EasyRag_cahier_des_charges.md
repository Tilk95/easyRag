# EasyRag — Cahier des charges détaillé pour développement

## 1. Objectif général
EasyRag est une application locale de type RAG permettant d’interroger un corpus documentaire via un LLM local (Ollama) ou distant (API OpenAI-compatible).
Le produit doit être simple à installer, maintenable, modulaire et extensible.

## 2. Contraintes
- Pas de Docker
- Fonctionnement local macOS / Windows
- Backend Python
- Frontend JS legacy sans framework ni bundler
- Dépendances minimales
- Séparation stricte des responsabilités

## 3. Cas d’usage
### 3.1 Utilisateur final
- Importer des documents (PDF, MD, TXT)
- Poser des questions
- Obtenir des réponses sourcées
- Modifier la configuration RAG
- Changer de LLM sans redéployer

### 3.2 Administrateur
- Configurer les providers
- Supprimer / réindexer des documents
- Gérer plusieurs projets documentaires

## 4. Architecture

Frontend (HTML/JS)
→ API Python locale
→ Services métiers (ingest, index, retrieve, llm)
→ Stockage local

## 5. Modules

### 5.1 API
- Expose routes REST
- Validation des entrées
- Gestion erreurs

### 5.2 Config
- Chargement / sauvegarde config
- Validation schéma
- Gestion env vars

### 5.3 Ingestion
- Lecture fichiers
- Extraction texte
- Normalisation

### 5.4 Chunking
- Découpage contrôlé
- Overlap paramétrable

### 5.5 Embeddings
- Local via sentence-transformers
- Abstraction pour futur API

### 5.6 Vector store
- Chroma local persistant
- Wrapper dédié

### 5.7 Retrieval
- Recherche top-k
- Scoring
- Formatage sources

### 5.8 Prompting
- Template paramétrable
- Mode strict_context

### 5.9 LLM
- Client Ollama
- Client API compatible
- Router

### 5.10 Frontend
- Chat
- Documents
- Configuration
- Providers

## 6. Données

### 6.1 Document
- id
- nom
- type
- taille
- hash
- date_import
- statut

### 6.2 Chunk
- id
- doc_id
- texte
- embedding

## 7. API

### 7.1 Chat
POST /api/chat
Input : question, top_k?, strict_context?
Output : answer, sources[]

### 7.2 Docs
POST /api/docs/upload
GET /api/docs
DELETE /api/docs/{id}

### 7.3 Config
GET /api/config
PUT /api/config

## 8. Règles métier
- Si strict_context = true et aucune info pertinente → "Je ne sais pas"
- Changement embeddings → réindex requis
- Déduplication par hash

## 9. Non-fonctionnel
- Logs centralisés
- Erreurs lisibles
- Index persistant
- Performances acceptables (<3s sur corpus moyen)

## 10. Roadmap

### Phase 1
- Import docs
- Indexation
- Chat simple

### Phase 2
- Multi-projets
- Reranking
- Streaming

### Phase 3
- Qdrant option
- Auth locale
- Export/import KB

## 11. Critères d’acceptation
- Application démarre sans Docker
- UI fonctionnelle
- RAG fiable
- Code modulaire


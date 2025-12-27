EasyRag — Spécification de développement (sans Docker)
1. Objectif produit
EasyRag est une application locale (PC ou Mac) permettant :
d’importer des documents PDF, MD, TXT
de construire un index RAG local (chunks + embeddings + vector store)
de poser des questions via une IHM web locale
de générer une réponse basée sur les passages récupérés (“retrieval”) avec sources/citations
de basculer à tout moment entre :
LLM local via Ollama
LLM distant via API OpenAI-compatible (base_url + api_key + model)
Contraintes :
Zéro Docker
Installation simple : venv + pip
IHM en JS legacy (vanilla), sans build, sans modules ES, dépendances front minimales
Séparation stricte des fonctions (maintenabilité / évolutivité)
2. Périmètre MVP (v0.1)
2.1 Fonctions utilisateur (IHM)
Chat RAG
zone de saisie question
affichage réponse
affichage des sources (document + extrait + score)
options rapides :
top_k (par défaut config)
strict_context ON/OFF : si ON, le modèle doit répondre uniquement selon le contexte, sinon “je ne sais pas”.
Documents
upload multi-fichiers (PDF/MD/TXT)
liste des documents importés :
nom, type, taille, date import, nb de chunks
statut indexation (OK/En cours/Erreur)
actions :
supprimer un document
réindexer un document
Configuration
chunk_size, chunk_overlap
top_k
prompt template (texte modifiable, variables standard)
choix embeddings (MVP : local, modèle par défaut)
chemin de stockage local (par défaut ~/.easyrag/)
Connecteurs LLM
Mode actif : Local (Ollama) ou API
Configuration Ollama :
base_url
model
bouton “tester”
liste modèles disponibles (si Ollama dispo)
Configuration API OpenAI-compatible :
base_url
api_key (masqué)
model
bouton “tester”
3. Architecture globale (obligatoire)
3.1 Processus
Backend Python : un serveur HTTP local (ex. 127.0.0.1)
Frontend statique : HTML/CSS/JS servi par le backend (pas de serveur séparé)
3.2 Séparation des responsabilités (exigence)
Interdit :
un gros fichier unique “fourre-tout”
mélanger UI, logique RAG, stockage, appels LLM dans un même module
Obligatoire :
modules dédiés par domaine (config, storage, ingest, index, retrieval, llm, api)
fonctions courtes, testables, à responsabilités uniques
logs et erreurs centralisés (gestion uniforme)
4. Structure de repository attendue
Le développeur doit produire une arborescence claire et stable :
easyrag/
api/
app.py (démarrage serveur, routes, middlewares)
routes/ (un fichier par domaine)
health_routes.py
config_routes.py
docs_routes.py
chat_routes.py
providers_routes.py
schemas/ (DTO/validation)
config_models.py
chat_models.py
docs_models.py
easyrag/core/
config/
config_service.py (load/save, env vars, validation)
storage/
paths.py (dossiers, conventions)
sqlite_repo.py (métadonnées documents, historique)
ingest/
loaders_pdf.py
loaders_md.py
loaders_txt.py
chunker.py
dedup.py (hash document)
index/
embeddings.py (local embeddings MVP)
vectordb.py (Chroma wrapper)
indexer.py (pipeline indexation)
rag/
retrieve.py
prompting.py
rag_service.py (orchestration query: retrieve→prompt→LLM)
llm/
ollama_client.py
openai_compat_client.py
llm_router.py (switch local/api)
utils/
logging.py
errors.py
time.py
web/ (frontend)
index.html
style.css
app.js (IIFE legacy, sans modules)
views/ (optionnel)
chat.js, docs.js, config.js (si séparation front)
README.md
requirements.txt
config.example.yaml
Notes :
Le développeur peut regrouper davantage, mais doit conserver la séparation “domain-driven”.
5. Stockage local
5.1 Emplacement
Par défaut sur macOS :
base : ~/.easyrag/
docs/ (fichiers originaux)
index/ (Chroma persist)
db/metadata.sqlite (métadonnées)
config/config.yaml
5.2 Métadonnées minimales (SQLite)
Table documents :
doc_id (UUID)
filename
filetype (pdf/md/txt)
size_bytes
sha256
created_at
indexed_at
chunk_count
status (OK|INDEXING|ERROR)
error_message (nullable)
6. Pipeline RAG (MVP)
6.1 Ingestion
upload → sauvegarde fichier (docs/)
extraction texte selon type
normalisation minimale (espaces, lignes)
chunking :
chunk_size (par défaut 800 “caractères” ou “tokens approximés”)
chunk_overlap (par défaut 120)
calcul embeddings pour chaque chunk
upsert dans Chroma avec metadata :
doc_id, filename, chunk_id, page (pdf si dispo), sha256, created_at
6.2 Retrieval
embedding de la question
recherche top_k dans vector store
renvoi des passages + score
formatage des sources
6.3 Prompting
Prompt template paramétrable (configurable)
Variables standard :
{context} (chunks concaténés, avec séparateurs)
{question}
{rules} (règles strict_context)
Si strict_context=true :
la réponse doit se limiter au contexte
si manque, répondre explicitement “je ne sais pas (contexte insuffisant)”
Réponse inclut des citations (au minimum une section “Sources” côté UI)
7. LLM : Local / API
7.1 Ollama (local)
Config :
base_url (par défaut http://localhost:11434)
model
Fonction :
appeler endpoint de génération (stream optionnel future)
Endpoint UI :
lister modèles disponibles si Ollama répond
7.2 API OpenAI-compatible
Config :
base_url (ex https://…/v1)
api_key (stocké sécurisé via env si possible)
model
Exigence :
interface “OpenAI-compatible” uniquement (pas de SDK spécifique)
timeouts et erreurs gérés proprement
7.3 Router
llm_router sélectionne le provider selon la config courante
Possibilité d’override “par requête” (optionnel v0.1)
8. Contrat API (backend)
Tous les endpoints sous /api.
8.1 Health
GET /api/health → { ok, version }
8.2 Config
GET /api/config → config courante
PUT /api/config → update config + validation + persist
8.3 Providers
GET /api/providers → { active_mode, available_modes }
POST /api/providers/test → test connexion provider courant
GET /api/ollama/models → liste modèles (si accessible)
8.4 Documents
POST /api/docs/upload (multipart) → lance indexation (sync MVP accepté)
GET /api/docs → liste documents
DELETE /api/docs/{doc_id} → supprime doc + chunks index
8.5 Chat
POST /api/chat
input : { question, project?, top_k?, strict_context? }
output : { answer, sources:[{ doc_id, filename, chunk_id, score, excerpt, page? }] }
9. Frontend JS legacy (contraintes)
Aucun build
Pas de modules ES
app.js en IIFE
fetch() uniquement
rendu DOM simple (templates)
code organisé :
soit app.js unique mais structuré en “sections”
soit views/chat.js, views/docs.js, views/config.js inclus via <script> (legacy-friendly)
10. Exigences non fonctionnelles
10.1 Performance
Indexation : progress minimal (statut)
Retrieval : réponse en < 2–3s sur corpus modeste (dépend du LLM)
Top_k par défaut 5
10.2 Robustesse
Gestion erreurs :
message UI lisible
logs côté serveur
Dédup : si un document déjà importé (sha256 identique), proposer :
ignorer
réindexer
conserver une nouvelle version
10.3 Sécurité locale
API key :
recommandation : variable d’environnement
si stockée en config, chiffrage optionnel (peut être v0.2)
CORS : inutile si UI servie par le backend (préférable)
11. Livrables attendus
Repo complet, exécutable localement
README.md :
installation venv
lancement
config
troubleshooting
config.example.yaml
(Optionnel) scripts :
run_dev.sh (macOS)
run_dev.bat (Windows ultérieur)
12. Critères d’acceptation (MVP)
L’application démarre localement sans Docker
Depuis l’IHM :
upload PDF/MD/TXT
indexation persistée sur disque
chat RAG renvoie réponse + sources
bascule Ollama ↔ API sans redéployer
Code structuré par modules (pas de mélange des responsabilités)
Notes de cadrage pour Cursor (à donner au développeur)
Respecter strictement l’architecture et la séparation en modules.
Ne pas ajouter de frameworks front ni de dépendances lourdes inutiles.
Préférer des “clients HTTP simples” pour Ollama et API compatible.
Prévoir la version Windows plus tard : éviter les chemins hardcodés, centraliser dans paths.py.

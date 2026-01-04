# EasyRag - RAG Local Simple

RAG minimaliste pour patrimoine OpenVMS (C / SQLMOD / DCL) utilisant SQLite FTS5.

## 🚀 Utilisation Simple

Tout est à la racine, pas besoin d'installer de package !

### 1. Indexer des fichiers

```bash
python3 cli.py index --root ./sources_vms --db rag.db
```

### 2. Rechercher dans l'index

```bash
python3 cli.py query --db rag.db --q "F$SEARCH OR SET NOON" --type dcl
```

### 3. Expliquer (RAG)

**Mode context** (sans LLM, juste les extraits) :
```bash
python3 cli.py explain --db rag.db --question "Comment gère-t-on les erreurs ?" --mode context
```

**Mode rules** (synthèse heuristique, sans LLM) :
```bash
python3 cli.py explain --db rag.db --question "Explique ce batch" --mode rules
```

**Mode Ollama** (avec LLM) :
```bash
python3 cli.py explain --db rag.db --question "Explique la gestion d'erreur" --mode ollama
```

### 4. Serveur HTTP (optionnel)

```bash
python3 cli.py serve --db rag.db --port 8787
```

## 📋 Commandes Disponibles

### Indexer
```bash
python3 cli.py index --root <dossier> --db <fichier.db> [--include-exts .c,.h,.com] [--quiet]
```

### Rechercher
```bash
python3 cli.py query --db <fichier.db> --q "<requête>" [--top-k 10] [--type dcl|c|sqlmod] [--format text|json]
```

### Expliquer (RAG)
```bash
python3 cli.py explain --db <fichier.db> --question "<question>" [--mode ollama|context|rules] [--top-k 8] [--model <modèle>]
```

### Serveur
```bash
python3 cli.py serve --db <fichier.db> [--host 127.0.0.1] [--port 8787]
```

## 🔧 Variables d'environnement (optionnel)

Pour Ollama :
- `RAGLITE_OLLAMA_URL` : URL Ollama (défaut: http://localhost:11434)
- `RAGLITE_OLLAMA_MODEL` : Modèle Ollama (défaut: llama3.1)

## 📁 Structure

```
easyRag/
├── cli.py          # Interface en ligne de commande
├── indexing.py     # Indexation des fichiers
├── rag.py          # RAG (retrieval + LLM)
├── llm.py          # Client Ollama
├── models.py       # Modèles de données
├── store/          # Base de données SQLite
└── chunkers/       # Découpage par type de fichier
```

## 💡 Aide

Pour voir toutes les options :
```bash
python3 cli.py --help
python3 cli.py index --help
python3 cli.py query --help
python3 cli.py explain --help
```


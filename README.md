# Text Data Analysis and Visualization Platform

A modular, production-ready, three-tier web application designed for processing raw text data, performing advanced NLP analyses, and visualizing plural text representations (sparse counts, Latent Dirichlet Allocation topics, and dense contextual embeddings).

## 🚀 Key Features
- **FastAPI Backend**: High-performance RESTful API structure with OAuth2 JWT token security and Role-Based Access Control (RBAC).
- **Asynchronous Processing**: Background workers powered by Celery & Redis to offload long-running text preprocessing and ML representation modeling.
- **Relational Storage**: PostgreSQL tracks project layouts, document states, and execution histories.
- **S3 Storage**: S3-compatible object storage (MinIO for local development) stores raw text uploads and calculated JSON outputs.
- **Hybrid Search Engine**: Elasticsearch combines BM25 lexical keyword matching with cosine similarity approximate nearest neighbor (ANN) vector searches.
- **Reproducibility Core**: Generates detailed, versioned execution provenance manifests capturing system environments, library versions, seeds, parameters, and storage paths.

---

## 🏗️ System Architecture

```
                                  +------------------------------------+
                                  |         Client UI / Consumers      |
                                  +-----------------+------------------+
                                                    | (FastAPI HTTP)
                                                    v
                                  +-----------------+------------------+
                                  |         FastAPI REST Web API       |
                                  +--------+--------+--------+---------+
                                           |        |        |
                         +-----------------+        |        +-----------------+
                         |                          |                          |
                         v                          v                          v
              +----------+-----------+   +----------+-----------+   +----------+-----------+
              |      PostgreSQL      |   |         Redis        |   |    Elasticsearch     |
              | (Metadata & Histories)|   | (Celery Queue/Cache) |   |  (Lexical & Vector)  |
              +----------------------+   +----------+-----------+   +----------------------+
                                                    |
                                                    v
                                         +----------+-----------+
                                         |    Celery Worker     |
                                         |  (NLTK/spaCy/SBERT)  |
                                         +----------+-----------+
                                                    |
                                                    v
                                         +----------+-----------+
                                         |      S3 / MinIO      |
                                         | (Raw texts/Artifacts)|
                                         +----------------------+
```

---

## 🛠️ Folder Layout
```
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI application root
│   │   ├── core/                   # Settings, security, DB connections, S3, Elasticsearch clients
│   │   ├── models/                 # SQLAlchemy ORM models (User, Project, Document, ProvenanceManifest)
│   │   ├── schemas/                # Pydantic schemas (Request / Response validation)
│   │   ├── api/                    # Route handlers (auth, documents, search, analysis)
│   │   ├── pipeline/               # spaCy preprocessors, representation modules, provenance trackers
│   │   └── tasks/                  # Celery tasks (NLP & Representation modeling)
│   ├── requirements.txt            # Python dependencies
│   └── Dockerfile                  # Application Dockerfile
├── docker-compose.yml              # Local container services orchestration
├── .env.example                    # Environment template
└── README.md                       # Documentation
```

---

## 🐳 Docker Deployment Setup

The backend and all dependencies are containerized. The Docker environment is locked to **Python 3.12** for compilation stability.

### Prerequisites
- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)

### Execution Steps
1. **Initialize Environments**:
   Copy the default settings template:
   ```bash
   cp .env.example .env
   ```

2. **Spin Up Containers**:
   Execute the docker-compose orchestrator. This compiles the backend, provisions databases, configures MinIO folders, and starts background workers:
   ```bash
   docker-compose up --build
   ```

3. **Verify Health**:
   - **FastAPI Endpoint**: [http://localhost:8000/](http://localhost:8000/)
   - **Swagger Docs API**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **MinIO Dashboard Console**: [http://localhost:9001/](http://localhost:9001/) (User: `minioadmin` / Pass: `minioadmin`)

---

## ⚙️ Local Development Setup (Manual)

If you wish to run the FastAPI app directly on your host machine (outside Docker):

1. **Create Virtual Environment**:
   ```bash
   cd backend
   python -m venv venv
   source venv/Scripts/activate  # On Windows
   # source venv/bin/activate    # On Unix/Mac
   ```

2. **Install Dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Install NLP Models**:
   ```bash
   python -m spacy download en_core_web_sm
   python -m nltk.downloader punkt stopwords wordnet
   ```

4. **Configure Local Variables**:
   Update `.env` values to point to your local PostgreSQL, Redis, Elasticsearch, and S3 servers.

5. **Start Application Servers**:
   - **Web Server**:
     ```bash
     uvicorn app.main:app --reload --port 8000
     ```
   - **Celery Worker**:
     ```bash
     celery -A app.tasks.celery_app worker --loglevel=info
     ```

---

## 🔒 Security & Role-Based Access Control (RBAC)

The application implements JWT token auth (`HS256`). Routes are guarded by roles:
1. **Viewer**: Read-only privileges. Can search document contents, read results, and download provenance manifests.
2. **Analyst**: Can create projects, upload raw text files, trigger asynchronous background worker analysis tasks, and delete documents.
3. **Admin**: Full system permissions, including deleting projects, modifying users, and triggering task operations.

*Note: The very first user registering on a clean database is automatically elevated to **Admin** status to simplify initial setups.*

---

## 🔍 Hybrid Search Workflow
The search endpoint (`GET /api/v1/projects/{project_id}/search?q=query`) implements hybrid query execution:
1. Computes dense contextual vector representations of the search term `q` on-the-fly using the Sentence-BERT encoder.
2. Executes a dual Elasticsearch search:
   - **Lexical Search (BM25)** matching keyword tokens in `title` and `clean_content`.
   - **ANN Search (Approximate Nearest Neighbor)** calculating cosine similarity matches against document vector fields.
3. Integrates scores with a tunable boost balance factor, returning combined search hits.

---

## 📝 Provenance & Reproducibility
For every document execution, a versioned provenance manifest is automatically generated and written to S3 as a JSON file.
It contains:
- `timestamp`: Execution time.
- `pipeline_version`: Current software version.
- `environment`: Python release, hardware host OS, and version constraints of all loaded NLP/ML libraries (`spacy`, `nltk`, `scikit-learn`, `gensim`, `sentence-transformers`).
- `parameters`: Configured random seeds, LDA topics, and count parameters.
- `data_manifest`: Absolute storage URIs for the raw source text and computed result files.

Retrieve the pre-signed S3 download link via: `GET /api/v1/documents/{document_id}/provenance`

---

## 🧪 Running Automated Tests

To execute tests and verify API routes, ML models, and S3/Elasticsearch mock wrappers:

1. **Activate Environment and Run PyTest**:
   ```bash
   cd backend
   pytest
   ```

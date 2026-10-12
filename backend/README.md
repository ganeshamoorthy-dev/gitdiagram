# Backend Architecture & Technical Documentation

The backend service is built with **FastAPI** and **Graphify (`graphifyy`)**. Its primary responsibility is to ingest remote Git repositories or local source code directories, perform deterministic AST analysis into a knowledge graph (`graph.json`), and transform the graph into optimized, styled **Mermaid.js** diagrams.

---

## 🏛️ System Architecture

```
                                  [ Client (React UI / CLI) ]
                                               │
                                 POST /api/generate (JSON payload)
                                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               FASTAPI APPLICATION LAYER                                │
│                                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ 1. HTTP Middleware Layer                                                         │  │
│  │    - Request duration logging (ms) & status code tracking                        │  │
│  │    - CORS handling (Cross-Origin Resource Sharing)                               │  │
│  └────────────────────────────────────────┬─────────────────────────────────────────┘  │
│                                           ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ 2. Controller & Ingestion Layer                                                  │  │
│  │    - Target Resolution: Remote Git URL vs. Local Directory (from .env)           │  │
│  │    - Validation & Query Parameter Normalization                                  │  │
│  └──────────────────┬───────────────────────────────────────────┬───────────────────┘  │
└─────────────────────┼───────────────────────────────────────────┼──────────────────────┘
                      ▼                                           ▼
      [ Case A: Remote Git URL ]                     [ Case B: Local Directory ]
┌──────────────────────────────────────────┐    ┌────────────────────────────────────────┐
│ 3. Git Ingestion Layer                   │    │ 3. Local Ingestion Layer               │
│    - Shallow clone: git clone --depth 1  │    │    - Validates path from .env / input  │
│    - Isolated temp workspace allocation  │    │    - Direct local filesystem access    │
└─────────────────────┬────────────────────┘    └───────────────────┬────────────────────┘
                      └─────────────────────┬───────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. AST Extraction Layer (Graphify Engine)                                              │
│    - Subprocess execution: `graphify extract <dir> --code-only`                       │
│    - Tree-sitter parsers (Python, TypeScript, JS, Go, Rust, Java, C++, etc.)           │
│    - Extracts symbols: functions, classes, calls, imports, containment, inheritance   │
│    - Leiden community clustering (subsystem identification)                           │
│    - Writes output to: `<work_dir>/graphify-out/graph.json`                            │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 5. Graph Transformer Layer (`graph_transformer.py`)                                   │
│    - Parsing & Degree Centrality Calculation (connectivity ranking)                   │
│    - Detail-level filtering (overview / components / detailed)                        │
│    - Node Pruning using `max_nodes` (prioritizes architectural hubs)                   │
│    - Sanitization & Deterministic Hashing (`n_{md5(id)[:10]}`)                         │
│    - Semantic Class Injection (hubNode, classNode, funcNode, fileNode, moduleNode)     │
│    - Subgraph Clustering (Community vs. Source File)                                   │
│    - Relation Mapping (`contains`, `calls`, `imports`, `inherits`, `method`)           │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 6. Response Layer & Teardown                                                           │
│    - Constructs JSON: { mermaid_code, stats, graph_json, repo_url, is_local }         │
│    - Workspace Teardown: Safely cleans up temporary clone folders (try/finally)        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📂 Backend File Organization

```
backend/
├── .env                     # Active environment variables (local dir, ports, timeouts)
├── .env.example             # Example environment configuration template
├── requirements.txt         # Production dependencies
├── main.py                  # FastAPI entry point, middleware, routes, and git executor
├── graph_transformer.py     # Graph.json parsing, degree centrality, & Mermaid generator
├── generate_diagram.py      # Standalone terminal CLI script
└── README.md                # Architecture and technical documentation (this file)
```

---

## 🔍 Layer Breakdown

### 1. HTTP Middleware Layer (`main.py`)
* Intercepts all incoming requests and measures execution latency in milliseconds.
* Structured logging format: `[HTTP Layer] --> Incoming request: POST /api/generate` and `[HTTP Layer] <-- Completed ... (4120ms)`.

### 2. Ingestion & Target Resolution Layer (`main.py`)
Determines the analysis source:
* **Remote Git Repository**: Recognizes `http://`, `https://`, and `git@`. Allocates a temporary directory (`tempfile.mkdtemp(prefix="git_diagram_")`) and performs a fast, lightweight clone:
  ```bash
  git clone --depth 1 [--branch <branch>] <repo_url> <temp_dir>
  ```
* **Local Directory**: Reads directory paths from user input or fallback to `LOCAL_CODE_DIR` specified in `.env`. Directly points to the local folder with zero network overhead.

### 3. AST Extraction Layer (`graphifyy`)
Executes the headless AST extraction engine:
```bash
graphify extract <target_dir> --code-only
```
* **Deterministic parsing**: Uses Tree-sitter grammar parsers for 20+ programming languages.
* **No external LLM / API keys required**: Runs completely offline and locally on your CPU.
* **Outputs**:
  * `graphify-out/graph.json`: Machine-readable graph structure with node and edge definitions.
  * `.graphify_analysis.json`: Leiden community clusters and connectivity scores.

### 4. Graph Transformer Layer (`graph_transformer.py`)
Translates the JSON graph into idiomatic, formatted Mermaid code:

#### **A. Degree Centrality Ranking**
Calculates `degree = in_degree + out_degree` for every node in the graph:
$$\text{Degree}(v) = |\{(u, v) \in E\}| + |\{(v, w) \in E\}|$$
Nodes with high connectivity represent core architectural components ("God nodes" or central coordinators).

#### **B. Detail Filtering**
* `overview`: Keeps only files and major classes.
* `components` *(default)*: Keeps files, classes, and top-level functions; filters private leaf methods (`.__init__`, etc.).
* `detailed`: Retains all AST entities up to the node threshold.

#### **C. Node Pruning (`max_nodes`)**
Sorts candidate nodes by degree in descending order and retains the top $N$ nodes. Edges where both endpoints exist in the selected set are preserved.

#### **D. Deterministic ID Hashing**
Mermaid syntax breaks if node IDs contain special characters like `.`, `/`, `-`, `\`, or whitespace.
Each node ID is deterministically hashed:
```python
def _safe_id(raw_id: str) -> str:
    digest = hashlib.md5(raw_id.encode("utf-8")).hexdigest()[:10]
    return f"n_{digest}"
```

#### **E. Semantic Color Styling**
Mermaid CSS classes are injected at the top of the diagram:
```mermaid
classDef fileNode fill:#1e293b,stroke:#0284c7,stroke-width:2px,color:#f8fafc;
classDef classNode fill:#2e1065,stroke:#a855f7,stroke-width:2px,color:#f8fafc;
classDef funcNode fill:#3b1d11,stroke:#f97316,stroke-width:2px,color:#f8fafc;
classDef moduleNode fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#f8fafc;
classDef hubNode fill:#831843,stroke:#ec4899,stroke-width:3px,stroke-dasharray: 4 2;
```
The top 3 connected nodes are highlighted with `hubNode` (pink dashed border).

#### **F. Relation Mapping**
AST relationships are mapped to Mermaid link types:
* `contains` $\rightarrow$ `A -.-> B` (dotted arrow)
* `inherits` $\rightarrow$ `A ==>|inherits| B` (thick solid arrow)
* `calls` $\rightarrow$ `A -->|calls| B` (labeled arrow)
* `imports` $\rightarrow$ `A -->|imports| B` (labeled arrow)
* `method` $\rightarrow$ `A -->|method| B` (labeled arrow)

---

## 📡 REST API Reference

### `POST /api/generate`
Generates a Mermaid diagram and graph metadata from a remote repo or local path.

**Request Body:**
```json
{
  "repo_url": "https://github.com/psf/requests",
  "branch": "main",
  "detail_level": "components",
  "max_nodes": 50,
  "direction": "TD",
  "group_by": "community"
}
```
*Note: If `repo_url` is omitted, the server uses `LOCAL_CODE_DIR` from `.env`.*

**Response Body:**
```json
{
  "mermaid_code": "flowchart TD\n    classDef ...\n    subgraph Comm_0 ...",
  "stats": {
    "total_nodes": 120,
    "total_edges": 164,
    "displayed_nodes": 45,
    "displayed_edges": 42,
    "file_count": 14,
    "community_count": 4,
    "top_connected": [
      {
        "id": "requests_sessions_Session",
        "label": "Session",
        "source_file": "requests/sessions.py",
        "connections": 28
      }
    ]
  },
  "graph_json": { ... },
  "repo_url": "https://github.com/psf/requests",
  "is_local": false
}
```

---

### `POST /api/generate-from-json`
Directly converts an existing `graph.json` payload into Mermaid code without re-running AST extraction.

---

### `GET /api/config`
Retrieves runtime configuration loaded from `.env` (`LOCAL_CODE_DIR`, defaults).

---

### `GET /api/health`
Verifies server health, Python environment, and detected Graphify executable path.

---

### `GET /api/sample`
Returns instant demo graph data and pre-generated Mermaid diagram without cloning.

---

## ⚙️ Environment Variables (`.env`)

| Variable | Default | Description |
|---|---|---|
| `HOST` | `127.0.0.1` | Server host address |
| `PORT` | `8000` | Server port |
| `LOCAL_CODE_DIR` | `./` | Path to local directory for instant offline codebase scanning |
| `DEFAULT_DETAIL_LEVEL` | `components` | Default detail filter (`overview`, `components`, `detailed`) |
| `DEFAULT_MAX_NODES` | `50` | Default maximum node count in Mermaid diagram |
| `DEFAULT_DIRECTION` | `TD` | Default layout flow (`TD` = Top-Down, `LR` = Left-to-Right) |
| `DEFAULT_GROUP_BY` | `community` | Clustering strategy (`community`, `file`, `none`) |
| `GIT_CLONE_TIMEOUT` | `90` | Maximum git clone execution time in seconds |
| `AST_EXTRACT_TIMEOUT` | `120` | Maximum Tree-sitter extraction time in seconds |

---

## 🧪 Testing & Standalone Execution

You can run the transformer or test extraction directly from the command line:

```powershell
cd backend

# Test sample endpoint output & logging
.\.venv\Scripts\python -c "import main; print(main.get_sample()['mermaid_code'])"

# Run standalone CLI against any local or remote repo
.\.venv\Scripts\python generate_diagram.py D:\path\to\code --detail components --out-mermaid diagram.mmd
```

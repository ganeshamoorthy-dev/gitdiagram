# Git Diagram Generator (Graphify + React + Mermaid)

An end-to-end tool to extract code structure and dependencies from any Git repository using **Graphify (`graphifyy`)**, output `graph.json`, and visualize it as an interactive **Mermaid.js** diagram in a modern **React** UI.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       React Frontend                        │
│  - Git Repo URL Input & Branch Selector                     │
│  - Filter Controls: Detail level, Layout, Subsystem Groups  │
│  - Interactive Mermaid Canvas: Zoom, Pan, Export SVG        │
│  - Mermaid Markdown Viewer with 1-Click Copy                │
│  - Raw graph.json Explorer & Download                       │
└───────────────────────────────┬─────────────────────────────┘
                                │ POST /api/generate
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Python Backend                   │
│  1. Shallow Git Clone (`git clone --depth 1 <repo>`)        │
│  2. Graphify AST Extraction (`graphify extract --code-only`)│
│  3. Read `graphify-out/graph.json`                          │
│  4. Transform nodes & edges into sanitized Mermaid syntax   │
│  5. Return Mermaid code, network statistics, and graph.json │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
git diagram/
├── backend/
│   ├── .venv/                   # Python virtual environment
│   ├── main.py                  # FastAPI server with CORS & endpoints
│   ├── graph_transformer.py     # Graph.json -> Mermaid converter
│   ├── generate_diagram.py      # Standalone CLI tool
│   └── requirements.txt         # Dependencies (graphifyy, fastapi, uvicorn)
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── MermaidViewer.tsx # Interactive Mermaid viewer (zoom/pan/SVG export)
│   │   ├── App.tsx              # Main UI with inputs, filters, tabs, & metrics
│   │   ├── main.tsx             # React entry point
│   │   └── style.css            # Modern dark slate UI design
│   ├── package.json             # Vite, React, Mermaid.js, Lucide icons
│   └── vite.config.ts           # Vite config with backend proxy
│
├── start_backend.bat            # One-click script to start FastAPI backend
├── start_frontend.bat           # One-click script to start React frontend
└── README.md
```

---

## 🚀 How to Run

### 1. Start Backend (FastAPI)

```bash
cd backend
.\.venv\Scripts\uvicorn main:app --reload --port 8000
```
Backend runs at `http://127.0.0.1:8000` (API docs at `http://127.0.0.1:8000/docs`).

### 2. Start Frontend (React + Vite)

```bash
cd frontend
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 💻 Standalone Python CLI

If you want to generate diagrams directly in the terminal without running the web UI:

```bash
cd backend
.\.venv\Scripts\python generate_diagram.py https://github.com/psf/requests --detail components --out-mermaid diagram.mmd --out-json graph.json
```

Or for a local codebase:

```bash
.\.venv\Scripts\python generate_diagram.py D:\path\to\your\codebase --detail overview
```

---

## ⚙️ Features

1. **Deterministic AST Parsing via Tree-sitter (`graphifyy`)**:
   - Zero LLM API keys needed for code structure extraction.
   - Parses classes, functions, calls, imports, containment, and inheritance.
2. **Intelligent Mermaid Generation**:
   - Sanitizes special characters and quotes to ensure valid Mermaid syntax.
   - Automatically ranks nodes by degree/centrality so key hub nodes ("God nodes" & primary interfaces) are prioritized when diagram node limits are applied.
   - Groups subsystems into Mermaid subgraphs by Leiden community cluster or source file.
3. **Interactive React UI**:
   - **Diagram Canvas**: Pan (drag) and Zoom (buttons / percentage view) with SVG export.
   - **Mermaid Code**: View raw Mermaid syntax with one-click copy to clipboard.
   - **graph.json Explorer**: Inspect and download the raw graph database file.
   - **Quick Demo**: One-click test button to inspect immediate visualizations without waiting for a git clone.

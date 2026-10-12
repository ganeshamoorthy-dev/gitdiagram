import os
import shutil
import subprocess
import sys
import tempfile
import json
import logging
import time
from typing import Optional, Literal
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph_transformer import transform_graph_to_mermaid

# Helper to load .env manually without extra external libraries
def load_env_file():
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = val

load_env_file()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("backend.api")

app = FastAPI(title="Git Diagram Generator", version="1.0.0")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    method = request.method
    url = request.url.path
    logger.info(f"[HTTP Layer] --> Incoming request: {method} {url}")
    
    try:
        response = await call_next(request)
        duration = (time.time() - start_time) * 1000
        logger.info(f"[HTTP Layer] <-- Completed {method} {url} with status {response.status_code} ({duration:.2f}ms)")
        return response
    except Exception as exc:
        duration = (time.time() - start_time) * 1000
        logger.error(f"[HTTP Layer] <-- Unhandled exception on {method} {url}: {exc} ({duration:.2f}ms)", exc_info=True)
        raise exc


class GenerateRequest(BaseModel):
    # repo_url can be a remote Git URL or a local folder path, or empty to fallback to .env LOCAL_CODE_DIR
    repo_url: Optional[str] = None
    branch: Optional[str] = None
    detail_level: Optional[Literal["overview", "components", "detailed"]] = None
    max_nodes: Optional[int] = None
    direction: Optional[Literal["TD", "LR"]] = None
    group_by: Optional[Literal["community", "file", "none"]] = None


class GenerateFromDataRequest(BaseModel):
    graph_data: dict
    detail_level: Literal["overview", "components", "detailed"] = "components"
    max_nodes: int = 50
    direction: Literal["TD", "LR"] = "TD"
    group_by: Literal["community", "file", "none"] = "community"


def get_graphify_executable() -> str:
    """Find the graphify CLI in the virtual environment or PATH."""
    venv_bin = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
    candidate = venv_bin / ("graphify.exe" if os.name == "nt" else "graphify")
    if candidate.exists():
        return str(candidate)
    system_which = shutil.which("graphify")
    if system_which:
        return system_which
    return f"{sys.executable} -m graphify"


@app.get("/api/config")
def get_config():
    """Returns runtime environment config."""
    return {
        "local_code_dir": os.environ.get("LOCAL_CODE_DIR", ""),
        "default_detail_level": os.environ.get("DEFAULT_DETAIL_LEVEL", "components"),
        "default_max_nodes": int(os.environ.get("DEFAULT_MAX_NODES", 50)),
        "default_direction": os.environ.get("DEFAULT_DIRECTION", "TD"),
        "default_group_by": os.environ.get("DEFAULT_GROUP_BY", "community"),
    }


@app.get("/api/health")
def health_check():
    logger.info("[Health Layer] Checking system and dependencies status")
    graphify_bin = get_graphify_executable()
    status_info = {
        "status": "ok",
        "python_version": sys.version,
        "graphify_path": graphify_bin,
        "env_local_code_dir": os.environ.get("LOCAL_CODE_DIR", ""),
    }
    logger.info(f"[Health Layer] Status healthy. Graphify binary: {graphify_bin}")
    return status_info


@app.post("/api/generate")
def generate_diagram(req: GenerateRequest):
    # Read target from request or fall back to .env LOCAL_CODE_DIR
    target_input = (req.repo_url or "").strip()
    if not target_input:
        target_input = os.environ.get("LOCAL_CODE_DIR", "").strip()

    if not target_input:
        logger.warning("[Controller Layer] Validation error: No repo URL or local directory provided, and LOCAL_CODE_DIR is unset.")
        raise HTTPException(
            status_code=400,
            detail="No target specified. Please provide a Git URL or local folder path, or set LOCAL_CODE_DIR in .env."
        )

    # Defaults from .env or request
    detail_level = req.detail_level or os.environ.get("DEFAULT_DETAIL_LEVEL", "components")
    max_nodes = req.max_nodes or int(os.environ.get("DEFAULT_MAX_NODES", 50))
    direction = req.direction or os.environ.get("DEFAULT_DIRECTION", "TD")
    group_by = req.group_by or os.environ.get("DEFAULT_GROUP_BY", "community")

    is_remote_git = target_input.startswith(("http://", "https://", "git@"))
    is_local_dir = False
    target_path = None

    if not is_remote_git:
        # Check if local folder path exists
        candidate_path = Path(target_input).resolve()
        if candidate_path.exists() and candidate_path.is_dir():
            is_local_dir = True
            target_path = str(candidate_path)
            logger.info(f"[Controller Layer] Target resolved to local directory: {target_path}")
        else:
            logger.warning(f"[Controller Layer] Validation error: '{target_input}' is neither a valid remote Git URL nor an existing local directory.")
            raise HTTPException(
                status_code=400,
                detail=f"Target '{target_input}' is not a valid Git URL or existing local folder directory."
            )

    logger.info(f"[Controller Layer] Processing target: {target_input} (is_local={is_local_dir})")
    logger.info(f"[Controller Layer] Options: branch={req.branch}, detail={detail_level}, max_nodes={max_nodes}, direction={direction}, group_by={group_by}")

    temp_dir = None
    work_dir = None

    try:
        if is_remote_git:
            # Shallow clone remote repo
            temp_dir = tempfile.mkdtemp(prefix="git_diagram_")
            work_dir = temp_dir
            logger.info(f"[Workspace Layer] Allocated temporary workspace at {temp_dir}")
            logger.info(f"[Git Layer] Starting git clone for '{target_input}' (depth=1)...")
            t_clone_start = time.time()
            clone_cmd = ["git", "clone", "--depth", "1"]
            if req.branch:
                clone_cmd.extend(["--branch", req.branch])
            clone_cmd.extend([target_input, temp_dir])

            try:
                clone_res = subprocess.run(
                    clone_cmd,
                    capture_output=True,
                    text=True,
                    timeout=int(os.environ.get("GIT_CLONE_TIMEOUT", 90)),
                    check=False,
                )
                if clone_res.returncode != 0:
                    err_msg = clone_res.stderr.strip() or clone_res.stdout.strip()
                    logger.error(f"[Git Layer] Git clone failed (exit code {clone_res.returncode}): {err_msg}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to clone repository: {err_msg}"
                    )
                logger.info(f"[Git Layer] Git clone completed successfully in {(time.time() - t_clone_start):.2f}s")
            except subprocess.TimeoutExpired:
                logger.error("[Git Layer] Git clone timed out")
                raise HTTPException(
                    status_code=408,
                    detail="Git clone timed out. Repository may be too large or network is slow."
                )
        else:
            # Use specified local directory directly from .env / input
            work_dir = target_path
            logger.info(f"[Local Layer] Analyzing local repository directly at {work_dir}")

        # Step 2: Run graphify extract
        graphify_cmd = get_graphify_executable()
        cmd_args = [graphify_cmd, "extract", work_dir, "--code-only"]
        logger.info(f"[Graphify Layer] Executing AST extraction: {' '.join(cmd_args)}")
        t_graphify_start = time.time()

        try:
            extract_res = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=int(os.environ.get("AST_EXTRACT_TIMEOUT", 120)),
                cwd=work_dir,
                check=False,
            )
            if extract_res.returncode != 0:
                logger.warning(f"[Graphify Layer] graphify extract exited with code {extract_res.returncode}. Stderr: {extract_res.stderr.strip()}")
            else:
                logger.info(f"[Graphify Layer] graphify AST extraction finished in {(time.time() - t_graphify_start):.2f}s")
        except subprocess.TimeoutExpired:
            logger.error("[Graphify Layer] Graph extraction timed out")
            raise HTTPException(
                status_code=408,
                detail="Graph extraction timed out."
            )

        # Step 3: Check for graphify-out/graph.json
        graph_json_path = Path(work_dir) / "graphify-out" / "graph.json"
        if not graph_json_path.exists():
            logger.error(f"[Storage Layer] Missing expected output file: {graph_json_path}")
            raise HTTPException(
                status_code=500,
                detail=f"graphify did not generate graph.json. Output: {extract_res.stderr or extract_res.stdout}"
            )

        logger.info(f"[Storage Layer] Loading graph.json from {graph_json_path} (size: {graph_json_path.stat().st_size} bytes)")
        with open(graph_json_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)

        node_count = len(graph_data.get("nodes", []))
        link_count = len(graph_data.get("links", []))
        logger.info(f"[Storage Layer] graph.json parsed successfully: {node_count} raw nodes, {link_count} raw links")

        # Step 4: Transform graph.json to Mermaid code
        logger.info("[Transformer Layer] Starting transformation from graph.json to Mermaid code...")
        t_trans_start = time.time()
        result = transform_graph_to_mermaid(
            graph_data=graph_data,
            detail_level=detail_level,
            max_nodes=max_nodes,
            direction=direction,
            group_by=group_by,
        )
        logger.info(f"[Transformer Layer] Transformation completed in {(time.time() - t_trans_start):.2f}s: {result['stats']['displayed_nodes']} nodes and {result['stats']['displayed_edges']} edges rendered in diagram")

        result["graph_json"] = graph_data
        result["repo_url"] = target_input
        result["is_local"] = is_local_dir
        logger.info(f"[Controller Layer] Successfully fulfilled request for {target_input}")
        return result

    finally:
        # If a temporary clone was created, clean it up safely
        if temp_dir and os.path.exists(temp_dir):
            def handle_remove_readonly(func, path, exc):
                import stat
                os.chmod(path, stat.S_IWRITE)
                func(path)

            logger.info(f"[Workspace Layer] Cleaning up temporary clone workspace at {temp_dir}")
            shutil.rmtree(temp_dir, onerror=handle_remove_readonly)


@app.post("/api/generate-from-json")
def generate_from_json(req: GenerateFromDataRequest):
    """Allows converting an existing graph.json to Mermaid directly."""
    logger.info("[Controller Layer] Received direct JSON conversion request")
    raw_nodes = len(req.graph_data.get("nodes", []))
    raw_links = len(req.graph_data.get("links", []))
    logger.info(f"[Controller Layer] Input JSON contains {raw_nodes} nodes, {raw_links} links")
    
    result = transform_graph_to_mermaid(
        graph_data=req.graph_data,
        detail_level=req.detail_level,
        max_nodes=req.max_nodes,
        direction=req.direction,
        group_by=req.group_by,
    )
    result["graph_json"] = req.graph_data
    logger.info(f"[Controller Layer] Direct JSON conversion complete: {result['stats']['displayed_nodes']} displayed nodes")
    return result


@app.get("/api/sample")
def get_sample():
    """Provides a sample graph.json and its Mermaid representation for quick testing."""
    logger.info("[Controller Layer] Generating sample demonstration diagram")
    sample_graph = {
        "directed": False,
        "multigraph": False,
        "nodes": [
            {"id": "main_py", "label": "main.py", "_callable": False, "community": 0, "source_file": "main.py"},
            {"id": "app", "label": "FastAPI App", "_callable": False, "community": 0, "source_file": "main.py"},
            {"id": "auth_service", "label": "AuthService", "_callable_class": True, "community": 1, "source_file": "services/auth.py"},
            {"id": "user_model", "label": "User", "_callable_class": True, "community": 1, "source_file": "models/user.py"},
            {"id": "db_session", "label": "get_db()", "_callable": True, "community": 2, "source_file": "db/session.py"},
            {"id": "router_users", "label": "users_router", "_callable": False, "community": 0, "source_file": "routers/users.py"},
        ],
        "links": [
            {"source": "main_py", "target": "app", "relation": "contains"},
            {"source": "main_py", "target": "router_users", "relation": "imports"},
            {"source": "router_users", "target": "auth_service", "relation": "calls"},
            {"source": "auth_service", "target": "user_model", "relation": "calls"},
            {"source": "router_users", "target": "db_session", "relation": "calls"},
        ]
    }
    result = transform_graph_to_mermaid(sample_graph, detail_level="components", max_nodes=50, direction="TD")
    result["graph_json"] = sample_graph
    logger.info("[Controller Layer] Sample demonstration data served successfully")
    return result


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host=host, port=port, reload=True)

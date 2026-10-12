"""
Standalone CLI script to generate graph.json using graphify and convert it to Mermaid.
Usage:
    python generate_diagram.py https://github.com/psf/requests
    python generate_diagram.py ./my-local-code --direction LR --detail overview
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from graph_transformer import transform_graph_to_mermaid


def get_graphify_cmd():
    venv_bin = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
    candidate = venv_bin / ("graphify.exe" if os.name == "nt" else "graphify")
    if candidate.exists():
        return str(candidate)
    system_which = shutil.which("graphify")
    if system_which:
        return system_which
    return f"{sys.executable} -m graphify"


def main():
    parser = argparse.ArgumentParser(description="Generate graph.json and Mermaid diagram from a Git repo or local directory.")
    parser.add_argument("target", help="Git repository URL (e.g. https://github.com/...) or local directory path")
    parser.add_argument("--branch", help="Git branch to clone (if target is a URL)", default=None)
    parser.add_argument("--detail", choices=["overview", "components", "detailed"], default="components", help="Level of detail")
    parser.add_argument("--max-nodes", type=int, default=60, help="Max nodes in diagram")
    parser.add_argument("--direction", choices=["TD", "LR"], default="TD", help="Flowchart layout direction")
    parser.add_argument("--group-by", choices=["community", "file", "none"], default="community", help="Subgraph grouping")
    parser.add_argument("--out-mermaid", default="diagram.mmd", help="Output file path for Mermaid diagram")
    parser.add_argument("--out-json", default="graph.json", help="Output file path for graph.json")
    args = parser.parse_args()

    is_git_url = args.target.startswith(("http://", "https://", "git@"))
    work_dir = None
    is_temp = False

    try:
        if is_git_url:
            print(f"[1/3] Cloning {args.target} (depth=1)...")
            work_dir = tempfile.mkdtemp(prefix="git_diagram_")
            is_temp = True
            cmd = ["git", "clone", "--depth", "1"]
            if args.branch:
                cmd.extend(["--branch", args.branch])
            cmd.extend([args.target, work_dir])
            subprocess.run(cmd, check=True)
        else:
            work_dir = os.path.abspath(args.target)
            if not os.path.exists(work_dir):
                print(f"Error: Target path does not exist: {work_dir}", file=sys.stderr)
                sys.exit(1)

        print(f"[2/3] Extracting code knowledge graph with graphify...")
        graphify_cmd = get_graphify_cmd()
        subprocess.run([graphify_cmd, "extract", work_dir, "--code-only"], check=True)

        graph_json_path = Path(work_dir) / "graphify-out" / "graph.json"
        if not graph_json_path.exists():
            print(f"Error: graphify did not produce {graph_json_path}", file=sys.stderr)
            sys.exit(1)

        with open(graph_json_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)

        print(f"[3/3] Converting graph.json to Mermaid flowchart...")
        result = transform_graph_to_mermaid(
            graph_data=graph_data,
            detail_level=args.detail,
            max_nodes=args.max_nodes,
            direction=args.direction,
            group_by=args.group_by,
        )

        # Save Mermaid
        with open(args.out_mermaid, "w", encoding="utf-8") as f:
            f.write(result["mermaid_code"])

        # Save graph.json
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, indent=2)

        print("\n--- Generation Complete ---")
        stats = result["stats"]
        print(f"Total Nodes: {stats['total_nodes']} | Edges: {stats['total_edges']}")
        print(f"Displayed in Diagram: {stats['displayed_nodes']} nodes, {stats['displayed_edges']} edges")
        print(f"Files: {stats['file_count']} | Communities: {stats['community_count']}")
        print(f"Mermaid file: {os.path.abspath(args.out_mermaid)}")
        print(f"Graph JSON:   {os.path.abspath(args.out_json)}\n")
        print("Mermaid Preview:")
        print("----------------")
        print(result["mermaid_code"])

    finally:
        if is_temp and work_dir and os.path.exists(work_dir):
            def handle_ro(func, path, exc):
                import stat
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(work_dir, onerror=handle_ro)


if __name__ == "__main__":
    main()

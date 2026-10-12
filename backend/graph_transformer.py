"""
Graph Transformer Module
Converts graphify graph.json structure into Mermaid flowchart syntax with rich semantic styling.
"""
import hashlib
import logging
from typing import Dict, Any, List, Set

logger = logging.getLogger("backend.transformer")


def _safe_id(raw_id: str) -> str:
    """Generate a valid, deterministic Mermaid node ID."""
    digest = hashlib.md5(raw_id.encode("utf-8")).hexdigest()[:10]
    return f"n_{digest}"


def _get_node_category(node: Dict[str, Any]) -> str:
    """Determine the semantic styling category of a node."""
    label = node.get("label", node.get("id", ""))
    is_class = node.get("_callable_class", False)
    is_callable = node.get("_callable", False)

    if is_class:
        return "classNode"
    elif is_callable:
        return "funcNode"
    elif label.endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".cpp", ".c", ".h")):
        return "fileNode"
    else:
        return "moduleNode"


def _format_label(node: Dict[str, Any]) -> str:
    """Format and escape a node label with a descriptive visual prefix."""
    label = node.get("label", node.get("id", "Unknown"))
    is_class = node.get("_callable_class", False)
    is_callable = node.get("_callable", False)

    # Prefix badge for visual clarity in Mermaid
    if is_class:
        prefix = "class: "
    elif is_callable:
        prefix = "fn: "
    elif label.endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".cpp", ".c", ".h")):
        prefix = "file: "
    else:
        prefix = ""

    # Sanitize label text for Mermaid
    clean_label = str(label).replace('"', "'").replace("\n", " ").strip()
    if len(clean_label) > 40:
        clean_label = clean_label[:37] + "..."
    return f'"{prefix}{clean_label}"'


def transform_graph_to_mermaid(
    graph_data: Dict[str, Any],
    detail_level: str = "components",
    max_nodes: int = 60,
    direction: str = "TD",
    group_by: str = "community"  # "community", "file", or "none"
) -> Dict[str, Any]:
    """
    Transforms graphify graph.json into Mermaid diagram syntax and metadata stats.

    Args:
        graph_data: Parsed graph.json dictionary containing nodes and links
        detail_level: 'overview', 'components', or 'detailed'
        max_nodes: Maximum number of nodes to render in the diagram
        direction: 'TD' (Top-Down) or 'LR' (Left-to-Right)
        group_by: 'community', 'file', or 'none'

    Returns:
        Dict with 'mermaid_code', 'stats', and 'included_nodes_count'
    """
    raw_nodes = graph_data.get("nodes", [])
    raw_links = graph_data.get("links", [])

    total_nodes = len(raw_nodes)
    total_edges = len(raw_links)
    logger.info(f"[Transformer Layer] Input graph stats: {total_nodes} nodes, {total_edges} edges")

    # Build node lookup and calculate node degrees for importance ranking
    node_map = {n["id"]: n for n in raw_nodes}
    degree_map = {n["id"]: 0 for n in raw_nodes}
    for link in raw_links:
        src = link.get("source")
        tgt = link.get("target")
        if src in degree_map:
            degree_map[src] += 1
        if tgt in degree_map:
            degree_map[tgt] += 1

    # Filter based on detail level
    candidate_node_ids = set()
    for n in raw_nodes:
        nid = n["id"]
        label = n.get("label", "")
        is_class = n.get("_callable_class", False)
        is_callable = n.get("_callable", False)
        is_file = label.endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".cpp", ".c", ".h"))

        if detail_level == "overview":
            if is_file or is_class:
                candidate_node_ids.add(nid)
        elif detail_level == "components":
            if is_file or is_class:
                candidate_node_ids.add(nid)
            elif is_callable and not label.startswith(".__"):
                candidate_node_ids.add(nid)
        else:  # 'detailed'
            candidate_node_ids.add(nid)

    logger.info(f"[Transformer Layer] Candidate nodes after '{detail_level}' filtering: {len(candidate_node_ids)} of {total_nodes}")

    if not candidate_node_ids:
        logger.warning("[Transformer Layer] Detail filter yielded 0 nodes. Falling back to all nodes.")
        candidate_node_ids = set(node_map.keys())

    # Sort candidates by degree descending to pick the most informative nodes
    sorted_candidates = sorted(candidate_node_ids, key=lambda x: degree_map.get(x, 0), reverse=True)
    selected_node_ids: Set[str] = set(sorted_candidates[:max_nodes])
    logger.info(f"[Transformer Layer] Selected top {len(selected_node_ids)} nodes by graph connectivity degree")

    # Filter links where both source and target are selected
    active_links = []
    connected_nodes: Set[str] = set()
    for link in raw_links:
        src = link.get("source")
        tgt = link.get("target")
        if src in selected_node_ids and tgt in selected_node_ids and src != tgt:
            active_links.append(link)
            connected_nodes.add(src)
            connected_nodes.add(tgt)

    logger.info(f"[Transformer Layer] Active edges between selected nodes: {len(active_links)}")

    display_nodes = [node_map[nid] for nid in selected_node_ids if nid in node_map]

    # Collect communities / files for subgraphs
    community_groups: Dict[Any, List[Dict[str, Any]]] = {}
    file_groups: Dict[str, List[Dict[str, Any]]] = {}

    for node in display_nodes:
        comm = node.get("community", 0)
        community_groups.setdefault(comm, []).append(node)

        src_file = node.get("source_file", "Other")
        file_groups.setdefault(src_file, []).append(node)

    logger.info(f"[Transformer Layer] Clustered into {len(community_groups)} communities and {len(file_groups)} files")

    # Build Mermaid syntax
    lines = [f"flowchart {direction}"]

    # Define high-contrast, modern semantic color classes
    # Files: Soft teal/cyan border
    # Classes: Vibrant Indigo/Purple accent
    # Functions: Amber/Orange badge
    # Modules: Emerald Green
    lines.append("    classDef fileNode fill:#1e293b,stroke:#0284c7,stroke-width:2px,color:#f8fafc;")
    lines.append("    classDef classNode fill:#2e1065,stroke:#a855f7,stroke-width:2px,color:#f8fafc;")
    lines.append("    classDef funcNode fill:#3b1d11,stroke:#f97316,stroke-width:2px,color:#f8fafc;")
    lines.append("    classDef moduleNode fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#f8fafc;")
    lines.append("    classDef hubNode fill:#831843,stroke:#ec4899,stroke-width:3px,color:#ffffff,stroke-dasharray: 4 2;")

    # Identify top 3 hub nodes to highlight them visually
    top_hub_ids = set(sorted_candidates[:3])

    # Render nodes, optionally inside subgraphs
    node_classes_applied: Dict[str, str] = {}

    def render_node_line(n: Dict[str, Any], indent: str = "    ") -> str:
        s_id = _safe_id(n["id"])
        lbl = _format_label(n)
        cat = _get_node_category(n)
        if n["id"] in top_hub_ids:
            cat = "hubNode"
        node_classes_applied[s_id] = cat
        return f"{indent}{s_id}[{lbl}]"

    if group_by == "community" and len(community_groups) > 1 and len(community_groups) <= 12:
        for comm_id, nodes_in_comm in community_groups.items():
            lines.append(f"    subgraph Comm_{comm_id} [\"Community {comm_id}\"]")
            for n in nodes_in_comm:
                lines.append(render_node_line(n, indent="        "))
            lines.append("    end")
    elif group_by == "file" and len(file_groups) > 1 and len(file_groups) <= 15:
        idx = 0
        for fname, nodes_in_file in file_groups.items():
            safe_group = f"sg_{idx}"
            idx += 1
            lines.append(f"    subgraph {safe_group} [\"{fname}\"]")
            for n in nodes_in_file:
                lines.append(render_node_line(n, indent="        "))
            lines.append("    end")
    else:
        for n in display_nodes:
            lines.append(render_node_line(n, indent="    "))

    # Apply class styles to nodes
    for s_id, cat in node_classes_applied.items():
        lines.append(f"    class {s_id} {cat}")

    # Render edges
    seen_edges = set()
    for link in active_links:
        src = link["source"]
        tgt = link["target"]
        relation = link.get("relation", "relates")
        edge_key = (src, tgt, relation)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)

        s_src = _safe_id(src)
        s_tgt = _safe_id(tgt)

        if relation == "contains":
            lines.append(f"    {s_src} -.-> {s_tgt}")
        elif relation == "inherits":
            lines.append(f"    {s_src} ==>|inherits| {s_tgt}")
        elif relation in ("calls", "imports", "method"):
            lines.append(f"    {s_src} -->|{relation}| {s_tgt}")
        else:
            lines.append(f"    {s_src} --> {s_tgt}")

    mermaid_code = "\n".join(lines)

    top_nodes = [
        {
            "id": nid,
            "label": node_map[nid].get("label", nid),
            "source_file": node_map[nid].get("source_file", ""),
            "connections": degree_map[nid],
        }
        for nid in sorted(node_map.keys(), key=lambda x: degree_map[x], reverse=True)[:5]
    ]

    unique_files = {n.get("source_file") for n in raw_nodes if n.get("source_file")}

    stats = {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "displayed_nodes": len(display_nodes),
        "displayed_edges": len(seen_edges),
        "file_count": len(unique_files),
        "community_count": len(community_groups),
        "top_connected": top_nodes,
    }

    logger.info(f"[Transformer Layer] Generated colored Mermaid code ({len(lines)} lines) successfully")
    return {
        "mermaid_code": mermaid_code,
        "stats": stats,
    }

import React, { useState, useEffect } from "react";
import {
  GitFork,
  Code2,
  FileJson,
  Play,
  Copy,
  Check,
  AlertCircle,
  Layers,
  Network,
  Share2,
  FolderTree,
} from "lucide-react";
import { MermaidViewer } from "./components/MermaidViewer";

interface Stats {
  total_nodes: number;
  total_edges: number;
  displayed_nodes: number;
  displayed_edges: number;
  file_count: number;
  community_count: number;
  top_connected: Array<{
    id: string;
    label: string;
    source_file: string;
    connections: number;
  }>;
}

interface ApiResponse {
  mermaid_code: string;
  stats: Stats;
  graph_json: any;
  repo_url?: string;
  is_local?: boolean;
}

const PRESET_REPOS = [
  { name: "Requests (Python)", url: "https://github.com/psf/requests" },
  { name: "FastAPI Sample", url: "https://github.com/tiangolo/fastapi" },
  { name: "Click CLI", url: "https://github.com/pallets/click" },
];

export const App: React.FC = () => {
  const [repoUrl, setRepoUrl] = useState<string>("");
  const [envLocalDir, setEnvLocalDir] = useState<string>("");
  const [branch, setBranch] = useState<string>("");
  const [detailLevel, setDetailLevel] = useState<"overview" | "components" | "detailed">("components");
  const [direction, setDirection] = useState<"TD" | "LR">("TD");
  const [groupBy, setGroupBy] = useState<"community" | "file" | "none">("community");
  const [maxNodes, setMaxNodes] = useState<number>(45);

  const [loading, setLoading] = useState<boolean>(false);
  const [loadingStep, setLoadingStep] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const [result, setResult] = useState<ApiResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"diagram" | "code" | "json">("diagram");
  const [copied, setCopied] = useState<boolean>(false);

  // Fetch initial config from backend (.env LOCAL_CODE_DIR)
  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/config")
      .then((res) => res.json())
      .then((data) => {
        if (data.local_code_dir) {
          setEnvLocalDir(data.local_code_dir);
          setRepoUrl(data.local_code_dir);
        } else {
          setRepoUrl("https://github.com/psf/requests");
        }
        if (data.default_detail_level) setDetailLevel(data.default_detail_level);
        if (data.default_max_nodes) setMaxNodes(data.default_max_nodes);
        if (data.default_direction) setDirection(data.default_direction);
        if (data.default_group_by) setGroupBy(data.default_group_by);
      })
      .catch((err) => {
        console.warn("Could not fetch backend config:", err);
        setRepoUrl("https://github.com/psf/requests");
      });
  }, []);

  const handleGenerate = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!repoUrl.trim() && !envLocalDir) return;

    setLoading(true);
    setError(null);
    setLoadingStep("Analyzing target repository...");

    try {
      const stepTimer = setTimeout(() => {
        setLoadingStep("Running Graphify AST analysis & building knowledge graph...");
      }, 3000);

      const res = await fetch("http://127.0.0.1:8000/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: repoUrl.trim() || undefined,
          branch: branch.trim() || undefined,
          detail_level: detailLevel,
          direction: direction,
          group_by: groupBy,
          max_nodes: maxNodes,
        }),
      });

      clearTimeout(stepTimer);

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server error: ${res.statusText}`);
      }

      const data: ApiResponse = await res.json();
      setResult(data);
      setActiveTab("diagram");
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "Failed to generate diagram. Please check the repository target and try again.");
    } finally {
      setLoading(false);
      setLoadingStep("");
    }
  };

  const handleLoadSample = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/sample");
      if (!res.ok) throw new Error("Could not load sample data.");
      const data: ApiResponse = await res.json();
      setResult(data);
      setActiveTab("diagram");
    } catch (err: any) {
      setError("Failed to connect to backend server. Make sure the FastAPI backend is running on port 8000.");
    } finally {
      setLoading(false);
    }
  };

  const handleCopyCode = () => {
    if (!result?.mermaid_code) return;
    navigator.clipboard.writeText(result.mermaid_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadJson = () => {
    if (!result?.graph_json) return;
    const blob = new Blob([JSON.stringify(result.graph_json, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "graph.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="container">
      {/* Header */}
      <header className="header">
        <div className="brand">
          <div className="brand-icon">
            <Share2 size={24} />
          </div>
          <div>
            <h1>Git Diagram Generator</h1>
            <p className="brand-tagline">
              Extract code structure to <code>graph.json</code> with Graphify & visualize in Mermaid
            </p>
          </div>
        </div>

        <div className="header-badges">
          <span className="badge">
            <Layers size={13} /> AST Powered
          </span>
          <span className="badge">
            <Network size={13} /> Graphify Engine
          </span>
        </div>
      </header>

      {/* Input & Configuration Card */}
      <section className="control-card">
        <form onSubmit={handleGenerate} className="form-grid">
          <div className="option-group">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <label className="option-label">Target Repository (Git URL or Local Directory)</label>
              {envLocalDir && (
                <button
                  type="button"
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "#38bdf8",
                    cursor: "pointer",
                    fontSize: "0.75rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                  onClick={() => setRepoUrl(envLocalDir)}
                >
                  <FolderTree size={12} />
                  <span>Use .env Local Dir: {envLocalDir.length > 35 ? envLocalDir.slice(0, 32) + "..." : envLocalDir}</span>
                </button>
              )}
            </div>

            <div className="input-row">
              <div className="url-input-wrapper">
                <GitFork size={18} />
                <input
                  type="text"
                  className="url-input"
                  placeholder="https://github.com/owner/repository OR C:\path\to\local\code"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  disabled={loading}
                />
              </div>

              <button
                type="submit"
                className="btn-primary"
                disabled={loading || (!repoUrl.trim() && !envLocalDir)}
              >
                {loading ? <div className="spinner" style={{ width: 18, height: 18 }} /> : <Play size={16} />}
                <span>Generate Diagram</span>
              </button>

              <button
                type="button"
                className="btn-secondary"
                onClick={handleLoadSample}
                disabled={loading}
                title="Quickly test with sample architecture without cloning"
              >
                Quick Demo
              </button>
            </div>
          </div>

          {/* Quick preset links */}
          <div className="quick-samples">
            <span>Quick presets:</span>
            {envLocalDir && (
              <button
                type="button"
                className="sample-pill"
                style={{ borderColor: "#38bdf8", color: "#38bdf8" }}
                onClick={() => setRepoUrl(envLocalDir)}
              >
                📁 Local Workspace (.env)
              </button>
            )}
            {PRESET_REPOS.map((sample) => (
              <button
                key={sample.name}
                type="button"
                className="sample-pill"
                onClick={() => setRepoUrl(sample.url)}
              >
                {sample.name}
              </button>
            ))}
          </div>

          {/* Options Grid */}
          <div className="options-row">
            <div className="option-group">
              <label className="option-label">Detail Level</label>
              <select
                className="select-input"
                value={detailLevel}
                onChange={(e: any) => setDetailLevel(e.target.value)}
                disabled={loading}
              >
                <option value="overview">Overview (Files & Classes)</option>
                <option value="components">Components (Classes & Functions)</option>
                <option value="detailed">Detailed (Full AST Symbols)</option>
              </select>
            </div>

            <div className="option-group">
              <label className="option-label">Grouping</label>
              <select
                className="select-input"
                value={groupBy}
                onChange={(e: any) => setGroupBy(e.target.value)}
                disabled={loading}
              >
                <option value="community">By Subsystem Community</option>
                <option value="file">By Source File</option>
                <option value="none">Flat (No Subgraphs)</option>
              </select>
            </div>

            <div className="option-group">
              <label className="option-label">Layout Direction</label>
              <select
                className="select-input"
                value={direction}
                onChange={(e: any) => setDirection(e.target.value)}
                disabled={loading}
              >
                <option value="TD">Top to Bottom (TD)</option>
                <option value="LR">Left to Right (LR)</option>
              </select>
            </div>

            <div className="option-group">
              <label className="option-label">Branch (Optional)</label>
              <input
                type="text"
                className="text-input"
                placeholder="main / master"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                disabled={loading}
              />
            </div>

            <div className="option-group">
              <label className="option-label">
                Max Nodes: {maxNodes}
              </label>
              <input
                type="range"
                min={15}
                max={100}
                step={5}
                value={maxNodes}
                onChange={(e) => setMaxNodes(Number(e.target.value))}
                disabled={loading}
                style={{ accentColor: "#38bdf8", marginTop: 8 }}
              />
            </div>
          </div>
        </form>
      </section>

      {/* Error Alert */}
      {error && (
        <div className="error-banner">
          <AlertCircle size={20} />
          <div>
            <strong>Error: </strong>
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="loading-container">
          <div className="spinner" />
          <p style={{ fontWeight: 600, color: "#f8fafc" }}>Processing Repository...</p>
          <p style={{ fontSize: "0.85rem", color: "#94a3b8" }}>{loadingStep}</p>
        </div>
      )}

      {/* Results Viewport */}
      {!loading && result && (
        <div>
          {/* Stats Metrics */}
          <div className="stats-grid">
            <div className="stat-card">
              <span className="stat-label">Total Nodes</span>
              <span className="stat-value">{result.stats.total_nodes}</span>
              <span className="stat-sub">{result.stats.displayed_nodes} in diagram</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Total Relations</span>
              <span className="stat-value">{result.stats.total_edges}</span>
              <span className="stat-sub">{result.stats.displayed_edges} in diagram</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Source Files</span>
              <span className="stat-value">{result.stats.file_count}</span>
              <span className="stat-sub">Parsed AST</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Communities</span>
              <span className="stat-value">{result.stats.community_count}</span>
              <span className="stat-sub">Leiden clusters</span>
            </div>
          </div>

          {/* Viewer Card */}
          <div className="results-card">
            {/* Tabs Header */}
            <div className="tabs-header">
              <div className="tabs-group">
                <button
                  className={`tab-btn ${activeTab === "diagram" ? "active" : ""}`}
                  onClick={() => setActiveTab("diagram")}
                >
                  <Share2 size={15} />
                  <span>Mermaid Diagram</span>
                </button>
                <button
                  className={`tab-btn ${activeTab === "code" ? "active" : ""}`}
                  onClick={() => setActiveTab("code")}
                >
                  <Code2 size={15} />
                  <span>Mermaid Code</span>
                </button>
                <button
                  className={`tab-btn ${activeTab === "json" ? "active" : ""}`}
                  onClick={() => setActiveTab("json")}
                >
                  <FileJson size={15} />
                  <span>graph.json</span>
                </button>
              </div>

              <div className="tab-actions">
                {activeTab === "code" && (
                  <button className="tool-btn" onClick={handleCopyCode}>
                    {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
                    <span>{copied ? "Copied!" : "Copy Mermaid"}</span>
                  </button>
                )}
                {activeTab === "json" && (
                  <button className="tool-btn" onClick={handleDownloadJson}>
                    <FileJson size={14} />
                    <span>Download graph.json</span>
                  </button>
                )}
              </div>
            </div>

            {/* Tab Contents */}
            <div className="viewer-content">
              {activeTab === "diagram" && (
                <MermaidViewer code={result.mermaid_code} />
              )}

              {activeTab === "code" && (
                <pre className="code-container">
                  <code>{result.mermaid_code}</code>
                </pre>
              )}

              {activeTab === "json" && (
                <pre className="code-container">
                  <code>{JSON.stringify(result.graph_json, null, 2)}</code>
                </pre>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && !result && !error && (
        <div className="empty-state">
          <Network size={54} strokeWidth={1.4} />
          <h3>No diagram generated yet</h3>
          <p style={{ maxWidth: 460, fontSize: "0.9rem" }}>
            Enter a Git repository URL or local folder directory above and click <strong>Generate Diagram</strong>, or select <strong>Local Workspace (.env)</strong> to scan your current code.
          </p>
        </div>
      )}
    </div>
  );
};

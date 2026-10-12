import React, { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";
import { ZoomIn, ZoomOut, RotateCcw, Download } from "lucide-react";

mermaid.initialize({
  startOnLoad: false,
  theme: "base",
  securityLevel: "loose",
  flowchart: {
    useMaxWidth: false,
    htmlLabels: true,
    curve: "basis",
  },
  themeVariables: {
    darkMode: true,
    background: "#090d16",
    mainBkg: "#1e293b",
    textColor: "#f8fafc",
    lineColor: "#64748b",
    clusterBkg: "#111827",
    clusterBorder: "#374151",
    defaultLinkColor: "#64748b",
    titleColor: "#e2e8f0",
    edgeLabelBackground: "#0f172a",
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif",
  },
});

interface MermaidViewerProps {
  code: string;
}

export const MermaidViewer: React.FC<MermaidViewerProps> = ({ code }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState<string>("");
  const [renderError, setRenderError] = useState<string | null>(null);
  const [scale, setScale] = useState<number>(1);
  const [position, setPosition] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  useEffect(() => {
    let isMounted = true;
    const renderDiagram = async () => {
      if (!code.trim()) {
        setSvgContent("");
        return;
      }
      try {
        setRenderError(null);
        const id = `mermaid_${Date.now()}`;
        const { svg } = await mermaid.render(id, code);
        if (isMounted) {
          setSvgContent(svg);
          setScale(1);
          setPosition({ x: 0, y: 0 });
        }
      } catch (err: any) {
        if (isMounted) {
          console.error("Mermaid Render Error:", err);
          setRenderError(err?.message || "Failed to render Mermaid diagram.");
        }
      }
    };

    renderDiagram();
    return () => {
      isMounted = false;
    };
  }, [code]);

  const handleZoomIn = () => setScale((prev) => Math.min(prev + 0.2, 3.5));
  const handleZoomOut = () => setScale((prev) => Math.max(prev - 0.2, 0.3));
  const handleResetZoom = () => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX - position.x, y: e.clientY - position.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPosition({
      x: e.clientX - dragStartRef.current.x,
      y: e.clientY - dragStartRef.current.y,
    });
  };

  const handleMouseUp = () => setIsDragging(false);

  const handleDownloadSvg = () => {
    if (!svgContent) return;
    const blob = new Blob([svgContent], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `diagram_${Date.now()}.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  if (renderError) {
    return (
      <div style={{ padding: "40px", color: "#fca5a5", textAlign: "center" }}>
        <p style={{ fontWeight: 600, marginBottom: "8px" }}>Mermaid Syntax / Render Error</p>
        <p style={{ fontSize: "0.85rem", color: "#94a3b8" }}>{renderError}</p>
      </div>
    );
  }

  return (
    <div style={{ position: "relative", width: "100%", height: "100%", overflow: "hidden" }}>
      {/* Visual Color Legend Bar */}
      <div
        style={{
          position: "absolute",
          top: "14px",
          left: "14px",
          display: "flex",
          alignItems: "center",
          gap: "12px",
          zIndex: 10,
          background: "rgba(15, 23, 42, 0.85)",
          backdropFilter: "blur(8px)",
          border: "1px solid #334155",
          borderRadius: "8px",
          padding: "6px 14px",
          fontSize: "0.76rem",
          color: "#94a3b8",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#ec4899", border: "1px solid #f472b6" }} />
          <span>Core Hub</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: "#a855f7" }} />
          <span>Class</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: "#f97316" }} />
          <span>Function</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: "#0284c7" }} />
          <span>File</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: "#10b981" }} />
          <span>Module</span>
        </div>
      </div>

      {/* Floating Canvas Controls */}
      <div
        style={{
          position: "absolute",
          top: "14px",
          right: "14px",
          display: "flex",
          gap: "6px",
          zIndex: 10,
          background: "rgba(15, 23, 42, 0.85)",
          backdropFilter: "blur(8px)",
          border: "1px solid #334155",
          borderRadius: "8px",
          padding: "4px",
        }}
      >
        <button
          onClick={handleZoomIn}
          title="Zoom In"
          className="tool-btn"
          style={{ padding: "5px 8px" }}
        >
          <ZoomIn size={15} />
        </button>
        <button
          onClick={handleZoomOut}
          title="Zoom Out"
          className="tool-btn"
          style={{ padding: "5px 8px" }}
        >
          <ZoomOut size={15} />
        </button>
        <button
          onClick={handleResetZoom}
          title="Reset View"
          className="tool-btn"
          style={{ padding: "5px 8px" }}
        >
          <RotateCcw size={15} />
          <span style={{ fontSize: "0.75rem" }}>{Math.round(scale * 100)}%</span>
        </button>
        <button
          onClick={handleDownloadSvg}
          title="Export SVG"
          className="tool-btn"
          style={{ padding: "5px 8px" }}
        >
          <Download size={15} />
        </button>
      </div>

      {/* Interactive Diagram Canvas */}
      <div
        ref={containerRef}
        className="diagram-viewport"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{
          cursor: isDragging ? "grabbing" : "grab",
          userSelect: "none",
          transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
          transformOrigin: "center center",
          transition: isDragging ? "none" : "transform 0.1s ease-out",
        }}
        dangerouslySetInnerHTML={{ __html: svgContent }}
      />
    </div>
  );
};

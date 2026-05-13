"use client";

import { useState } from "react";
import Editor, { DiffEditor, useMonaco } from "@monaco-editor/react";
import type { PromptVersion } from "@/lib/types";

// Setup Monaco Theme on mount
function useMonacoTheme() {
  const monaco = useMonaco();
  if (monaco) {
    monaco.editor.defineTheme("void-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "keyword", foreground: "00D4C8", fontStyle: "bold" },
        { token: "string", foreground: "F5A623" },
        { token: "variable", foreground: "4C9EFF" },
        { token: "comment", foreground: "4A5568", fontStyle: "italic" },
      ],
      colors: {
        "editor.background": "#080B0F",
        "editor.foreground": "#C8D4E0",
        "editor.lineHighlightBackground": "#171F2A",
        "editorLineNumber.foreground": "#4A5568",
        "editorIndentGuide.background": "#171F2A",
        "editor.selectionBackground": "#00D4C840",
      },
    });
  }
}

// ── Diff Viewer ───────────────────────────────────────────────────────────────

interface VersionDiffProps {
  versionA: PromptVersion;
  versionB: PromptVersion;
}

export function VersionDiff({ versionA, versionB }: VersionDiffProps) {
  // Rather than calling the backend /diff endpoint which returns unified diff strings,
  // we can just use Monaco's built in DiffEditor if we have the raw templates.
  // We'll assume versionA and versionB both have populated `templates` dictionaries.
  useMonacoTheme();

  const [selectedKey, setSelectedKey] = useState<string>(
    Object.keys(versionA.templates ?? {})[0] ?? ""
  );

  const keysA = Object.keys(versionA.templates ?? {});
  const keysB = Object.keys(versionB.templates ?? {});
  const allKeys = Array.from(new Set([...keysA, ...keysB])).sort();

  return (
    <div className="flex gap-4 h-[600px] animate-fade-in">
      {/* Key List */}
      <div
        className="w-48 shrink-0 flex flex-col rounded-xl overflow-hidden"
        style={{ background: "rgba(12,16,23,0.7)", border: "1px solid rgba(255,255,255,0.07)" }}
      >
        <div className="px-3 py-2 text-[9px] font-mono uppercase tracking-[0.15em]" style={{ color: "#4A5568", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
          Templates
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {allKeys.map((key) => {
            const inA = keysA.includes(key);
            const inB = keysB.includes(key);
            const isSelected = key === selectedKey;
            return (
              <button
                key={key}
                onClick={() => setSelectedKey(key)}
                className="w-full flex items-center justify-between px-2.5 py-2 text-left text-xs font-mono rounded-lg transition-all"
                style={{
                  background: isSelected ? "rgba(255,255,255,0.05)" : "transparent",
                  color: isSelected ? "#F0F4F8" : "#8B9BB4",
                }}
              >
                <span className="truncate">{key}</span>
                {!inA && <span className="text-[9px] text-[#00E676]">+</span>}
                {!inB && <span className="text-[9px] text-[#FF4545]">-</span>}
              </button>
            );
          })}
        </div>
      </div>

      {/* Editor */}
      <div
        className="flex-1 rounded-xl overflow-hidden"
        style={{ border: "1px solid rgba(255,255,255,0.07)", background: "#080B0F" }}
      >
        <div className="flex items-center justify-between px-4 py-2" style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", background: "rgba(12,16,23,0.9)" }}>
          <span className="text-[10px] font-mono text-[#F5A623]">{versionA.version_id}</span>
          <span className="text-[10px] font-mono text-[#4A5568]">→</span>
          <span className="text-[10px] font-mono text-[#00D4C8]">{versionB.version_id}</span>
        </div>
        <DiffEditor
          height="100%"
          language="markdown"
          theme="void-dark"
          original={versionA.templates?.[selectedKey] ?? ""}
          modified={versionB.templates?.[selectedKey] ?? ""}
          options={{
            readOnly: true,
            minimap: { enabled: false },
            wordWrap: "on",
            fontSize: 13,
            fontFamily: "JetBrains Mono, monospace",
            renderLineHighlight: "none",
          }}
        />
      </div>
    </div>
  );
}

// ── Single Prompt Editor ──────────────────────────────────────────────────────

interface PromptEditorProps {
  templates: Record<string, string>;
  onChange: (templates: Record<string, string>) => void;
  readOnly?: boolean;
}

export function PromptEditor({ templates, onChange, readOnly = false }: PromptEditorProps) {
  useMonacoTheme();
  const keys = Object.keys(templates);
  const [selectedKey, setSelectedKey] = useState(keys[0] ?? "");

  const handleEditorChange = (value: string | undefined) => {
    if (value !== undefined) {
      onChange({ ...templates, [selectedKey]: value });
    }
  };

  return (
    <div className="flex gap-4 h-[600px] animate-fade-in">
      {/* File Explorer style sidebar */}
      <div
        className="w-48 shrink-0 flex flex-col rounded-xl overflow-hidden"
        style={{ background: "rgba(12,16,23,0.7)", border: "1px solid rgba(255,255,255,0.07)" }}
      >
        <div className="px-3 py-2 text-[9px] font-mono uppercase tracking-[0.15em]" style={{ color: "#4A5568", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
          Templates
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {keys.map((key) => {
            const isSelected = key === selectedKey;
            return (
              <button
                key={key}
                onClick={() => setSelectedKey(key)}
                className="w-full flex items-center gap-2 px-2.5 py-2 text-left text-xs font-mono rounded-lg transition-all"
                style={{
                  background: isSelected ? "rgba(0,212,200,0.1)" : "transparent",
                  color: isSelected ? "#00D4C8" : "#8B9BB4",
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
                </svg>
                <span className="truncate">{key}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Monaco Editor Wrapper */}
      <div
        className="flex-1 flex flex-col rounded-xl overflow-hidden"
        style={{ border: "1px solid rgba(255,255,255,0.07)", background: "#080B0F" }}
      >
        <div className="flex items-center px-4 py-2" style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", background: "rgba(12,16,23,0.9)" }}>
          <span className="text-[11px] font-mono" style={{ color: "#8B9BB4" }}>
            {selectedKey}
          </span>
        </div>
        <div className="flex-1">
          <Editor
            language="markdown"
            theme="void-dark"
            value={templates[selectedKey] ?? ""}
            onChange={handleEditorChange}
            options={{
              readOnly,
              minimap: { enabled: false },
              wordWrap: "on",
              fontSize: 13,
              fontFamily: "JetBrains Mono, monospace",
              padding: { top: 16, bottom: 16 },
              cursorBlinking: "smooth",
              cursorSmoothCaretAnimation: "on",
              formatOnType: true,
            }}
          />
        </div>
      </div>
    </div>
  );
}

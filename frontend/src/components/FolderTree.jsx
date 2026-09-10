import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";

const lsGet = (k, d) => {
  try {
    const v = localStorage.getItem(k);
    return v === null ? d : v;
  } catch {
    return d;
  }
};
const lsSet = (k, v) => {
  try {
    localStorage.setItem(k, v);
  } catch {}
};

export default function FolderTree({ selected, onSelect, reloadKey }) {
  const [tree, setTree] = useState(null);
  const [open, setOpen] = useState(lsGet("folderTreeOpen", "1") === "1");
  const [expanded, setExpanded] = useState(() => new Set());

  useEffect(() => {
    api.folders().then(setTree).catch(() => setTree([]));
  }, [reloadKey]);

  // auto-expand the path to the current selection
  useEffect(() => {
    if (!selected) return;
    setExpanded((e) => {
      const n = new Set(e);
      const parts = selected.split("\\");
      let acc = "";
      for (const p of parts) {
        acc = acc ? `${acc}\\${p}` : p;
        n.add(acc);
      }
      return n;
    });
  }, [selected]);

  const total = useMemo(
    () => (tree || []).reduce((s, n) => s + n.count, 0),
    [tree]
  );

  const toggleOpen = () => {
    const n = !open;
    setOpen(n);
    lsSet("folderTreeOpen", n ? "1" : "0");
  };

  const toggleNode = (path) =>
    setExpanded((e) => {
      const n = new Set(e);
      n.has(path) ? n.delete(path) : n.add(path);
      return n;
    });

  return (
    <div className="tree">
      <div className="tree-head">
        <button className="tree-toggle" onClick={toggleOpen} title="Show/hide folders">
          {open ? "▾" : "▸"} Folders
        </button>
        {selected && (
          <span className="chip active" onClick={() => onSelect(undefined)} title="clear folder filter">
            {selected.split("\\").pop()} ✕
          </span>
        )}
      </div>

      {open && (
        <div className="tree-body">
          {tree === null && <div className="muted">loading…</div>}
          {tree?.length === 0 && <div className="muted">No folders indexed.</div>}
          {tree?.length > 0 && (
            <div
              className={"tree-row" + (!selected ? " sel" : "")}
              onClick={() => onSelect(undefined)}
            >
              <span className="tree-caret" />
              <span className="tree-label">All folders <span className="muted">{total}</span></span>
            </div>
          )}
          {(tree || []).map((n) => (
            <TreeNode
              key={n.path}
              node={n}
              depth={0}
              expanded={expanded}
              onToggle={toggleNode}
              selected={selected}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function TreeNode({ node, depth, expanded, onToggle, selected, onSelect }) {
  const hasKids = node.children?.length > 0;
  const isOpen = expanded.has(node.path);
  const isSel = selected === node.path;
  return (
    <div>
      <div
        className={"tree-row" + (isSel ? " sel" : "")}
        style={{ paddingLeft: 4 + depth * 13 }}
      >
        <span
          className="tree-caret"
          onClick={() => hasKids && onToggle(node.path)}
        >
          {hasKids ? (isOpen ? "▾" : "▸") : ""}
        </span>
        <span
          className="tree-label"
          onClick={() => onSelect(isSel ? undefined : node.path)}
          title={node.path}
        >
          {node.name} <span className="muted">{node.count}</span>
        </span>
      </div>
      {isOpen &&
        node.children.map((c) => (
          <TreeNode
            key={c.path}
            node={c}
            depth={depth + 1}
            expanded={expanded}
            onToggle={onToggle}
            selected={selected}
            onSelect={onSelect}
          />
        ))}
    </div>
  );
}

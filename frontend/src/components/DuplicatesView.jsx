import { useEffect, useState } from "react";
import { api, humanBytes, thumbUrl } from "../api.js";
import { useToast } from "../App.jsx";

const PAGE_SIZE = 50;

export default function DuplicatesView() {
  const notify = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [keep, setKeep] = useState({}); // groupKey -> photoId
  const [filterKind, setFilterKind] = useState("all");
  const [page, setPage] = useState(1);

  const groupKey = (g) => g.photos.map((p) => p.id).sort((a, b) => a - b).join("-");
  const getKeepId = (g) => keep[groupKey(g)] ?? g.suggested_keep;
  const setKeepId = (g, photoId) =>
    setKeep((prev) => ({ ...prev, [groupKey(g)]: photoId }));

  const load = () => {
    setLoading(true);
    setError(null);
    api
      .duplicates()
      .then((d) => {
        setData(d);
        setError(null);
        setPage(1);
      })
      .catch((e) => {
        setError(e.message || "Failed to load duplicates");
        notify(e.message);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  if (loading) return <div className="content">Scanning for duplicates…</div>;
  if (error) {
    return (
      <div className="content">
        <div className="card" style={{ textAlign: "center", padding: 32 }}>
          <p style={{ color: "var(--danger, #f43f5e)", marginBottom: 16 }}>
            Failed to load: {error}
          </p>
          <button className="primary" onClick={load}>
            Retry
          </button>
        </div>
      </div>
    );
  }
  if (!data) return <div className="content">No duplicates data.</div>;

  const resolveGroup = async (g) => {
    const keepId = getKeepId(g);
    const remove = g.photos.map((p) => p.id).filter((id) => id !== keepId);
    if (!remove.length) return;
    if (!confirm(`Keep 1, move ${remove.length} to Recycle Bin?`)) return;
    try {
      setBusy(true);
      await api.resolveDup(keepId, remove);
      notify(`Resolved — ${remove.length} removed`);
      const key = groupKey(g);
      setData((d) => ({
        ...d,
        groups: d.groups.filter((grp) => groupKey(grp) !== key),
        group_count: Math.max(0, d.group_count - 1),
        reclaimable_bytes: Math.max(0, d.reclaimable_bytes - g.wasted_bytes),
      }));
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };

  const ignoreGroup = async (g) => {
    try {
      setBusy(true);
      for (let i = 0; i < g.photos.length; i++) {
        for (let j = i + 1; j < g.photos.length; j++) {
          await api.ignoreDup(g.photos[i].id, g.photos[j].id);
        }
      }
      const key = groupKey(g);
      setData((d) => ({
        ...d,
        groups: d.groups.filter((grp) => groupKey(grp) !== key),
        group_count: Math.max(0, d.group_count - 1),
        reclaimable_bytes: Math.max(0, d.reclaimable_bytes - g.wasted_bytes),
      }));
      notify("Marked as not duplicate");
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };

  const autoResolve = async (kinds) => {
    if (!confirm(`Auto-resolve all ${kinds.join(" & ")} groups (keep best, bin the rest)?`))
      return;
    try {
      setBusy(true);
      const r = await api.autoResolveDup(kinds);
      notify(`Removed ${r.removed.length} file(s)`);
      load();
    } catch (e) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };

  const filteredGroups = data.groups.filter((g) =>
    filterKind === "all" ? true : g.kind === filterKind
  );
  const totalPages = Math.max(1, Math.ceil(filteredGroups.length / PAGE_SIZE));
  const currentPage = Math.min(Math.max(1, page), totalPages);
  const pageGroups = filteredGroups.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  );

  return (
    <div className="content">
      <div className="card">
        <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
          <b>{data.group_count}</b> duplicate group(s) ·{" "}
          <b>{humanBytes(data.reclaimable_bytes)}</b> reclaimable
          <div className="spacer" />
          <div className="row" style={{ gap: 4 }}>
            <button
              className={filterKind === "all" ? "primary" : ""}
              onClick={() => {
                setFilterKind("all");
                setPage(1);
              }}
            >
              All ({data.groups.length})
            </button>
            <button
              className={filterKind === "exact" ? "primary" : ""}
              onClick={() => {
                setFilterKind("exact");
                setPage(1);
              }}
            >
              Exact ({data.groups.filter((g) => g.kind === "exact").length})
            </button>
            <button
              className={filterKind === "near" ? "primary" : ""}
              onClick={() => {
                setFilterKind("near");
                setPage(1);
              }}
            >
              Near ({data.groups.filter((g) => g.kind === "near").length})
            </button>
          </div>
          <div className="spacer" />
          <button disabled={busy} onClick={() => autoResolve(["exact"])}>
            Auto-resolve exact
          </button>
          <button disabled={busy} onClick={() => autoResolve(["exact", "near"])}>
            Auto-resolve all
          </button>
          <button disabled={busy} onClick={load}>
            Refresh
          </button>
        </div>
      </div>

      {totalPages > 1 && (
        <div className="row" style={{ justifyContent: "center", gap: 12, margin: "12px 0" }}>
          <button
            disabled={currentPage <= 1 || busy}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            ← Previous
          </button>
          <span>
            Page {currentPage} of {totalPages} ({filteredGroups.length} groups)
          </span>
          <button
            disabled={currentPage >= totalPages || busy}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            Next →
          </button>
        </div>
      )}

      {pageGroups.map((g) => {
        const key = groupKey(g);
        const currentKeep = getKeepId(g);
        return (
          <div className="card" key={key}>
            <div className="row" style={{ marginBottom: 8 }}>
              <span className="pill">{g.kind}</span>
              <span className="muted">{g.photos.length} copies</span>
              <span className="muted">wastes {humanBytes(g.wasted_bytes)}</span>
              <div className="spacer" />
              <button disabled={busy} onClick={() => ignoreGroup(g)}>
                Not a duplicate
              </button>
              <button
                disabled={busy}
                className="primary"
                onClick={() => resolveGroup(g)}
              >
                Keep selected, bin rest
              </button>
            </div>
            <div className="dup-group">
              {g.photos.map((p) => (
                <div
                  key={p.id}
                  className={"dup-photo" + (currentKeep === p.id ? " keep" : "")}
                  onClick={() => setKeepId(g, p.id)}
                >
                  <img src={thumbUrl(p.id)} alt={p.filename} />
                  <div>
                    <small>
                      {currentKeep === p.id ? "✓ keep · " : ""}
                      {p.width}×{p.height} · {humanBytes(p.size_bytes)}
                    </small>
                    <br />
                    <small className="muted">{p.rel_path}</small>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}

      {totalPages > 1 && (
        <div className="row" style={{ justifyContent: "center", gap: 12, margin: "12px 0" }}>
          <button
            disabled={currentPage <= 1 || busy}
            onClick={() => {
              setPage((p) => Math.max(1, p - 1));
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          >
            ← Previous
          </button>
          <span>
            Page {currentPage} of {totalPages}
          </span>
          <button
            disabled={currentPage >= totalPages || busy}
            onClick={() => {
              setPage((p) => Math.min(totalPages, p + 1));
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          >
            Next →
          </button>
        </div>
      )}

      {filteredGroups.length === 0 && (
        <p className="muted" style={{ textAlign: "center", padding: 24 }}>
          No duplicates found. 🎉
        </p>
      )}
    </div>
  );
}

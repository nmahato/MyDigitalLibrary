import { useEffect, useState } from "react";
import { api, humanBytes, thumbUrl } from "../api.js";
import { useToast } from "../App.jsx";

export default function DuplicatesView() {
  const notify = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [keep, setKeep] = useState({}); // groupIdx -> photoId

  const load = () => {
    setLoading(true);
    api
      .duplicates()
      .then((d) => {
        setData(d);
        const k = {};
        d.groups.forEach((g, i) => (k[i] = g.suggested_keep));
        setKeep(k);
      })
      .catch((e) => notify(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  if (loading) return <div className="content">Scanning for duplicates…</div>;
  if (!data) return <div className="content">Failed to load.</div>;

  const resolveGroup = async (g, i) => {
    const keepId = keep[i];
    const remove = g.photos.map((p) => p.id).filter((id) => id !== keepId);
    if (!remove.length) return;
    if (!confirm(`Keep 1, move ${remove.length} to Recycle Bin?`)) return;
    await api.resolveDup(keepId, remove);
    notify(`Resolved — ${remove.length} removed`);
    setData((d) => ({ ...d, groups: d.groups.filter((_, idx) => idx !== i) }));
  };

  const autoResolve = async (kinds) => {
    if (!confirm(`Auto-resolve all ${kinds.join(" & ")} groups (keep best, bin the rest)?`))
      return;
    const r = await api.autoResolveDup(kinds);
    notify(`Removed ${r.removed.length} file(s)`);
    load();
  };

  return (
    <div className="content">
      <div className="card">
        <div className="row">
          <b>{data.group_count}</b> duplicate group(s) ·{" "}
          <b>{humanBytes(data.reclaimable_bytes)}</b> reclaimable
          <div className="spacer" />
          <button onClick={() => autoResolve(["exact"])}>Auto-resolve exact</button>
          <button onClick={() => autoResolve(["exact", "near"])}>
            Auto-resolve all
          </button>
          <button onClick={load}>Refresh</button>
        </div>
      </div>

      {data.groups.map((g, i) => (
        <div className="card" key={i}>
          <div className="row" style={{ marginBottom: 8 }}>
            <span className={"pill"}>{g.kind}</span>
            <span className="muted">{g.photos.length} copies</span>
            <span className="muted">wastes {humanBytes(g.wasted_bytes)}</span>
            <div className="spacer" />
            <button
              onClick={() =>
                api
                  .ignoreDup(g.photos[0].id, g.photos[1].id)
                  .then(() =>
                    setData((d) => ({
                      ...d,
                      groups: d.groups.filter((_, idx) => idx !== i),
                    }))
                  )
              }
            >
              Not a duplicate
            </button>
            <button className="primary" onClick={() => resolveGroup(g, i)}>
              Keep selected, bin rest
            </button>
          </div>
          <div className="dup-group">
            {g.photos.map((p) => (
              <div
                key={p.id}
                className={"dup-photo" + (keep[i] === p.id ? " keep" : "")}
                onClick={() => setKeep((k) => ({ ...k, [i]: p.id }))}
              >
                <img src={thumbUrl(p.id)} alt={p.filename} />
                <div>
                  <small>
                    {keep[i] === p.id ? "✓ keep · " : ""}
                    {p.width}×{p.height} · {humanBytes(p.size_bytes)}
                  </small>
                  <br />
                  <small className="muted">{p.rel_path}</small>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {data.groups.length === 0 && <p className="muted">No duplicates. 🎉</p>}
    </div>
  );
}

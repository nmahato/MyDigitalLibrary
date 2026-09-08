import { useEffect, useRef, useState } from "react";
import { api, humanBytes } from "../api.js";
import { useToast } from "../App.jsx";

export default function ImportWizard({ onDone }) {
  const notify = useToast();
  const [source, setSource] = useState("");
  const [plan, setPlan] = useState(null);
  const [planning, setPlanning] = useState(false);
  const [status, setStatus] = useState(null);
  const poll = useRef(null);

  useEffect(() => {
    api.importStatus().then(setStatus).catch(() => {});
    return () => clearInterval(poll.current);
  }, []);

  const startPolling = () => {
    clearInterval(poll.current);
    poll.current = setInterval(async () => {
      const s = await api.importStatus();
      setStatus(s);
      if (!s.running) {
        clearInterval(poll.current);
        onDone?.();
      }
    }, 1000);
  };

  const doPlan = async () => {
    setPlanning(true);
    setPlan(null);
    try {
      const p = await api.importPlan(source.trim());
      if (p.error) notify(p.error);
      else setPlan(p);
    } catch (e) {
      notify(e.message);
    } finally {
      setPlanning(false);
    }
  };

  const run = async (dryRun) => {
    const r = await api.importRun(source.trim(), dryRun);
    if (!r.started) return notify(r.reason || "could not start");
    notify(dryRun ? "Dry run started" : "Import started");
    startPolling();
  };

  const running = status?.running;
  const pct = status ? (100 * status.done) / Math.max(status.total, 1) : 0;

  return (
    <div className="content" style={{ maxWidth: 780 }}>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Import into the library</h3>
        <p className="muted">
          Files are organised as{" "}
          <code>D:\PhotoLibrary\YYYY\YYYY-MM-DD\Location\</code> using the photo's EXIF
          date and GPS. Files already in the library (by content hash) are skipped.
        </p>
        <div className="field">
          <label>Source folder (scanned recursively)</label>
          <input
            value={source}
            placeholder="D:\Camera dump   or   C:\Users\me\Downloads\photos"
            onChange={(e) => setSource(e.target.value)}
          />
        </div>
        <div className="row">
          <button onClick={doPlan} disabled={!source.trim() || planning || running}>
            {planning ? "Analysing…" : "Preview plan"}
          </button>
          <button
            onClick={() => run(true)}
            disabled={!source.trim() || running}
          >
            Dry run
          </button>
          <button
            className="primary"
            onClick={() => run(false)}
            disabled={!source.trim() || running}
          >
            Import now
          </button>
        </div>
      </div>

      {plan && (
        <div className="card">
          <div className="row">
            <span className="pill">{plan.total_media} media files found</span>
            <span className="pill">{plan.to_import} to import</span>
            <span className="pill">{plan.already_in_library} already in library</span>
            <span className="pill">mode: {plan.mode}</span>
          </div>
          <table className="kv" style={{ marginTop: 10 }}>
            <tbody>
              {plan.preview.slice(0, 40).map((it, i) => (
                <tr key={i}>
                  <td className="muted">{it.source.split(/[\\/]/).pop()}</td>
                  <td>→ {it.target}</td>
                  <td>{humanBytes(it.size_bytes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {plan.preview.length > 40 && (
            <p className="muted">…and {plan.to_import - 40} more</p>
          )}
        </div>
      )}

      {status && status.phase !== "idle" && (
        <div className="card">
          <div className="row">
            <b>{status.phase}</b>
            <span className="muted">
              {status.done}/{status.total}
            </span>
            {status.dry_run && <span className="pill">dry run</span>}
          </div>
          <div className="progress" style={{ margin: "8px 0" }}>
            <div style={{ width: `${pct}%` }} />
          </div>
          <div className="row">
            <span className="pill">{status.imported} imported</span>
            <span className="pill">{status.skipped_dupe} skipped (dupe)</span>
            <span className="pill">{status.errors} errors</span>
          </div>
          {status.log?.length > 0 && (
            <pre
              style={{
                maxHeight: 220,
                overflow: "auto",
                background: "var(--bg)",
                padding: 10,
                borderRadius: 8,
                fontSize: 12,
              }}
            >
              {status.log.slice(-200).join("\n")}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

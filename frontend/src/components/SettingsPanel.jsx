import { useEffect, useState } from "react";
import { api, humanBytes } from "../api.js";
import { useToast } from "../App.jsx";

export default function SettingsPanel({ status, onSaved }) {
  const notify = useToast();
  const [form, setForm] = useState(null);

  useEffect(() => {
    if (status?.settings) setForm(status.settings);
  }, [status?.settings]);

  if (!form) return <div className="content">Loading…</div>;

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    await api.saveSettings({
      library_path: form.library_path,
      import_mode: form.import_mode,
      near_duplicate_threshold: Number(form.near_duplicate_threshold),
      geocode: form.geocode,
      nominatim_email: form.nominatim_email,
    });
    notify("Settings saved");
    onSaved?.();
  };

  const c = status?.counts || {};

  return (
    <div className="content" style={{ maxWidth: 620 }}>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Library</h3>
        <div className="field">
          <label>Library folder</label>
          <input
            value={form.library_path}
            onChange={(e) => set("library_path", e.target.value)}
          />
          {!status?.library_exists && (
            <p style={{ color: "var(--danger)" }}>This path does not exist.</p>
          )}
        </div>
        <p className="muted">
          {c.total || 0} items · {humanBytes(c.bytes)} · {c.earliest?.slice(0, 10) || "?"} →{" "}
          {c.latest?.slice(0, 10) || "?"}
        </p>
        <div className="row">
          <button onClick={() => api.scan(false).then(() => notify("Quick rescan started"))}>
            Quick rescan
          </button>
          <button onClick={() => api.scan(true).then(() => notify("Full rescan started"))}>
            Full re-index
          </button>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Import</h3>
        <div className="field">
          <label>When importing</label>
          <select
            value={form.import_mode}
            onChange={(e) => set("import_mode", e.target.value)}
          >
            <option value="copy">Copy files (keep source)</option>
            <option value="move">Move files (delete from source)</option>
          </select>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Duplicates</h3>
        <div className="field">
          <label>
            Near-duplicate sensitivity (perceptual hash distance):{" "}
            {form.near_duplicate_threshold}
          </label>
          <input
            type="range"
            min="0"
            max="20"
            value={form.near_duplicate_threshold}
            onChange={(e) => set("near_duplicate_threshold", e.target.value)}
            style={{ width: "100%" }}
          />
          <p className="muted">
            0 = identical look only · higher = catches crops, edits, re-compressions (more
            false positives).
          </p>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Location names</h3>
        <div className="field">
          <label>Reverse geocoding for GPS coordinates</label>
          <select value={form.geocode} onChange={(e) => set("geocode", e.target.value)}>
            <option value="offline">Offline (reverse_geocoder package)</option>
            <option value="nominatim">OpenStreetMap Nominatim (online)</option>
            <option value="off">Off — use "Unknown location"</option>
          </select>
        </div>
        {form.geocode === "nominatim" && (
          <div className="field">
            <label>Contact email (Nominatim usage policy)</label>
            <input
              value={form.nominatim_email || ""}
              onChange={(e) => set("nominatim_email", e.target.value)}
            />
          </div>
        )}
      </div>

      <button className="primary" onClick={save}>
        Save settings
      </button>
    </div>
  );
}

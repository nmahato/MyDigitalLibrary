import { useState } from "react";
import { api, humanBytes } from "../api.js";

export default function ConvertDialog({ photo, onClose, onDone }) {
  const [target, setTarget] = useState("webp");
  const [maxDim, setMaxDim] = useState("");
  const [quality, setQuality] = useState(90);
  const [keepExif, setKeepExif] = useState(true);
  const [overwrite, setOverwrite] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const run = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.convert(photo.id, {
        target,
        max_dimension: maxDim ? Number(maxDim) : null,
        quality: Number(quality),
        keep_exif: keepExif,
        overwrite,
      });
      onDone(
        `${overwrite ? "Replaced" : "Saved"} ${r.output.split(/[\\/]/).pop()} · ${humanBytes(
          r.size_bytes
        )}`
      );
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="lightbox" style={{ background: "rgba(0,0,0,0.75)" }} onClick={onClose}>
      <div
        className="card"
        style={{ maxWidth: 380, margin: "auto" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ marginTop: 0 }}>Convert {photo.filename}</h3>

        <div className="field">
          <label>Target format</label>
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="webp">WebP</option>
            <option value="jpg">JPEG</option>
            <option value="png">PNG</option>
            <option value="tiff">TIFF</option>
            <option value="heic">HEIC</option>
          </select>
        </div>

        <div className="field">
          <label>Max dimension (px, blank = keep)</label>
          <input
            type="number"
            value={maxDim}
            placeholder="e.g. 2048"
            onChange={(e) => setMaxDim(e.target.value)}
          />
        </div>

        {["webp", "jpg", "heic"].includes(target) && (
          <div className="field">
            <label>Quality: {quality}</label>
            <input
              type="range"
              min="40"
              max="100"
              value={quality}
              onChange={(e) => setQuality(e.target.value)}
              style={{ width: "100%" }}
            />
          </div>
        )}

        <div className="field">
          <label>
            <input
              type="checkbox"
              checked={keepExif}
              onChange={(e) => setKeepExif(e.target.checked)}
            />{" "}
            Keep EXIF metadata
          </label>
          <label>
            <input
              type="checkbox"
              checked={overwrite}
              onChange={(e) => setOverwrite(e.target.checked)}
            />{" "}
            Replace original (else save a copy)
          </label>
        </div>

        {err && <p style={{ color: "var(--danger)" }}>{err}</p>}

        <div className="row">
          <button className="primary" onClick={run} disabled={busy}>
            {busy ? "Converting…" : "Convert"}
          </button>
          <button onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

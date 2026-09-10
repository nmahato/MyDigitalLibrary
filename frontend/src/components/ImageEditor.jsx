import { useEffect, useState } from "react";
import { api, fileUrl, humanBytes } from "../api.js";

export default function ImageEditor({ photo, onClose, onChanged, onDeleted }) {
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState(null);
  const [meta, setMeta] = useState(photo);
  const [ver, setVer] = useState(0); // cache-buster after edits
  const [maxDim, setMaxDim] = useState("");
  const [enh, setEnh] = useState({ brightness: 1, contrast: 1, color: 1, sharpness: 1 });
  const [overwrite, setOverwrite] = useState(true);

  useEffect(() => {
    api.photo(photo.id).then(setMeta).catch(() => {});
  }, [photo.id, ver]);

  const run = async (label, fn) => {
    setBusy(label);
    setErr(null);
    try {
      const r = await fn();
      setVer((v) => v + 1);
      onChanged?.(r);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy("");
    }
  };

  const del = async () => {
    if (!confirm(`Move "${meta.filename}" to the Recycle Bin?`)) return;
    const r = await api.deletePhotos([photo.id]);
    if (r.removed.length) {
      onDeleted?.(photo.id);
    } else {
      setErr(r.errors[0]?.error || "delete failed");
    }
  };

  return (
    <div className="modal-scrim" onMouseDown={onClose}>
      <div className="editor" onMouseDown={(e) => e.stopPropagation()}>
        <div className="editor-head">
          <b>Edit — {meta.filename}</b>
          <span className="muted">
            {meta.width}×{meta.height} · {humanBytes(meta.size_bytes)}
          </span>
          <div className="spacer" />
          <button onClick={onClose}>Close</button>
        </div>

        <div className="editor-body">
          <div className="editor-preview">
            <img
              src={`${fileUrl(photo.id)}?v=${ver}`}
              alt={meta.filename}
              key={ver}
            />
          </div>

          <div className="editor-tools">
            {err && <p style={{ color: "var(--danger)" }}>{err}</p>}

            <section>
              <h4>Rotate</h4>
              <div className="row">
                <button
                  disabled={!!busy}
                  onClick={() => run("rot", () => api.rotate(photo.id, 270))}
                >
                  ⟲ Left
                </button>
                <button
                  disabled={!!busy}
                  onClick={() => run("rot", () => api.rotate(photo.id, 90))}
                >
                  ⟳ Right
                </button>
                <button
                  disabled={!!busy}
                  onClick={() => run("rot", () => api.rotate(photo.id, 180))}
                >
                  180°
                </button>
              </div>
            </section>

            <section>
              <h4>Resize</h4>
              <div className="row">
                <input
                  type="number"
                  placeholder="max px (e.g. 2048)"
                  value={maxDim}
                  onChange={(e) => setMaxDim(e.target.value)}
                  style={{ width: 130 }}
                />
                <button
                  disabled={!!busy || !maxDim}
                  onClick={() =>
                    run("resize", () =>
                      api.resize(photo.id, {
                        max_dimension: Number(maxDim),
                        overwrite,
                      })
                    )
                  }
                >
                  Apply
                </button>
                {[1024, 2048, 4096].map((d) => (
                  <button
                    key={d}
                    disabled={!!busy}
                    onClick={() =>
                      run("resize", () =>
                        api.resize(photo.id, { max_dimension: d, overwrite })
                      )
                    }
                  >
                    {d}
                  </button>
                ))}
              </div>
            </section>

            <section>
              <h4>Enhance</h4>
              <button
                disabled={!!busy}
                onClick={() =>
                  run("enh", () => api.enhance(photo.id, { auto: true, overwrite }))
                }
              >
                ✨ Auto
              </button>
              {["brightness", "contrast", "color", "sharpness"].map((k) => (
                <label key={k} className="slider">
                  <span>
                    {k} {enh[k].toFixed(2)}
                  </span>
                  <input
                    type="range"
                    min="0.3"
                    max="2"
                    step="0.05"
                    value={enh[k]}
                    onChange={(e) =>
                      setEnh((s) => ({ ...s, [k]: Number(e.target.value) }))
                    }
                  />
                </label>
              ))}
              <button
                disabled={!!busy}
                onClick={() =>
                  run("enh", () =>
                    api.enhance(photo.id, { auto: false, ...enh, overwrite })
                  )
                }
              >
                Apply adjustments
              </button>
            </section>

            <section>
              <h4>Convert</h4>
              <div className="row">
                {["webp", "jpg", "png"].map((f) => (
                  <button
                    key={f}
                    disabled={!!busy}
                    onClick={() =>
                      run("conv", () =>
                        api.convert(photo.id, { target: f, overwrite })
                      )
                    }
                  >
                    → {f.toUpperCase()}
                  </button>
                ))}
              </div>
            </section>

            <label>
              <input
                type="checkbox"
                checked={overwrite}
                onChange={(e) => setOverwrite(e.target.checked)}
              />{" "}
              Replace original (uncheck to save a copy)
            </label>

            <section>
              <button className="danger" disabled={!!busy} onClick={del}>
                🗑 Delete photo
              </button>
            </section>

            {busy && <p className="muted">working… ({busy})</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

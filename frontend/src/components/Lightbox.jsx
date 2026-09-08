import { useEffect, useState } from "react";
import { api, downloadUrl, fileUrl, humanBytes } from "../api.js";
import { useToast } from "../App.jsx";
import ConvertDialog from "./ConvertDialog.jsx";

export default function Lightbox({
  items,
  index,
  people,
  onIndex,
  onClose,
  onDeleted,
  onNeedMore,
}) {
  const notify = useToast();
  const item = items[index];
  const [detail, setDetail] = useState(null);
  const [showConvert, setShowConvert] = useState(false);

  useEffect(() => {
    setDetail(null);
    if (item) api.photo(item.id).then(setDetail).catch(() => {});
  }, [item?.id]);

  const go = (delta) => {
    const next = index + delta;
    if (next < 0 || next >= items.length) return;
    if (next >= items.length - 3) onNeedMore?.();
    onIndex(next);
  };

  useEffect(() => {
    const h = (e) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") go(-1);
      if (e.key === "ArrowRight") go(1);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  if (!item) return null;

  const del = async () => {
    if (!confirm(`Move "${item.filename}" to the Recycle Bin?`)) return;
    const r = await api.deletePhotos([item.id]);
    if (r.removed.length) {
      notify("Moved to Recycle Bin");
      onDeleted(item.id);
    } else {
      notify(r.errors[0]?.error || "Delete failed");
    }
  };

  const tag = async () => {
    const name = prompt("Add person to this photo:");
    if (!name) return;
    let person = people.find((p) => p.name.toLowerCase() === name.toLowerCase());
    if (!person) person = await api.createPerson(name);
    await api.tagPhoto(item.id, person.id);
    notify(`Tagged as ${person.name}`);
    api.photo(item.id).then(setDetail);
  };

  return (
    <div className="lightbox">
      <div className="lb-top">
        <button onClick={onClose}>✕ Close</button>
        <span>{item.filename}</span>
        <span className="muted">
          {index + 1} / {items.length}
        </span>
        <div className="spacer" />
        <a href={downloadUrl(item.id)}>Download</a>
        {item.media_type === "image" && (
          <button onClick={() => setShowConvert(true)}>Convert…</button>
        )}
        <button onClick={tag}>Tag person</button>
        <button className="danger" onClick={del}>
          Delete
        </button>
      </div>

      <div className="stage">
        <button className="nav prev" onClick={() => go(-1)}>
          ‹
        </button>
        {item.media_type === "video" ? (
          <video src={fileUrl(item.id)} controls autoPlay />
        ) : (
          <img src={fileUrl(item.id)} alt={item.filename} />
        )}
        <button className="nav next" onClick={() => go(1)}>
          ›
        </button>
      </div>

      <div className="lb-bottom">
        <table className="kv">
          <tbody>
            <tr>
              <td>Taken</td>
              <td>
                {item.taken_at?.replace("T", " ") || "—"}{" "}
                <span className="muted">({item.date_source})</span>
              </td>
              <td>Size</td>
              <td>{humanBytes(item.size_bytes)}</td>
            </tr>
            <tr>
              <td>Dimensions</td>
              <td>
                {item.width && item.height ? `${item.width}×${item.height}` : "—"}
              </td>
              <td>Camera</td>
              <td>
                {[item.camera_make, item.camera_model].filter(Boolean).join(" ") || "—"}
              </td>
            </tr>
            <tr>
              <td>Location</td>
              <td>{item.location || (item.gps_lat ? `${item.gps_lat}, ${item.gps_lon}` : "—")}</td>
              <td>Folder</td>
              <td className="muted">{item.rel_path}</td>
            </tr>
          </tbody>
        </table>
        <div className="spacer" />
        <div>
          {detail?.people_tags?.map((p) => (
            <span
              key={p.id}
              className="chip"
              onClick={async () => {
                await api.untagPhoto(item.id, p.id);
                api.photo(item.id).then(setDetail);
              }}
              title="click to remove"
            >
              {p.name} ✕
            </span>
          ))}
          {detail?.faces?.filter((f) => f.name).map((f) => (
            <span key={f.id} className="chip active">
              {f.name}
            </span>
          ))}
        </div>
      </div>

      {showConvert && (
        <ConvertDialog
          photo={item}
          onClose={() => setShowConvert(false)}
          onDone={(msg) => {
            notify(msg);
            setShowConvert(false);
          }}
        />
      )}
    </div>
  );
}

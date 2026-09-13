import { useEffect, useRef, useState } from "react";
import { api, downloadUrl, fileUrl, humanBytes } from "../api.js";
import { useToast } from "../App.jsx";
import FaceOverlay from "./FaceOverlay.jsx";

export default function Lightbox({
  items,
  index,
  people,
  albums = [],
  onIndex,
  onClose,
  onEdit,
  onDeleted,
  onNeedMore,
}) {
  const notify = useToast();
  const item = items[index];
  const [detail, setDetail] = useState(null);
  const [showFaces, setShowFaces] = useState(true);
  const touchStart = useRef(null);

  const reload = () => item && api.photo(item.id).then(setDetail).catch(() => {});
  useEffect(() => {
    setDetail(null);
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item?.id]);

  const hasPrev = index > 0;
  const hasNext = index < items.length - 1;

  const go = (delta) => {
    const next = index + delta;
    if (next < 0 || next >= items.length) return;
    if (next >= items.length - 3) onNeedMore?.();
    onIndex(next);
  };

  useEffect(() => {
    const h = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft" || e.key === "PageUp") go(-1);
      if (e.key === "ArrowRight" || e.key === "PageDown") go(1);
      if (e.key === "Home") {
        onIndex(0);
      }
      if (e.key === "End") {
        if (items.length - 1 >= items.length - 3) onNeedMore?.();
        onIndex(items.length - 1);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  // Touch swipe handling for mobile / touchscreen preview
  const handleTouchStart = (e) => {
    if (e.touches && e.touches.length === 1) {
      touchStart.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    }
  };

  const handleTouchEnd = (e) => {
    if (!touchStart.current || !e.changedTouches || e.changedTouches.length === 0) return;
    const dx = e.changedTouches[0].clientX - touchStart.current.x;
    const dy = e.changedTouches[0].clientY - touchStart.current.y;
    touchStart.current = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
      if (dx > 0) go(-1);
      else go(1);
    }
  };

  if (!item) return null;

  const del = async () => {
    if (!confirm(`Move "${item.filename}" to the Recycle Bin?`)) return;
    const r = await api.deletePhotos([item.id]);
    if (r.removed.length) {
      notify("Moved to Recycle Bin");
      onDeleted(item.id);
    } else notify(r.errors[0]?.error || "Delete failed");
  };

  const tagPerson = async () => {
    const name = prompt("Add person to this photo:");
    if (!name) return;
    let person = people.find((p) => p.name.toLowerCase() === name.toLowerCase());
    if (!person) person = await api.createPerson(name);
    await api.tagPhoto(item.id, person.id);
    notify(`Tagged as ${person.name}`);
    reload();
  };

  const addHashtag = async () => {
    const name = prompt("Add hashtag:  #");
    if (!name) return;
    const r = await api.addTag(item.id, name);
    notify(`#${r.tag}`);
    reload();
  };

  const addToAlbum = async () => {
    let name = prompt("Add to album (existing or new):");
    if (!name) return;
    name = name.trim();
    let album = albums.find((a) => a.name.toLowerCase() === name.toLowerCase());
    if (!album) album = await api.createAlbum(name);
    await api.addToAlbum(album.id, [item.id]);
    notify(`Added to "${album.name}"`);
    reload();
  };

  return (
    <div className="lightbox">
      <div className="lb-top">
        <button onClick={onClose} title="Close (Esc)">✕ Close</button>
        <div className="lb-nav-group">
          <button
            className="lb-nav-btn"
            disabled={!hasPrev}
            onClick={() => go(-1)}
            title="Previous (Left Arrow / PageUp)"
          >
            ‹ Prev
          </button>
          <span className="lb-counter">
            {index + 1} / {items.length}
          </span>
          <button
            className="lb-nav-btn"
            disabled={!hasNext}
            onClick={() => go(1)}
            title="Next (Right Arrow / PageDown)"
          >
            Next ›
          </button>
        </div>
        <span className="lb-filename" title={item.filename}>{item.filename}</span>
        <div className="spacer" />
        {item.media_type === "image" && detail?.faces?.length > 0 && (
          <button
            className={showFaces ? "active" : ""}
            onClick={() => setShowFaces((v) => !v)}
            title="Toggle face boxes"
          >
            🙂 {detail.faces.length}
          </button>
        )}
        <a href={downloadUrl(item.id)} className="button-like">Download</a>
        <button onClick={addHashtag}># Tag</button>
        <button onClick={addToAlbum}>+ Album</button>
        <button onClick={tagPerson}>Person</button>
        {item.media_type === "image" && (
          <button className="primary" onClick={() => onEdit?.(item)}>
            ✎ Edit
          </button>
        )}
        <button className="danger" onClick={del}>
          Delete
        </button>
      </div>

      <div
        className="stage"
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        <button
          className="nav prev"
          disabled={!hasPrev}
          onClick={() => go(-1)}
          title="Previous (Left Arrow)"
          aria-label="Previous"
        >
          ‹
        </button>
        {item.media_type === "video" ? (
          <video src={fileUrl(item.id)} controls autoPlay />
        ) : (
          <div className="stage-img">
            <img src={fileUrl(item.id)} alt={item.filename} />
            {showFaces && detail?.faces?.length > 0 && (
              <FaceOverlay
                photo={item}
                faces={detail.faces}
                people={people}
                onChanged={reload}
              />
            )}
          </div>
        )}
        <button
          className="nav next"
          disabled={!hasNext}
          onClick={() => go(1)}
          title="Next (Right Arrow)"
          aria-label="Next"
        >
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
              <td>{item.width && item.height ? `${item.width}×${item.height}` : "—"}</td>
              <td>Camera</td>
              <td>{[item.camera_make, item.camera_model].filter(Boolean).join(" ") || "—"}</td>
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
        <div className="lb-chips">
          {detail?.albums?.map((a) => (
            <span key={"al" + a.id} className="chip">📁 {a.name}</span>
          ))}
          {detail?.hashtags?.map((t) => (
            <span
              key={"h" + t.id}
              className="chip"
              title="click to remove"
              onClick={async () => {
                await api.removeTag(item.id, t.name);
                reload();
              }}
            >
              #{t.name} ✕
            </span>
          ))}
          {detail?.people_tags?.map((p) => (
            <span
              key={"p" + p.id}
              className="chip"
              title="click to remove"
              onClick={async () => {
                await api.untagPhoto(item.id, p.id);
                reload();
              }}
            >
              {p.name} ✕
            </span>
          ))}
          {detail?.faces?.filter((f) => f.name).map((f) => (
            <span key={"f" + f.id} className="chip active">
              🙂 {f.name}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

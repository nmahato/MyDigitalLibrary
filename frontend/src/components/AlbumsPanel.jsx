import { useCallback, useEffect, useState } from "react";
import { api, thumbUrl } from "../api.js";
import { useToast } from "../App.jsx";
import Lightbox from "./Lightbox.jsx";

export default function AlbumsPanel() {
  const notify = useToast();
  const [albums, setAlbums] = useState([]);
  const [open, setOpen] = useState(null); // album object
  const [photos, setPhotos] = useState([]);
  const [sel, setSel] = useState(new Set());
  const [lightboxIdx, setLightboxIdx] = useState(null);

  const refresh = useCallback(() => {
    api.albums().then(setAlbums).catch(() => {});
  }, []);
  useEffect(() => refresh(), [refresh]);

  useEffect(() => {
    if (open) {
      api
        .photos({ album_id: open.id, limit: 500, sort: "date", order: "desc" })
        .then((r) => setPhotos(r.items))
        .catch(() => setPhotos([]));
      setSel(new Set());
    }
  }, [open]);

  const create = async () => {
    const name = prompt("New album name:");
    if (!name) return;
    await api.createAlbum(name);
    refresh();
  };

  if (open) {
    const toggle = (id) =>
      setSel((s) => {
        const n = new Set(s);
        n.has(id) ? n.delete(id) : n.add(id);
        return n;
      });
    const removeSel = async () => {
      await api.removeFromAlbum(open.id, [...sel]);
      notify(`Removed ${sel.size} from "${open.name}"`);
      setPhotos((p) => p.filter((x) => !sel.has(x.id)));
      setSel(new Set());
      refresh();
    };
    return (
      <div className="content">
        <div className="row" style={{ marginBottom: 12 }}>
          <button onClick={() => setOpen(null)}>← Albums</button>
          <h2 style={{ margin: 0 }}>{open.name}</h2>
          <span className="muted">{photos.length} photos</span>
          <div className="spacer" />
          <button
            onClick={async () => {
              const name = prompt("Rename album:", open.name);
              if (name) {
                await api.renameAlbum(open.id, name);
                setOpen({ ...open, name });
                refresh();
              }
            }}
          >
            Rename
          </button>
          <button
            className="danger"
            onClick={async () => {
              if (confirm(`Delete album "${open.name}"? Photos are kept.`)) {
                await api.deleteAlbum(open.id);
                setOpen(null);
                refresh();
              }
            }}
          >
            Delete album
          </button>
          {sel.size > 0 && (
            <button className="danger" onClick={removeSel}>
              Remove {sel.size} from album
            </button>
          )}
        </div>
        <div className="grid">
          {photos.map((it, idx) => (
            <div
              key={it.id}
              className={"tile" + (sel.has(it.id) ? " selected" : "")}
              onClick={(e) => (e.shiftKey || e.ctrlKey ? toggle(it.id) : setLightboxIdx(idx))}
            >
              <img loading="lazy" src={thumbUrl(it.id)} alt={it.filename} />
              <span
                className="pick"
                onClick={(e) => {
                  e.stopPropagation();
                  toggle(it.id);
                }}
              />
            </div>
          ))}
        </div>
        {photos.length === 0 && (
          <p className="muted">
            Empty. Select photos in the Library and use <b>+ Album</b>.
          </p>
        )}
        {lightboxIdx != null && (
          <Lightbox
            items={photos}
            index={lightboxIdx}
            people={[]}
            albums={albums}
            onIndex={setLightboxIdx}
            onClose={() => setLightboxIdx(null)}
            onDeleted={(id) => {
              setPhotos((p) => p.filter((x) => x.id !== id));
              setLightboxIdx(null);
            }}
            onNeedMore={() => {}}
          />
        )}
      </div>
    );
  }

  return (
    <div className="content">
      <div className="row" style={{ marginBottom: 14 }}>
        <h2 style={{ margin: 0 }}>Albums</h2>
        <div className="spacer" />
        <button className="primary" onClick={create}>
          + New album
        </button>
      </div>
      <div className="people-grid">
        {albums.map((a) => (
          <div key={a.id} className="person" onClick={() => setOpen(a)}>
            {a.cover_photo ? (
              <img className="face" src={thumbUrl(a.cover_photo)} alt={a.name} />
            ) : (
              <div className="face" />
            )}
            <div className="label">
              <b>{a.name}</b>
              <span className="muted">
                {a.photo_count} photo{a.photo_count === 1 ? "" : "s"}
              </span>
            </div>
          </div>
        ))}
      </div>
      {albums.length === 0 && (
        <p className="muted">No albums yet. Create one, then add photos from the Library.</p>
      )}
    </div>
  );
}

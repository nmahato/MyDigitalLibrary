import { useCallback, useEffect, useRef, useState } from "react";
import { api, thumbUrl } from "../api.js";
import { useToast } from "../App.jsx";
import FilterBar from "./FilterBar.jsx";
import Lightbox from "./Lightbox.jsx";
import ImageEditor from "./ImageEditor.jsx";

const PAGE = 120;

export default function Gallery({ status }) {
  const notify = useToast();
  const [filters, setFilters] = useState({
    sort: "date",
    order: "desc",
    limit: PAGE,
    offset: 0,
  });
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [lightboxIdx, setLightboxIdx] = useState(null);
  const [editing, setEditing] = useState(null); // photo object
  const [people, setPeople] = useState([]);
  const [albums, setAlbums] = useState([]);
  const sentinel = useRef(null);

  const refreshMeta = useCallback(() => {
    api.people().then(setPeople).catch(() => {});
    api.albums().then(setAlbums).catch(() => {});
  }, []);
  useEffect(() => {
    refreshMeta();
  }, [refreshMeta, lightboxIdx, editing]);

  const scanRunning = !!status?.scan?.running;
  const prevScanRunning = useRef(scanRunning);
  useEffect(() => {
    if (prevScanRunning.current && !scanRunning) {
      setItems([]);
      load(true);
      refreshMeta();
    }
    prevScanRunning.current = scanRunning;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scanRunning]);

  const load = useCallback(
    async (reset) => {
      setLoading(true);
      try {
        const offset = reset ? 0 : items.length;
        const res = await api.photos({ ...filters, offset });
        setTotal(res.total);
        setItems((prev) => (reset ? res.items : [...prev, ...res.items]));
      } catch (e) {
        notify(e.message);
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [filters, items.length, notify]
  );

  useEffect(() => {
    setItems([]);
    setSelected(new Set());
    load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);

  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;
    const io = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && !loading && items.length < total) load(false);
    });
    io.observe(el);
    return () => io.disconnect();
  }, [loading, items.length, total, load]);

  const toggle = (id) =>
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  const clearSel = () => setSelected(new Set());
  const ids = () => [...selected];

  const bulk = async (label, fn, { refresh } = {}) => {
    try {
      await fn(ids());
      notify(`${label}: ${selected.size} item(s)`);
      clearSel();
      if (refresh) load(true);
      refreshMeta();
    } catch (e) {
      notify(e.message);
    }
  };

  const bulkDelete = async () => {
    if (!confirm(`Move ${selected.size} item(s) to the Recycle Bin?`)) return;
    const r = await api.deletePhotos(ids());
    notify(`Deleted ${r.removed.length}${r.errors.length ? `, ${r.errors.length} failed` : ""}`);
    setItems((prev) => prev.filter((p) => !r.removed.includes(p.id)));
    clearSel();
  };

  const bulkTagPerson = async () => {
    const name = prompt("Tag selected photos with person:");
    if (!name) return;
    let person = people.find((p) => p.name.toLowerCase() === name.toLowerCase());
    if (!person) person = await api.createPerson(name);
    await Promise.all(ids().map((id) => api.tagPhoto(id, person.id)));
    notify(`Tagged ${selected.size} as ${person.name}`);
    clearSel();
    refreshMeta();
  };

  const bulkHashtag = async () => {
    const name = prompt("Add hashtag to selected photos:  #");
    if (!name) return;
    const r = await api.bulkTag(ids(), name);
    notify(`#${r.tag} added to ${selected.size} photo(s)`);
    clearSel();
    refreshMeta();
  };

  const bulkAlbum = async () => {
    let name = prompt("Add selected to album (existing or new):");
    if (!name) return;
    name = name.trim();
    let album = albums.find((a) => a.name.toLowerCase() === name.toLowerCase());
    if (!album) album = await api.createAlbum(name);
    const r = await api.addToAlbum(album.id, ids());
    notify(`Added ${r.added} to "${album.name}"`);
    clearSel();
    refreshMeta();
  };

  const onEdited = () => load(true);

  return (
    <>
      <FilterBar filters={filters} setFilters={setFilters} people={people} status={status} />
      <div className="content">
        <div className="row" style={{ marginBottom: 12 }}>
          <span className="muted">
            {total.toLocaleString()} result{total === 1 ? "" : "s"}
          </span>
          <div className="spacer" />
          {selected.size > 0 && (
            <>
              <span className="pill">{selected.size} selected</span>
              <button onClick={bulkAlbum}>+ Album</button>
              <button onClick={bulkHashtag}># Hashtag</button>
              <button onClick={bulkTagPerson}>Person</button>
              <button
                onClick={() =>
                  bulk("Rotated left", (x) => Promise.all(x.map((id) => api.rotate(id, 270))), { refresh: true })
                }
              >
                ⟲
              </button>
              <button
                onClick={() =>
                  bulk("Rotated right", (x) => Promise.all(x.map((id) => api.rotate(id, 90))), { refresh: true })
                }
              >
                ⟳
              </button>
              <button
                onClick={() =>
                  bulk("Enhanced", (x) => Promise.all(x.map((id) => api.enhance(id, { auto: true }))), { refresh: true })
                }
              >
                ✨
              </button>
              <button
                onClick={() => {
                  const d = prompt("Resize selected — max dimension (px):", "2048");
                  if (d)
                    bulk("Resized", (x) => Promise.all(x.map((id) => api.resize(id, { max_dimension: Number(d) }))), { refresh: true });
                }}
              >
                ⤢
              </button>
              <button className="danger" onClick={bulkDelete}>
                🗑
              </button>
              <button onClick={clearSel}>Clear</button>
            </>
          )}
        </div>

        <div className="grid">
          {items.map((it, idx) => (
            <div
              key={it.id}
              className={"tile" + (selected.has(it.id) ? " selected" : "")}
              onClick={(e) => {
                if (e.shiftKey || e.metaKey || e.ctrlKey) toggle(it.id);
                else setLightboxIdx(idx);
              }}
            >
              <img loading="lazy" src={thumbUrl(it.id)} alt={it.filename} />
              {it.media_type === "video" && (
                <span className="badge">▶ {it.duration_sec ? fmtDur(it.duration_sec) : "video"}</span>
              )}
              {it.media_type === "image" && (
                <span
                  className="edit-btn"
                  title="Edit"
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditing(it);
                  }}
                >
                  ✎
                </span>
              )}
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

        <div ref={sentinel} style={{ height: 40 }} />
        {loading && <p className="muted">Loading…</p>}
        {!loading && items.length === 0 && (
          <p className="muted">
            {scanRunning ? (
              <>
                Indexing library… {status.scan.done}/{status.scan.total || "?"} scanned.
              </>
            ) : (status?.counts?.total ?? 0) === 0 ? (
              <>
                Nothing indexed yet. Click <b>Rescan</b> (top right) to index{" "}
                <code>{status?.settings?.library_path}</code>.
              </>
            ) : (
              <>No media matches these filters.</>
            )}
          </p>
        )}
      </div>

      {lightboxIdx != null && (
        <Lightbox
          items={items}
          index={lightboxIdx}
          people={people}
          albums={albums}
          onIndex={setLightboxIdx}
          onClose={() => setLightboxIdx(null)}
          onEdit={(p) => setEditing(p)}
          onDeleted={(id) => {
            setItems((prev) => prev.filter((p) => p.id !== id));
            setLightboxIdx(null);
          }}
          onNeedMore={() => items.length < total && load(false)}
        />
      )}

      {editing && (
        <ImageEditor
          photo={editing}
          onClose={() => setEditing(null)}
          onChanged={onEdited}
          onDeleted={(id) => {
            setItems((prev) => prev.filter((p) => p.id !== id));
            setEditing(null);
          }}
        />
      )}
    </>
  );
}

function fmtDur(s) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

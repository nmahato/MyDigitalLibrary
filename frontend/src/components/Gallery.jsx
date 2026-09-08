import { useCallback, useEffect, useRef, useState } from "react";
import { api, thumbUrl } from "../api.js";
import { useToast } from "../App.jsx";
import FilterBar from "./FilterBar.jsx";
import Lightbox from "./Lightbox.jsx";

const PAGE = 120;

export default function Gallery() {
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
  const [people, setPeople] = useState([]);
  const sentinel = useRef(null);

  useEffect(() => {
    api.people().then(setPeople).catch(() => {});
  }, [lightboxIdx]);

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

  // reload when filters change
  useEffect(() => {
    setItems([]);
    setSelected(new Set());
    load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);

  // infinite scroll
  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;
    const io = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && !loading && items.length < total) {
        load(false);
      }
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

  const bulkDelete = async () => {
    if (!confirm(`Move ${selected.size} item(s) to the Recycle Bin?`)) return;
    const r = await api.deletePhotos([...selected]);
    notify(`Deleted ${r.removed.length}${r.errors.length ? `, ${r.errors.length} failed` : ""}`);
    setItems((prev) => prev.filter((p) => !r.removed.includes(p.id)));
    setSelected(new Set());
  };

  const bulkTag = async () => {
    const name = prompt("Tag selected photos with person:");
    if (!name) return;
    let person = people.find((p) => p.name.toLowerCase() === name.toLowerCase());
    if (!person) person = await api.createPerson(name);
    await Promise.all([...selected].map((id) => api.tagPhoto(id, person.id)));
    notify(`Tagged ${selected.size} photo(s) as ${person.name}`);
    setSelected(new Set());
    api.people().then(setPeople);
  };

  return (
    <>
      <FilterBar filters={filters} setFilters={setFilters} people={people} />
      <div className="content">
        <div className="row" style={{ marginBottom: 12 }}>
          <span className="muted">
            {total.toLocaleString()} result{total === 1 ? "" : "s"}
          </span>
          <div className="spacer" />
          {selected.size > 0 && (
            <>
              <span className="pill">{selected.size} selected</span>
              <button onClick={bulkTag}>Tag person</button>
              <button className="danger" onClick={bulkDelete}>
                Delete
              </button>
              <button onClick={() => setSelected(new Set())}>Clear</button>
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
                <span className="badge">
                  ▶ {it.duration_sec ? fmtDur(it.duration_sec) : "video"}
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
            No media. Try <b>Rescan</b> or adjust filters.
          </p>
        )}
      </div>

      {lightboxIdx != null && (
        <Lightbox
          items={items}
          index={lightboxIdx}
          people={people}
          onIndex={setLightboxIdx}
          onClose={() => setLightboxIdx(null)}
          onDeleted={(id) => {
            setItems((prev) => prev.filter((p) => p.id !== id));
            setLightboxIdx(null);
          }}
          onNeedMore={() => items.length < total && load(false)}
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

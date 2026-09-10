import { useEffect, useState } from "react";
import { api } from "../api.js";
import FolderTree from "./FolderTree.jsx";

export default function FilterBar({ filters, setFilters, people, status }) {
  const [facets, setFacets] = useState(null);
  const [albums, setAlbums] = useState([]);
  const [tags, setTags] = useState([]);

  const reloadKey = JSON.stringify(status?.counts || {});

  useEffect(() => {
    api.facets().then(setFacets).catch(() => {});
    api.albums().then(setAlbums).catch(() => {});
    api.tags().then(setTags).catch(() => {});
  }, [reloadKey]);

  const set = (patch) => setFilters((f) => ({ ...f, ...patch, offset: 0 }));

  return (
    <div className="sidebar">
      <FolderTree
        selected={filters.folder}
        onSelect={(folder) => set({ folder })}
        reloadKey={reloadKey}
      />

      <div className="field">
        <label>Search</label>
        <input
          value={filters.q || ""}
          placeholder="filename, folder, place…"
          onChange={(e) => set({ q: e.target.value })}
        />
      </div>

      <div className="field">
        <label>Media</label>
        <select
          value={filters.media_type || ""}
          onChange={(e) => set({ media_type: e.target.value })}
        >
          <option value="">All</option>
          <option value="image">Photos</option>
          <option value="video">Videos</option>
        </select>
      </div>

      <div className="field">
        <label>Sort</label>
        <div className="row">
          <select
            value={filters.sort}
            onChange={(e) => set({ sort: e.target.value })}
            style={{ flex: 1 }}
          >
            <option value="date">Date taken</option>
            <option value="name">Name</option>
            <option value="size">Size</option>
            <option value="added">Recently added</option>
            <option value="random">Shuffle</option>
          </select>
          <button
            onClick={() => set({ order: filters.order === "asc" ? "desc" : "asc" })}
            title="Toggle direction"
          >
            {filters.order === "asc" ? "↑" : "↓"}
          </button>
        </div>
      </div>

      <div className="field">
        <label>Date range</label>
        <div className="row">
          <input
            type="date"
            value={filters.date_from || ""}
            onChange={(e) => set({ date_from: e.target.value })}
          />
          <input
            type="date"
            value={filters.date_to || ""}
            onChange={(e) => set({ date_to: e.target.value })}
          />
        </div>
      </div>

      {facets?.years?.length > 0 && (
        <div className="field">
          <label>Year</label>
          <div className="row">
            {facets.years.slice(0, 24).map((y) => (
              <span
                key={y}
                className={"chip" + (String(filters.year) === y ? " active" : "")}
                onClick={() =>
                  set({ year: String(filters.year) === y ? undefined : Number(y) })
                }
              >
                {y}
              </span>
            ))}
          </div>
        </div>
      )}

      {people?.length > 0 && (
        <div className="field">
          <label>Person (face)</label>
          <select
            value={filters.person_id || ""}
            onChange={(e) =>
              set({ person_id: e.target.value ? Number(e.target.value) : undefined })
            }
          >
            <option value="">Anyone</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.photo_count})
              </option>
            ))}
          </select>
        </div>
      )}

      {albums.length > 0 && (
        <div className="field">
          <label>Album</label>
          <select
            value={filters.album_id || ""}
            onChange={(e) =>
              set({ album_id: e.target.value ? Number(e.target.value) : undefined })
            }
          >
            <option value="">Any</option>
            {albums.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.photo_count})
              </option>
            ))}
          </select>
        </div>
      )}

      {tags.length > 0 && (
        <div className="field">
          <label>Hashtag</label>
          <div className="row">
            {tags.slice(0, 30).map((t) => (
              <span
                key={t.id}
                className={"chip" + (filters.tag === t.name ? " active" : "")}
                onClick={() =>
                  set({ tag: filters.tag === t.name ? undefined : t.name })
                }
              >
                #{t.name} <span className="muted">{t.photo_count}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {facets?.locations?.length > 0 && (
        <div className="field">
          <label>Location</label>
          <select
            value={filters.location || ""}
            onChange={(e) => set({ location: e.target.value })}
          >
            <option value="">Anywhere</option>
            {facets.locations.map((l) => (
              <option key={l.location} value={l.location}>
                {l.location} ({l.n})
              </option>
            ))}
          </select>
        </div>
      )}

      {facets?.cameras?.length > 0 && (
        <div className="field">
          <label>Camera</label>
          <select
            value={filters.camera || ""}
            onChange={(e) => set({ camera: e.target.value })}
          >
            <option value="">Any camera</option>
            {facets.cameras.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="field">
        <label>
          <input
            type="checkbox"
            checked={!!filters.duplicates_only}
            onChange={(e) => set({ duplicates_only: e.target.checked || undefined })}
          />{" "}
          Only duplicates
        </label>
      </div>

      <button
        onClick={() =>
          setFilters({ sort: "date", order: "desc", limit: 120, offset: 0 })
        }
      >
        Clear filters
      </button>

      {facets?.counts?.bytes != null && (
        <p className="muted" style={{ marginTop: 16, fontSize: 12 }}>
          Library size: {(facets.counts.bytes / 1024 ** 3).toFixed(1)} GB
        </p>
      )}
    </div>
  );
}

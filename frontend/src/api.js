const BASE = "";

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {}
    throw new Error(detail);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res;
}

export const api = {
  // library
  status: () => req("/api/library/status"),
  scan: (full = false) => req("/api/library/scan", { method: "POST", body: { full } }),
  scanProgress: () => req("/api/library/scan"),
  saveSettings: (patch) => req("/api/settings", { method: "POST", body: patch }),
  folders: () => req("/api/library/folders"),

  // photos
  photos: (params) => req("/api/photos?" + new URLSearchParams(clean(params))),
  photo: (id) => req(`/api/photos/${id}`),
  facets: () => req("/api/photos/facets"),
  deletePhotos: (ids) => req("/api/photos/delete", { method: "POST", body: { ids } }),
  setRating: (id, rating) =>
    req(`/api/photos/${id}/rating`, { method: "PATCH", body: { rating } }),
  convert: (id, body) => req(`/api/photos/${id}/convert`, { method: "POST", body }),
  rotate: (id, degrees, overwrite = true) =>
    req(`/api/photos/${id}/rotate`, { method: "POST", body: { degrees, overwrite } }),
  resize: (id, body) => req(`/api/photos/${id}/resize`, { method: "POST", body }),
  enhance: (id, body) => req(`/api/photos/${id}/enhance`, { method: "POST", body }),

  // albums
  albums: () => req("/api/albums"),
  createAlbum: (name) => req("/api/albums", { method: "POST", body: { name } }),
  renameAlbum: (id, name) =>
    req(`/api/albums/${id}`, { method: "PATCH", body: { name } }),
  deleteAlbum: (id) => req(`/api/albums/${id}`, { method: "DELETE" }),
  addToAlbum: (id, photo_ids) =>
    req(`/api/albums/${id}/photos`, { method: "POST", body: { photo_ids } }),
  removeFromAlbum: (id, photo_ids) =>
    req(`/api/albums/${id}/photos`, { method: "DELETE", body: { photo_ids } }),

  // hashtags
  tags: () => req("/api/tags"),
  addTag: (photoId, name) =>
    req(`/api/photos/${photoId}/tags`, { method: "POST", body: { name } }),
  removeTag: (photoId, name) =>
    req(`/api/photos/${photoId}/tags/${encodeURIComponent(name)}`, { method: "DELETE" }),
  bulkTag: (photo_ids, name) =>
    req("/api/tags/bulk", { method: "POST", body: { photo_ids, name } }),

  // people / faces
  people: () => req("/api/people"),
  createPerson: (name) => req("/api/people", { method: "POST", body: { name } }),
  renamePerson: (id, name) =>
    req(`/api/people/${id}`, { method: "PATCH", body: { name } }),
  deletePerson: (id) => req(`/api/people/${id}`, { method: "DELETE" }),
  mergePeople: (source_id, target_id) =>
    req("/api/people/merge", { method: "POST", body: { source_id, target_id } }),
  personFaces: (id, status = "all") =>
    req(`/api/people/${id}/faces?status=${status}`),
  assignFace: (faceId, body) =>
    req(`/api/faces/${faceId}/assign`, { method: "POST", body }),
  confirmFace: (faceId) =>
    req(`/api/faces/${faceId}/confirm`, { method: "POST", body: {} }),
  rejectFace: (faceId) =>
    req(`/api/faces/${faceId}/reject`, { method: "POST", body: {} }),
  tagPhoto: (photoId, person_id) =>
    req(`/api/photos/${photoId}/people`, { method: "POST", body: { person_id } }),
  untagPhoto: (photoId, personId) =>
    req(`/api/photos/${photoId}/people/${personId}`, { method: "DELETE" }),
  facesStatus: () => req("/api/faces/status"),
  detectFaces: (limit) => req("/api/faces/detect", { method: "POST", body: { limit } }),
  recognizeFaces: () => req("/api/faces/recognize", { method: "POST", body: {} }),
  clusterFaces: () => req("/api/faces/cluster", { method: "POST", body: {} }),

  // duplicates
  duplicates: () => req("/api/duplicates"),
  resolveDup: (keep_id, remove_ids) =>
    req("/api/duplicates/resolve", { method: "POST", body: { keep_id, remove_ids } }),
  ignoreDup: (a, b) => req("/api/duplicates/ignore", { method: "POST", body: { a, b } }),
  autoResolveDup: (kinds) =>
    req("/api/duplicates/auto-resolve", { method: "POST", body: { kinds } }),

  // import
  importPlan: (source) => req("/api/import/plan", { method: "POST", body: { source } }),
  importRun: (source, dry_run) =>
    req("/api/import/run", { method: "POST", body: { source, dry_run } }),
  importStatus: () => req("/api/import/status"),
};

function clean(obj) {
  const out = {};
  for (const [k, v] of Object.entries(obj || {})) {
    if (v !== undefined && v !== null && v !== "") out[k] = v;
  }
  return out;
}

export const thumbUrl = (id) => `/api/photos/${id}/thumb`;
export const fileUrl = (id) => `/api/photos/${id}/file`;
export const downloadUrl = (id) => `/api/photos/${id}/download`;
export const faceCropUrl = (id) => `/api/faces/${id}/crop`;

export function humanBytes(n) {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(n) / Math.log(1024));
  return `${(n / 1024 ** i).toFixed(i ? 1 : 0)} ${u[i]}`;
}

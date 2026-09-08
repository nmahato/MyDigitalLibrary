import { useCallback, useEffect, useState } from "react";
import { api, faceCropUrl, thumbUrl } from "../api.js";
import { useToast } from "../App.jsx";

export default function PeoplePanel() {
  const notify = useToast();
  const [people, setPeople] = useState([]);
  const [faceStatus, setFaceStatus] = useState(null);
  const [selected, setSelected] = useState(null);
  const [faces, setFaces] = useState([]);
  const [mergeFrom, setMergeFrom] = useState(null);

  const refresh = useCallback(() => {
    api.people().then(setPeople).catch(() => {});
    api.facesStatus().then(setFaceStatus).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(() => api.facesStatus().then(setFaceStatus).catch(() => {}), 3000);
    return () => clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    if (selected) api.personFaces(selected.id).then(setFaces).catch(() => setFaces([]));
  }, [selected]);

  const prog = faceStatus?.progress;

  const detect = async () => {
    try {
      await api.detectFaces(null);
      notify("Face detection started");
    } catch (e) {
      notify(e.message);
    }
  };

  const rename = async (p) => {
    const name = prompt("Rename person:", p.name);
    if (name && name !== p.name) {
      await api.renamePerson(p.id, name);
      refresh();
      if (selected?.id === p.id) setSelected({ ...p, name });
    }
  };

  const doMerge = async (target) => {
    if (mergeFrom && mergeFrom.id !== target.id) {
      await api.mergePeople(mergeFrom.id, target.id);
      notify(`Merged ${mergeFrom.name} → ${target.name}`);
      setMergeFrom(null);
      setSelected(null);
      refresh();
    }
  };

  return (
    <div className="content">
      <div className="card">
        <div className="row">
          <b>Face recognition</b>
          {faceStatus && (
            <span className="pill">
              {faceStatus.engine_available ? "engine ready" : "engine not installed"}
            </span>
          )}
          <div className="spacer" />
          <button
            onClick={detect}
            disabled={!faceStatus?.engine_available || prog?.running}
          >
            {prog?.running
              ? `${prog.phase} ${prog.done}/${prog.total}`
              : "Detect faces"}
          </button>
          <button onClick={() => api.clusterFaces().then(refresh)}>Re-cluster</button>
        </div>
        {!faceStatus?.engine_available && (
          <p className="muted">
            Automatic face detection needs the optional engine:{" "}
            <code>pip install -r requirements-faces.txt</code>. You can still tag whole
            photos with a person from the gallery and lightbox.
          </p>
        )}
        {faceStatus?.engine_available && (
          <p className="muted">
            {faceStatus.faces} faces detected · {faceStatus.named_faces} named ·{" "}
            {faceStatus.photos_pending} photos pending
          </p>
        )}
        {prog?.running && (
          <div className="progress">
            <div style={{ width: `${(100 * prog.done) / Math.max(prog.total, 1)}%` }} />
          </div>
        )}
      </div>

      {mergeFrom && (
        <div className="card">
          Merging <b>{mergeFrom.name}</b> into… pick a target person below, or{" "}
          <button onClick={() => setMergeFrom(null)}>cancel</button>
        </div>
      )}

      {!selected && (
        <>
          <div className="row" style={{ margin: "8px 0" }}>
            <button
              onClick={async () => {
                const name = prompt("New person name:");
                if (name) {
                  await api.createPerson(name);
                  refresh();
                }
              }}
            >
              + Add person
            </button>
          </div>
          <div className="people-grid">
            {people.map((p) => (
              <div
                key={p.id}
                className="person"
                onClick={() => (mergeFrom ? doMerge(p) : setSelected(p))}
              >
                {p.cover_face ? (
                  <img className="face" src={faceCropUrl(p.cover_face)} alt={p.name} />
                ) : (
                  <div className="face" />
                )}
                <div className="label">
                  <b>{p.name}</b>
                  <span className="muted">
                    {p.photo_count} photo{p.photo_count === 1 ? "" : "s"}
                    {p.auto ? " · auto" : ""}
                  </span>
                </div>
              </div>
            ))}
          </div>
          {people.length === 0 && <p className="muted">No people yet.</p>}
        </>
      )}

      {selected && (
        <PersonDetail
          person={selected}
          faces={faces}
          onBack={() => setSelected(null)}
          onRename={() => rename(selected)}
          onMerge={() => setMergeFrom(selected)}
          onDelete={async () => {
            if (confirm(`Delete person "${selected.name}"? Photos are kept.`)) {
              await api.deletePerson(selected.id);
              setSelected(null);
              refresh();
            }
          }}
        />
      )}
    </div>
  );
}

function PersonDetail({ person, faces, onBack, onRename, onMerge, onDelete }) {
  return (
    <div>
      <div className="row" style={{ marginBottom: 12 }}>
        <button onClick={onBack}>← People</button>
        <h2 style={{ margin: 0 }}>{person.name}</h2>
        <div className="spacer" />
        <button onClick={onRename}>Rename</button>
        <button onClick={onMerge}>Merge…</button>
        <button className="danger" onClick={onDelete}>
          Delete
        </button>
      </div>
      <p className="muted">
        {person.face_count} detected face{person.face_count === 1 ? "" : "s"}
      </p>
      <div className="grid">
        {faces.map((f) => (
          <div key={f.id} className="tile">
            <img src={faceCropUrl(f.id)} alt="" />
          </div>
        ))}
      </div>
      {faces.length === 0 && (
        <p className="muted">
          No detected faces linked yet — this person may only have photo-level tags.
        </p>
      )}
    </div>
  );
}

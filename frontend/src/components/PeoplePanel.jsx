import { useCallback, useEffect, useState } from "react";
import { api, faceCropUrl } from "../api.js";
import { useToast } from "../App.jsx";

export default function PeoplePanel() {
  const notify = useToast();
  const [people, setPeople] = useState([]);
  const [fs, setFs] = useState(null);
  const [selected, setSelected] = useState(null);
  const [mergeFrom, setMergeFrom] = useState(null);

  const refresh = useCallback(() => {
    api.people().then(setPeople).catch(() => {});
    api.facesStatus().then(setFs).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(() => api.facesStatus().then(setFs).catch(() => {}), 2500);
    return () => clearInterval(t);
  }, [refresh]);

  const prog = fs?.progress;
  const running = prog?.running;
  const named = people.filter((p) => !p.auto);
  const groups = people.filter((p) => p.auto);

  const detect = () => api.detectFaces(null).then(() => notify("Detection started")).catch((e) => notify(e.message));
  const recognize = () =>
    api.recognizeFaces().then((r) => { notify(`${r.suggested} new suggestions`); refresh(); }).catch((e) => notify(e.message));

  const rename = async (p, initial) => {
    const name = prompt(p.auto ? "Name this person:" : "Rename:", initial ?? (p.auto ? "" : p.name));
    if (name && name !== p.name) {
      await api.renamePerson(p.id, name);
      refresh();
      if (selected?.id === p.id) setSelected({ ...p, name, auto: 0 });
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

  if (selected) {
    return (
      <PersonDetail
        person={selected}
        onBack={() => setSelected(null)}
        onChanged={() => {
          refresh();
          api.people().then((ps) => {
            const p = ps.find((x) => x.id === selected.id);
            if (p) setSelected(p);
            else setSelected(null);
          });
        }}
        onRename={() => rename(selected)}
        onMerge={() => setMergeFrom(selected)}
        onDelete={async () => {
          if (confirm(`Delete "${selected.name}"? Photos are kept.`)) {
            await api.deletePerson(selected.id);
            setSelected(null);
            refresh();
          }
        }}
      />
    );
  }

  return (
    <div className="content">
      <div className="card">
        <div className="row">
          <b>Face recognition</b>
          <span className="pill">{fs?.engine_available ? "engine ready" : "engine not installed"}</span>
          <div className="spacer" />
          <button onClick={detect} disabled={!fs?.engine_available || running}>
            {running ? `${prog.phase} ${prog.done}/${prog.total}` : "Detect faces"}
          </button>
          <button onClick={recognize} disabled={!fs?.engine_available || running}>
            Recognise
          </button>
          <button onClick={() => api.clusterFaces().then(refresh)} disabled={running}>
            Re-group
          </button>
        </div>
        {!fs?.engine_available && (
          <p className="muted">
            Install the engine: <code>pip install -r requirements-faces.txt</code> (or
            deploy with <code>-WithFaces</code>). Photo-level people tags still work.
          </p>
        )}
        {fs?.engine_available && (
          <p className="muted">
            {fs.faces} faces · {fs.named_faces} named · {fs.suggested_faces} suggested ·{" "}
            {fs.unnamed_groups} unnamed groups · {fs.unassigned_faces} loose ·{" "}
            {fs.photos_pending} photos pending
          </p>
        )}
        {running && (
          <div className="progress">
            <div style={{ width: `${(100 * prog.done) / Math.max(prog.total, 1)}%` }} />
          </div>
        )}
      </div>

      {mergeFrom && (
        <div className="card">
          Merging <b>{mergeFrom.name}</b> into… click a target person below, or{" "}
          <button onClick={() => setMergeFrom(null)}>cancel</button>
        </div>
      )}

      <div className="row" style={{ margin: "4px 0 10px" }}>
        <h3 style={{ margin: 0 }}>People</h3>
        <div className="spacer" />
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
        {named.map((p) => (
          <PersonCard
            key={p.id}
            p={p}
            onClick={() => (mergeFrom ? doMerge(p) : setSelected(p))}
          />
        ))}
      </div>
      {named.length === 0 && <p className="muted">No named people yet.</p>}

      {groups.length > 0 && (
        <>
          <h3 style={{ margin: "22px 0 10px" }}>
            Unnamed groups <span className="muted">— click to name</span>
          </h3>
          <div className="people-grid">
            {groups.map((p) => (
              <PersonCard key={p.id} p={p} onClick={() => rename(p)} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function PersonCard({ p, onClick }) {
  return (
    <div className="person" onClick={onClick}>
      {p.cover_face ? (
        <img className="face" src={faceCropUrl(p.cover_face)} alt={p.name} />
      ) : (
        <div className="face" />
      )}
      <div className="label">
        <b>{p.name}</b>
        <span className="muted">
          {p.photo_count} photo{p.photo_count === 1 ? "" : "s"}
          {p.suggested_count ? ` · ${p.suggested_count} to review` : ""}
        </span>
      </div>
    </div>
  );
}

function PersonDetail({ person, onBack, onChanged, onRename, onMerge, onDelete }) {
  const notify = useToast();
  const [tab, setTab] = useState(person.suggested_count ? "suggested" : "confirmed");
  const [faces, setFaces] = useState([]);

  const load = useCallback(() => {
    api.personFaces(person.id, tab).then(setFaces).catch(() => setFaces([]));
  }, [person.id, tab]);
  useEffect(load, [load]);

  const act = async (fn, f) => {
    await fn(f.id);
    setFaces((xs) => xs.filter((x) => x.id !== f.id));
    onChanged();
  };

  return (
    <div className="content">
      <div className="row" style={{ marginBottom: 12 }}>
        <button onClick={onBack}>← People</button>
        <h2 style={{ margin: 0 }}>{person.name}</h2>
        {person.auto ? <span className="pill">unnamed group</span> : null}
        <div className="spacer" />
        <button onClick={onRename}>{person.auto ? "Name" : "Rename"}</button>
        <button onClick={onMerge}>Merge…</button>
        <button className="danger" onClick={onDelete}>Delete</button>
      </div>

      <div className="tabs" style={{ marginBottom: 12 }}>
        {[
          ["confirmed", `Confirmed (${person.confirmed_count})`],
          ["suggested", `To review (${person.suggested_count})`],
          ["all", "All"],
        ].map(([k, label]) => (
          <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
      </div>

      <div className="grid">
        {faces.map((f) => (
          <div key={f.id} className="tile face-tile">
            <img src={faceCropUrl(f.id)} alt="" />
            {f.similarity != null && (
              <span className="badge">{Math.round(f.similarity * 100)}%</span>
            )}
            {!f.confirmed && (
              <div className="face-actions">
                <button
                  title="Yes, this is them"
                  onClick={() => act(api.confirmFace, f)}
                >
                  ✓
                </button>
                <button
                  className="danger"
                  title="Not this person"
                  onClick={() => act(api.rejectFace, f)}
                >
                  ✕
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
      {faces.length === 0 && (
        <p className="muted">
          {tab === "suggested"
            ? "Nothing to review. Run Recognise to find more, or Detect faces on new photos."
            : "No faces here yet."}
        </p>
      )}
    </div>
  );
}

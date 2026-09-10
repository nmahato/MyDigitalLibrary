import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

/**
 * Absolutely-positioned face boxes over an image whose displayed size equals its
 * content size (parent wrapper sized to the image, img is max-width/height:100%).
 * Boxes are placed as a percentage of the natural pixel dimensions.
 */
export default function FaceOverlay({ photo, faces, people, onChanged }) {
  const [nat, setNat] = useState(null); // { w, h }
  const [menuFor, setMenuFor] = useState(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const im = new Image();
    im.onload = () => setNat({ w: im.naturalWidth, h: im.naturalHeight });
    im.src = `/api/photos/${photo.id}/file`;
    return () => (im.onload = null);
  }, [photo.id]);

  useEffect(() => {
    if (menuFor && inputRef.current) inputRef.current.focus();
  }, [menuFor]);

  if (!nat || !faces?.length) return null;

  const stateClass = (f) =>
    f.person_id
      ? f.confirmed
        ? "fb confirmed"
        : "fb suggested"
      : "fb unknown";

  const assign = async (face, name) => {
    name = name.trim();
    if (!name) return;
    await api.assignFace(face.id, { name });
    setMenuFor(null);
    onChanged?.();
  };

  return (
    <div className="face-layer">
      {faces.map((f) => {
        if (f.bbox_w == null) return null;
        const style = {
          left: `${(f.bbox_x / nat.w) * 100}%`,
          top: `${(f.bbox_y / nat.h) * 100}%`,
          width: `${(f.bbox_w / nat.w) * 100}%`,
          height: `${(f.bbox_h / nat.h) * 100}%`,
        };
        return (
          <div key={f.id} className={stateClass(f)} style={style}>
            <span
              className="fb-label"
              onClick={(e) => {
                e.stopPropagation();
                setMenuFor(menuFor === f.id ? null : f.id);
              }}
            >
              {f.name || "unknown"}
              {f.similarity != null && !f.confirmed
                ? ` ${Math.round(f.similarity * 100)}%`
                : ""}
            </span>

            {menuFor === f.id && (
              <div className="fb-menu" onClick={(e) => e.stopPropagation()}>
                <input
                  ref={inputRef}
                  list="people-names"
                  placeholder="name…"
                  defaultValue={f.name && !f.auto ? f.name : ""}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") assign(f, e.currentTarget.value);
                    if (e.key === "Escape") setMenuFor(null);
                  }}
                />
                <div className="row">
                  {f.person_id && !f.confirmed && (
                    <button
                      onClick={async () => {
                        await api.confirmFace(f.id);
                        setMenuFor(null);
                        onChanged?.();
                      }}
                    >
                      ✓ confirm
                    </button>
                  )}
                  {f.person_id && (
                    <button
                      className="danger"
                      onClick={async () => {
                        await api.rejectFace(f.id);
                        setMenuFor(null);
                        onChanged?.();
                      }}
                    >
                      detach
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
      <datalist id="people-names">
        {(people || []).filter((p) => !p.auto).map((p) => (
          <option key={p.id} value={p.name} />
        ))}
      </datalist>
    </div>
  );
}

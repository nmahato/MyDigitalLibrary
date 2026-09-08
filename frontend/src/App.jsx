import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api.js";
import Gallery from "./components/Gallery.jsx";
import PeoplePanel from "./components/PeoplePanel.jsx";
import DuplicatesView from "./components/DuplicatesView.jsx";
import ImportWizard from "./components/ImportWizard.jsx";
import SettingsPanel from "./components/SettingsPanel.jsx";

const ToastCtx = createContext(() => {});
export const useToast = () => useContext(ToastCtx);

const TABS = [
  ["library", "Library"],
  ["people", "People"],
  ["duplicates", "Duplicates"],
  ["import", "Import"],
  ["settings", "Settings"],
];

export default function App() {
  const [tab, setTab] = useState("library");
  const [toast, setToast] = useState(null);
  const [status, setStatus] = useState(null);

  const notify = useCallback((msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  }, []);

  const refreshStatus = useCallback(async () => {
    try {
      setStatus(await api.status());
    } catch (e) {
      notify("Backend not reachable — is it running on :8077?");
    }
  }, [notify]);

  useEffect(() => {
    refreshStatus();
    const t = setInterval(refreshStatus, 4000);
    return () => clearInterval(t);
  }, [refreshStatus]);

  const scan = status?.scan;
  const scanning = scan?.running;

  return (
    <ToastCtx.Provider value={notify}>
      <div className="app">
        <div className="topbar">
          <h1>📷 PhotoLibrary</h1>
          <div className="tabs">
            {TABS.map(([id, label]) => (
              <button
                key={id}
                className={tab === id ? "active" : ""}
                onClick={() => setTab(id)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="spacer" />
          {status && (
            <span className="muted">
              {status.counts.total || 0} items · {status.counts.images || 0} photos ·{" "}
              {status.counts.videos || 0} videos
            </span>
          )}
          <button
            onClick={async () => {
              await api.scan(false);
              notify("Rescan started");
              refreshStatus();
            }}
            disabled={scanning}
          >
            {scanning ? `Scanning… ${scan.done}/${scan.total}` : "Rescan"}
          </button>
        </div>

        {scanning && (
          <div className="progress">
            <div style={{ width: `${(100 * scan.done) / Math.max(scan.total, 1)}%` }} />
          </div>
        )}

        <div className="body">
          {tab === "library" && <Gallery status={status} />}
          {tab === "people" && <PeoplePanel />}
          {tab === "duplicates" && <DuplicatesView />}
          {tab === "import" && <ImportWizard onDone={refreshStatus} />}
          {tab === "settings" && (
            <SettingsPanel status={status} onSaved={refreshStatus} />
          )}
        </div>

        {toast && <div className="toast">{toast}</div>}
      </div>
    </ToastCtx.Provider>
  );
}

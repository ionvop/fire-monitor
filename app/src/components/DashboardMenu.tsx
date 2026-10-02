import { useState } from "react";
import DashboardSettingsModal from "./DashboardSettingsModal";
import {
  loadDashboardUrls,
  resetDashboardUrls,
  saveDashboardUrls,
  type DashboardUrls,
} from "../services/dashboardUrls";

/** Navbar button that links to the controller dashboard (LAN or dev tunnel). */
export default function DashboardMenu() {
  const [urls, setUrls] = useState<DashboardUrls>(loadDashboardUrls);
  const [settingsOpen, setSettingsOpen] = useState(false);

  function handleSave(next: DashboardUrls) {
    saveDashboardUrls(next);
    setUrls(next);
    setSettingsOpen(false);
  }

  function handleReset() {
    resetDashboardUrls();
    setUrls(loadDashboardUrls());
  }

  return (
    <>
      <div className="dropdown dropdown-end">
        <button
          type="button"
          tabIndex={0}
          className="btn btn-sm btn-outline"
          aria-label="Open controller dashboard"
        >
          📊 Dashboard
        </button>
        <ul
          tabIndex={0}
          className="dropdown-content menu bg-base-100 rounded-box z-20 mt-2 w-64 p-2 shadow"
        >
          <li>
            <a href={urls.lan} target="_blank" rel="noopener noreferrer">
              <span className="flex flex-col items-start">
                <span className="font-medium">Same network</span>
                <span className="text-xs opacity-60 break-all">{urls.lan}</span>
              </span>
            </a>
          </li>
          <li>
            <a href={urls.tunnel} target="_blank" rel="noopener noreferrer">
              <span className="flex flex-col items-start">
                <span className="font-medium">Dev tunnel</span>
                <span className="text-xs opacity-60 break-all">
                  {urls.tunnel}
                </span>
              </span>
            </a>
          </li>
          <li>
            <button type="button" onClick={() => setSettingsOpen(true)}>
              ⚙️ Edit URLs
            </button>
          </li>
        </ul>
      </div>

      <DashboardSettingsModal
        open={settingsOpen}
        urls={urls}
        onSave={handleSave}
        onReset={handleReset}
        onClose={() => setSettingsOpen(false)}
      />
    </>
  );
}

import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  DEFAULT_DASHBOARD_URLS,
  normalizeUrl,
  type DashboardUrls,
} from "../services/dashboardUrls";

interface DashboardSettingsModalProps {
  /** Whether the modal is currently shown. */
  open: boolean;
  /** The URLs to edit (already loaded from storage). */
  urls: DashboardUrls;
  /** Called with validated URLs when the user saves. */
  onSave: (urls: DashboardUrls) => void;
  /** Called when the user restores the built-in defaults. */
  onReset: () => void;
  /** Called when the modal is dismissed without saving. */
  onClose: () => void;
}

/** Modal for editing the LAN and dev-tunnel dashboard URLs. */
export default function DashboardSettingsModal({
  open,
  urls,
  onSave,
  onReset,
  onClose,
}: DashboardSettingsModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [lan, setLan] = useState(urls.lan);
  const [tunnel, setTunnel] = useState(urls.tunnel);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      setLan(urls.lan);
      setTunnel(urls.tunnel);
      setError(null);
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open, urls]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const nextLan = normalizeUrl(lan, "http");
    const nextTunnel = normalizeUrl(tunnel, "https");

    if (!nextLan || !nextTunnel) {
      setError(
        "Enter a valid http(s) URL for both fields, e.g. 192.168.4.2:5000.",
      );
      return;
    }

    setError(null);
    onSave({ lan: nextLan, tunnel: nextTunnel });
  }

  function handleReset() {
    setLan(DEFAULT_DASHBOARD_URLS.lan);
    setTunnel(DEFAULT_DASHBOARD_URLS.tunnel);
    setError(null);
    onReset();
  }

  return (
    <dialog ref={dialogRef} className="modal" onClose={onClose}>
      <div className="modal-box">
        <h3 className="font-bold text-lg">Dashboard URLs</h3>
        <p className="text-sm opacity-70 mt-1">
          Point these at the controller dashboard. The LAN URL is used on the
          same network; the dev tunnel URL works over the internet.
        </p>

        <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
          <fieldset className="fieldset">
            <legend className="fieldset-legend">LAN address</legend>
            <input
              type="text"
              className="input w-full"
              value={lan}
              onChange={(e) => setLan(e.target.value)}
              placeholder={DEFAULT_DASHBOARD_URLS.lan}
              spellCheck={false}
              autoComplete="off"
            />
          </fieldset>

          <fieldset className="fieldset">
            <legend className="fieldset-legend">Dev tunnel URL</legend>
            <input
              type="text"
              className="input w-full"
              value={tunnel}
              onChange={(e) => setTunnel(e.target.value)}
              placeholder={DEFAULT_DASHBOARD_URLS.tunnel}
              spellCheck={false}
              autoComplete="off"
            />
          </fieldset>

          {error && <p className="text-sm text-error">{error}</p>}

          <div className="modal-action">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={handleReset}
            >
              Reset to defaults
            </button>
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Save
            </button>
          </div>
        </form>
      </div>
      <form method="dialog" className="modal-backdrop">
        <button onClick={onClose}>close</button>
      </form>
    </dialog>
  );
}

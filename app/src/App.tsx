import { useEffect, useState } from "react";
import { fetchFireHistory } from "./api/client";
import { POLL_INTERVAL_MS, MAX_ALERTS } from "./config";
import type { FireAlert } from "./types";
import ConnectionStatus from "./components/ConnectionStatus";
import AlertCard from "./components/AlertCard";
import EmptyView from "./components/EmptyView";
import ErrorView from "./components/ErrorView";
import SubscribeButton from "./components/SubscribeButton";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; alerts: FireAlert[] };

export default function App() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [live, setLive] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const alerts = await fetchFireHistory();
        if (cancelled) return;
        setState({ kind: "ready", alerts: alerts.slice(0, MAX_ALERTS) });
        setLive(true);
      } catch (err) {
        if (cancelled) return;
        setLive(false);
        setState({
          kind: "error",
          message: err instanceof Error ? err.message : String(err),
        });
      }
    }

    load();
    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="min-h-screen bg-base-200">
      <div className="navbar bg-base-100 shadow-sm sticky top-0 z-10">
        <div className="flex-1">
          <span className="text-xl font-bold text-orange-600">
            🔥 Fire Monitor
          </span>
        </div>
        <div className="flex-none flex items-center gap-3">
          <SubscribeButton />
          <ConnectionStatus live={live} />
        </div>
      </div>

      <main className="max-w-2xl mx-auto p-4">
        {state.kind === "loading" && (
          <div className="flex justify-center py-16">
            <span className="loading loading-spinner loading-lg text-orange-600" />
          </div>
        )}

        {state.kind === "error" && <ErrorView message={state.message} />}

        {state.kind === "ready" &&
          (state.alerts.length === 0 ? (
            <EmptyView />
          ) : (
            <ul className="space-y-3">
              {state.alerts.map((alert) => (
                <AlertCard key={alert.id} alert={alert} />
              ))}
            </ul>
          ))}
      </main>
    </div>
  );
}
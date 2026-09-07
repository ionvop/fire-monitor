import { useState } from "react";
import { subscribeToPush } from "../services/push";

type SubscribeState =
  | { kind: "idle" }
  | { kind: "subscribing" }
  | { kind: "subscribed" }
  | { kind: "error"; message: string };

/** Requests notification permission and registers the Web Push subscription. */
export default function SubscribeButton() {
  const [state, setState] = useState<SubscribeState>({ kind: "idle" });

  async function handleClick() {
    setState({ kind: "subscribing" });
    try {
      await subscribeToPush();
      setState({ kind: "subscribed" });
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }

  if (state.kind === "subscribed") {
    return (
      <span className="badge badge-success gap-1">
        <span className="w-2 h-2 rounded-full bg-success" />
        Notifications on
      </span>
    );
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        className="btn btn-sm btn-primary"
        onClick={handleClick}
        disabled={state.kind === "subscribing"}
      >
        {state.kind === "subscribing" ? (
          <>
            <span className="loading loading-spinner loading-xs" />
            Subscribing…
          </>
        ) : (
          "Enable notifications"
        )}
      </button>
      {state.kind === "error" && (
        <span className="text-xs text-error">{state.message}</span>
      )}
    </div>
  );
}
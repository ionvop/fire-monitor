import type { FireAlert } from "../types";

interface AlertCardProps {
  alert: FireAlert;
}

/** A single fire-detection alert card, mirroring the Dart app's ListTile. */
export default function AlertCard({ alert }: AlertCardProps) {
  const isActive = alert.status === "detected";
  const accent = isActive ? "error" : "primary";

  return (
    <li className="card bg-base-100 shadow-sm">
      <div className="card-body flex-row items-start gap-4 p-4">
        <div
          className={`avatar placeholder ${
            isActive ? "bg-error/15" : "bg-primary/15"
          } rounded-full`}
        >
          <div className="w-12 rounded-full">
            <span className={`text-2xl text-${accent}`}>
              {isActive ? "🔥" : "✅"}
            </span>
          </div>
        </div>

        <div className="flex-1">
          <h3
            className={`font-bold ${
              isActive ? "text-error" : "text-primary"
            }`}
          >
            {isActive ? "Fire detected" : "Fire resolved"}
          </h3>
          <p className="text-sm opacity-70">{formatTimestamp(alert.timestamp)}</p>
          {alert.confidence_score != null && (
            <p className="text-sm">
              Confidence: {Math.round(alert.confidence_score * 100)}%
            </p>
          )}
          {(alert.x != null || alert.y != null) && (
            <p className="text-sm">
              Position: X {alert.x != null ? Math.round(alert.x) : "?"}° · Y{" "}
              {alert.y != null ? Math.round(alert.y) : "?"}°
            </p>
          )}
        </div>
      </div>
    </li>
  );
}

function formatTimestamp(ts: string): string {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return ts;
  const pad = (n: number) => n.toString().padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  );
}
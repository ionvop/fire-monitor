interface ConnectionStatusProps {
  /** Whether the most recent API poll succeeded. */
  live: boolean;
}

/** A small badge showing whether the app is receiving live updates. */
export default function ConnectionStatus({ live }: ConnectionStatusProps) {
  return (
    <span
      className={`badge badge-sm gap-1 ${
        live ? "badge-success" : "badge-warning"
      }`}
    >
      <span
        className={`w-2 h-2 rounded-full ${
          live ? "bg-success" : "bg-warning"
        }`}
      />
      {live ? "live" : "offline"}
    </span>
  );
}
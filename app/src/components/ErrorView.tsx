interface ErrorViewProps {
  message: string;
}

/** Shown when the fire-history list fails to load. */
export default function ErrorView({ message }: ErrorViewProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <span className="text-6xl mb-4">⚠️</span>
      <h2 className="text-lg font-semibold text-error">
        Could not load alerts
      </h2>
      <p className="text-sm opacity-70 mt-1 break-all">{message}</p>
    </div>
  );
}
/** Shown when the fire-history list is empty. */
export default function EmptyView() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <span className="text-6xl mb-4">🛡️</span>
      <h2 className="text-lg font-semibold">No fire alerts yet</h2>
      <p className="text-sm opacity-70 mt-1">
        Waiting for the controller to report a fire…
      </p>
    </div>
  );
}
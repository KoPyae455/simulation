import type { HealthStatus } from "../types/api";
import { ErrorMessage } from "./ErrorMessage";
import { LoadingState } from "./LoadingState";

interface ApiStatusProps {
  status: HealthStatus | null;
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function ApiStatus({ status, isLoading, error, onRefresh }: ApiStatusProps) {
  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900 p-4" aria-label="API status">
      <div className="flex items-center justify-between gap-4">
        <h2 className="font-semibold text-slate-100">API status</h2>
        <button className="rounded bg-slate-700 px-3 py-1 text-sm hover:bg-slate-600" type="button" onClick={onRefresh}>
          Refresh
        </button>
      </div>
      {isLoading && <LoadingState label="API status" />}
      {error !== null && <ErrorMessage message={error} />}
      {status !== null && (
        <dl className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          <div><dt className="text-slate-400">Status</dt><dd className="font-medium text-emerald-400">{status.status}</dd></div>
          <div><dt className="text-slate-400">Application</dt><dd>{status.app_name}</dd></div>
          <div><dt className="text-slate-400">Version</dt><dd>{status.app_version}</dd></div>
          <div><dt className="text-slate-400">Environment</dt><dd>{status.environment}</dd></div>
        </dl>
      )}
    </section>
  );
}

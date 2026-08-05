import { ProgressBar } from "./ProgressBar";

interface StateCardProps {
  label: string;
  value: number | null;
}

export function StateCard({ label, value }: StateCardProps) {
  return (
    <article className="rounded-md border border-slate-700 bg-slate-900 p-3">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium capitalize text-slate-200">{label}</h3>
        <span className="text-sm font-semibold text-slate-100">{value === null ? "N/A" : `${value}/100`}</span>
      </div>
      {value === null ? <p className="text-xs text-slate-500">Not exposed by the API</p> : <ProgressBar value={value} />}
    </article>
  );
}

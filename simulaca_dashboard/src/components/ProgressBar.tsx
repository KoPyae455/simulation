interface ProgressBarProps {
  value: number;
}

export function ProgressBar({ value }: ProgressBarProps) {
  const clampedValue = Math.max(0, Math.min(100, value));
  const barColor = clampedValue >= 80 ? "bg-red-500" : clampedValue >= 50 ? "bg-amber-400" : "bg-emerald-500";

  return (
    <div className="h-2 overflow-hidden rounded-full bg-slate-700" role="progressbar" aria-valuenow={clampedValue} aria-valuemin={0} aria-valuemax={100}>
      <div className={`h-full rounded-full ${barColor}`} style={{ width: `${clampedValue}%` }} />
    </div>
  );
}

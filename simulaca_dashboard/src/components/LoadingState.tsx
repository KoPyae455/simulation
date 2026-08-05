interface LoadingStateProps {
  label: string;
}

export function LoadingState({ label }: LoadingStateProps) {
  return <p className="py-4 text-sm text-slate-400">Loading {label}…</p>;
}

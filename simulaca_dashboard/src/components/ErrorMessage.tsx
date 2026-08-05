interface ErrorMessageProps {
  message: string;
}

export function ErrorMessage({ message }: ErrorMessageProps) {
  return <p className="rounded-md border border-red-900 bg-red-950/60 p-3 text-sm text-red-200">{message}</p>;
}

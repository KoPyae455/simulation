import { FormEvent, useState } from "react";

interface AgentCreateFormProps {
  isSubmitting: boolean;
  onCreate: (name: string) => Promise<void>;
}

export function AgentCreateForm({ isSubmitting, onCreate }: AgentCreateFormProps) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const trimmedName = name.trim();

    if (trimmedName.length === 0) {
      setError("An agent name is required.");
      return;
    }

    setError(null);
    try {
      await onCreate(trimmedName);
      setName("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to create the agent.");
    }
  }

  return (
    <form className="rounded-lg border border-slate-700 bg-slate-900 p-4" onSubmit={(event) => void handleSubmit(event)}>
      <h2 className="font-semibold text-slate-100">Create agent</h2>
      <p className="mt-1 text-xs text-slate-400">New agents start with all current needs at zero.</p>
      <label className="mt-3 block text-sm text-slate-300" htmlFor="agent-name">Name</label>
      <div className="mt-1 flex gap-2">
        <input id="agent-name" className="min-w-0 flex-1 rounded border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-sky-400" value={name} onChange={(event) => setName(event.target.value)} maxLength={100} disabled={isSubmitting} />
        <button className="rounded bg-sky-600 px-3 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Creating…" : "Create"}
        </button>
      </div>
      {error !== null && <p className="mt-2 text-sm text-red-300">{error}</p>}
    </form>
  );
}

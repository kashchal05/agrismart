import { useState } from "react";
import { api, setToken } from "./api";

export function Auth({ onAuthed }: { onAuthed: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const fn = mode === "register" ? api.register : api.login;
      const { access_token } = await fn(email, password);
      setToken(access_token);
      onAuthed();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <h1>Agrismart 2.0</h1>
      <p className="sub">Satellite crop intelligence. Draw a field to get started.</p>
      <form onSubmit={submit}>
        {error && <div className="error">{error}</div>}
        <input
          type="email" placeholder="Email" value={email} required
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          type="password" placeholder="Password (min 8 chars)" value={password}
          required minLength={8} onChange={(e) => setPassword(e.target.value)}
        />
        <button type="submit" disabled={busy}>
          {busy ? "…" : mode === "register" ? "Create account" : "Log in"}
        </button>
      </form>
      <div className="toggle">
        {mode === "register" ? "Already have an account? " : "Need an account? "}
        <a onClick={() => setMode(mode === "register" ? "login" : "register")}>
          {mode === "register" ? "Log in" : "Sign up"}
        </a>
      </div>
    </div>
  );
}

import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";

const API_URL = "http://localhost:8000";

type ImportResult = {
  created_count: number;
  duplicate_count: number;
  total_found: number;
};

async function readError(res: Response) {
  try {
    const data = await res.json();
    return data.detail || "Request failed";
  } catch {
    return "Request failed";
  }
}

export default function AddContacts() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [adding, setAdding] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function addContact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setError("");

    const normalizedEmail = email.trim();
    if (!normalizedEmail) {
      setError("Enter an email address");
      return;
    }

    setAdding(true);

    try {
      const res = await fetch(`${API_URL}/contacts/add`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          email: normalizedEmail,
          name: name.trim() || null
        })
      });

      if (!res.ok) {
        throw new Error(await readError(res));
      }

      const contact = await res.json();
      setEmail("");
      setName("");
      setMessage(`Added ${contact.email}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add contact");
    } finally {
      setAdding(false);
    }
  }

  async function importContacts(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setError("");

    if (!file) {
      setError("Choose a CSV or TXT file");
      return;
    }

    setImporting(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${API_URL}/contacts/import`, {
        method: "POST",
        credentials: "include",
        body: formData
      });

      if (!res.ok) {
        throw new Error(await readError(res));
      }

      const result: ImportResult = await res.json();
      setFile(null);
      setMessage(
        `Imported ${result.created_count} new contacts. ${result.duplicate_count} duplicates skipped from ${result.total_found} emails.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import contacts");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="min-h-full bg-app-bg p-6 text-app-text md:p-10">
      <header className="mb-6 flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
        <div>
          <h1 className="m-0 text-4xl font-black md:text-[40px]">Add contacts</h1>
          <p className="mt-2 text-app-muted">
            Add one contact manually or import a CSV/TXT file.
          </p>
        </div>
        <button type="button" onClick={() => navigate("/contacts")} className="btn">
          Back to contacts
        </button>
      </header>

      {message && (
        <div className="mb-5 rounded-lg border border-app-success/30 bg-app-success/10 px-4 py-3 font-bold text-app-success">
          {message}
        </div>
      )}
      {error && (
        <div className="mb-5 rounded-lg border border-app-error/30 bg-app-error/10 px-4 py-3 font-bold text-app-error">
          {error}
        </div>
      )}

      <div className="grid max-w-250 gap-6 xl:grid-cols-[minmax(320px,420px)_minmax(360px,1fr)]">
        <section className="panel p-6">
          <h2 className="mb-4 mt-0 text-2xl font-black">Add one contact</h2>
          <form onSubmit={addContact} className="grid gap-4">
            <label className="block">
              <span className="mb-1.5 block text-sm font-extrabold text-app-muted">Email</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="field"
                placeholder="person@example.com"
                required
              />
            </label>

            <label className="block">
              <span className="mb-1.5 block text-sm font-extrabold text-app-muted">Name</span>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="field"
                placeholder="Jane Smith"
              />
            </label>

            <button type="submit" disabled={adding} className="btn btn-primary justify-self-start">
              {adding ? "Adding..." : "Add contact"}
            </button>
          </form>
        </section>

        <section className="panel p-6">
          <h2 className="mb-4 mt-0 text-2xl font-black">Import contacts</h2>
          <form onSubmit={importContacts} className="grid gap-4">
            <label className="block">
              <span className="mb-1.5 block text-sm font-extrabold text-app-muted">
                CSV or TXT file
              </span>
              <input
                key={file ? file.name : "empty-file"}
                type="file"
                accept=".csv,.txt,text/csv,text/plain"
                onChange={(event) => setFile(event.target.files?.[0] || null)}
                className="field"
              />
            </label>

            <div className="rounded-lg border border-app-border bg-app-soft p-4 text-sm text-app-muted">
              File should contain an email column, or one email address per line.
            </div>

            <button
              type="submit"
              disabled={importing}
              className="btn btn-primary justify-self-start">
              {importing ? "Importing..." : "Import contacts"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

type Contact = {
  id: string;
  email: string;
  name?: string;
  created_at?: string;
};

const API_URL = "http://localhost:8000";
const EMAIL_PATTERN = /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i;

function buildRecipientCsv(emails: string[]) {
  const rows = emails.map((email) => `"${email.replaceAll('"', '""')}"`);
  return `email\n${rows.join("\n")}`;
}

export default function CreateCampaign() {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [fromEmail, setFromEmail] = useState("");
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selectedEmails, setSelectedEmails] = useState<string[]>([]);
  const [loadingContacts, setLoadingContacts] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const selectedCount = selectedEmails.length;
  const validContacts = useMemo(
    () => contacts.filter((contact) => EMAIL_PATTERN.test(contact.email)),
    [contacts]
  );
  const allEmails = useMemo(() => validContacts.map((contact) => contact.email), [validContacts]);

  async function loadContacts() {
    setLoadingContacts(true);
    setError("");

    try {
      const res = await fetch(`${API_URL}/contacts`, {
        method: "GET",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to load contacts");
      }

      setContacts(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load contacts");
    } finally {
      setLoadingContacts(false);
    }
  }

  useEffect(() => {
    loadContacts();
  }, []);

  function toggleEmail(email: string) {
    setSelectedEmails((current) => {
      if (current.includes(email)) {
        return current.filter((selectedEmail) => selectedEmail !== email);
      }

      return [...current, email];
    });
  }

  function selectAllContacts() {
    setSelectedEmails(allEmails);
  }

  function clearSelectedContacts() {
    setSelectedEmails([]);
  }

  const onButtonClick = async () => {
    setError("");

    if (!subject.trim() || !body.trim() || !fromEmail.trim()) {
      setError("Subject, body, and from email are required");
      return;
    }

    if (!EMAIL_PATTERN.test(fromEmail.trim())) {
      setError("From email is invalid");
      return;
    }

    if (selectedEmails.length === 0) {
      setError("Mark at least one email to send");
      return;
    }

    setSaving(true);

    try {
      const formData = new FormData();

      formData.append("subject", subject.trim());
      formData.append("body", body);
      formData.append("from_email", fromEmail.trim());
      formData.append(
        "csv_file",
        new Blob([buildRecipientCsv(selectedEmails)], {
          type: "text/csv"
        }),
        "recipients.csv"
      );

      const res = await fetch(`${API_URL}/campaigns/create`, {
        method: "POST",
        credentials: "include",
        body: formData
      });

      if (!res.ok) {
        throw new Error("Failed to create campaign");
      }

      setSubject("");
      setBody("");
      setSelectedEmails([]);
      alert("Campaign created successfully!");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create campaign");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-full w-full bg-app-bg p-6 text-app-text md:p-10">
      <header className="mb-6">
        <h1 className="m-0 text-4xl font-black">Create Campaign</h1>
        <p className="mt-2 text-app-muted">{selectedCount} recipients marked</p>
      </header>

      <div className="grid max-w-[1100px] gap-5 xl:grid-cols-[minmax(320px,1fr)_minmax(280px,420px)]">
        <div className="flex flex-col gap-3">
          <input
            placeholder="Subject"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            className="field"
          />

          <textarea
            placeholder="Email Body"
            value={body}
            rows={10}
            onChange={(event) => setBody(event.target.value)}
            className="field"
          />

          <input
            type="email"
            placeholder="From Email"
            value={fromEmail}
            onChange={(event) => setFromEmail(event.target.value)}
            className="field"
          />

          <button type="button" onClick={onButtonClick} disabled={saving} className="btn btn-primary">
            {saving ? "Creating..." : "Create Campaign"}
          </button>
        </div>

        <section className="overflow-hidden rounded-lg border border-app-border bg-app-surface">
          <div className="flex items-center justify-between gap-3 border-b border-app-border px-4 py-3.5">
            <strong>Recipients</strong>
            <div className="flex gap-2">
              <button type="button" className="btn py-2" onClick={selectAllContacts} disabled={validContacts.length === 0}>
                Select All
              </button>
              <button type="button" className="btn py-2" onClick={clearSelectedContacts} disabled={selectedCount === 0}>
                Clear
              </button>
            </div>
          </div>

          {loadingContacts && <p className="p-4 text-app-muted">Loading contacts...</p>}

          {!loadingContacts && contacts.length === 0 && (
            <div className="p-4 text-app-muted">
              No contacts yet.{" "}
              <Link to="/contacts" className="text-app-text">
                Add emails
              </Link>
            </div>
          )}

          {!loadingContacts &&
            contacts.map((contact) => {
              const isValid = EMAIL_PATTERN.test(contact.email);

              return (
                <label
                  key={contact.id}
                  className={[
                    "flex items-center gap-2.5 border-b border-app-border px-4 py-3 last:border-b-0",
                    isValid ? "cursor-pointer text-app-text" : "cursor-not-allowed text-app-muted"
                  ].join(" ")}>
                  <input
                    type="checkbox"
                    disabled={!isValid}
                    checked={selectedEmails.includes(contact.email)}
                    onChange={() => toggleEmail(contact.email)}
                    className="h-4 w-4 accent-app-accent"
                  />
                  <span>{contact.email}</span>
                  {!isValid && <span className="ml-auto text-app-error">invalid</span>}
                </label>
              );
            })}
        </section>
      </div>

      {error && <p className="mt-5 text-app-error">{error}</p>}
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import SelectField from "../components/SelectField";

type Contact = {
  id: string;
  email: string;
  name?: string;
  created_at?: string;
};

const API_URL = "http://localhost:8000";

function splitName(name?: string) {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  return {
    firstName: parts[0] || "",
    lastName: parts.slice(1).join(" ")
  };
}

function initials(contact: Contact) {
  const { firstName, lastName } = splitName(contact.name);
  const source = `${firstName[0] || ""}${lastName[0] || ""}` || contact.email.slice(0, 2);
  return source.toUpperCase();
}

function formatDate(value?: string) {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

export default function Contacts() {
  const navigate = useNavigate();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState("");
  const [search, setSearch] = useState("");

  async function loadContacts() {
    setLoading(true);
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
      setLoading(false);
    }
  }

  useEffect(() => {
    loadContacts();
  }, []);

  const filteredContacts = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) {
      return contacts;
    }

    return contacts.filter((contact) => {
      const { firstName, lastName } = splitName(contact.name);
      return (
        contact.email.toLowerCase().includes(term) ||
        firstName.toLowerCase().includes(term) ||
        lastName.toLowerCase().includes(term)
      );
    });
  }, [contacts, search]);

  async function deleteContact(contact: Contact) {
    const shouldDelete = window.confirm(`Delete ${contact.email}?`);
    if (!shouldDelete) {
      return;
    }

    setDeletingId(contact.id);
    setError("");

    try {
      const res = await fetch(`${API_URL}/contacts/${contact.id}`, {
        method: "DELETE",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to delete contact");
      }

      setContacts((current) => current.filter((savedContact) => savedContact.id !== contact.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete contact");
    } finally {
      setDeletingId("");
    }
  }

  return (
    <div className="min-h-full bg-app-bg p-6 text-app-text md:p-10">
      <header className="mb-6 flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
        <div>
          <h1 className="m-0 text-4xl font-black md:text-[40px]">Contacts</h1>
          <p className="mt-2 text-app-muted">{contacts.length} subscribed contacts</p>
        </div>
        <button
          type="button"
          onClick={() => navigate("/contacts/add")}
          className="inline-flex rounded-full bg-app-accent px-5 py-3 font-extrabold text-app-text no-underline hover:bg-app-accent-hover">
          Add contacts
        </button>
      </header>

      <section className="panel overflow-hidden">
        <div className="grid gap-3 border-b border-app-border p-4 lg:grid-cols-[minmax(220px,1fr)_160px_150px_130px]">
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search contacts"
            className="field"
          />
          <SelectField
            ariaLabel="Status"
            value="subscribed"
            options={[{ value: "subscribed", label: "subscribed" }]}
          />
          <SelectField
            ariaLabel="Segment"
            value="segment"
            options={[{ value: "segment", label: "Segment" }]}
          />
          <SelectField
            ariaLabel="Tags"
            value="tags"
            options={[{ value: "tags", label: "Tags" }]}
          />
        </div>

        <div className="border-b border-app-border px-4 py-3 text-app-muted">
          {filteredContacts.length} results - 50 per page
        </div>

        {loading && <p className="p-5 text-app-muted">Loading contacts...</p>}
        {error && <p className="p-5 text-app-error">{error}</p>}

        {!loading && !error && filteredContacts.length === 0 && (
          <div className="p-8 text-app-muted">
            <h2 className="mt-0 text-app-text">No contacts yet</h2>
            <p>Import a CSV file to start building your audience.</p>
            <button
              type="button"
              onClick={() => navigate("/contacts/add")}
              className="inline-flex rounded-full bg-app-accent px-4 py-2.5 font-extrabold text-app-text no-underline hover:bg-app-accent-hover">
              Add contact
            </button>
          </div>
        )}

        {filteredContacts.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] border-collapse">
              <thead>
                <tr className="bg-app-panel">
                  {[
                    "Email address",
                    "First name",
                    "Last name",
                    "Created at",
                    "Last updated at",
                    ""
                  ].map((heading) => (
                    <th
                      key={heading}
                      className="border-b border-app-border px-4 py-3 text-left text-[13px] font-extrabold text-app-muted">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredContacts.map((contact) => {
                  const { firstName, lastName } = splitName(contact.name);
                  return (
                    <tr key={contact.id}>
                      <td className="border-b border-app-border px-4 py-3.5">
                        <div className="flex items-center gap-2.5">
                          <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-[#FFF3A5] font-black">
                            {initials(contact)}
                          </span>
                          <span className="font-extrabold text-[#6B5200]">{contact.email}</span>
                        </div>
                      </td>
                      <td className="border-b border-app-border px-4 py-3.5">{firstName || "-"}</td>
                      <td className="border-b border-app-border px-4 py-3.5">{lastName || "-"}</td>
                      <td className="border-b border-app-border px-4 py-3.5">
                        {formatDate(contact.created_at)}
                      </td>
                      <td className="border-b border-app-border px-4 py-3.5">
                        {formatDate(contact.created_at)}
                      </td>
                      <td className="border-b border-app-border px-4 py-3.5">
                        <button
                          type="button"
                          onClick={() => deleteContact(contact)}
                          disabled={deletingId === contact.id}
                          className="rounded-lg border border-[#E6B7B7] bg-[#FFF5F5] px-4 py-2 font-extrabold text-app-error">
                          {deletingId === contact.id ? "Deleting..." : "Delete"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

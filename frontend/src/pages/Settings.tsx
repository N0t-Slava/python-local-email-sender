import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

type DomainStatus = "unknown" | "pending" | "valid" | "invalid" | "missing" | "failed" | string;

type SendingDomain = {
  id: string;
  user_id: string;
  domain: string;
  mail_from_domain: string;
  verification_status: DomainStatus;
  dkim_status: DomainStatus;
  spf_status: DomainStatus;
  dmarc_status: DomainStatus;
  mail_from_status: DomainStatus;
  last_checked_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type DomainDnsRecord = {
  type: string;
  host: string;
  value: string;
  purpose: string;
};

type DomainSetupRecords = {
  domain_id: string;
  domain: string;
  mail_from_domain: string;
  records: DomainDnsRecord[];
};

type SendingCheckResult = {
  can_send: boolean;
  from_email: string;
  domain: string;
  sending_domain: SendingDomain | null;
  blockers: string[];
  warnings: string[];
};

const API_URL = "http://localhost:8000";

function normalizeDomainInput(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .split("/", 1)[0]
    .replace(/^\.+|\.+$/g, "");
}

function defaultMailFromDomain(domain: string) {
  return domain ? `mail.${domain}` : "";
}

function formatDate(value?: string | null) {
  if (!value) {
    return "Never";
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function statusClass(status: DomainStatus) {
  switch (status) {
    case "valid":
      return "border-app-success/30 bg-app-success/10 text-app-success";
    case "pending":
    case "unknown":
      return "border-app-warning/40 bg-app-warning/15 text-app-text";
    case "invalid":
    case "missing":
    case "failed":
      return "border-app-error/30 bg-app-error/10 text-app-error";
    default:
      return "border-app-border bg-app-panel text-app-muted";
  }
}

function formatStatus(status: DomainStatus) {
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function StatusBadge({ status }: { status: DomainStatus }) {
  return (
    <span
      className={`inline-flex w-fit rounded-lg border px-2.5 py-1 text-xs font-black ${statusClass(status)}`}>
      {formatStatus(status)}
    </span>
  );
}

function StatusRow({ label, status }: { label: string; status: DomainStatus }) {
  return (
    <div className="flex min-h-11 items-center justify-between gap-3 border-b border-app-border py-2 last:border-b-0">
      <span className="text-sm font-extrabold text-app-muted">{label}</span>
      <StatusBadge status={status} />
    </div>
  );
}

function DnsRecord({ type, host, value }: { type: string; host: string; value: string }) {
  return (
    <div className="grid gap-2 rounded-lg border border-app-border bg-app-soft p-4 text-sm lg:grid-cols-[72px_minmax(140px,220px)_minmax(0,1fr)]">
      <span className="font-black leading-6">{type}</span>
      <code className="min-w-0 wrap-break-word leading-6 text-app-muted">{host}</code>
      <code className="min-w-0 whitespace-pre-wrap wrap-break-word leading-6 text-app-text">
        {value}
      </code>
    </div>
  );
}

export default function Settings() {
  const [domains, setDomains] = useState<SendingDomain[]>([]);
  const [setupRecordsByDomainId, setSetupRecordsByDomainId] = useState<
    Record<string, DomainDnsRecord[]>
  >({});
  const [domainInput, setDomainInput] = useState("");
  const [mailFromInput, setMailFromInput] = useState("");
  const [mailFromTouched, setMailFromTouched] = useState(false);
  const [checkFromEmail, setCheckFromEmail] = useState("");
  const [checkingFromEmail, setCheckingFromEmail] = useState(false);
  const [checkResult, setCheckResult] = useState<SendingCheckResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshingDomainId, setRefreshingDomainId] = useState("");
  const [deletingDomainId, setDeletingDomainId] = useState("");
  const [error, setError] = useState("");

  const normalizedDomain = useMemo(() => normalizeDomainInput(domainInput), [domainInput]);
  const suggestedMailFromDomain = useMemo(
    () => defaultMailFromDomain(normalizedDomain),
    [normalizedDomain]
  );

  const loadSetupRecords = useCallback(async (domainIds: string[]) => {
    const entries = await Promise.all(
      domainIds.map(async (domainId) => {
        const res = await fetch(`${API_URL}/domains/${domainId}/setup-records`, {
          method: "GET",
          credentials: "include"
        });

        if (!res.ok) {
          return [domainId, []] as const;
        }

        const payload = (await res.json()) as DomainSetupRecords;
        return [domainId, payload.records] as const;
      })
    );

    setSetupRecordsByDomainId(Object.fromEntries(entries));
  }, []);

  const loadDomains = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API_URL}/domains`, {
        method: "GET",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to load sending domains");
      }

      const loadedDomains = (await res.json()) as SendingDomain[];
      setDomains(loadedDomains);
      await loadSetupRecords(loadedDomains.map((domain) => domain.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sending domains");
    } finally {
      setLoading(false);
    }
  }, [loadSetupRecords]);

  useEffect(() => {
    loadDomains();
  }, [loadDomains]);

  useEffect(() => {
    if (!mailFromTouched) {
      setMailFromInput(suggestedMailFromDomain);
    }
  }, [mailFromTouched, suggestedMailFromDomain]);

  async function addDomain(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const domain = normalizeDomainInput(domainInput);
    const mailFromDomain = normalizeDomainInput(mailFromInput);

    if (!domain || !mailFromDomain) {
      setError("Domain and MAIL FROM domain are required");
      return;
    }

    setSaving(true);

    try {
      const res = await fetch(`${API_URL}/domains`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          domain,
          mail_from_domain: mailFromDomain
        })
      });

      if (res.status === 409) {
        throw new Error("Domain already exists");
      }
      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new Error(payload?.detail || "Failed to add domain");
      }

      setDomainInput("");
      setMailFromInput("");
      setMailFromTouched(false);
      await loadDomains();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add domain");
    } finally {
      setSaving(false);
    }
  }

  async function refreshDomain(domainId: string) {
    setRefreshingDomainId(domainId);
    setError("");

    try {
      const res = await fetch(`${API_URL}/domains/${domainId}/refresh`, {
        method: "POST",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to refresh domain");
      }

      const refreshedDomain = await res.json();
      setDomains((current) =>
        current.map((domain) => (domain.id === refreshedDomain.id ? refreshedDomain : domain))
      );
      await loadSetupRecords([domainId]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh domain");
    } finally {
      setRefreshingDomainId("");
    }
  }

  async function deleteDomain(domain: SendingDomain) {
    const confirmed = window.confirm(
      `Delete ${domain.domain} from Domain Status? This will remove its saved SES setup status.`
    );
    if (!confirmed) {
      return;
    }

    setDeletingDomainId(domain.id);
    setError("");

    try {
      const res = await fetch(`${API_URL}/domains/${domain.id}`, {
        method: "DELETE",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to delete domain");
      }

      setDomains((current) => current.filter((item) => item.id !== domain.id));
      setSetupRecordsByDomainId((current) => {
        const next = { ...current };
        delete next[domain.id];
        return next;
      });

      if (checkResult?.sending_domain?.id === domain.id) {
        setCheckResult(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete domain");
    } finally {
      setDeletingDomainId("");
    }
  }

  async function checkSendingDomain(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setCheckResult(null);

    const fromEmail = checkFromEmail.trim().toLowerCase();
    if (!fromEmail) {
      setError("From email is required");
      return;
    }

    setCheckingFromEmail(true);

    try {
      const res = await fetch(`${API_URL}/domains/check-sending`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          from_email: fromEmail
        })
      });

      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new Error(payload?.detail || "Failed to check sending domain");
      }

      setCheckResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to check sending domain");
    } finally {
      setCheckingFromEmail(false);
    }
  }

  return (
    <div className="min-h-full bg-app-bg p-6 text-app-text md:p-10">
      <header className="mb-7">
        <h1 className="m-0 text-4xl font-black md:text-[40px]">Settings</h1>
      </header>

      <div className="grid w-full max-w-385 gap-5 xl:grid-cols-[minmax(320px,420px)_minmax(720px,1fr)]">
        <section className="panel p-6">
          <h2 className="mb-2 mt-0 text-2xl font-black">Sending Domains</h2>
          <p className="mb-5 mt-0 text-app-muted">
            Add a verified SES domain before using it in campaigns.
          </p>

          <form onSubmit={addDomain} className="grid gap-3">
            <label className="grid gap-1.5 text-sm font-extrabold">
              Domain
              <input
                className="field"
                value={domainInput}
                onChange={(event) => setDomainInput(event.target.value)}
                placeholder="n0tslava.xyz"
              />
            </label>

            <label className="grid gap-1.5 text-sm font-extrabold">
              MAIL FROM domain
              <input
                className="field"
                value={mailFromInput}
                onChange={(event) => {
                  setMailFromTouched(true);
                  setMailFromInput(event.target.value);
                }}
                placeholder="mail.n0tslava.xyz"
              />
            </label>

            <button type="submit" disabled={saving} className="btn btn-primary">
              {saving ? "Adding..." : "Add domain"}
            </button>
          </form>

          {error && <p className="mt-4 text-app-error">{error}</p>}

          <div className="mt-6 border-t border-app-border pt-5">
            <h2 className="mb-2 mt-0 text-2xl font-black">Pre-send Check</h2>

            <form onSubmit={checkSendingDomain} className="grid gap-3">
              <label className="grid gap-1.5 text-sm font-extrabold">
                From email
                <input
                  className="field"
                  type="email"
                  value={checkFromEmail}
                  onChange={(event) => setCheckFromEmail(event.target.value)}
                  placeholder="hello@n0tslava.xyz"
                />
              </label>

              <button type="submit" disabled={checkingFromEmail} className="btn">
                {checkingFromEmail ? "Checking..." : "Check sender"}
              </button>
            </form>

            {checkResult && (
              <div
                className={[
                  "mt-4 rounded-lg border p-4",
                  checkResult.can_send
                    ? "border-app-success/30 bg-app-success/10"
                    : "border-app-error/30 bg-app-error/10"
                ].join(" ")}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="font-black">{checkResult.from_email}</div>
                    <div className="text-sm text-app-muted">{checkResult.domain}</div>
                  </div>
                  <StatusBadge status={checkResult.can_send ? "valid" : "invalid"} />
                </div>

                {checkResult.blockers.length > 0 && (
                  <div className="mt-4">
                    <div className="mb-2 text-sm font-black text-app-error">Blockers</div>
                    <ul className="m-0 grid gap-1 pl-5 text-sm text-app-error">
                      {checkResult.blockers.map((blocker) => (
                        <li key={blocker}>{blocker}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {checkResult.warnings.length > 0 && (
                  <div className="mt-4">
                    <div className="mb-2 text-sm font-black text-app-muted">Warnings</div>
                    <ul className="m-0 grid gap-1 pl-5 text-sm text-app-muted">
                      {checkResult.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        <section className="min-w-0">
          <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="m-0 text-2xl font-black">Domain Status</h2>
            <button
              type="button"
              onClick={loadDomains}
              disabled={loading}
              className="btn py-2 text-sm">
              {loading ? "Loading..." : "Reload"}
            </button>
          </div>

          {loading && <div className="panel p-6 text-app-muted">Loading domains...</div>}

          {!loading && domains.length === 0 && (
            <div className="panel p-6 text-app-muted">No sending domains have been added yet.</div>
          )}

          {!loading && domains.length > 0 && (
            <div className="grid gap-4">
              {domains.map((domain) => (
                <article key={domain.id} className="panel overflow-hidden">
                  <div className="flex flex-col gap-3 border-b border-app-border p-5 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0">
                      <h3 className="m-0 break-all text-xl font-black">{domain.domain}</h3>
                      <p className="mb-0 mt-1 break-all text-sm text-app-muted">
                        MAIL FROM: {domain.mail_from_domain}
                      </p>
                      <p className="mb-0 mt-2 text-xs font-bold text-app-muted">
                        Last checked: {formatDate(domain.last_checked_at)}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => refreshDomain(domain.id)}
                        disabled={
                          refreshingDomainId === domain.id || deletingDomainId === domain.id
                        }
                        className="btn py-2 text-sm">
                        {refreshingDomainId === domain.id ? "Refreshing..." : "Refresh"}
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteDomain(domain)}
                        disabled={
                          deletingDomainId === domain.id || refreshingDomainId === domain.id
                        }
                        className="btn border-app-error/30 bg-app-error/10 py-2 text-sm text-app-error hover:bg-app-error/15">
                        {deletingDomainId === domain.id ? "Deleting..." : "Delete"}
                      </button>
                    </div>
                  </div>

                  <div className="grid gap-5 p-5 2xl:grid-cols-[minmax(220px,320px)_minmax(0,1fr)]">
                    <div>
                      <StatusRow label="SES verification" status={domain.verification_status} />
                      <StatusRow label="DKIM" status={domain.dkim_status} />
                      <StatusRow label="SPF" status={domain.spf_status} />
                      <StatusRow label="DMARC" status={domain.dmarc_status} />
                      <StatusRow label="MAIL FROM" status={domain.mail_from_status} />
                    </div>

                    <div className="grid gap-3">
                      {(setupRecordsByDomainId[domain.id] || []).map((record, index) => (
                        <DnsRecord
                          key={`${record.purpose}-${record.host}-${index}`}
                          type={record.type}
                          host={record.host}
                          value={record.value}
                        />
                      ))}

                      {(setupRecordsByDomainId[domain.id] || []).length === 0 && (
                        <div className="rounded-lg border border-app-border bg-app-soft p-3 text-sm text-app-muted">
                          DNS setup records are unavailable. Reload or refresh the domain.
                        </div>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

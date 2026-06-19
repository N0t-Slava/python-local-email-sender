import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent, PointerEvent } from "react";

import SelectField from "../components/SelectField";

type User = {
  id: string;
  email: string;
  name: string;
  unsubscribe_public_key?: string | null;
};

type Campaign = {
  id: string;
  subject: string;
  queued_recipients: number;
  sent_count?: number;
  status: string;
  created_at: string;
};

type SesAlert = {
  level: "info" | "warning" | "error";
  code: string;
  message: string;
};

type SesStatus = {
  region: string;
  sending_enabled: boolean;
  production_access_enabled: boolean;
  mode: "local" | "production" | "sandbox" | string;
  from_email: string;
  from_email_verified: boolean;
  quota?: {
    max_24h_send?: number | null;
    sent_last_24h?: number | null;
    remaining_24h?: number | null;
    max_send_rate?: number | null;
  };
  alerts?: SesAlert[];
};

type SuppressionSyncRun = {
  id: string;
  source: string;
  status: "success" | "failed" | string;
  started_at: string;
  finished_at?: string | null;
  synced: number;
  created: number;
  updated: number;
  skipped: number;
  error_message?: string | null;
};

type SuppressionStatus = {
  active_count: number;
  last_sync?: SuppressionSyncRun | null;
};

type SuppressionEntry = {
  id: string;
  user_id?: string | null;
  email: string;
  reason?: "hard_bounce" | "complaint" | "manual" | "unsubscribe" | string | null;
  source?: "ses" | "local" | "admin" | string | null;
  status: "active" | "inactive" | string;
  note?: string | null;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type DeliverabilityAlert = {
  level: "warning" | "critical" | string;
  code: string;
  message: string;
};

type DeliverabilitySummary = {
  campaign_count: number;
  sent_count: number;
  bounce_count: number;
  complaint_count: number;
  bounce_rate: number;
  complaint_rate: number;
  bounce_status: "good" | "warning" | "critical" | string;
  complaint_status: "good" | "warning" | "critical" | string;
  reputation_status: "good" | "warning" | "critical" | string;
  alerts?: DeliverabilityAlert[];
};

type DeliverabilityEvent = {
  id: string;
  event_type: "bounce" | "complaint" | string;
  email: string;
  campaign_id?: string | null;
  recipient_id?: string | null;
  attempt_id?: string | null;
  ses_message_id?: string | null;
  sns_message_id?: string | null;
  bounce_type?: string | null;
  bounce_subtype?: string | null;
  complaint_feedback_type?: string | null;
  diagnostic_code?: string | null;
  occurred_at?: string | null;
  created_at?: string | null;
};

type DashboardProps = {
  user: User | null;
};

const API_URL = "http://localhost:8000";
const STAT_CHART_DAYS = 7;
const DASHBOARD_REFRESH_MS = 30_000;

function normalizeStatus(status: string) {
  if (status.toLowerCase() === "queued") {
    return "Sent";
  }
  return status || "Draft";
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function formatNumber(value?: number | null) {
  if (value === null || value === undefined) {
    return "N/A";
  }

  return new Intl.NumberFormat().format(value);
}

function formatPercent(value?: number | null) {
  if (value === null || value === undefined) {
    return "N/A";
  }

  return `${(value * 100).toFixed(2)}%`;
}

function formatLabel(value?: string | null) {
  if (!value) {
    return "N/A";
  }

  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

type StatMetric = "totalCampaigns" | "sentCampaigns" | "draftCampaigns" | "sentEmails";
type SelectedStatMetric = StatMetric | "all";
type DashboardStats = Record<StatMetric, number>;
type DashboardStatSeries = Record<StatMetric, number[]>;

const STAT_METRICS: {
  key: StatMetric;
  label: string;
  color: string;
}[] = [
  { key: "totalCampaigns", label: "Total campaigns", color: "#6C4BD8" },
  { key: "sentCampaigns", label: "Sent campaigns", color: "#00856F" },
  { key: "draftCampaigns", label: "Draft campaigns", color: "#A46A1F" },
  { key: "sentEmails", label: "Total sent emails", color: "#2C7BE5" }
];

function getStartOfDay(value: Date) {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
  return date;
}

function buildStatSeries(campaigns: Campaign[], metric: StatMetric) {
  const today = getStartOfDay(new Date());
  const start = new Date(today);
  start.setDate(today.getDate() - (STAT_CHART_DAYS - 1));

  const dailyAdds = Array.from({ length: STAT_CHART_DAYS }, () => 0);
  let runningTotal = 0;

  campaigns.forEach((campaign) => {
    const createdAt = new Date(campaign.created_at);
    if (Number.isNaN(createdAt.getTime())) {
      return;
    }

    const campaignDay = getStartOfDay(createdAt);
    const status = normalizeStatus(campaign.status);
    let value = 0;

    if (metric === "totalCampaigns") {
      value = 1;
    } else if (metric === "sentCampaigns" && ["Sent", "Partially Sent"].includes(status)) {
      value = 1;
    } else if (metric === "draftCampaigns" && status === "Draft") {
      value = 1;
    } else if (metric === "sentEmails" && ["Sent", "Partially Sent"].includes(status)) {
      value = campaign.sent_count ?? campaign.queued_recipients ?? 0;
    }

    if (value === 0) {
      return;
    }

    if (campaignDay < start) {
      runningTotal += value;
      return;
    }

    if (campaignDay <= today) {
      const index = Math.floor((campaignDay.getTime() - start.getTime()) / 86_400_000);
      dailyAdds[index] += value;
    }
  });

  return dailyAdds.map((value) => {
    runningTotal += value;
    return runningTotal;
  });
}

function buildStatDates() {
  const today = getStartOfDay(new Date());

  return Array.from({ length: STAT_CHART_DAYS }, (_, index) => {
    const date = new Date(today);
    date.setDate(today.getDate() - (STAT_CHART_DAYS - 1 - index));
    return date;
  });
}

function formatSesMode(mode?: string) {
  if (mode === "local") {
    return "Local SMTP";
  }
  if (mode === "production") {
    return "Production";
  }
  if (mode === "sandbox") {
    return "Sandbox";
  }
  return "N/A";
}

export default function Dashboard({ user }: DashboardProps) {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sesStatus, setSesStatus] = useState<SesStatus | null>(null);
  const [sesLoading, setSesLoading] = useState(true);
  const [sesError, setSesError] = useState("");
  const [suppressionStatus, setSuppressionStatus] = useState<SuppressionStatus | null>(null);
  const [suppressionLoading, setSuppressionLoading] = useState(true);
  const [suppressionSyncing, setSuppressionSyncing] = useState(false);
  const [suppressionError, setSuppressionError] = useState("");
  const [suppressionEntries, setSuppressionEntries] = useState<SuppressionEntry[]>([]);
  const [suppressionEntriesLoading, setSuppressionEntriesLoading] = useState(true);
  const [suppressionActionLoading, setSuppressionActionLoading] = useState("");
  const [suppressionFilters, setSuppressionFilters] = useState({
    status: "active",
    reason: "",
    source: ""
  });
  const [manualSuppressionEmail, setManualSuppressionEmail] = useState("");
  const [manualSuppressionNote, setManualSuppressionNote] = useState("");
  const [deliverabilitySummary, setDeliverabilitySummary] = useState<DeliverabilitySummary | null>(
    null
  );
  const [deliverabilityLoading, setDeliverabilityLoading] = useState(true);
  const [deliverabilityError, setDeliverabilityError] = useState("");
  const [deliverabilityEvents, setDeliverabilityEvents] = useState<DeliverabilityEvent[]>([]);
  const [deliverabilityEventsLoading, setDeliverabilityEventsLoading] = useState(true);
  const sesAlerts = sesStatus?.alerts ?? [];
  const hasSesError = sesAlerts.some((alert) => alert.level === "error");
  const isSesReady = Boolean(
    sesStatus?.sending_enabled && sesStatus?.from_email_verified && !hasSesError
  );

  const loadCampaigns = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setLoading(true);
    }
    setError("");

    try {
      const res = await fetch(`${API_URL}/campaigns`, {
        method: "GET",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to load dashboard data");
      }

      setCampaigns(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard data");
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadCampaigns();

    const refreshTimer = window.setInterval(() => {
      loadCampaigns(false);
    }, DASHBOARD_REFRESH_MS);

    return () => window.clearInterval(refreshTimer);
  }, [loadCampaigns]);

  const loadSesStatus = useCallback(async () => {
    setSesLoading(true);
    setSesError("");

    try {
      const res = await fetch(`${API_URL}/dashboard/ses-status`, {
        method: "GET",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to load SES status");
      }

      setSesStatus(await res.json());
    } catch (err) {
      setSesStatus(null);
      setSesError(err instanceof Error ? err.message : "Failed to load SES status");
    } finally {
      setSesLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSesStatus();
  }, [loadSesStatus]);

  const loadDeliverabilitySummary = useCallback(async () => {
    setDeliverabilityLoading(true);
    setDeliverabilityError("");

    try {
      const res = await fetch(`${API_URL}/dashboard/deliverability-summary`, {
        method: "GET",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to load deliverability summary");
      }

      setDeliverabilitySummary(await res.json());
    } catch (err) {
      setDeliverabilitySummary(null);
      setDeliverabilityError(
        err instanceof Error ? err.message : "Failed to load deliverability summary"
      );
    } finally {
      setDeliverabilityLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDeliverabilitySummary();
  }, [loadDeliverabilitySummary]);

  const loadDeliverabilityEvents = useCallback(async () => {
    setDeliverabilityEventsLoading(true);
    setDeliverabilityError("");

    try {
      const res = await fetch(`${API_URL}/dashboard/email-events?limit=10`, {
        method: "GET",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to load deliverability events");
      }

      setDeliverabilityEvents(await res.json());
    } catch (err) {
      setDeliverabilityEvents([]);
      setDeliverabilityError(
        err instanceof Error ? err.message : "Failed to load deliverability events"
      );
    } finally {
      setDeliverabilityEventsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDeliverabilityEvents();
  }, [loadDeliverabilityEvents]);

  const loadSuppressionStatus = useCallback(async () => {
    setSuppressionLoading(true);
    setSuppressionError("");

    try {
      const res = await fetch(`${API_URL}/suppression/status`, {
        method: "GET",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to load suppression status");
      }

      setSuppressionStatus(await res.json());
    } catch (err) {
      setSuppressionError(err instanceof Error ? err.message : "Failed to load suppression status");
    } finally {
      setSuppressionLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSuppressionStatus();
  }, [loadSuppressionStatus]);

  const loadSuppressionEntries = useCallback(async () => {
    setSuppressionEntriesLoading(true);
    setSuppressionError("");

    try {
      const params = new URLSearchParams();
      if (suppressionFilters.status) {
        params.set("status", suppressionFilters.status);
      }
      if (suppressionFilters.reason) {
        params.set("reason", suppressionFilters.reason);
      }
      if (suppressionFilters.source) {
        params.set("source", suppressionFilters.source);
      }

      const query = params.toString();
      const res = await fetch(`${API_URL}/suppression${query ? `?${query}` : ""}`, {
        method: "GET",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to load suppression list");
      }

      setSuppressionEntries(await res.json());
    } catch (err) {
      setSuppressionError(err instanceof Error ? err.message : "Failed to load suppression list");
    } finally {
      setSuppressionEntriesLoading(false);
    }
  }, [suppressionFilters]);

  useEffect(() => {
    loadSuppressionEntries();
  }, [loadSuppressionEntries]);

  async function syncSuppressionList() {
    setSuppressionSyncing(true);
    setSuppressionError("");

    try {
      const res = await fetch(`${API_URL}/suppression/sync-ses`, {
        method: "POST",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to sync suppression list");
      }

      await res.json();
      await loadSuppressionStatus();
      await loadSuppressionEntries();
    } catch (err) {
      setSuppressionError(err instanceof Error ? err.message : "Failed to sync suppression list");
    } finally {
      setSuppressionSyncing(false);
    }
  }

  async function addManualSuppression(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSuppressionActionLoading("manual");
    setSuppressionError("");

    try {
      const formData = new FormData();
      formData.set("email", manualSuppressionEmail);
      if (manualSuppressionNote.trim()) {
        formData.set("note", manualSuppressionNote.trim());
      }

      const res = await fetch(`${API_URL}/suppression/manual`, {
        method: "POST",
        credentials: "include",
        body: formData
      });

      if (!res.ok) {
        throw new Error("Failed to add suppressed email");
      }

      setManualSuppressionEmail("");
      setManualSuppressionNote("");
      await loadSuppressionStatus();
      await loadSuppressionEntries();
    } catch (err) {
      setSuppressionError(err instanceof Error ? err.message : "Failed to add suppressed email");
    } finally {
      setSuppressionActionLoading("");
    }
  }

  async function deactivateSuppression(email: string) {
    setSuppressionActionLoading(email);
    setSuppressionError("");

    try {
      const res = await fetch(`${API_URL}/suppression/${encodeURIComponent(email)}/deactivate`, {
        method: "POST",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to deactivate suppression");
      }

      await loadSuppressionStatus();
      await loadSuppressionEntries();
    } catch (err) {
      setSuppressionError(err instanceof Error ? err.message : "Failed to deactivate suppression");
    } finally {
      setSuppressionActionLoading("");
    }
  }

  async function resubscribeEmail(email: string) {
    setSuppressionActionLoading(email);
    setSuppressionError("");

    try {
      const res = await fetch(`${API_URL}/unsubscribe/${encodeURIComponent(email)}/resubscribe`, {
        method: "POST",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to resubscribe email");
      }

      await loadSuppressionStatus();
      await loadSuppressionEntries();
    } catch (err) {
      setSuppressionError(err instanceof Error ? err.message : "Failed to resubscribe email");
    } finally {
      setSuppressionActionLoading("");
    }
  }

  const stats = useMemo(() => {
    const sentCampaigns = campaigns.filter((campaign) =>
      ["Sent", "Partially Sent"].includes(normalizeStatus(campaign.status))
    );
    const draftCampaigns = campaigns.filter(
      (campaign) => normalizeStatus(campaign.status) === "Draft"
    );
    const sentEmails = sentCampaigns.reduce(
      (total, campaign) => total + (campaign.sent_count ?? campaign.queued_recipients ?? 0),
      0
    );

    return {
      totalCampaigns: campaigns.length,
      sentCampaigns: sentCampaigns.length,
      draftCampaigns: draftCampaigns.length,
      sentEmails
    };
  }, [campaigns]);

  const statSeries = useMemo(
    () => ({
      totalCampaigns: buildStatSeries(campaigns, "totalCampaigns"),
      sentCampaigns: buildStatSeries(campaigns, "sentCampaigns"),
      draftCampaigns: buildStatSeries(campaigns, "draftCampaigns"),
      sentEmails: buildStatSeries(campaigns, "sentEmails")
    }),
    [campaigns]
  );

  return (
    <div className="min-h-full bg-app-bg p-6 text-app-text md:p-10">
      <header className="mb-7">
        <h1 className="m-0 text-4xl font-black leading-tight md:text-[40px]">Menu</h1>
        <p className="mt-2.5 text-app-muted">Overview of your email activity</p>
      </header>

      {error && <p className="text-app-error">{error}</p>}

      <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(560px,1.1fr)_minmax(480px,0.9fr)]">
        <AnalyticsTrendCard loading={loading} stats={stats} statSeries={statSeries} />

        <section className="panel p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="mb-2 mt-0 text-2xl font-black">Amazon SES</h2>
              <p className="m-0 wrap-break-word text-app-muted">
                {sesLoading
                  ? "Loading SES account status..."
                  : sesStatus?.from_email || "SES status unavailable"}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={loadSesStatus}
                disabled={sesLoading}
                className="btn py-1.5 text-sm">
                {sesLoading ? "Reloading..." : "Reload"}
              </button>
              <span
                className={`inline-flex w-fit rounded-lg border px-3 py-1.5 text-sm font-extrabold ${
                  isSesReady
                    ? "border-app-success/30 bg-app-success/10 text-app-success"
                    : "border-app-warning/40 bg-app-warning/15 text-app-text"
                }`}>
                {sesLoading ? "Checking" : isSesReady ? "Ready" : "Needs attention"}
              </span>
            </div>
          </div>

          {sesError && <p className="mt-4 text-app-error">{sesError}</p>}

          <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 2xl:grid-cols-4">
            <SesMetric
              label="Mode"
              value={sesLoading ? "..." : formatSesMode(sesStatus?.mode)}
            />
            <SesMetric
              label="Sender verified"
              value={sesLoading ? "..." : sesStatus?.from_email_verified ? "Yes" : "No"}
            />
            <SesMetric
              label="Remaining 24h quota"
              value={sesLoading ? "..." : formatNumber(sesStatus?.quota?.remaining_24h)}
            />
            <SesMetric
              label="Send rate"
              value={sesLoading ? "..." : `${formatNumber(sesStatus?.quota?.max_send_rate)}/sec`}
            />
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 text-sm text-app-muted sm:grid-cols-3">
            <span>Region: {sesLoading ? "..." : sesStatus?.region || "N/A"}</span>
            <span>
              Sent last 24h: {sesLoading ? "..." : formatNumber(sesStatus?.quota?.sent_last_24h)}
            </span>
            <span>
              Daily limit: {sesLoading ? "..." : formatNumber(sesStatus?.quota?.max_24h_send)}
            </span>
          </div>

          {!sesLoading && sesAlerts.length > 0 && (
            <div className="mt-5 grid gap-2">
              {sesAlerts.map((alert) => (
                <SesAlertRow key={alert.code} alert={alert} />
              ))}
            </div>
          )}
        </section>
      </div>
      <section className="panel mb-6 p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="mb-2 mt-0 text-2xl font-black">Sender Reputation</h2>
            <p className="m-0 text-app-muted">
              {deliverabilityLoading
                ? "Loading sender reputation..."
                : `${formatNumber(deliverabilitySummary?.sent_count)} sent emails measured`}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                loadDeliverabilitySummary();
                loadDeliverabilityEvents();
              }}
              disabled={deliverabilityLoading || deliverabilityEventsLoading}
              className="btn py-1.5 text-sm">
              {deliverabilityLoading || deliverabilityEventsLoading ? "Reloading..." : "Reload"}
            </button>
            <ReputationBadge
              status={deliverabilitySummary?.reputation_status || "good"}
              loading={deliverabilityLoading}
            />
          </div>
        </div>

        {deliverabilityError && <p className="mt-4 text-app-error">{deliverabilityError}</p>}

        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <SesMetric
            label="Bounce rate"
            value={
              deliverabilityLoading ? "..." : formatPercent(deliverabilitySummary?.bounce_rate)
            }
          />
          <SesMetric
            label="Complaint rate"
            value={
              deliverabilityLoading ? "..." : formatPercent(deliverabilitySummary?.complaint_rate)
            }
          />
          <SesMetric
            label="Bounces"
            value={
              deliverabilityLoading ? "..." : formatNumber(deliverabilitySummary?.bounce_count)
            }
          />
          <SesMetric
            label="Complaints"
            value={
              deliverabilityLoading ? "..." : formatNumber(deliverabilitySummary?.complaint_count)
            }
          />
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 text-sm text-app-muted sm:grid-cols-3">
          <span>
            Campaigns measured:{" "}
            {deliverabilityLoading ? "..." : formatNumber(deliverabilitySummary?.campaign_count)}
          </span>
          <span>
            Bounce status:{" "}
            {deliverabilityLoading ? "..." : formatLabel(deliverabilitySummary?.bounce_status)}
          </span>
          <span>
            Complaint status:{" "}
            {deliverabilityLoading ? "..." : formatLabel(deliverabilitySummary?.complaint_status)}
          </span>
        </div>

        {!deliverabilityLoading &&
          deliverabilitySummary?.alerts &&
          deliverabilitySummary.alerts.length > 0 && (
            <div className="mt-5 grid gap-2">
              {deliverabilitySummary.alerts.map((alert) => (
                <DeliverabilityAlertRow key={alert.code} alert={alert} />
              ))}
            </div>
          )}
      </section>
      <section className="panel mb-6 p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="mb-2 mt-0 text-2xl font-black">Recent Deliverability Events</h2>
            <p className="m-0 text-app-muted">
              {deliverabilityEventsLoading
                ? "Loading bounce and complaint events..."
                : `${formatNumber(deliverabilityEvents.length)} recent events`}
            </p>
          </div>
          <button
            type="button"
            onClick={loadDeliverabilityEvents}
            disabled={deliverabilityEventsLoading}
            className="btn py-1.5 text-sm">
            {deliverabilityEventsLoading ? "Loading..." : "Reload"}
          </button>
        </div>

        <div className="mt-5 overflow-x-auto rounded-lg border border-app-border">
          <table className="w-full min-w-195 border-collapse bg-app-surface text-left text-sm">
            <thead className="bg-app-panel text-app-muted">
              <tr>
                <th className="px-4 py-3 font-black">Type</th>
                <th className="px-4 py-3 font-black">Email</th>
                <th className="px-4 py-3 font-black">Details</th>
                <th className="px-4 py-3 font-black">Campaign</th>
                <th className="px-4 py-3 font-black">Occurred</th>
              </tr>
            </thead>
            <tbody>
              {deliverabilityEventsLoading && (
                <tr>
                  <td className="px-4 py-5 text-app-muted" colSpan={5}>
                    Loading deliverability events...
                  </td>
                </tr>
              )}

              {!deliverabilityEventsLoading && deliverabilityEvents.length === 0 && (
                <tr>
                  <td className="px-4 py-5 text-app-muted" colSpan={5}>
                    No bounce or complaint events have been received yet.
                  </td>
                </tr>
              )}

              {!deliverabilityEventsLoading &&
                deliverabilityEvents.map((event) => (
                  <tr key={event.id} className="border-t border-app-border">
                    <td className="px-4 py-3">
                      <EventBadge eventType={event.event_type} />
                    </td>
                    <td className="max-w-60 wrap-break-word px-4 py-3 font-extrabold">
                      {event.email}
                    </td>
                    <td className="max-w-70 wrap-break-word px-4 py-3 text-app-muted">
                      {formatEventDetails(event)}
                    </td>
                    <td className="max-w-54 wrap-break-word px-4 py-3 text-app-muted">
                      {event.campaign_id || "N/A"}
                    </td>
                    <td className="px-4 py-3 text-app-muted">
                      {event.occurred_at ? formatDate(event.occurred_at) : "N/A"}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel mb-6 p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="mb-2 mt-0 text-2xl font-black">Suppression List</h2>
            <p className="m-0 text-app-muted">
              {suppressionLoading
                ? "Loading suppression status..."
                : `${formatNumber(suppressionStatus?.active_count)} active suppressed recipients`}
            </p>
          </div>
          <button
            type="button"
            onClick={syncSuppressionList}
            disabled={suppressionSyncing}
            className="btn btn-primary py-1.5 text-sm">
            {suppressionSyncing ? "Syncing..." : "Sync from SES"}
          </button>
        </div>

        {suppressionError && <p className="mt-4 text-app-error">{suppressionError}</p>}

        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <SesMetric
            label="Active suppressed"
            value={suppressionLoading ? "..." : formatNumber(suppressionStatus?.active_count)}
          />
          <SesMetric
            label="Last sync"
            value={
              suppressionLoading
                ? "..."
                : suppressionStatus?.last_sync?.finished_at
                  ? formatDate(suppressionStatus.last_sync.finished_at)
                  : "Never"
            }
          />
          <SesMetric
            label="Last result"
            value={suppressionLoading ? "..." : suppressionStatus?.last_sync?.status || "N/A"}
          />
        </div>

        {suppressionStatus?.last_sync && (
          <div className="mt-4 grid grid-cols-1 gap-3 text-sm text-app-muted sm:grid-cols-4">
            <span>Synced: {formatNumber(suppressionStatus.last_sync.synced)}</span>
            <span>Created: {formatNumber(suppressionStatus.last_sync.created)}</span>
            <span>Updated: {formatNumber(suppressionStatus.last_sync.updated)}</span>
            <span>Skipped: {formatNumber(suppressionStatus.last_sync.skipped)}</span>
          </div>
        )}

        <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(280px,360px)_minmax(0,1fr)]">
          <form
            onSubmit={addManualSuppression}
            className="rounded-lg border border-app-border bg-app-soft p-4">
            <h3 className="mb-3 mt-0 text-lg font-black">Manual suppression</h3>
            <div className="grid gap-3">
              <input
                className="field"
                type="email"
                value={manualSuppressionEmail}
                onChange={(event) => setManualSuppressionEmail(event.target.value)}
                placeholder="recipient@example.com"
                required
              />
              <textarea
                className="field min-h-24 resize-y"
                value={manualSuppressionNote}
                onChange={(event) => setManualSuppressionNote(event.target.value)}
                placeholder="Note"
              />
              <button
                type="submit"
                disabled={suppressionActionLoading === "manual"}
                className="btn btn-primary">
                {suppressionActionLoading === "manual" ? "Adding..." : "Add"}
              </button>
            </div>

            {user?.unsubscribe_public_key && (
              <div className="mt-4 border-t border-app-border pt-4">
                <div className="mb-2 text-sm font-extrabold text-app-muted">
                  Public unsubscribe key
                </div>
                <input
                  className="field text-sm"
                  value={user.unsubscribe_public_key}
                  readOnly
                  onFocus={(event) => event.target.select()}
                />
              </div>
            )}
          </form>

          <div className="min-w-0">
            <div className="mb-3 grid gap-3 md:grid-cols-4">
              <SelectField
                ariaLabel="Suppression status"
                value={suppressionFilters.status}
                onChange={(status) =>
                  setSuppressionFilters((current) => ({ ...current, status }))
                }
                options={[
                  { value: "", label: "All statuses" },
                  { value: "active", label: "Active" },
                  { value: "inactive", label: "Inactive" }
                ]}
              />
              <SelectField
                ariaLabel="Suppression reason"
                value={suppressionFilters.reason}
                onChange={(reason) =>
                  setSuppressionFilters((current) => ({ ...current, reason }))
                }
                options={[
                  { value: "", label: "All reasons" },
                  { value: "hard_bounce", label: "Hard bounce" },
                  { value: "complaint", label: "Complaint" },
                  { value: "manual", label: "Manual" },
                  { value: "unsubscribe", label: "Unsubscribe" }
                ]}
              />
              <SelectField
                ariaLabel="Suppression source"
                value={suppressionFilters.source}
                onChange={(source) =>
                  setSuppressionFilters((current) => ({ ...current, source }))
                }
                options={[
                  { value: "", label: "All sources" },
                  { value: "ses", label: "SES" },
                  { value: "local", label: "Local" },
                  { value: "admin", label: "Admin" }
                ]}
              />
              <button
                type="button"
                onClick={loadSuppressionEntries}
                disabled={suppressionEntriesLoading}
                className="btn">
                {suppressionEntriesLoading ? "Loading..." : "Reload"}
              </button>
            </div>

            <div className="overflow-x-auto rounded-lg border border-app-border">
              <table className="w-full min-w-190 border-collapse bg-app-surface text-left text-sm">
                <thead className="bg-app-panel text-app-muted">
                  <tr>
                    <th className="px-4 py-3 font-black">Email</th>
                    <th className="px-4 py-3 font-black">Reason</th>
                    <th className="px-4 py-3 font-black">Source</th>
                    <th className="px-4 py-3 font-black">Status</th>
                    <th className="px-4 py-3 font-black">Updated</th>
                    <th className="px-4 py-3 font-black">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {suppressionEntriesLoading && (
                    <tr>
                      <td className="px-4 py-5 text-app-muted" colSpan={6}>
                        Loading suppression entries...
                      </td>
                    </tr>
                  )}

                  {!suppressionEntriesLoading && suppressionEntries.length === 0 && (
                    <tr>
                      <td className="px-4 py-5 text-app-muted" colSpan={6}>
                        No suppression entries match the selected filters.
                      </td>
                    </tr>
                  )}

                  {!suppressionEntriesLoading &&
                    suppressionEntries.map((entry) => (
                      <tr key={entry.id} className="border-t border-app-border">
                        <td className="max-w-60 wrap-break-word px-4 py-3 font-extrabold">
                          {entry.email}
                          {entry.note && (
                            <div className="mt-1 text-xs font-bold text-app-muted">
                              {entry.note}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3">{formatLabel(entry.reason)}</td>
                        <td className="px-4 py-3">{formatLabel(entry.source)}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex rounded-lg border px-2.5 py-1 text-xs font-black ${
                              entry.status === "active"
                                ? "border-app-error/30 bg-app-error/10 text-app-error"
                                : "border-app-success/30 bg-app-success/10 text-app-success"
                            }`}>
                            {formatLabel(entry.status)}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-app-muted">
                          {entry.updated_at ? formatDate(entry.updated_at) : "N/A"}
                        </td>
                        <td className="px-4 py-3">
                          {entry.status === "active" && entry.reason === "unsubscribe" ? (
                            <button
                              type="button"
                              onClick={() => resubscribeEmail(entry.email)}
                              disabled={suppressionActionLoading === entry.email}
                              className="btn py-1.5 text-sm">
                              {suppressionActionLoading === entry.email
                                ? "Working..."
                                : "Resubscribe"}
                            </button>
                          ) : entry.status === "active" ? (
                            <button
                              type="button"
                              onClick={() => deactivateSuppression(entry.email)}
                              disabled={suppressionActionLoading === entry.email}
                              className="btn py-1.5 text-sm">
                              {suppressionActionLoading === entry.email
                                ? "Working..."
                                : "Deactivate"}
                            </button>
                          ) : (
                            <span className="text-app-muted">Inactive</span>
                          )}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function AnalyticsTrendCard({
  loading,
  stats,
  statSeries
}: {
  loading: boolean;
  stats: DashboardStats;
  statSeries: DashboardStatSeries;
}) {
  const [selectedMetric, setSelectedMetric] = useState<SelectedStatMetric>("all");
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const width = 760;
  const height = 300;
  const padding = {
    top: 28,
    right: 22,
    bottom: 48,
    left: 54
  };
  const dates = useMemo(() => buildStatDates(), []);
  const allValues = STAT_METRICS.flatMap((metric) => statSeries[metric.key]);
  const rawMax = Math.max(0, ...allValues);
  const yMax = Math.max(4, Math.ceil(rawMax * 1.15));
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const step = plotWidth / (STAT_CHART_DAYS - 1);
  const yTicks = Array.from({ length: 5 }, (_, index) =>
    Math.round((yMax / 4) * (4 - index))
  );
  const seriesPoints = STAT_METRICS.map((metric) => {
    const points = statSeries[metric.key].map((value, index) => {
      const ratio = yMax === 0 ? 0 : value / yMax;
      return {
        value,
        x: padding.left + index * step,
        y: padding.top + plotHeight - ratio * plotHeight
      };
    });

    return {
      ...metric,
      points,
      path: buildSmoothPath(points)
    };
  });
  const activeX = activeIndex === null ? null : padding.left + activeIndex * step;
  const activeDate = activeIndex === null ? null : dates[activeIndex];
  const tooltipPosition =
    activeX === null ? "50%" : `${Math.min(Math.max((activeX / width) * 100, 20), 80)}%`;
  const selectedValue =
    selectedMetric === "all" ? null : stats[selectedMetric as StatMetric];

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * width;
    const nextIndex = dates.reduce((closestIndex, _date, index) => {
      const pointX = padding.left + index * step;
      const closestX = padding.left + closestIndex * step;
      return Math.abs(pointX - x) < Math.abs(closestX - x) ? index : closestIndex;
    }, 0);

    setActiveIndex(nextIndex);
  }

  return (
    <section className="panel min-h-98 p-6 shadow-sm">
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setSelectedMetric("all")}
            className={[
              "rounded-full border px-3 py-1.5 text-xs font-black transition",
              selectedMetric === "all"
                ? "border-app-text bg-app-text text-white shadow-sm"
                : "border-app-border bg-app-surface text-app-muted hover:border-app-text hover:text-app-text"
            ].join(" ")}>
            All
          </button>

          {STAT_METRICS.map((metric) => {
            const isSelected = selectedMetric === metric.key;
            return (
              <button
                key={metric.key}
                type="button"
                onClick={() => setSelectedMetric(metric.key)}
                className={[
                  "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-black transition",
                  isSelected
                    ? "border-app-text bg-app-text text-white shadow-sm"
                    : "border-app-border bg-app-surface text-app-muted hover:border-app-text hover:text-app-text"
                ].join(" ")}>
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: metric.color }}
                />
                {metric.label}
              </button>
            );
          })}
        </div>

        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="m-0 text-2xl font-black">Campaign Analytics</h2>
            <p className="mt-1 text-sm text-app-muted">Seven day cumulative activity</p>
          </div>
          <div className="text-left sm:text-right">
            <div className="text-[32px] font-black leading-none">
              {loading
                ? "..."
                : selectedValue === null
                  ? formatNumber(stats.totalCampaigns)
                  : formatNumber(selectedValue)}
            </div>
            <div className="mt-1 text-xs font-extrabold text-app-muted">
              {selectedMetric === "all"
                ? "Total campaigns"
                : STAT_METRICS.find((metric) => metric.key === selectedMetric)?.label}
            </div>
          </div>
        </div>
      </div>

      <div className="relative mt-5">
        {activeIndex !== null && activeDate && (
          <div
            className="pointer-events-none absolute top-2 z-10 w-56 -translate-x-1/2 rounded-lg border border-app-border bg-app-surface p-3 text-xs shadow-lg"
            style={{ left: tooltipPosition }}>
            <div className="mb-2 font-black text-app-text">
              {activeDate.toLocaleDateString(undefined, { month: "short", day: "numeric" })}
            </div>
            <div className="grid gap-1.5">
              {STAT_METRICS.map((metric) => (
                <div key={metric.key} className="flex items-center justify-between gap-3">
                  <span className="flex min-w-0 items-center gap-2 text-app-muted">
                    <span
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: metric.color }}
                    />
                    <span className="truncate">{metric.label}</span>
                  </span>
                  <span className="font-black text-app-text">
                    {formatNumber(statSeries[metric.key][activeIndex])}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
        <svg
          role="img"
          tabIndex={0}
          aria-label="Seven day campaign analytics chart"
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="none"
          onPointerMove={handlePointerMove}
          onPointerLeave={() => setActiveIndex(null)}
          onFocus={() => setActiveIndex(STAT_CHART_DAYS - 1)}
          onBlur={() => setActiveIndex(null)}
          className="h-72 w-full cursor-crosshair outline-none focus-visible:ring-4 focus-visible:ring-app-accent/25">
          <rect
            x={padding.left}
            y={padding.top}
            width={plotWidth}
            height={plotHeight}
            fill="#FFFFFF"
          />

          {yTicks.map((tick) => {
            const y = padding.top + plotHeight - (tick / yMax) * plotHeight;
            return (
              <g key={tick}>
                <line
                  x1={padding.left}
                  x2={width - padding.right}
                  y1={y}
                  y2={y}
                  stroke="#E7DED1"
                  strokeWidth="1"
                />
                <text
                  x={padding.left - 14}
                  y={y + 4}
                  textAnchor="end"
                  fill="var(--color-app-muted)"
                  className="text-[11px] font-bold">
                  {formatNumber(tick)}
                </text>
              </g>
            );
          })}

          {activeX !== null && (
            <line
              x1={activeX}
              x2={activeX}
              y1={padding.top}
              y2={height - padding.bottom}
              stroke="#241C18"
              strokeDasharray="4 4"
              strokeOpacity="0.4"
            />
          )}

          {seriesPoints.map((series) => {
            const isSelected = selectedMetric === "all" || selectedMetric === series.key;
            return (
              <g key={series.key} opacity={isSelected ? 1 : 0.25}>
                <path
                  d={series.path}
                  fill="none"
                  stroke={series.color}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={isSelected && selectedMetric !== "all" ? "4" : "2.8"}
                />
                {series.points.map((point, index) => {
                  const isActive = index === activeIndex;
                  return (
                    <circle
                      key={`${series.key}-${index}`}
                      cx={point.x}
                      cy={point.y}
                      r={isActive && isSelected ? 5 : 3.2}
                      fill="#FFFFFF"
                      stroke={series.color}
                      strokeWidth={isActive && isSelected ? "2.6" : "2"}
                    />
                  );
                })}
              </g>
            );
          })}

          {dates.map((date, index) => {
            const x = padding.left + index * step;
            return (
              <text
                key={date.toISOString()}
                x={x}
                y={height - 16}
                textAnchor="middle"
                fill="var(--color-app-muted)"
                className="text-[12px] font-bold">
                {date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}
              </text>
            );
          })}
        </svg>
      </div>
    </section>
  );
}

function buildSmoothPath(points: { x: number; y: number }[]) {
  if (points.length === 0) {
    return "";
  }

  return points
    .map((point, index) => {
      if (index === 0) {
        return `M ${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
      }

      const previous = points[index - 1];
      const controlDistance = (point.x - previous.x) / 2;
      const c1x = previous.x + controlDistance;
      const c2x = point.x - controlDistance;
      return [
        `C ${c1x.toFixed(2)} ${previous.y.toFixed(2)}`,
        `${c2x.toFixed(2)} ${point.y.toFixed(2)}`,
        `${point.x.toFixed(2)} ${point.y.toFixed(2)}`
      ].join(" ");
    })
    .join(" ");
}

function SesMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-app-border bg-app-soft p-4">
      <div className="text-sm font-extrabold text-app-muted">{label}</div>
      <div className="mt-2 wrap-break-word text-2xl font-black">{value}</div>
    </div>
  );
}

function SesAlertRow({ alert }: { alert: SesAlert }) {
  const className =
    alert.level === "error"
      ? "border-app-error/30 bg-app-error/10 text-app-error"
      : alert.level === "warning"
        ? "border-app-warning/40 bg-app-warning/15 text-app-text"
        : "border-app-border bg-app-soft text-app-muted";

  return (
    <div className={`rounded-lg border px-4 py-3 text-sm font-bold ${className}`}>
      {alert.message}
    </div>
  );
}

function ReputationBadge({ status, loading }: { status: string; loading: boolean }) {
  const className =
    status === "critical"
      ? "border-app-error/30 bg-app-error/10 text-app-error"
      : status === "warning"
        ? "border-app-warning/40 bg-app-warning/15 text-app-text"
        : "border-app-success/30 bg-app-success/10 text-app-success";

  return (
    <span
      className={`inline-flex w-fit rounded-lg border px-3 py-1.5 text-sm font-extrabold ${className}`}>
      {loading ? "Checking" : formatLabel(status)}
    </span>
  );
}

function DeliverabilityAlertRow({ alert }: { alert: DeliverabilityAlert }) {
  const className =
    alert.level === "critical"
      ? "border-app-error/30 bg-app-error/10 text-app-error"
      : "border-app-warning/40 bg-app-warning/15 text-app-text";

  return (
    <div className={`rounded-lg border px-4 py-3 text-sm font-bold ${className}`}>
      {alert.message}
    </div>
  );
}

function EventBadge({ eventType }: { eventType: string }) {
  const className =
    eventType === "complaint"
      ? "border-app-error/30 bg-app-error/10 text-app-error"
      : "border-app-warning/40 bg-app-warning/15 text-app-text";

  return (
    <span className={`inline-flex rounded-lg border px-2.5 py-1 text-xs font-black ${className}`}>
      {formatLabel(eventType)}
    </span>
  );
}

function formatEventDetails(event: DeliverabilityEvent) {
  if (event.event_type === "complaint") {
    return event.complaint_feedback_type
      ? `Feedback: ${formatLabel(event.complaint_feedback_type)}`
      : "Complaint received";
  }

  if (event.event_type === "bounce") {
    const parts = [event.bounce_type, event.bounce_subtype].filter(Boolean).map(formatLabel);
    if (event.diagnostic_code) {
      parts.push(event.diagnostic_code);
    }
    return parts.length ? parts.join(" / ") : "Bounce received";
  }

  return formatLabel(event.event_type);
}

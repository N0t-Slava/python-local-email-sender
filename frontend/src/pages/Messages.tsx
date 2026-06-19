import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

type Campaign = {
  id: string;
  user_id: string;
  task_id: string;
  subject: string;
  body: string;
  from_email: string;
  queued_recipients: number;
  status: string;
  created_at: string;
  batch_size?: number | null;
  per_batch_delay?: number | null;
};

const API_URL = "http://localhost:8000";

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

export default function Messages() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadCampaigns() {
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API_URL}/campaigns`, {
        method: "GET",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to load campaigns");
      }

      setCampaigns(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load campaigns");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCampaigns();
  }, []);

  return (
    <div className="min-h-full w-full bg-app-bg p-6 text-app-text md:p-10">
      <header className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="m-0 text-4xl font-black">Messages</h1>
          <p className="mt-2 text-app-muted">{campaigns.length} campaigns for this account</p>
        </div>

        <Link to="/campaigns/create" className="btn btn-primary no-underline">
          Create Campaign
        </Link>
      </header>

      {loading && <p className="text-app-muted">Loading campaigns...</p>}
      {error && <p className="text-app-error">{error}</p>}

      {!loading && !error && campaigns.length === 0 && (
        <div className="panel p-6 text-app-muted">No campaigns yet.</div>
      )}

      {campaigns.length > 0 && (
        <div className="flex flex-col gap-3">
          {campaigns.map((campaign) => (
            <article key={campaign.id} className="panel p-5">
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                <div>
                  <h2 className="m-0 text-xl font-black">{campaign.subject}</h2>
                  <p className="mt-1.5 text-app-muted">
                    From {campaign.from_email} - {formatDate(campaign.created_at)}
                  </p>
                </div>

                <span className="rounded-lg border border-app-border bg-app-panel px-2.5 py-1 text-[13px] capitalize text-app-text">
                  {campaign.status}
                </span>
              </div>

              <p className="my-3.5 whitespace-pre-wrap break-words text-app-text">{campaign.body}</p>

              <div className="flex flex-wrap gap-3 text-sm text-app-muted">
                <span>{campaign.queued_recipients} recipients</span>
                <span>Task {campaign.task_id}</span>
                {campaign.batch_size ? <span>Batch {campaign.batch_size}</span> : null}
                {campaign.per_batch_delay ? <span>Delay {campaign.per_batch_delay}s</span> : null}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

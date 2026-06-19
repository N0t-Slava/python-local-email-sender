import { useMemo, useState } from "react";
import type { FormEvent } from "react";

import SelectField from "../components/SelectField";

type User = {
  id: string;
  email: string;
  name: string;
};

type ProfileProps = {
  user: User | null;
};

const timezones = ["Europe/Kyiv", "UTC", "Europe/London", "Europe/Warsaw", "America/New_York"];

function splitName(name?: string) {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  return {
    firstName: parts[0] || "",
    lastName: parts.slice(1).join(" ")
  };
}

export default function Profile({ user }: ProfileProps) {
  return (
    <div className="min-h-full bg-app-bg p-6 text-app-text md:p-10">
      <header className="mb-6">
        <h1 className="m-0 text-4xl font-black md:text-[40px]">Account</h1>
      </header>

      <YourProfile user={user} />
    </div>
  );
}

function YourProfile({ user }: { user: User | null }) {
  const names = useMemo(() => splitName(user?.name), [user?.name]);
  const [firstName, setFirstName] = useState(names.firstName);
  const [lastName, setLastName] = useState(names.lastName);
  const [timezone, setTimezone] = useState("Europe/Kyiv");
  const [tips, setTips] = useState(true);
  const [news, setNews] = useState(true);
  const [receipts, setReceipts] = useState(true);
  const [detailsMessage, setDetailsMessage] = useState("");

  function saveDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDetailsMessage(
      "Profile preferences saved locally. Backend profile update is not available yet."
    );
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(320px,1fr)_minmax(300px,420px)]">
      <section className="panel p-6">
        <h2 className="m-0 text-2xl font-black">Your details</h2>
        <form onSubmit={saveDetails} className="mt-5 grid gap-4">
          <div>
            <label className="mb-1.5 block text-sm font-extrabold text-app-muted">
              Email address
            </label>
            <div className="flex flex-wrap items-center gap-3 rounded-lg border border-app-border bg-app-panel px-3 py-3">
              <span className="font-bold">{user?.email || "No email available"}</span>
              <button
                type="button"
                className="text-sm font-extrabold text-[#6B5200] hover:text-app-text">
                change
              </button>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-sm font-extrabold text-app-muted">First name</span>
              <input
                value={firstName}
                onChange={(event) => setFirstName(event.target.value)}
                className="field"
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-extrabold text-app-muted">Last name</span>
              <input
                value={lastName}
                onChange={(event) => setLastName(event.target.value)}
                className="field"
              />
            </label>
          </div>

          <label className="block">
            <span className="mb-1.5 block text-sm font-extrabold text-app-muted">Timezone</span>
            <SelectField
              ariaLabel="Timezone"
              value={timezone}
              onChange={setTimezone}
              options={timezones.map((zone) => ({ value: zone, label: zone }))}
            />
          </label>

          <div className="rounded-lg border border-app-border bg-app-soft p-4">
            <h3 className="m-0 text-lg font-black">Email preferences</h3>
            <div className="mt-3 grid gap-3">
              <Checkbox
                checked={tips}
                onChange={setTips}
                label="Receive tips on how to use the platform"
              />
              <Checkbox
                checked={news}
                onChange={setNews}
                label="Receive product news and feature updates"
              />
              <Checkbox
                checked={receipts}
                onChange={setReceipts}
                label="Receive payment receipts via email"
              />
            </div>
          </div>

          <button type="submit" className="btn btn-primary justify-self-start">
            Save
          </button>

          {detailsMessage && (
            <p className="m-0 rounded-lg border border-app-success/30 bg-app-success/10 px-4 py-3 font-bold text-app-success">
              {detailsMessage}
            </p>
          )}
        </form>
      </section>

      <aside className="grid gap-5">
        <PlaceholderSection
          title="Account preferences"
          description="Control account-level defaults for your Mailflow workspace."
          rows={[
            ["Workspace name", user?.name || "Mailflow account"],
            ["Language", "English"],
            ["Timezone", timezone]
          ]}
        />
        <PlaceholderSection
          title="Default sender settings"
          description="Use these details as defaults when creating new campaigns."
          rows={[
            ["Sender name", user?.name || "Account owner"],
            ["Sender email", user?.email || "Not available"],
            ["Reply handling", "Use campaign sender address"]
          ]}
        />
      </aside>

      <ConnectedAccounts user={user} />
    </div>
  );
}

function ConnectedAccounts({ user }: { user: User | null }) {
  return (
    <section className="panel xl:col-span-2">
      <div className="border-b border-app-border px-6 py-4">
        <h2 className="m-0 text-2xl font-black">Connected accounts</h2>
      </div>
      <div className="divide-y divide-app-border">
        <div className="flex flex-col justify-between gap-3 px-6 py-4 sm:flex-row sm:items-center">
          <div>
            <div className="font-black">{user?.name || "Current account"}</div>
            <div className="text-sm text-app-muted">{user?.email || "No email available"}</div>
          </div>
          <button type="button" className="btn self-start text-app-error sm:self-auto">
            Leave
          </button>
        </div>
      </div>
    </section>
  );
}

function PlaceholderSection({
  title,
  description,
  rows
}: {
  title: string;
  description: string;
  rows: [string, string][];
}) {
  return (
    <section className="panel p-6">
      <h2 className="m-0 text-2xl font-black">{title}</h2>
      <p className="text-app-muted">{description}</p>
      <div className="mt-5 divide-y divide-app-border rounded-lg border border-app-border bg-app-soft">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4 px-4 py-3">
            <span className="font-extrabold text-app-muted">{label}</span>
            <span className="text-right font-bold">{value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function Checkbox({
  checked,
  onChange,
  label
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-2.5 font-bold text-app-text">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1 h-4 w-4 accent-app-accent"
      />
      <span>{label}</span>
    </label>
  );
}

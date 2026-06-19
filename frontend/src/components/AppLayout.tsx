import type { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";

type User = {
  id: string;
  email: string;
  name: string;
};

type AppLayoutProps = {
  children: ReactNode;
  user: User;
};

const navItems = [
  { path: "/dashboard", icon: "⌂", label: "Menu" },
  { path: "/campaigns", icon: "✉", label: "Campaigns" },
  { path: "/contacts", icon: "◎", label: "Contacts" },
  { path: "/messages", icon: "▤", label: "Messages" },
  { path: "/settings", icon: "⚙", label: "Settings" }
];

export default function AppLayout({ children, user }: AppLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const accountPaths = [
    "/profile",
    "/settings/profile"
  ];
  const isAccountPage = accountPaths.some((path) => location.pathname === path);

  const isActive = (path: string) => {
    if (path === "/settings") {
      return location.pathname === "/settings";
    }

    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  const navClass = (path: string) =>
    [
      "flex items-center gap-2.5 rounded-lg border px-3 py-2.5 text-sm font-extrabold transition",
      isActive(path)
        ? "border-app-accent bg-[#FFF3A5] text-app-text"
        : "border-transparent text-app-muted hover:bg-app-panel hover:text-app-text"
    ].join(" ");

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-app-bg text-app-text">
      <aside className="flex h-screen w-67 min-w-67 flex-col overflow-y-auto border-r border-app-border bg-app-soft px-4 py-5">
        <div className="mb-6">
          <div className="mb-4 text-[22px] font-black">Mailflow</div>

          <button
            type="button"
            title="Open profile"
            aria-label="Open profile"
            onClick={() => navigate("/settings/profile")}
            className={[
              "flex w-full cursor-pointer items-center gap-3 rounded-lg border p-3 text-left transition",
              isAccountPage
                ? "border-app-accent bg-[#FFF3A5]"
                : "border-app-border bg-app-panel hover:bg-app-surface"
            ].join(" ")}>
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-app-accent font-black">
              {user.name?.charAt(0).toUpperCase() || "?"}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-black">{user.name || "Account"}</span>
            </span>
          </button>
        </div>

        <nav className="flex flex-1 flex-col gap-2">
          {navItems.map((item) => (
            <button
              key={item.path}
              type="button"
              className={navClass(item.path)}
              onClick={() => navigate(item.path)}>
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto bg-app-bg text-app-text">{children}</main>
    </div>
  );
}

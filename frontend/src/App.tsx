import { useState, useEffect } from "react";
import type { ReactNode } from "react";
import { Routes, Route, Navigate } from "react-router-dom";

import AppLayout from "./components/AppLayout";
import Campaigns from "./pages/Campaigns";
import Settings from "./pages/Settings";
import Dashboard from "./pages/Dashboard";

import Contacts from "./pages/Contacts";
import AddContacts from "./pages/AddContacts";
import Messages from "./pages/Messages";
import Profile from "./pages/Profile";
import CampaignCreateSetupPage from "./pages/campaignCreate/SetupPage";
import CampaignCreateDesignPage from "./pages/campaignCreate/DesignPage";
import CampaignCreateContentPage from "./pages/campaignCreate/ContentPage";
import CampaignCreateSendPage from "./pages/campaignCreate/SendPage";

interface User {
  id: string;
  email: string;
  name: string;
  unsubscribe_public_key?: string | null;
}

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function LoadMe() {
      try {
        const res = await fetch("http://localhost:8000/me", {
          method: "GET",
          credentials: "include"
        });

        if (res.ok) {
          const data = await res.json();
          setUser(data);
        } else {
          setUser(null);
        }
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    }

    LoadMe();
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-app-bg text-app-text">
        Loading...
      </div>
    );
  }

  const protectedRoute = (element: ReactNode) => {
    return user ? (
      <AppLayout user={user}>
        {element}
      </AppLayout>
    ) : (
      <div className="flex h-screen w-screen items-center justify-center bg-app-bg px-6 text-center text-app-text">
        Local user is not available. Check that the API is running and open the app again.
      </div>
    );
  };

  return (
    <Routes>
      {/* APP */}
      <Route path="/dashboard" element={protectedRoute(<Dashboard user={user} />)} />

      <Route path="/contacts" element={protectedRoute(<Contacts />)} />

      <Route path="/contacts/add" element={protectedRoute(<AddContacts />)} />

      <Route path="/messages" element={protectedRoute(<Messages />)} />

      <Route path="/profile" element={protectedRoute(<Profile user={user} />)} />

      <Route path="/campaigns" element={protectedRoute(<Campaigns />)} />

      <Route path="/settings" element={protectedRoute(<Settings />)} />

      <Route
        path="/settings/profile"
        element={protectedRoute(<Profile user={user} />)}
      />

      <Route path="/settings/account" element={<Navigate to="/settings/profile" />} />

      <Route path="/campaigns/create" element={<Navigate to="/campaigns/create/setup" />} />
      <Route path="/campaigns/create/setup" element={protectedRoute(<CampaignCreateSetupPage />)} />
      <Route
        path="/campaigns/create/design"
        element={protectedRoute(<CampaignCreateDesignPage />)}
      />
      <Route
        path="/campaigns/create/content"
        element={protectedRoute(<CampaignCreateContentPage />)}
      />
      <Route path="/campaigns/create/send" element={protectedRoute(<CampaignCreateSendPage />)} />

      {/* FALLBACK */}
      <Route path="*" element={<Navigate to="/dashboard" />} />
    </Routes>
  );
}

export default App;

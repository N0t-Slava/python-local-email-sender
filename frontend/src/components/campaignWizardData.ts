export type CampaignWizardStep = "setup" | "design" | "content" | "send";
export type AudienceTab = "all" | "segment" | "tag" | "advanced";
export type DeliveryType = "immediate" | "scheduled";
export type ContentEditorTab = "content" | "rows" | "settings";
export type DesignChoiceId =
  | "announce"
  | "birthday"
  | "explore"
  | "share"
  | "update"
  | "welcome"
  | "scratch-drag"
  | "scratch-code";
export type DesignSidebarItemId =
  | "yours"
  | "branded"
  | "inspirational"
  | "drag"
  | "code"
  | "campaigns"
  | "automations";

export type DesignTemplate = {
  id: DesignChoiceId;
  name: string;
  tone: "hero" | "split" | "text";
};

export type SendingCheckResult = {
  can_send: boolean;
  from_email: string;
  domain: string;
  blockers: string[];
  warnings: string[];
};

export const campaignWizardSteps: { id: CampaignWizardStep; label: string }[] = [
  { id: "setup", label: "Setup" },
  { id: "design", label: "Design" },
  { id: "content", label: "Content" },
  { id: "send", label: "Send" }
];

export const designTemplates: DesignTemplate[] = [
  { id: "announce", name: "Announce", tone: "hero" },
  { id: "birthday", name: "Birthday", tone: "split" },
  { id: "explore", name: "Explore", tone: "hero" },
  { id: "share", name: "Share", tone: "text" },
  { id: "update", name: "Update", tone: "split" },
  { id: "welcome", name: "Welcome", tone: "text" }
];

export const defaultEmailContent = `

This is a plain text style template, which uses our drag and drop editor. It's perfect for building out simple and personal emails.

Drag in any element from the left-hand side to begin to enrich your design.

Many thanks,`;

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function buildEmailCanvasHtml(content: string) {
  const paragraphs = content
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
    .map(
      (paragraph) =>
        `<p style="margin:0 0 18px;font:16px/1.65 Arial,sans-serif;color:#1f1f29;">${escapeHtml(
          paragraph
        ).replaceAll("\n", "<br />")}</p>`
    )
    .join("");

  return `<div style="background:#ffffff;padding:40px 48px;max-width:680px;margin:0 auto;">${paragraphs}<div style="border-top:1px solid #dadde6;margin-top:34px;padding-top:22px;font:13px/1.55 Arial,sans-serif;color:#626270;">You received this email because you subscribed to our list. You can unsubscribe at any time.<br /><br /><br /><br />Powered by Mailflow</div></div>`;
}

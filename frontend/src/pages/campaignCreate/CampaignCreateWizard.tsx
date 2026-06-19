import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CampaignWizardLayout,
  ContentEditorPage,
  DesignPage,
  SendReviewPage,
  SetupPage
} from "../../components/campaignWizard";
import {
  buildEmailCanvasHtml,
  campaignWizardSteps,
  defaultEmailContent,
  designTemplates,
  type AudienceTab,
  type CampaignWizardStep,
  type ContentEditorTab,
  type DeliveryType,
  type DesignSidebarItemId,
  type SendingCheckResult
} from "../../components/campaignWizardData";

type Contact = {
  id: string;
  email: string;
  name?: string | null;
};

type ContentType = "plain" | "html" | "multipart";

type CampaignCreationState = {
  campaignTitle: string;
  fromName: string;
  fromEmail: string;
  subject: string;
  previewText: string;
  audienceType: AudienceTab;
  selectedSegment: string;
  selectedTag: string;
  openTracking: boolean;
  clickTracking: boolean;
  googleAnalyticsTracking: boolean;
  personalisedToField: boolean;
  selectedTemplate: string;
  emailContent: string;
  deliveryType: DeliveryType;
  scheduledAt: string;
  selectedEmails: string[];
};

type EmailPreviewPayload = {
  subject: string;
  body: string;
  htmlBody: string;
  contentType: ContentType;
  previewEmail: string;
};

const API_URL = "http://localhost:8000";
const CAMPAIGN_CREATION_DRAFT_KEY = "mailflow:campaign-creation-draft";
const EMAIL_PATTERN = /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i;

const defaultCampaignCreationState: CampaignCreationState = {
  campaignTitle: "Untitled",
  fromName: "",
  fromEmail: "",
  subject: "",
  previewText: "",
  audienceType: "all",
  selectedSegment: "",
  selectedTag: "",
  openTracking: true,
  clickTracking: true,
  googleAnalyticsTracking: false,
  personalisedToField: true,
  selectedTemplate: "",
  emailContent: defaultEmailContent,
  deliveryType: "immediate",
  scheduledAt: "",
  selectedEmails: []
};

const wizardStepPaths: Record<CampaignWizardStep, string> = {
  setup: "/campaigns/create/setup",
  design: "/campaigns/create/design",
  content: "/campaigns/create/content",
  send: "/campaigns/create/send"
};

function readCampaignCreationDraft() {
  if (typeof window === "undefined") {
    return defaultCampaignCreationState;
  }

  try {
    const storedDraft = window.localStorage.getItem(CAMPAIGN_CREATION_DRAFT_KEY);
    if (!storedDraft) {
      return defaultCampaignCreationState;
    }

    const parsedDraft = JSON.parse(storedDraft) as Partial<CampaignCreationState>;
    return {
      ...defaultCampaignCreationState,
      ...parsedDraft
    };
  } catch {
    return defaultCampaignCreationState;
  }
}

function persistCampaignCreationDraft(draft: CampaignCreationState) {
  if (typeof window === "undefined") {
    return;
  }

  // TODO: move wizard-only fields into the backend draft API when it supports them.
  window.localStorage.setItem(CAMPAIGN_CREATION_DRAFT_KEY, JSON.stringify(draft));
}

function clearCampaignCreationDraft() {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(CAMPAIGN_CREATION_DRAFT_KEY);
}

function buildRecipientCsv(emails: string[]) {
  const rows = emails.map((email) => `"${email.replaceAll('"', '""')}"`);
  return `email\n${rows.join("\n")}`;
}

function buildPreviewVariables(subject: string, body: string, htmlBody: string) {
  const variables: Record<string, string> = {
    company: "Acme",
    coupon_code: "SAVE20"
  };
  const source = `${subject}\n${body}\n${htmlBody}`;
  const matches = source.matchAll(/\{\{\s*variables\.([A-Za-z_][A-Za-z0-9_]*)/g);

  for (const match of matches) {
    const name = match[1];
    if (!variables[name]) {
      variables[name] = "Sample";
    }
  }

  return variables;
}

export default function CampaignCreateWizard({ step }: { step: CampaignWizardStep }) {
  const navigate = useNavigate();
  const [campaignCreationState, setCampaignCreationState] =
    useState<CampaignCreationState>(readCampaignCreationDraft);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selectedEmails, setSelectedEmails] = useState<string[]>(
    campaignCreationState.selectedEmails
  );
  const [campaignTitle, setCampaignTitle] = useState(campaignCreationState.campaignTitle);
  const [activeAudienceTab, setActiveAudienceTab] = useState<AudienceTab>(
    campaignCreationState.audienceType
  );
  const [selectedSegment, setSelectedSegment] = useState(campaignCreationState.selectedSegment);
  const [selectedTag, setSelectedTag] = useState(campaignCreationState.selectedTag);
  const [activeDesignSidebarItem, setActiveDesignSidebarItem] =
    useState<DesignSidebarItemId>("branded");
  const [selectedDesignTemplate, setSelectedDesignTemplate] = useState(
    campaignCreationState.selectedTemplate
  );
  const [designSearch, setDesignSearch] = useState("");
  const [designSortDirection, setDesignSortDirection] = useState<"asc" | "desc">("asc");
  const [activeContentEditorTab, setActiveContentEditorTab] =
    useState<ContentEditorTab>("content");
  const [emailContentTemplate, setEmailContentTemplate] = useState(
    campaignCreationState.emailContent
  );
  const [subject, setSubject] = useState(campaignCreationState.subject);
  const [previewText, setPreviewText] = useState(campaignCreationState.previewText);
  const [body, setBody] = useState(campaignCreationState.emailContent);
  const [fromEmail, setFromEmail] = useState(campaignCreationState.fromEmail);
  const [fromName, setFromName] = useState(campaignCreationState.fromName);
  const [replyToEmail, setReplyToEmail] = useState("");
  const [sendRatePerSecond] = useState("");
  const [deliveryType, setDeliveryType] = useState<DeliveryType>(
    campaignCreationState.deliveryType
  );
  const [scheduledAt, setScheduledAt] = useState(campaignCreationState.scheduledAt);
  const [trackOpens, setTrackOpens] = useState(campaignCreationState.openTracking);
  const [trackClicks, setTrackClicks] = useState(campaignCreationState.clickTracking);
  const [googleAnalyticsTracking, setGoogleAnalyticsTracking] = useState(
    campaignCreationState.googleAnalyticsTracking
  );
  const [personalizedToField, setPersonalizedToField] = useState(
    campaignCreationState.personalisedToField
  );
  const [category] = useState("");
  const [tags] = useState("");
  const [htmlBody, setHtmlBody] = useState(buildEmailCanvasHtml(campaignCreationState.emailContent));
  const [contentType, setContentType] = useState<ContentType>("plain");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [fromEmailCheck, setFromEmailCheck] = useState<SendingCheckResult | null>(null);
  const [fromEmailCheckLoading, setFromEmailCheckLoading] = useState(false);
  const [fromEmailCheckError, setFromEmailCheckError] = useState("");
  const titleInputRef = useRef<HTMLInputElement | null>(null);
  const initializedSelectedEmailsRef = useRef(campaignCreationState.selectedEmails.length > 0);

  const validContacts = useMemo(
    () => contacts.filter((contact) => EMAIL_PATTERN.test(contact.email)),
    [contacts]
  );
  const campaignRecipientEmails = useMemo(
    () => selectedEmails.filter((email) => EMAIL_PATTERN.test(email)),
    [selectedEmails]
  );

  const filteredDesignTemplates = useMemo(() => {
    const term = designSearch.trim().toLowerCase();
    return designTemplates
      .filter((template) => !term || template.name.toLowerCase().includes(term))
      .sort((a, b) =>
        designSortDirection === "asc"
          ? a.name.localeCompare(b.name)
          : b.name.localeCompare(a.name)
      );
  }, [designSearch, designSortDirection]);

  useEffect(() => {
    async function loadContacts() {
      try {
        const res = await fetch(`${API_URL}/contacts`, {
          method: "GET",
          credentials: "include"
        });

        if (res.ok) {
          setContacts(await res.json());
        }
      } catch {
        setContacts([]);
      }
    }

    loadContacts();
  }, []);

  useEffect(() => {
    if (initializedSelectedEmailsRef.current) {
      return;
    }

    if (validContacts.length > 0) {
      initializedSelectedEmailsRef.current = true;
      setSelectedEmails(validContacts.map((contact) => contact.email));
    }
  }, [validContacts]);

  useEffect(() => {
    setBody(emailContentTemplate);
    setHtmlBody(buildEmailCanvasHtml(emailContentTemplate));
  }, [emailContentTemplate]);

  useEffect(() => {
    const nextCampaignCreationState: CampaignCreationState = {
      campaignTitle,
      fromName,
      fromEmail,
      subject,
      previewText,
      audienceType: activeAudienceTab,
      selectedSegment,
      selectedTag,
      openTracking: trackOpens,
      clickTracking: trackClicks,
      googleAnalyticsTracking,
      personalisedToField: personalizedToField,
      selectedTemplate: selectedDesignTemplate,
      emailContent: emailContentTemplate,
      deliveryType,
      scheduledAt,
      selectedEmails
    };

    setCampaignCreationState(nextCampaignCreationState);
    persistCampaignCreationDraft(nextCampaignCreationState);
  }, [
    activeAudienceTab,
    campaignTitle,
    deliveryType,
    emailContentTemplate,
    fromEmail,
    fromName,
    googleAnalyticsTracking,
    personalizedToField,
    previewText,
    scheduledAt,
    selectedDesignTemplate,
    selectedEmails,
    selectedSegment,
    selectedTag,
    subject,
    trackClicks,
    trackOpens
  ]);

  useEffect(() => {
    const normalizedFromEmail = fromEmail.trim().toLowerCase();
    setFromEmailCheck(null);
    setFromEmailCheckError("");

    if (!EMAIL_PATTERN.test(normalizedFromEmail)) {
      setFromEmailCheckLoading(false);
      return;
    }

    let cancelled = false;
    setFromEmailCheckLoading(true);

    const timeoutId = window.setTimeout(async () => {
      try {
        const res = await fetch(`${API_URL}/domains/check-sending`, {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            from_email: normalizedFromEmail
          })
        });

        if (!res.ok) {
          const payload = await res.json().catch(() => null);
          throw new Error(payload?.detail || "Failed to check sender domain");
        }

        const result = await res.json();
        if (!cancelled) {
          setFromEmailCheck(result);
        }
      } catch (err) {
        if (!cancelled) {
          setFromEmailCheckError(
            err instanceof Error ? err.message : "Failed to check sender domain"
          );
        }
      } finally {
        if (!cancelled) {
          setFromEmailCheckLoading(false);
        }
      }
    }, 500);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [fromEmail]);

  function resetWizard() {
    clearCampaignCreationDraft();
    setCampaignCreationState(defaultCampaignCreationState);
    setCampaignTitle("Untitled");
    setFromName("");
    setFromEmail("");
    setReplyToEmail("");
    setSubject("");
    setPreviewText("");
    setActiveAudienceTab("all");
    setSelectedSegment("");
    setSelectedTag("");
    setTrackOpens(true);
    setTrackClicks(true);
    setGoogleAnalyticsTracking(false);
    setPersonalizedToField(true);
    setSelectedDesignTemplate("");
    setActiveDesignSidebarItem("branded");
    setDesignSearch("");
    setDesignSortDirection("asc");
    setActiveContentEditorTab("content");
    setEmailContentTemplate(defaultEmailContent);
    setBody(defaultEmailContent);
    setHtmlBody(buildEmailCanvasHtml(defaultEmailContent));
    setDeliveryType("immediate");
    setScheduledAt("");
    setSelectedEmails([]);
    initializedSelectedEmailsRef.current = false;
    setContentType("plain");
  }

  function buildCampaignDraftFormData() {
    const formData = new FormData();
    formData.append("subject", subject.trim());
    formData.append("body", body);
    formData.append("from_email", fromEmail.trim());
    formData.append("from_name", fromName.trim());
    formData.append("reply_to_email", replyToEmail.trim());
    formData.append("send_rate_per_second", sendRatePerSecond.trim());
    formData.append("track_opens", String(trackOpens));
    formData.append("track_clicks", String(trackClicks));
    formData.append("category", category.trim());
    formData.append("tags", tags.trim());
    formData.append("html_body", htmlBody);
    formData.append("content_type", contentType);
    formData.append(
      "csv_file",
      new Blob([buildRecipientCsv(campaignRecipientEmails)], { type: "text/csv" }),
      "recipients.csv"
    );

    return formData;
  }

  async function saveWizardProgress() {
    const res = await fetch(`${API_URL}/campaigns/draft`, {
      method: "POST",
      credentials: "include",
      body: buildCampaignDraftFormData()
    });

    if (!res.ok) {
      const payload = await res.json().catch(() => null);
      throw new Error(payload?.detail || "Failed to save campaign draft");
    }
  }

  function validateForm() {
    if (!subject.trim() || !fromEmail.trim()) {
      setError("Subject and from email are required");
      return false;
    }

    if (contentType === "plain" && !body.trim()) {
      setError("Plain text body is required");
      return false;
    }

    if (contentType === "html" && !htmlBody.trim()) {
      setError("HTML body is required");
      return false;
    }

    if (contentType === "multipart" && (!body.trim() || !htmlBody.trim())) {
      setError("Multipart campaigns require both plain text body and HTML body");
      return false;
    }

    if (!EMAIL_PATTERN.test(fromEmail.trim())) {
      setError("From email is invalid");
      return false;
    }

    if (replyToEmail.trim() && !EMAIL_PATTERN.test(replyToEmail.trim())) {
      setError("Reply-to email is invalid");
      return false;
    }

    if (campaignRecipientEmails.length === 0) {
      setError("Choose at least one recipient");
      return false;
    }

    return true;
  }

  async function requestEmailPreview(payload: EmailPreviewPayload) {
    const res = await fetch(`${API_URL}/email-templates/preview`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        subject: payload.subject.trim(),
        body: payload.body,
        html_body: payload.htmlBody || null,
        content_type: payload.contentType,
        contact: {
          email: payload.previewEmail,
          name: "Recipient"
        },
        variables: buildPreviewVariables(payload.subject, payload.body, payload.htmlBody)
      })
    });

    if (!res.ok) {
      const responsePayload = await res.json().catch(() => null);
      throw new Error(responsePayload?.detail || "Failed to preview email");
    }
  }

  async function previewRenderedEmail() {
    setError("");
    setSuccess("");

    if (!subject.trim()) {
      setError("Subject is required");
      return;
    }

    const previewEmail = campaignRecipientEmails[0] || "recipient@example.com";
    setPreviewLoading(true);

    try {
      await requestEmailPreview({
        subject,
        body,
        htmlBody,
        contentType,
        previewEmail
      });
      setSuccess("Preview rendered successfully");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to preview email");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function submitCampaign(mode: "send" | "schedule") {
    setError("");
    setSuccess("");

    if (!validateForm()) {
      return;
    }

    if (mode === "schedule") {
      if (!scheduledAt.trim()) {
        setError("Scheduled time is required");
        return;
      }

      const scheduledDate = new Date(scheduledAt);
      if (Number.isNaN(scheduledDate.getTime()) || scheduledDate <= new Date()) {
        setError("Scheduled time must be in the future");
        return;
      }
    }

    setSaving(true);

    try {
      const res = await fetch(`${API_URL}/campaigns/create`, {
        method: "POST",
        credentials: "include",
        body: buildCampaignDraftFormData()
      });

      if (!res.ok) {
        throw new Error("Failed to send campaign");
      }

      const created = await res.json();
      const campaignId = created?.campaign?.id;

      if (!campaignId) {
        throw new Error(
          mode === "schedule"
            ? "Campaign was created but could not be scheduled"
            : "Campaign was created but could not be sent"
        );
      }

      if (mode === "send") {
        const sendRes = await fetch(`${API_URL}/campaigns/${campaignId}/send`, {
          method: "POST",
          credentials: "include"
        });

        if (!sendRes.ok) {
          throw new Error("Campaign was saved but failed to start sending");
        }
      }

      if (mode === "schedule") {
        const scheduleData = new FormData();
        scheduleData.append("scheduled_at", new Date(scheduledAt).toISOString());
        const scheduleRes = await fetch(`${API_URL}/campaigns/${campaignId}/schedule`, {
          method: "POST",
          credentials: "include",
          body: scheduleData
        });

        if (!scheduleRes.ok) {
          const payload = await scheduleRes.json().catch(() => null);
          const detail = payload?.detail;
          throw new Error(
            typeof detail === "string"
              ? detail
              : detail?.message || "Campaign was saved but failed to schedule"
          );
        }
      }

      resetWizard();
      navigate("/campaigns");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send campaign");
    } finally {
      setSaving(false);
    }
  }

  async function handlePrimaryAction() {
    persistCampaignCreationDraft(campaignCreationState);

    if (step === "send") {
      await submitCampaign(deliveryType === "scheduled" ? "schedule" : "send");
      return;
    }

    setError("");
    setSuccess("");
    setSaving(true);

    try {
      await saveWizardProgress();
      const activeStepIndex = campaignWizardSteps.findIndex((wizardStep) => wizardStep.id === step);
      const nextStep = campaignWizardSteps[activeStepIndex + 1];
      if (nextStep) {
        navigate(wizardStepPaths[nextStep.id]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save campaign draft");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-full bg-[#FAFAFC] p-6 text-[#1F1F29] md:p-10">
      {error && <p className="mt-0 text-app-error">{error}</p>}
      {success && <p className="mt-0 font-bold text-app-success">{success}</p>}

      <CampaignWizardLayout
        campaignTitle={campaignTitle}
        titleInputRef={titleInputRef}
        activeStep={step}
        saving={saving}
        previewLoading={previewLoading}
        onCampaignTitleChange={setCampaignTitle}
        onStepChange={(wizardStep) => navigate(wizardStepPaths[wizardStep])}
        onPrimaryAction={handlePrimaryAction}
        onPreview={previewRenderedEmail}
        onClose={() => {
          resetWizard();
          navigate("/campaigns");
        }}>
        {step === "setup" && (
          <SetupPage
            fromName={fromName}
            fromEmail={fromEmail}
            subject={subject}
            previewText={previewText}
            audienceType={activeAudienceTab}
            openTracking={trackOpens}
            clickTracking={trackClicks}
            contacts={validContacts}
            selectedEmails={selectedEmails}
            fromEmailCheck={fromEmailCheck}
            fromEmailCheckLoading={fromEmailCheckLoading}
            fromEmailCheckError={fromEmailCheckError}
            onFromNameChange={setFromName}
            onFromEmailChange={(value) => {
              setFromEmail(value);
              setReplyToEmail(value);
            }}
            onSubjectChange={setSubject}
            onPreviewTextChange={setPreviewText}
            onAudienceTypeChange={setActiveAudienceTab}
            onOpenTrackingChange={setTrackOpens}
            onClickTrackingChange={setTrackClicks}
            onSelectedEmailsChange={setSelectedEmails}
          />
        )}

        {step === "design" && (
          <DesignPage
            activeSidebarItem={activeDesignSidebarItem}
            selectedTemplate={selectedDesignTemplate}
            search={designSearch}
            sortDirection={designSortDirection}
            templates={filteredDesignTemplates}
            onSidebarItemChange={(item, designChoice) => {
              setActiveDesignSidebarItem(item);
              if (designChoice) {
                setSelectedDesignTemplate(designChoice);
              }
            }}
            onTemplateSelect={(template) => {
              setSelectedDesignTemplate(template);
              setActiveDesignSidebarItem("branded");
              setContentType("html");
            }}
            onSearchChange={setDesignSearch}
            onSortDirectionChange={setDesignSortDirection}
          />
        )}

        {step === "content" && (
          <ContentEditorPage
            activeTab={activeContentEditorTab}
            content={emailContentTemplate}
            onTabChange={setActiveContentEditorTab}
            onContentChange={setEmailContentTemplate}
          />
        )}

        {step === "send" && (
          <SendReviewPage
            deliveryType={deliveryType}
            scheduledAt={scheduledAt}
            fromName={fromName}
            fromEmail={fromEmail}
            subject={subject}
            content={emailContentTemplate}
            recipientCount={campaignRecipientEmails.length}
            onDeliveryTypeChange={setDeliveryType}
            onScheduledAtChange={setScheduledAt}
            onEditSetup={() => navigate(wizardStepPaths.setup)}
            onEditContent={() => navigate(wizardStepPaths.content)}
            onPreview={previewRenderedEmail}
          />
        )}
      </CampaignWizardLayout>
    </div>
  );
}

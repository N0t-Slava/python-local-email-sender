import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CampaignWizardLayout,
  ContentEditorPage,
  DesignPage,
  SendReviewPage,
  SetupPage
} from "../components/campaignWizard";
import SelectField from "../components/SelectField";
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
} from "../components/campaignWizardData";

type Contact = {
  id: string;
  email: string;
};

type ContentType = "plain" | "html" | "multipart";
type CampaignsTab = "campaigns" | "templates";

type Campaign = {
  id: string;
  task_id?: string | null;
  subject: string;
  body: string;
  html_body?: string | null;
  content_type?: ContentType;
  from_email: string;
  from_name?: string | null;
  reply_to_email?: string | null;
  queued_recipients: number;
  sent_count?: number;
  opened_count?: number;
  clicked_count?: number;
  status: string;
  created_at: string;
  recipients?: string[];
  batch_size?: number | null;
  per_batch_delay?: number | null;
  send_rate_per_second?: number | null;
  track_opens?: boolean;
  track_clicks?: boolean;
  category?: string | null;
  tags?: string[];
  scheduled_at?: string | null;
};

type EmailTemplate = {
  id: string;
  name: string;
  subject: string;
  body: string;
  html_body?: string | null;
  content_type: ContentType;
};

type EmailPreview = {
  subject: string;
  body: string;
  html_body?: string | null;
  content_type: ContentType;
};

type EmailPreviewPayload = {
  subject: string;
  body: string;
  htmlBody: string;
  contentType: ContentType;
  previewEmail: string;
};

type CampaignsProps = {
  startCreating?: boolean;
};

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

const API_URL = "http://localhost:8000";
const CAMPAIGN_CREATION_DRAFT_KEY = "mailflow:campaign-creation-draft";
const EMAIL_PATTERN = /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i;
const statusFilters = [
  { label: "All", icon: "☰" },
  { label: "Sent", icon: "✓" },
  { label: "Sending", icon: "◷" },
  { label: "Paused", icon: "Ⅱ" },
  { label: "Partially Sent", icon: "!" },
  { label: "Failed", icon: "×" },
  { label: "Cancelled", icon: "×" },
  { label: "Scheduled", icon: "◷" }
];
const pageTabs: { id: CampaignsTab; label: string }[] = [
  { id: "campaigns", label: "Campaigns" },
  { id: "templates", label: "Templates" }
];
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

function normalizeStatus(status: string) {
  if (status.toLowerCase() === "queued") {
    return "Sent";
  }

  return status || "Draft";
}

function formatRate(count: number | undefined, total: number | undefined) {
  if (!total || total <= 0) {
    return "0%";
  }

  return `${Math.round(((count || 0) / total) * 100)}%`;
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

function hasDraftContent(draft: DraftState) {
  return (
    draft.subject.trim().length > 0 ||
    draft.body.trim().length > 0 ||
    draft.htmlBody.trim().length > 0 ||
    draft.fromEmail.trim().length > 0 ||
    draft.fromName.trim().length > 0 ||
    draft.replyToEmail.trim().length > 0 ||
    draft.sendRatePerSecond.trim().length > 0 ||
    draft.scheduledAt.trim().length > 0 ||
    draft.deliveryType !== "immediate" ||
    draft.selectedDesignTemplate.trim().length > 0 ||
    draft.category.trim().length > 0 ||
    draft.tags.trim().length > 0 ||
    draft.selectedEmails.length > 0 ||
    draft.contentType !== "plain" ||
    !draft.trackOpens ||
    !draft.trackClicks
  );
}

type DraftState = {
  isCreating: boolean;
  subject: string;
  body: string;
  fromEmail: string;
  fromName: string;
  replyToEmail: string;
  sendRatePerSecond: string;
  scheduledAt: string;
  deliveryType: DeliveryType;
  selectedDesignTemplate: string;
  trackOpens: boolean;
  trackClicks: boolean;
  category: string;
  tags: string;
  selectedEmails: string[];
  htmlBody: string;
  contentType: ContentType;
};

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function formatDateTimeLocal(value: string | null | undefined) {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const offsetMs = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

function isInDateFilter(value: string, filter: string) {
  if (filter === "all") {
    return true;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return false;
  }

  const now = Date.now();
  const diff = now - date.getTime();
  const day = 24 * 60 * 60 * 1000;

  if (filter === "today") {
    return new Date(value).toDateString() === new Date().toDateString();
  }

  if (filter === "7") {
    return diff <= 7 * day;
  }

  if (filter === "30") {
    return diff <= 30 * day;
  }

  return true;
}

export default function Campaigns({ startCreating = false }: CampaignsProps) {
  const navigate = useNavigate();
  const [campaignCreationState, setCampaignCreationState] =
    useState<CampaignCreationState>(readCampaignCreationDraft);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [statusFilter, setStatusFilter] = useState("All");
  const [activeTab, setActiveTab] = useState<CampaignsTab>("campaigns");
  const [dateFilter, setDateFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [sortDirection, setSortDirection] = useState<"desc" | "asc">("desc");
  const [openActionsId, setOpenActionsId] = useState("");
  const [isCreating, setIsCreating] = useState(startCreating);
  const [activeWizardStep, setActiveWizardStep] = useState<CampaignWizardStep>("setup");
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
  const [activeContentEditorTab, setActiveContentEditorTab] = useState<ContentEditorTab>("content");
  const [emailContentTemplate, setEmailContentTemplate] = useState(
    campaignCreationState.emailContent
  );
  const [subject, setSubject] = useState(campaignCreationState.subject);
  const [previewText, setPreviewText] = useState(campaignCreationState.previewText);
  const [body, setBody] = useState(campaignCreationState.emailContent);
  const [fromEmail, setFromEmail] = useState(campaignCreationState.fromEmail);
  const [fromName, setFromName] = useState(campaignCreationState.fromName);
  const [replyToEmail, setReplyToEmail] = useState("");
  const [sendRatePerSecond, setSendRatePerSecond] = useState("");
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
  const [category, setCategory] = useState("");
  const [tags, setTags] = useState("");
  const [selectedEmails, setSelectedEmails] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [htmlBody, setHtmlBody] = useState(
    buildEmailCanvasHtml(campaignCreationState.emailContent)
  );
  const [contentType, setContentType] = useState<ContentType>("plain");
  const [emailTemplates, setEmailTemplates] = useState<EmailTemplate[]>([]);
  const [deletingTemplateId, setDeletingTemplateId] = useState("");
  const [deletingCampaignId, setDeletingCampaignId] = useState("");
  const [controllingCampaignId, setControllingCampaignId] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [fromEmailCheck, setFromEmailCheck] = useState<SendingCheckResult | null>(null);
  const [fromEmailCheckLoading, setFromEmailCheckLoading] = useState(false);
  const [fromEmailCheckError, setFromEmailCheckError] = useState("");
  const [previewingTemplateId, setPreviewingTemplateId] = useState("");
  const [templatePreviewName, setTemplatePreviewName] = useState("");
  const [templatePreview, setTemplatePreview] = useState<EmailPreview | null>(null);
  const subjectInputRef = useRef<HTMLInputElement | null>(null);
  const draftStateRef = useRef<DraftState>({
    isCreating: startCreating,
    subject: "",
    body: "",
    fromEmail: "",
    fromName: "",
    replyToEmail: "",
    sendRatePerSecond: "",
    scheduledAt: "",
    deliveryType: "immediate",
    selectedDesignTemplate: "",
    trackOpens: true,
    trackClicks: true,
    category: "",
    tags: "",
    selectedEmails: [],
    htmlBody: "",
    contentType: "plain"
  });

  const validContacts = useMemo(
    () => contacts.filter((contact) => EMAIL_PATTERN.test(contact.email)),
    [contacts]
  );
  const campaignRecipientEmails = useMemo(
    () =>
      selectedEmails.length > 0 ? selectedEmails : validContacts.map((contact) => contact.email),
    [selectedEmails, validContacts]
  );

  const filteredCampaigns = useMemo(() => {
    return campaigns
      .filter((campaign) => {
        const status = normalizeStatus(campaign.status);
        const matchesStatus = statusFilter === "All" || status === statusFilter;
        const term = search.trim().toLowerCase();
        const matchesSearch =
          !term ||
          campaign.subject.toLowerCase().includes(term) ||
          campaign.body.toLowerCase().includes(term) ||
          (campaign.html_body || "").toLowerCase().includes(term);

        return matchesStatus && matchesSearch && isInDateFilter(campaign.created_at, dateFilter);
      })
      .sort((a, b) => {
        const left = new Date(a.created_at).getTime();
        const right = new Date(b.created_at).getTime();
        return sortDirection === "desc" ? right - left : left - right;
      });
  }, [campaigns, dateFilter, search, sortDirection, statusFilter]);

  const filteredDesignTemplates = useMemo(() => {
    const term = designSearch.trim().toLowerCase();
    return designTemplates
      .filter((template) => !term || template.name.toLowerCase().includes(term))
      .sort((a, b) =>
        designSortDirection === "asc" ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name)
      );
  }, [designSearch, designSortDirection]);

  function openCreateWizard(
    draft: Partial<CampaignCreationState> = {},
    step: CampaignWizardStep = "setup"
  ) {
    persistCampaignCreationDraft({
      ...defaultCampaignCreationState,
      ...draft
    });
    navigate(`/campaigns/create/${step}`);
  }

  const loadCampaigns = useCallback(async () => {
    const res = await fetch(`${API_URL}/campaigns`, {
      method: "GET",
      credentials: "include"
    });

    if (!res.ok) {
      throw new Error("Failed to load campaigns");
    }

    setCampaigns(await res.json());
  }, []);

  const loadContacts = useCallback(async () => {
    const res = await fetch(`${API_URL}/contacts`, {
      method: "GET",
      credentials: "include"
    });

    if (!res.ok) {
      throw new Error("Failed to load contacts");
    }

    setContacts(await res.json());
  }, []);

  const loadEmailTemplates = useCallback(async () => {
    const res = await fetch(`${API_URL}/email-templates`, {
      method: "GET",
      credentials: "include"
    });

    if (!res.ok) {
      throw new Error("Failed to load email templates");
    }

    setEmailTemplates(await res.json());
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      await Promise.all([loadCampaigns(), loadContacts(), loadEmailTemplates()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load campaign data");
    } finally {
      setLoading(false);
    }
  }, [loadCampaigns, loadContacts, loadEmailTemplates]);

  useEffect(() => {
    loadData();
  }, [loadData]);

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
    draftStateRef.current = {
      isCreating,
      subject,
      body,
      fromEmail,
      fromName,
      replyToEmail,
      sendRatePerSecond,
      scheduledAt,
      deliveryType,
      selectedDesignTemplate,
      trackOpens,
      trackClicks,
      category,
      tags,
      selectedEmails: campaignRecipientEmails,
      htmlBody,
      contentType
    };
  }, [
    body,
    category,
    contentType,
    deliveryType,
    fromEmail,
    fromName,
    htmlBody,
    isCreating,
    replyToEmail,
    scheduledAt,
    selectedEmails,
    campaignRecipientEmails,
    selectedDesignTemplate,
    sendRatePerSecond,
    subject,
    tags,
    trackClicks,
    trackOpens
  ]);

  useEffect(() => {
    const normalizedFromEmail = fromEmail.trim().toLowerCase();
    setFromEmailCheck(null);
    setFromEmailCheckError("");

    if (!isCreating || !EMAIL_PATTERN.test(normalizedFromEmail)) {
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
  }, [fromEmail, isCreating]);

  useEffect(() => {
    return () => {
      const draft = draftStateRef.current;
      if (!draft.isCreating || !hasDraftContent(draft)) {
        return;
      }

      const formData = new FormData();
      formData.append("subject", draft.subject.trim());
      formData.append("body", draft.body);
      formData.append("from_email", draft.fromEmail.trim());
      formData.append("from_name", draft.fromName.trim());
      formData.append("reply_to_email", draft.replyToEmail.trim());
      formData.append("send_rate_per_second", draft.sendRatePerSecond.trim());
      formData.append("track_opens", String(draft.trackOpens));
      formData.append("track_clicks", String(draft.trackClicks));
      formData.append("category", draft.category.trim());
      formData.append("tags", draft.tags.trim());
      formData.append("html_body", draft.htmlBody);
      formData.append("content_type", draft.contentType);
      formData.append(
        "csv_file",
        new Blob([buildRecipientCsv(draft.selectedEmails)], { type: "text/csv" }),
        "recipients.csv"
      );

      void fetch(`${API_URL}/campaigns/draft`, {
        method: "POST",
        credentials: "include",
        body: formData
      });
    };
  }, []);

  function resetForm() {
    draftStateRef.current = {
      isCreating: false,
      subject: "",
      body: "",
      fromEmail: "",
      fromName: "",
      replyToEmail: "",
      sendRatePerSecond: "",
      scheduledAt: "",
      deliveryType: "immediate",
      selectedDesignTemplate: "",
      trackOpens: true,
      trackClicks: true,
      category: "",
      tags: "",
      selectedEmails: [],
      htmlBody: "",
      contentType: "plain"
    };
    setSubject("");
    setCampaignTitle("Untitled");
    setPreviewText("");
    setSelectedDesignTemplate("");
    setActiveDesignSidebarItem("branded");
    setDesignSearch("");
    setDesignSortDirection("asc");
    setActiveContentEditorTab("content");
    setEmailContentTemplate(defaultEmailContent);
    setBody(defaultEmailContent);
    setHtmlBody(buildEmailCanvasHtml(defaultEmailContent));
    setContentType("multipart");
    setFromEmail("");
    setFromName("");
    setReplyToEmail("");
    setSendRatePerSecond("");
    setDeliveryType("immediate");
    setScheduledAt("");
    setTrackOpens(true);
    setTrackClicks(true);
    setGoogleAnalyticsTracking(false);
    setPersonalizedToField(true);
    setActiveAudienceTab("all");
    setSelectedSegment("");
    setSelectedTag("");
    setCategory("");
    setTags("");
    setSelectedEmails([]);
    setSuccess("");
    setFromEmailCheck(null);
    setFromEmailCheckError("");
    setFromEmailCheckLoading(false);
    setActiveWizardStep("setup");
    clearCampaignCreationDraft();
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

  async function handleWizardPrimaryAction() {
    const currentCampaignCreationState: CampaignCreationState = {
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
    setCampaignCreationState(currentCampaignCreationState);
    persistCampaignCreationDraft(currentCampaignCreationState);

    if (activeWizardStep === "send") {
      await submitCampaign(deliveryType === "scheduled" ? "schedule" : "send");
      return;
    }

    setError("");
    setSuccess("");
    setSaving(true);

    try {
      await saveWizardProgress();
      const activeStepIndex = campaignWizardSteps.findIndex((step) => step.id === activeWizardStep);
      const nextStep = campaignWizardSteps[activeStepIndex + 1];
      if (nextStep) {
        setActiveWizardStep(nextStep.id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save campaign draft");
    } finally {
      setSaving(false);
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

    if (sendRatePerSecond.trim()) {
      const parsedSendRate = Number(sendRatePerSecond);
      if (!Number.isFinite(parsedSendRate) || parsedSendRate <= 0) {
        setError("Send rate must be greater than 0");
        return false;
      }
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

    return (await res.json()) as EmailPreview;
  }

  function startCampaignFromTemplate(template: EmailTemplate) {
    openCreateWizard(
      {
        campaignTitle: template.subject || template.name || "Untitled",
        subject: template.subject,
        emailContent: template.body || defaultEmailContent,
        selectedTemplate: template.id
      },
      "content"
    );
  }

  async function deleteEmailTemplate(template: EmailTemplate) {
    const shouldDelete = window.confirm(`Delete template "${template.name}"?`);
    if (!shouldDelete) {
      return;
    }

    setDeletingTemplateId(template.id);
    setError("");

    try {
      const res = await fetch(`${API_URL}/email-templates/${template.id}`, {
        method: "DELETE",
        credentials: "include"
      });

      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new Error(payload?.detail || "Failed to delete template");
      }

      setEmailTemplates((current) => current.filter((item) => item.id !== template.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete template");
    } finally {
      setDeletingTemplateId("");
    }
  }

  async function deleteCampaign(campaign: Campaign) {
    const shouldDelete = window.confirm(`Delete campaign "${campaign.subject || "Untitled"}"?`);
    if (!shouldDelete) {
      return;
    }

    setDeletingCampaignId(campaign.id);
    setOpenActionsId("");
    setError("");
    setSuccess("");

    try {
      const res = await fetch(`${API_URL}/campaigns/${campaign.id}`, {
        method: "DELETE",
        credentials: "include"
      });

      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new Error(payload?.detail || "Failed to delete campaign");
      }

      setCampaigns((current) => current.filter((item) => item.id !== campaign.id));
      setSuccess("Campaign deleted");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete campaign");
    } finally {
      setDeletingCampaignId("");
    }
  }

  async function controlCampaign(campaign: Campaign, action: "pause" | "resume" | "cancel") {
    if (action === "cancel") {
      const shouldCancel = window.confirm(`Cancel campaign "${campaign.subject || "Untitled"}"?`);
      if (!shouldCancel) {
        return;
      }
    }

    setControllingCampaignId(campaign.id);
    setOpenActionsId("");
    setError("");
    setSuccess("");

    try {
      const res = await fetch(`${API_URL}/campaigns/${campaign.id}/${action}`, {
        method: "POST",
        credentials: "include"
      });

      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new Error(payload?.detail || `Failed to ${action} campaign`);
      }

      const payload = await res.json();
      if (payload?.campaign) {
        setCampaigns((current) =>
          current.map((item) => (item.id === campaign.id ? payload.campaign : item))
        );
      } else {
        await loadCampaigns();
      }

      setSuccess(
        action === "pause"
          ? "Campaign paused"
          : action === "resume"
            ? "Campaign resumed"
            : "Campaign cancelled"
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} campaign`);
    } finally {
      setControllingCampaignId("");
    }
  }

  async function previewRenderedEmail() {
    setError("");
    setSuccess("");

    if (!subject.trim()) {
      setError("Subject is required");
      return;
    }

    if (contentType === "plain" && !body.trim()) {
      setError("Plain text body is required");
      return;
    }

    if (contentType === "html" && !htmlBody.trim()) {
      setError("HTML body is required");
      return;
    }

    if (contentType === "multipart" && (!body.trim() || !htmlBody.trim())) {
      setError("Multipart preview requires both plain text body and HTML body");
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

  async function previewEmailTemplate(template: EmailTemplate) {
    setError("");
    setTemplatePreview(null);
    setTemplatePreviewName(template.name);
    setPreviewingTemplateId(template.id);

    const previewEmail = campaignRecipientEmails[0] || "recipient@example.com";

    try {
      const renderedPreview = await requestEmailPreview({
        subject: template.subject,
        body: template.body || "",
        htmlBody: template.html_body || "",
        contentType: template.content_type || "plain",
        previewEmail
      });
      setTemplatePreview(renderedPreview);
    } catch (err) {
      setTemplatePreviewName("");
      setError(err instanceof Error ? err.message : "Failed to preview template");
    } finally {
      setPreviewingTemplateId("");
    }
  }

  async function submitCampaign(mode: "save" | "send" | "schedule") {
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

      const res = await fetch(`${API_URL}/campaigns/create`, {
        method: "POST",
        credentials: "include",
        body: formData
      });

      if (!res.ok) {
        throw new Error(mode === "save" ? "Failed to save campaign" : "Failed to send campaign");
      }

      const created = await res.json();
      const campaignId = created?.campaign?.id;

      if (mode === "send") {
        if (!campaignId) {
          throw new Error("Campaign was created but could not be sent");
        }

        const sendRes = await fetch(`${API_URL}/campaigns/${campaignId}/send`, {
          method: "POST",
          credentials: "include"
        });

        if (!sendRes.ok) {
          throw new Error("Campaign was saved but failed to start sending");
        }
      }

      if (mode === "schedule") {
        if (!campaignId) {
          throw new Error("Campaign was created but could not be scheduled");
        }

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

      resetForm();
      setIsCreating(false);
      await loadCampaigns();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save campaign");
    } finally {
      setSaving(false);
    }
  }

  async function sendDraft(campaign: Campaign) {
    setOpenActionsId("");
    setError("");

    try {
      const res = await fetch(`${API_URL}/campaigns/${campaign.id}/send`, {
        method: "POST",
        credentials: "include"
      });

      if (!res.ok) {
        throw new Error("Failed to send draft");
      }

      await loadCampaigns();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send draft");
    }
  }

  function duplicateCampaign(campaign: Campaign) {
    setOpenActionsId("");
    openCreateWizard({
      campaignTitle: campaign.subject || "Untitled",
      fromName: campaign.from_name || "",
      fromEmail: campaign.from_email,
      subject: campaign.subject,
      emailContent: campaign.body || defaultEmailContent,
      deliveryType: campaign.scheduled_at ? "scheduled" : "immediate",
      scheduledAt: formatDateTimeLocal(campaign.scheduled_at),
      openTracking: campaign.track_opens ?? true,
      clickTracking: campaign.track_clicks ?? true,
      selectedEmails: campaign.recipients || []
    });
  }

  function editDraft(campaign: Campaign) {
    duplicateCampaign(campaign);
  }

  return (
    <div
      className={[
        "min-h-full p-6 md:p-10",
        isCreating ? "bg-[#FAFAFC] text-[#1F1F29]" : "bg-app-bg text-app-text"
      ].join(" ")}>
      <header className="mb-7 flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
        <h1 className="m-0 text-4xl font-black md:text-[40px]">Campaigns</h1>
        <button
          type="button"
          onClick={() => openCreateWizard()}
          className="btn btn-primary rounded-full px-6">
          Create
        </button>
      </header>

      <div className="mb-4 flex flex-wrap gap-1.5 border-b border-app-border">
        {pageTabs.map((tab) => {
          const selected = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={[
                "rounded-t-lg border border-transparent border-b-[3px] px-4 py-2.5 font-extrabold",
                selected
                  ? "border-b-app-accent bg-[#FFF3A5] text-app-text"
                  : "border-b-transparent text-app-muted hover:bg-app-panel"
              ].join(" ")}>
              {tab.label}
            </button>
          );
        })}
      </div>

      {error && <p className="mt-0 text-app-error">{error}</p>}
      {success && <p className="mt-0 font-bold text-app-success">{success}</p>}

      {activeTab === "campaigns" && isCreating && (
        <CampaignWizardLayout
          campaignTitle={campaignTitle}
          titleInputRef={subjectInputRef}
          activeStep={activeWizardStep}
          saving={saving}
          previewLoading={previewLoading}
          onCampaignTitleChange={setCampaignTitle}
          onStepChange={setActiveWizardStep}
          onPrimaryAction={handleWizardPrimaryAction}
          onPreview={previewRenderedEmail}
          onClose={() => {
            resetForm();
            setIsCreating(false);
          }}>
          {activeWizardStep === "setup" && (
            <SetupPage
              fromName={fromName}
              fromEmail={fromEmail}
              subject={subject}
              previewText={previewText}
              audienceType={activeAudienceTab}
              openTracking={trackOpens}
              clickTracking={trackClicks}
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
            />
          )}

          {activeWizardStep === "design" && (
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

          {activeWizardStep === "content" && (
            <ContentEditorPage
              activeTab={activeContentEditorTab}
              content={emailContentTemplate}
              onTabChange={setActiveContentEditorTab}
              onContentChange={setEmailContentTemplate}
            />
          )}

          {activeWizardStep === "send" && (
            <SendReviewPage
              deliveryType={deliveryType}
              scheduledAt={scheduledAt}
              fromName={fromName}
              fromEmail={fromEmail}
              subject={subject}
              content={emailContentTemplate}
              onDeliveryTypeChange={setDeliveryType}
              onScheduledAtChange={setScheduledAt}
              onEditSetup={() => setActiveWizardStep("setup")}
              onEditContent={() => setActiveWizardStep("content")}
              onPreview={previewRenderedEmail}
            />
          )}
        </CampaignWizardLayout>
      )}

      {activeTab === "campaigns" && (
        <div className="grid gap-6 xl:grid-cols-[220px_minmax(0,1fr)]">
          <aside className="panel self-start p-4">
            <h3 className="mb-3 mt-0 text-lg font-black">Status</h3>
            <div className="flex flex-col gap-1.5">
              {statusFilters.map((filter) => {
                const selected = statusFilter === filter.label;
                return (
                  <button
                    key={filter.label}
                    type="button"
                    onClick={() => setStatusFilter(filter.label)}
                    className={[
                      "flex items-center justify-start gap-2.5 rounded-lg border border-transparent px-4 py-2.5 font-extrabold transition",
                      selected
                        ? "bg-[#FFF7BE] text-app-text shadow-[inset_4px_0_0_var(--color-app-accent)]"
                        : "text-app-muted hover:bg-app-panel"
                    ].join(" ")}>
                    <span className={selected ? "text-[#6B5200]" : "text-app-muted"}>
                      {filter.icon}
                    </span>
                    {filter.label}
                  </button>
                );
              })}
            </div>

            <div className="my-4 border-t border-app-border" />
            <h3 className="mb-3 text-lg font-black">Date</h3>
            <SelectField
              ariaLabel="Date"
              value={dateFilter}
              onChange={setDateFilter}
              className="field bg-app-bg"
              options={[
                { value: "all", label: "all dates" },
                { value: "today", label: "today" },
                { value: "7", label: "last 7 days" },
                { value: "30", label: "last 30 days" }
              ]}
            />
          </aside>

          <section className="min-w-0">
            <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
              <label className="relative flex-1">
                <span className="absolute left-3.5 top-3 text-app-muted">⌕</span>
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search"
                  className="field pl-9"
                />
              </label>
              <span className="text-app-muted">Sort by</span>
              <SelectField
                ariaLabel="Sort by"
                value="date"
                onChange={() => undefined}
                className="field lg:w-auto"
                options={[{ value: "date", label: "Date" }]}
              />
              <button
                type="button"
                className="btn"
                onClick={() => setSortDirection(sortDirection === "desc" ? "asc" : "desc")}>
                {sortDirection === "desc" ? "↓" : "↑"}
              </button>
              <span className="whitespace-nowrap text-app-muted">
                {filteredCampaigns.length === 0 ? "0-0" : `1-${filteredCampaigns.length}`} of{" "}
                {filteredCampaigns.length}
              </span>
            </div>

            {loading && <p className="text-app-muted">Loading campaigns...</p>}

            {!loading &&
              filteredCampaigns.map((campaign) => {
                const status = normalizeStatus(campaign.status);
                const isDraft = status === "Draft";
                const isReady = status === "Ready";
                const isSent = status === "Sent";
                const isFailed = status === "Failed";
                const isPaused = status === "Paused";
                const isCancelled = status === "Cancelled";
                const isInProgress = status === "Sending" || status === "Partially Sent";
                const badgeClass = isSent
                  ? "bg-app-success text-white"
                  : isFailed || isCancelled
                    ? "bg-app-error text-white"
                    : isInProgress || isPaused
                      ? "bg-app-warning text-app-text"
                      : isDraft
                        ? "bg-app-panel text-app-text"
                        : "bg-app-warning text-app-text";

                return (
                  <article
                    key={campaign.id}
                    className="panel relative mb-3 grid items-center gap-4 p-4 lg:grid-cols-[92px_minmax(220px,1.4fr)_150px_repeat(3,90px)_48px]">
                    <div className="h-20 w-20 rounded-lg border border-app-border bg-app-surface p-2">
                      <div className="mb-2 h-2 bg-app-accent" />
                      <div className="mb-1.5 h-1.5 bg-[#D9D2BE]" />
                      <div className="mb-1.5 h-1.5 bg-[#E6DFCE]" />
                      <div className="h-5.5 bg-[#F5F1E7]" />
                    </div>

                    <div className="min-w-0">
                      <h2 className="mb-2 mt-0 truncate text-lg font-black">
                        {campaign.subject || "Untitled"}
                      </h2>
                      <p className="m-0 truncate text-app-muted">
                        <strong className="text-app-text">Subject:</strong>{" "}
                        {campaign.subject || "Untitled"}
                      </p>
                      {(campaign.category || (campaign.tags && campaign.tags.length > 0)) && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {campaign.category && (
                            <span className="rounded-lg border border-app-border bg-app-soft px-2 py-1 text-xs font-bold text-app-text">
                              {campaign.category}
                            </span>
                          )}
                          {(campaign.tags || []).slice(0, 3).map((tag) => (
                            <span
                              key={tag}
                              className="rounded-lg border border-app-border bg-app-surface px-2 py-1 text-xs font-bold text-app-muted">
                              {tag}
                            </span>
                          ))}
                          {(campaign.tags?.length || 0) > 3 && (
                            <span className="rounded-lg border border-app-border bg-app-surface px-2 py-1 text-xs font-bold text-app-muted">
                              +{(campaign.tags?.length || 0) - 3}
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    <div>
                      <span
                        className={`rounded-lg px-2.5 py-1 text-[13px] font-bold ${badgeClass}`}>
                        {status}
                      </span>
                      <div className="mt-2 text-[13px] text-app-muted">
                        {formatDate(campaign.created_at)}
                      </div>
                      {campaign.scheduled_at && (
                        <div className="mt-1 text-[13px] font-bold text-app-muted">
                          Scheduled {formatDate(campaign.scheduled_at)}
                        </div>
                      )}
                    </div>

                    <Metric
                      value={
                        isDraft
                          ? "~"
                          : String(campaign.sent_count ?? campaign.queued_recipients ?? 0)
                      }
                      label="Sent"
                    />
                    <Metric
                      value={
                        isDraft
                          ? "~"
                          : formatRate(
                              campaign.opened_count,
                              campaign.sent_count ?? campaign.queued_recipients
                            )
                      }
                      label="Opened"
                    />
                    <Metric
                      value={
                        isDraft
                          ? "~"
                          : formatRate(
                              campaign.clicked_count,
                              campaign.sent_count ?? campaign.queued_recipients
                            )
                      }
                      label="Clicked"
                    />
                    <button
                      type="button"
                      className="btn h-10 w-10 px-0"
                      onClick={() =>
                        setOpenActionsId(openActionsId === campaign.id ? "" : campaign.id)
                      }>
                      ▾
                    </button>

                    {openActionsId === campaign.id && (
                      <div className="absolute right-4 top-16 z-10 flex min-w-37.5 flex-col rounded-lg border border-app-border bg-app-surface p-1.5 shadow-lg">
                        {isDraft && (
                          <button
                            type="button"
                            className="btn justify-start border-transparent"
                            onClick={() => editDraft(campaign)}>
                            Edit
                          </button>
                        )}
                        {isReady && (
                          <button
                            type="button"
                            className="btn justify-start border-transparent"
                            onClick={() => sendDraft(campaign)}>
                            Send
                          </button>
                        )}
                        {isInProgress && (
                          <button
                            type="button"
                            className="btn justify-start border-transparent"
                            onClick={() => controlCampaign(campaign, "pause")}
                            disabled={controllingCampaignId === campaign.id}>
                            {controllingCampaignId === campaign.id ? "Pausing..." : "Pause"}
                          </button>
                        )}
                        {isPaused && (
                          <button
                            type="button"
                            className="btn justify-start border-transparent"
                            onClick={() => controlCampaign(campaign, "resume")}
                            disabled={controllingCampaignId === campaign.id}>
                            {controllingCampaignId === campaign.id ? "Resuming..." : "Resume"}
                          </button>
                        )}
                        <button
                          type="button"
                          className="btn justify-start border-transparent"
                          onClick={() => duplicateCampaign(campaign)}>
                          Duplicate
                        </button>
                        {(isInProgress || isPaused || status === "Scheduled") && (
                          <button
                            type="button"
                            className="btn justify-start border-transparent text-app-error"
                            onClick={() => controlCampaign(campaign, "cancel")}
                            disabled={controllingCampaignId === campaign.id}>
                            {controllingCampaignId === campaign.id ? "Cancelling..." : "Cancel"}
                          </button>
                        )}
                        <button
                          type="button"
                          className="btn justify-start border-transparent text-app-error"
                          onClick={() => deleteCampaign(campaign)}
                          disabled={deletingCampaignId === campaign.id || isInProgress}>
                          {deletingCampaignId === campaign.id ? "Deleting..." : "Delete"}
                        </button>
                      </div>
                    )}
                  </article>
                );
              })}

            {!loading && filteredCampaigns.length === 0 && (
              <div className="panel p-7 text-app-muted">
                No campaigns match the current filters.
              </div>
            )}
          </section>
        </div>
      )}

      {activeTab === "templates" && (
        <section className="panel overflow-hidden">
          <div className="flex flex-col justify-between gap-3 border-b border-app-border p-4 sm:flex-row sm:items-center">
            <div>
              <h2 className="m-0 text-2xl font-black">Templates</h2>
              <p className="mb-0 mt-1 text-app-muted">{emailTemplates.length} saved templates</p>
            </div>
            <button
              type="button"
              onClick={() => {
                setActiveTab("campaigns");
                openCreateWizard();
              }}
              className="btn btn-primary rounded-full">
              Create Template
            </button>
          </div>

          {loading && <p className="p-5 text-app-muted">Loading templates...</p>}

          {!loading && emailTemplates.length === 0 && (
            <div className="p-8 text-app-muted">
              <h3 className="mt-0 text-app-text">No templates yet</h3>
              <p>Create a campaign draft, then save it as a reusable template.</p>
              <button
                type="button"
                onClick={() => {
                  setActiveTab("campaigns");
                  openCreateWizard();
                }}
                className="btn btn-primary rounded-full">
                Create Template
              </button>
            </div>
          )}

          {templatePreview && (
            <div className="border-b border-app-border bg-app-bg p-4">
              <div className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <div className="text-[13px] font-extrabold uppercase text-app-muted">Preview</div>
                  <h3 className="mb-0 mt-1 text-xl font-black">{templatePreviewName}</h3>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setTemplatePreview(null);
                    setTemplatePreviewName("");
                  }}
                  className="btn py-2">
                  Close
                </button>
              </div>

              <div className="overflow-hidden rounded-lg border border-app-border bg-app-surface">
                <div className="border-b border-app-border px-4 py-3">
                  <div className="text-[13px] font-extrabold uppercase text-app-muted">
                    Rendered subject
                  </div>
                  <div className="mt-1 font-extrabold">{templatePreview.subject}</div>
                </div>

                {(templatePreview.content_type === "html" ||
                  templatePreview.content_type === "multipart") &&
                  templatePreview.html_body && (
                    <div className="border-b border-app-border">
                      <div className="px-4 py-3 text-[13px] font-extrabold uppercase text-app-muted">
                        HTML
                      </div>
                      <iframe
                        title="Rendered template HTML email"
                        sandbox=""
                        srcDoc={templatePreview.html_body}
                        className="h-72 w-full border-0 bg-white"
                      />
                    </div>
                  )}

                {(templatePreview.content_type === "plain" ||
                  templatePreview.content_type === "multipart") && (
                  <div className="px-4 py-3">
                    <div className="mb-2 text-[13px] font-extrabold uppercase text-app-muted">
                      Plain text
                    </div>
                    <div className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-app-bg p-3 font-mono text-sm">
                      {templatePreview.body}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {emailTemplates.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-245 border-collapse">
                <thead>
                  <tr className="bg-app-panel">
                    {["Name", "Type", "Subject", "Body", ""].map((heading) => (
                      <th
                        key={heading}
                        className="border-b border-app-border px-4 py-3 text-left text-[13px] font-extrabold text-app-muted">
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {emailTemplates.map((template) => (
                    <tr key={template.id}>
                      <td className="border-b border-app-border px-4 py-3.5 font-extrabold">
                        {template.name}
                      </td>
                      <td className="border-b border-app-border px-4 py-3.5 capitalize">
                        {template.content_type}
                      </td>
                      <td className="max-w-60 truncate border-b border-app-border px-4 py-3.5">
                        {template.subject}
                      </td>
                      <td className="max-w-70 truncate border-b border-app-border px-4 py-3.5 text-app-muted">
                        {template.content_type === "html"
                          ? template.html_body || "-"
                          : template.body || template.html_body || "-"}
                      </td>
                      <td className="border-b border-app-border px-4 py-3.5">
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => previewEmailTemplate(template)}
                            disabled={previewingTemplateId === template.id}
                            className="btn py-2">
                            {previewingTemplateId === template.id ? "Rendering..." : "Preview"}
                          </button>
                          <button
                            type="button"
                            onClick={() => startCampaignFromTemplate(template)}
                            className="btn py-2">
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => deleteEmailTemplate(template)}
                            disabled={deletingTemplateId === template.id}
                            className="rounded-lg border border-[#E6B7B7] bg-[#FFF5F5] px-4 py-2 font-extrabold text-app-error">
                            {deletingTemplateId === template.id ? "Deleting..." : "Delete"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <strong className="block text-app-text">{value}</strong>
      <span className="text-[13px] text-app-muted">{label}</span>
    </div>
  );
}

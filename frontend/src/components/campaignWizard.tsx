import type { ReactNode, RefObject } from "react";

import SelectField from "./SelectField";

export type CampaignWizardStep = "setup" | "design" | "content" | "send";
export type AudienceTab = "all" | "segment" | "tag" | "advanced";
export type DeliveryType = "immediate" | "scheduled";
export type ContentEditorTab = "content" | "rows" | "settings";
export type ContentBlockId =
  | "title"
  | "text"
  | "logo"
  | "image"
  | "video"
  | "button"
  | "social"
  | "divider"
  | "code";
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

const campaignWizardSteps: { id: CampaignWizardStep; label: string }[] = [
  { id: "setup", label: "Setup" },
  { id: "design", label: "Design" },
  { id: "content", label: "Content" },
  { id: "send", label: "Send" }
];

const audienceTabs: { id: AudienceTab; label: string }[] = [
  { id: "all", label: "All subscribers" },
  { id: "segment", label: "Segment" },
  { id: "tag", label: "Tag" },
  { id: "advanced", label: "Advanced" }
];

const designSidebarSections: {
  title: string;
  items: { id: DesignSidebarItemId; label: string; designChoice?: DesignChoiceId }[];
}[] = [
  {
    title: "Templates",
    items: [
      { id: "yours", label: "Yours" },
      { id: "branded", label: "Branded" },
      { id: "inspirational", label: "Inspirational" }
    ]
  },
  {
    title: "Start from scratch",
    items: [
      { id: "drag", label: "Drag and drop", designChoice: "scratch-drag" },
      { id: "code", label: "Code your own", designChoice: "scratch-code" }
    ]
  },
  {
    title: "Past emails",
    items: [
      { id: "campaigns", label: "Campaigns" },
      { id: "automations", label: "Automations" }
    ]
  }
];

const contentEditorTabs: { id: ContentEditorTab; label: string; icon: string }[] = [
  { id: "content", label: "Content", icon: "▦" },
  { id: "rows", label: "Rows", icon: "☷" },
  { id: "settings", label: "Settings", icon: "⚙" }
];

const contentBlocks: { id: ContentBlockId; label: string; icon: string }[] = [
  { id: "title", label: "Title", icon: "T" },
  { id: "text", label: "Text", icon: "¶" },
  { id: "logo", label: "Logo", icon: "◧" },
  { id: "image", label: "Image", icon: "▧" },
  { id: "video", label: "Video", icon: "▶" },
  { id: "button", label: "Button", icon: "▭" },
  { id: "social", label: "Social follow", icon: "◎" },
  { id: "divider", label: "Divider", icon: "—" },
  { id: "code", label: "Code", icon: "<>" }
];

const wizardFieldClass =
  "min-h-12 rounded-lg border border-[#DADDE6] bg-white px-3 text-[#1F1F29] placeholder:text-[#6B6B7A] focus:border-[#6F4BD8] focus:ring-4 focus:ring-[#6F4BD8]/15";

const wizardLabelClass = "mb-1.5 block text-sm font-semibold text-[#1F1F29]";
const wizardHelperClass = "mb-2.5 mt-0 text-sm text-[#626270]";

export function PrimaryButton({
  children,
  disabled,
  onClick
}: {
  children: ReactNode;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="min-h-12 w-full rounded-full border border-[#6F4BD8] bg-[#6F4BD8] px-6 font-semibold text-white transition hover:bg-[#5F3FC3] disabled:bg-[#8C79D7] sm:w-auto">
      {children}
    </button>
  );
}

export function SecondaryButton({
  children,
  disabled,
  onClick
}: {
  children: ReactNode;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="min-h-12 w-full rounded-full border border-[#DADDE6] bg-white px-5 font-semibold text-[#1F1F29] transition hover:bg-[#FAFAFC] disabled:text-[#626270] sm:w-auto">
      {children}
    </button>
  );
}

export function EditableCampaignTitle({
  value,
  inputRef,
  onChange
}: {
  value: string;
  inputRef: RefObject<HTMLInputElement | null>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="group inline-flex max-w-full items-center gap-2">
      <input
        ref={inputRef}
        aria-label="Campaign title"
        value={value}
        placeholder="Untitled"
        onChange={(event) => onChange(event.target.value)}
        className="min-w-0 max-w-full border-0 border-b border-dotted border-[#8B8B98] bg-transparent px-0 py-1 text-2xl font-semibold text-[#1F1F29] outline-none placeholder:text-[#1F1F29] focus:border-[#6F4BD8] sm:text-3xl md:text-[34px]"
      />
      <span className="text-lg text-[#626270] transition group-focus-within:text-[#6F4BD8]">✎</span>
    </label>
  );
}

export function CampaignStepper({
  activeStep,
  onStepChange
}: {
  activeStep: CampaignWizardStep;
  onStepChange: (step: CampaignWizardStep) => void;
}) {
  const activeStepIndex = campaignWizardSteps.findIndex((step) => step.id === activeStep);

  return (
    <div className="flex flex-wrap items-center justify-center gap-1.5 text-xs font-semibold text-[#626270] sm:gap-3 sm:text-sm">
      {campaignWizardSteps.map((step, index) => {
        const isCompleted = index < activeStepIndex;
        const isCurrent = index === activeStepIndex;
        const circleClass = isCompleted
          ? "border-[#00856F] bg-[#00856F] text-white"
          : isCurrent
            ? "border-[#6F4BD8] bg-white text-[#6F4BD8] ring-4 ring-[#6F4BD8]/15"
            : "border-[#DADDE6] bg-[#FAFAFC] text-[#9A9AA6]";

        return (
          <div key={step.id} className="flex items-center gap-1.5 sm:gap-3">
            <button
              type="button"
              onClick={() => onStepChange(step.id)}
              className={[
                "flex items-center gap-1.5 rounded-full border border-transparent px-1 py-1 transition sm:gap-2",
                isCurrent ? "text-[#1F1F29]" : "hover:text-[#1F1F29]"
              ].join(" ")}>
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full border text-[11px] font-black sm:h-7 sm:w-7 sm:text-xs ${circleClass}`}>
                {isCompleted ? "✓" : index + 1}
              </span>
              <span className="max-[420px]:sr-only">{step.label}</span>
            </button>
            {index < campaignWizardSteps.length - 1 && (
              <span className="hidden text-lg font-normal text-[#B8BAC5] sm:inline">›</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function CampaignWizardLayout({
  campaignTitle,
  titleInputRef,
  activeStep,
  saving,
  previewLoading,
  children,
  onCampaignTitleChange,
  onStepChange,
  onPrimaryAction,
  onPreview,
  onClose
}: {
  campaignTitle: string;
  titleInputRef: RefObject<HTMLInputElement | null>;
  activeStep: CampaignWizardStep;
  saving: boolean;
  previewLoading: boolean;
  children: ReactNode;
  onCampaignTitleChange: (title: string) => void;
  onStepChange: (step: CampaignWizardStep) => void;
  onPrimaryAction: () => void;
  onPreview: () => void;
  onClose: () => void;
}) {
  const primaryLabel = saving
    ? activeStep === "send"
      ? "Sending..."
      : "Saving..."
    : activeStep === "send"
      ? "Send"
      : "Save & next";

  return (
    <div className="mb-10">
      <div className="mb-6 flex justify-center">
        <CampaignStepper activeStep={activeStep} onStepChange={onStepChange} />
      </div>

      <section className="rounded-xl border border-[#DADDE6] bg-app-surface p-4 text-[#1F1F29] sm:p-6">
        <div className="mb-8 flex flex-col gap-6 xl:mb-10 xl:flex-row xl:items-start xl:justify-between xl:gap-8">
          <div className="min-w-0">
            <EditableCampaignTitle
              value={campaignTitle}
              inputRef={titleInputRef}
              onChange={onCampaignTitleChange}
            />
          </div>

          <div className="grid shrink-0 grid-cols-1 gap-3 sm:flex sm:flex-wrap">
            {activeStep === "content" && (
              <SecondaryButton onClick={onPreview} disabled={previewLoading}>
                {previewLoading ? "Rendering..." : "Preview & test"}
              </SecondaryButton>
            )}
            <PrimaryButton onClick={onPrimaryAction} disabled={saving}>
              {primaryLabel}
            </PrimaryButton>
            <button
              type="button"
              className="min-h-12 w-full rounded-full border border-[#DADDE6] bg-white px-5 font-semibold text-[#626270] transition hover:bg-[#FAFAFC] sm:w-auto"
              onClick={onClose}>
              Close
            </button>
          </div>
        </div>

        {children}
      </section>
    </div>
  );
}

export function ToggleSwitch({
  checked,
  onChange
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={[
        "relative mt-0.5 h-6 w-11 shrink-0 rounded-full border transition",
        checked ? "border-[#00856F] bg-[#00856F]" : "border-[#DADDE6] bg-[#DADDE6]"
      ].join(" ")}>
      <span
        className={[
          "absolute top-1/2 h-5 w-5 -translate-y-1/2 rounded-full bg-white transition",
          checked ? "left-4.75" : "left-0.5"
        ].join(" ")}
      />
    </button>
  );
}

export function SegmentedTabs<T extends string>({
  tabs,
  activeTab,
  onChange
}: {
  tabs: { id: T; label: string }[];
  activeTab: T;
  onChange: (tab: T) => void;
}) {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {tabs.map((tab) => {
        const selected = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={[
              "min-h-11 rounded-full border px-4 text-sm font-semibold transition",
              selected
                ? "border-[#6F4BD8] bg-[#6F4BD8]/10 text-[#6F4BD8]"
                : "border-[#DADDE6] bg-white text-[#626270] hover:bg-[#FAFAFC]"
            ].join(" ")}>
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

function AdvancedSetting({
  title,
  description,
  checked,
  onChange
}: {
  title: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-[#DADDE6] pb-5 last:border-b-0 last:pb-0">
      <div>
        <h3 className="mb-1.5 mt-0 text-sm font-semibold text-[#1F1F29]">{title}</h3>
        <p className="m-0 text-sm leading-5 text-[#626270]">{description}</p>
      </div>
      <ToggleSwitch checked={checked} onChange={onChange} />
    </div>
  );
}

export function SetupPage({
  fromName,
  fromEmail,
  subject,
  previewText,
  audienceType,
  openTracking,
  clickTracking,
  contacts = [],
  selectedEmails = [],
  fromEmailCheck,
  fromEmailCheckLoading,
  fromEmailCheckError,
  onFromNameChange,
  onFromEmailChange,
  onSubjectChange,
  onPreviewTextChange,
  onAudienceTypeChange,
  onOpenTrackingChange,
  onClickTrackingChange,
  onSelectedEmailsChange
}: {
  fromName: string;
  fromEmail: string;
  subject: string;
  previewText: string;
  audienceType: AudienceTab;
  openTracking: boolean;
  clickTracking: boolean;
  contacts?: { id: string; email: string; name?: string | null }[];
  selectedEmails?: string[];
  fromEmailCheck: SendingCheckResult | null;
  fromEmailCheckLoading: boolean;
  fromEmailCheckError: string;
  onFromNameChange: (value: string) => void;
  onFromEmailChange: (value: string) => void;
  onSubjectChange: (value: string) => void;
  onPreviewTextChange: (value: string) => void;
  onAudienceTypeChange: (value: AudienceTab) => void;
  onOpenTrackingChange: (value: boolean) => void;
  onClickTrackingChange: (value: boolean) => void;
  onSelectedEmailsChange?: (emails: string[]) => void;
}) {
  const selectedEmailSet = new Set(selectedEmails.map((email) => email.toLowerCase()));
  const allContactEmails = contacts.map((contact) => contact.email);
  const selectedCount = onSelectedEmailsChange ? selectedEmails.length : allContactEmails.length;

  const toggleEmail = (email: string) => {
    if (!onSelectedEmailsChange) {
      return;
    }

    const normalizedEmail = email.toLowerCase();
    if (selectedEmailSet.has(normalizedEmail)) {
      onSelectedEmailsChange(
        selectedEmails.filter((selectedEmail) => selectedEmail.toLowerCase() !== normalizedEmail)
      );
      return;
    }

    onSelectedEmailsChange([...selectedEmails, email]);
  };

  const selectAllContacts = () => onSelectedEmailsChange?.(allContactEmails);

  return (
    <div className="grid gap-8 xl:grid-cols-[minmax(0,0.7fr)_minmax(280px,0.3fr)] xl:gap-12">
      <div className="flex flex-col gap-3">
        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <label className={wizardLabelClass}>Sending from (name)</label>
            <p className={wizardHelperClass}>The name your emails will come from</p>
            <input
              placeholder="Sender name"
              value={fromName}
              onChange={(event) => onFromNameChange(event.target.value)}
              className={wizardFieldClass}
            />
          </div>
          <div>
            <label className={wizardLabelClass}>Sending from (email address)</label>
            <p className={wizardHelperClass}>Send from and receive replies to this address</p>
            <input
              type="email"
              placeholder="sender@example.com"
              value={fromEmail}
              onChange={(event) => onFromEmailChange(event.target.value)}
              className={wizardFieldClass}
            />
          </div>
        </div>

        <div>
          <label className={wizardLabelClass}>Subject</label>
          <p className={wizardHelperClass}>
            The email subject line (merge tags are supported here)
          </p>
          <div className="relative">
            <input
              placeholder="Write a subject line"
              value={subject}
              onChange={(event) => onSubjectChange(event.target.value)}
              className={`${wizardFieldClass} pr-20`}
            />
            <div className="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-2 text-[#626270]">
              <button
                type="button"
                aria-label="Insert emoji"
                className="flex h-8 w-8 items-center justify-center rounded-full hover:bg-[#FAFAFC]">
                ☺
              </button>
              <button
                type="button"
                aria-label="Insert merge tag"
                className="flex h-8 w-8 items-center justify-center rounded-full hover:bg-[#FAFAFC]">
                #
              </button>
            </div>
          </div>
        </div>

        <div>
          <label className={wizardLabelClass}>Preview text</label>
          <p className={wizardHelperClass}>
            Typically displayed after the subject in a subscriber's inbox
          </p>
          <input
            placeholder="Add preview text"
            value={previewText}
            onChange={(event) => onPreviewTextChange(event.target.value)}
            className={wizardFieldClass}
          />
        </div>

        <div>
          <label className={wizardLabelClass}>Sending to</label>
          <SegmentedTabs
            tabs={audienceTabs}
            activeTab={audienceType}
            onChange={onAudienceTypeChange}
          />
          <p className="mb-0 mt-4 text-sm font-semibold text-[#626270]">
            Matches {selectedCount} subscribed {selectedCount === 1 ? "contact" : "contacts"}
          </p>

          {contacts.length > 0 && onSelectedEmailsChange && (
            <div className="mt-5 rounded-xl border border-[#DADDE6] bg-white">
              <div className="flex flex-col gap-3 border-b border-[#DADDE6] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h3 className="m-0 text-sm font-semibold text-[#1F1F29]">Recipients</h3>
                  <p className="mb-0 mt-1 text-sm text-[#626270]">
                    Mark users who should receive this campaign
                  </p>
                </div>
                <button
                  type="button"
                  onClick={selectAllContacts}
                  className="text-sm font-semibold text-[#6F4BD8] hover:underline">
                  Select all
                </button>
              </div>

              <div className="max-h-64 overflow-auto">
                {contacts.map((contact) => {
                  const checked = selectedEmailSet.has(contact.email.toLowerCase());
                  return (
                    <label
                      key={contact.id}
                      className="flex cursor-pointer items-center justify-between gap-4 border-b border-[#E7E9EF] px-4 py-3 last:border-b-0 hover:bg-[#FAFAFC]">
                      <span className="min-w-0">
                        {contact.name && (
                          <span className="block truncate text-sm font-semibold text-[#1F1F29]">
                            {contact.name}
                          </span>
                        )}
                        <span className="block truncate text-sm text-[#626270]">
                          {contact.email}
                        </span>
                      </span>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleEmail(contact.email)}
                        className="h-4 w-4 shrink-0 accent-[#6F4BD8]"
                      />
                    </label>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {fromEmail.trim() && (
          <div
            className={[
              "rounded-lg border px-4 py-3 text-sm",
              fromEmailCheck?.can_send
                ? "border-[#00856F]/30 bg-[#00856F]/10 text-[#00856F]"
                : fromEmailCheck || fromEmailCheckError
                  ? "border-[#DADDE6] bg-[#FAFAFC] text-[#1F1F29]"
                  : "border-[#DADDE6] bg-[#FAFAFC] text-[#626270]"
            ].join(" ")}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold">
                {fromEmailCheckLoading
                  ? "Checking sender domain..."
                  : fromEmailCheck?.can_send
                    ? "Sender domain ready"
                    : fromEmailCheck
                      ? "Sender domain needs attention"
                      : fromEmailCheckError || "Enter a valid sender email to check the domain"}
              </span>
              {fromEmailCheck && (
                <span className="rounded-full border border-current px-2.5 py-1 text-xs font-semibold">
                  {fromEmailCheck.domain}
                </span>
              )}
            </div>

            {fromEmailCheck?.blockers && fromEmailCheck.blockers.length > 0 && (
              <ul className="mb-0 mt-2 grid gap-1 pl-5 font-semibold">
                {fromEmailCheck.blockers.map((blocker) => (
                  <li key={blocker}>{blocker}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <aside className="self-start rounded-xl border border-[#DADDE6] bg-white p-5 xl:sticky xl:top-6">
        <h2 className="mb-5 mt-0 text-xs font-black uppercase tracking-[0.12em] text-[#626270]">
          Advanced Settings
        </h2>

        <div className="grid gap-5">
          <AdvancedSetting
            checked={openTracking}
            onChange={onOpenTrackingChange}
            title="Open tracking"
            description="Discover who opened your campaign, and when they opened it"
          />
          <AdvancedSetting
            checked={clickTracking}
            onChange={onClickTrackingChange}
            title="Click tracking"
            description="Discover who clicked the links in your campaign, which links were clicked, and when they were clicked"
          />
        </div>
      </aside>
    </div>
  );
}

export function TemplateCard({
  template,
  selected,
  onSelect
}: {
  template: DesignTemplate;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="group min-w-0 rounded-xl border border-transparent bg-transparent p-0 text-left">
      <div
        className={[
          "aspect-4/5 overflow-hidden rounded-xl border bg-white p-4 transition",
          selected
            ? "border-[#6F4BD8] ring-4 ring-[#6F4BD8]/15"
            : "border-[#DADDE6] group-hover:border-[#BDB6DF]"
        ].join(" ")}>
        <div className="mx-auto h-full max-w-36 rounded-lg border border-[#DADDE6] bg-[#FAFAFC] p-3">
          <div className="mb-3 h-2.5 w-16 rounded-full bg-[#D7DAE3]" />

          {template.tone === "hero" && (
            <>
              <div className="mb-3 h-20 rounded-md bg-[#DADDE6]" />
              <div className="mb-2 h-2 rounded-full bg-[#C7CBD7]" />
              <div className="mb-2 h-2 w-5/6 rounded-full bg-[#DADDE6]" />
              <div className="mt-4 h-7 w-24 rounded-full bg-[#6F4BD8]/25" />
            </>
          )}

          {template.tone === "split" && (
            <>
              <div className="mb-3 grid grid-cols-2 gap-2">
                <div className="h-20 rounded-md bg-[#DADDE6]" />
                <div>
                  <div className="mb-2 h-2 rounded-full bg-[#C7CBD7]" />
                  <div className="mb-2 h-2 rounded-full bg-[#DADDE6]" />
                  <div className="mb-2 h-2 w-2/3 rounded-full bg-[#DADDE6]" />
                </div>
              </div>
              <div className="mb-2 h-2 rounded-full bg-[#DADDE6]" />
              <div className="h-2 w-4/5 rounded-full bg-[#DADDE6]" />
            </>
          )}

          {template.tone === "text" && (
            <>
              <div className="mb-3 h-8 rounded-md bg-[#E7E9EF]" />
              <div className="mb-2 h-2 rounded-full bg-[#C7CBD7]" />
              <div className="mb-2 h-2 rounded-full bg-[#DADDE6]" />
              <div className="mb-2 h-2 w-11/12 rounded-full bg-[#DADDE6]" />
              <div className="mb-5 h-2 w-3/4 rounded-full bg-[#DADDE6]" />
              <div className="grid grid-cols-3 gap-2">
                <div className="h-10 rounded-md bg-[#DADDE6]" />
                <div className="h-10 rounded-md bg-[#DADDE6]" />
                <div className="h-10 rounded-md bg-[#DADDE6]" />
              </div>
            </>
          )}
        </div>
      </div>
      <div
        className={[
          "mt-3 truncate text-sm font-semibold",
          selected ? "text-[#4E34AA]" : "text-[#1F1F29]"
        ].join(" ")}>
        {template.name}
      </div>
    </button>
  );
}

export function DesignPage({
  activeSidebarItem,
  selectedTemplate,
  search,
  sortDirection,
  templates,
  onSidebarItemChange,
  onTemplateSelect,
  onSearchChange,
  onSortDirectionChange
}: {
  activeSidebarItem: DesignSidebarItemId;
  selectedTemplate: string;
  search: string;
  sortDirection: "asc" | "desc";
  templates: DesignTemplate[];
  onSidebarItemChange: (item: DesignSidebarItemId, designChoice?: DesignChoiceId) => void;
  onTemplateSelect: (template: DesignChoiceId) => void;
  onSearchChange: (value: string) => void;
  onSortDirectionChange: (direction: "asc" | "desc") => void;
}) {
  return (
    <div className="grid gap-8 md:grid-cols-[minmax(150px,180px)_minmax(0,1fr)] xl:grid-cols-[220px_minmax(0,1fr)] xl:gap-12">
      <aside className="w-full md:w-auto xl:w-55">
        {designSidebarSections.map((section, sectionIndex) => (
          <div
            key={section.title}
            className={
              sectionIndex > 0 ? "mt-5 border-t border-[#DADDE6] pt-5 xl:mt-6 xl:pt-6" : ""
            }>
            <h2 className="mb-3 mt-0 text-xs font-black uppercase tracking-[0.12em] text-[#626270]">
              {section.title}
            </h2>
            <div className="grid gap-1.5">
              {section.items.map((item) => {
                const selected = activeSidebarItem === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onSidebarItemChange(item.id, item.designChoice)}
                    className={[
                      "rounded-lg px-3 py-2 text-left text-sm font-semibold transition xl:py-2.5",
                      selected
                        ? "bg-[#F0ECFB] text-[#4E34AA]"
                        : "text-[#626270] hover:bg-[#FAFAFC] hover:text-[#1F1F29]"
                    ].join(" ")}>
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </aside>

      <section className="min-w-0">
        <div className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-center">
          <label className="relative min-w-0 flex-1">
            <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#626270]">⌕</span>
            <input
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder="Search"
              className={`${wizardFieldClass} pl-9`}
            />
          </label>

          <span className="text-sm font-semibold text-[#626270]">Sort by</span>
          <SelectField
            ariaLabel="Sort by"
            value="name"
            className={`${wizardFieldClass} lg:w-36`}
            options={[{ value: "name", label: "Name" }]}
          />
          <button
            type="button"
            aria-label="Toggle sort direction"
            onClick={() => onSortDirectionChange(sortDirection === "asc" ? "desc" : "asc")}
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border border-[#DADDE6] bg-white font-semibold text-[#626270] transition hover:bg-[#FAFAFC]">
            {sortDirection === "asc" ? "↑" : "↓"}
          </button>
          <span className="ml-auto whitespace-nowrap text-sm font-semibold text-[#626270]">
            {templates.length === 0 ? "0-0 of 6" : `1-${templates.length} of 6`}
          </span>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
          {templates.map((template) => (
            <TemplateCard
              key={template.id}
              template={template}
              selected={selectedTemplate === template.id}
              onSelect={() => onTemplateSelect(template.id)}
            />
          ))}
        </div>
      </section>
    </div>
  );
}

export function EditorBlockCard({
  block
}: {
  block: { id: ContentBlockId; label: string; icon: string };
}) {
  return (
    <button
      type="button"
      draggable
      data-block-id={block.id}
      className="group flex min-h-28 flex-col items-center justify-center gap-3 rounded-lg border border-[#DADDE6] bg-[#FAFAFC] p-3 text-center transition hover:border-[#BDB6DF] hover:bg-white">
      <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#E7E9EF] text-xl font-black text-[#8D92A3] transition group-hover:text-[#6F4BD8]">
        {block.icon}
      </span>
      <span className="text-sm font-semibold leading-tight text-[#1F1F29]">{block.label}</span>
    </button>
  );
}

function EmailCanvas({
  content,
  onContentChange
}: {
  content: string;
  onContentChange: (content: string) => void;
}) {
  const paragraphs = content.split(/\n{2,}/).filter((paragraph) => paragraph.trim().length > 0);
  const getTextareaRows = (paragraph: string) => {
    return paragraph.split("\n").reduce((rows, line) => {
      return rows + Math.max(1, Math.ceil(line.length / 76));
    }, 0);
  };

  return (
    <section className="min-w-0">
      <div className="mb-3 flex justify-end">
        <button type="button" className="text-sm font-semibold text-[#6F4BD8] hover:underline">
          Merge tag cheatsheet
        </button>
      </div>

      <div className="min-h-205 rounded-xl border border-[#DADDE6] bg-white px-4 py-10">
        <div className="mx-auto min-h-180 w-full max-w-205 border border-[#DADDE6] bg-white px-8 py-10 md:px-12">
          <div className="grid gap-5">
            {paragraphs.map((paragraph, index) => (
              <textarea
                key={index}
                value={paragraph}
                onChange={(event) => {
                  const nextParagraphs = [...paragraphs];
                  nextParagraphs[index] = event.target.value;
                  onContentChange(nextParagraphs.join("\n\n"));
                }}
                rows={Math.max(2, getTextareaRows(paragraph))}
                className="w-full resize-none overflow-hidden border-0 bg-transparent p-0 text-base leading-7 text-[#1F1F29] outline-none"
              />
            ))}
          </div>

          <footer className="mt-12 border-t border-[#DADDE6] pt-6 text-sm leading-6 text-[#626270]">
            <p className="mb-4 mt-0">
              You received this email because you subscribed to our list. You can unsubscribe at any
              time.
            </p>
            <p className="m-0">Powered by Mailflow</p>
          </footer>
        </div>
      </div>
    </section>
  );
}

export function ContentEditorPage({
  activeTab,
  content,
  onTabChange,
  onContentChange
}: {
  activeTab: ContentEditorTab;
  content: string;
  onTabChange: (tab: ContentEditorTab) => void;
  onContentChange: (content: string) => void;
}) {
  return (
    <div className="grid gap-12 xl:grid-cols-[minmax(340px,420px)_minmax(0,1fr)]">
      <aside className="self-start rounded-xl border border-[#DADDE6] bg-white">
        <div className="flex border-b border-[#DADDE6] px-5">
          {contentEditorTabs.map((tab) => {
            const selected = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => onTabChange(tab.id)}
                className={[
                  "flex min-h-14 items-center gap-2 border-b-2 px-3 text-sm font-semibold transition",
                  selected
                    ? "border-[#6F4BD8] text-[#1F1F29]"
                    : "border-transparent text-[#626270] hover:text-[#1F1F29]"
                ].join(" ")}>
                <span className={selected ? "text-[#6F4BD8]" : "text-[#9A9AA6]"}>{tab.icon}</span>
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="p-5">
          <p className="mb-5 mt-0 text-sm font-semibold text-[#626270]">
            Drag and drop content onto the page
          </p>

          {activeTab === "content" && (
            <div className="grid grid-cols-3 gap-3">
              {contentBlocks.map((block) => (
                <EditorBlockCard key={block.id} block={block} />
              ))}
            </div>
          )}

          {activeTab !== "content" && (
            <div className="rounded-lg border border-dashed border-[#DADDE6] bg-[#FAFAFC] p-5 text-sm font-semibold text-[#626270]">
              {activeTab === "rows"
                ? "Row layouts will appear here."
                : "Email-wide settings will appear here."}
            </div>
          )}
        </div>
      </aside>

      <EmailCanvas content={content} onContentChange={onContentChange} />
    </div>
  );
}

function isFreeEmailAddress(email: string) {
  const domain = email.trim().toLowerCase().split("@")[1] || "";
  return [
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "ymail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "icloud.com",
    "me.com",
    "aol.com"
  ].includes(domain);
}

function buildGeneratedSenderAddress(email: string) {
  const localPart =
    email
      .split("@")[0]
      ?.replace(/[^a-z0-9]/gi, "")
      .toLowerCase() || "campaign";
  return `${localPart || "campaign"}@mailflow-sender.local`;
}

export function ReviewSection({
  title,
  children,
  onEdit
}: {
  title: string;
  children: ReactNode;
  onEdit?: () => void;
}) {
  return (
    <section className="border-t border-[#DADDE6] py-6 first:border-t-0 first:pt-0 last:pb-0">
      <div className="flex items-start justify-between gap-5">
        <div className="min-w-0">
          <h3 className="mb-3 mt-0 text-sm font-black text-[#1F1F29]">{title}</h3>
          {children}
        </div>
        {onEdit && (
          <button
            type="button"
            onClick={onEdit}
            className="shrink-0 text-sm font-semibold text-[#6F4BD8] hover:underline">
            ✎ Edit
          </button>
        )}
      </div>
    </section>
  );
}

export function SendReviewPage({
  deliveryType,
  scheduledAt,
  fromName,
  fromEmail,
  subject,
  content,
  recipientCount,
  onDeliveryTypeChange,
  onScheduledAtChange,
  onEditSetup,
  onEditContent,
  onPreview
}: {
  deliveryType: DeliveryType;
  scheduledAt: string;
  fromName: string;
  fromEmail: string;
  subject: string;
  content: string;
  recipientCount?: number;
  onDeliveryTypeChange: (deliveryType: DeliveryType) => void;
  onScheduledAtChange: (scheduledAt: string) => void;
  onEditSetup: () => void;
  onEditContent: () => void;
  onPreview: () => void;
}) {
  const usesFreeEmail = isFreeEmailAddress(fromEmail);
  const generatedSenderAddress = buildGeneratedSenderAddress(fromEmail);
  const previewLines = content
    .split(/\n{2,}/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 3);
  const recipientsLabel =
    typeof recipientCount === "number"
      ? `Selected subscribers (${recipientCount} ${recipientCount === 1 ? "recipient" : "recipients"})`
      : "All subscribers (1 recipient)";

  return (
    <section className="mx-auto w-full max-w-185">
      <div className="mb-8 text-center">
        <h2 className="mb-3 mt-0 text-4xl font-black text-[#1F1F29]">Ready to go!</h2>
        <p className="m-0 text-base text-[#626270]">
          One last chance to review your campaign before clicking send.
        </p>
      </div>

      <div className="rounded-xl border border-[#DADDE6] bg-white p-8 md:p-10">
        <ReviewSection title="Delivery">
          <div className="grid gap-3">
            <label className="flex items-center gap-3 text-sm font-semibold text-[#1F1F29]">
              <input
                type="radio"
                name="delivery"
                checked={deliveryType === "immediate"}
                onChange={() => onDeliveryTypeChange("immediate")}
                className="h-4 w-4 accent-[#6F4BD8]"
              />
              Send immediately
            </label>
            <label className="flex items-center gap-3 text-sm font-semibold text-[#1F1F29]">
              <input
                type="radio"
                name="delivery"
                checked={deliveryType === "scheduled"}
                onChange={() => onDeliveryTypeChange("scheduled")}
                className="h-4 w-4 accent-[#6F4BD8]"
              />
              Send at a specific time
            </label>
            {deliveryType === "scheduled" && (
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={(event) => onScheduledAtChange(event.target.value)}
                className={`${wizardFieldClass} mt-2 max-w-sm`}
              />
            )}
          </div>
        </ReviewSection>

        <ReviewSection title="To" onEdit={onEditSetup}>
          <p className="m-0 text-base font-semibold text-[#1F1F29]">{recipientsLabel}</p>
        </ReviewSection>

        <ReviewSection title="From" onEdit={onEditSetup}>
          <p className="m-0 wrap-break-word text-base font-semibold text-[#1F1F29]">
            {fromName || "Sender name"} &lt;{fromEmail || "sender@example.com"}&gt;
          </p>
          {usesFreeEmail && (
            <div className="mt-4 rounded-lg border border-[#DADDE6] bg-[#FAFAFC] p-4 text-sm leading-6 text-[#626270]">
              Emails sent from a free email address are unlikely to be delivered, so we'll send your
              email from {generatedSenderAddress} instead. Replies will continue to go to the email
              address you entered.
            </div>
          )}
          <p className="mb-0 mt-4 text-sm italic leading-6 text-[#626270]">
            Tip: for the best chance of your emails landing in the inbox, send from a domain you own
            (e.g. you@yoursite.com).
          </p>
        </ReviewSection>

        <ReviewSection title="Subject" onEdit={onEditSetup}>
          <p className="m-0 wrap-break-word text-base font-semibold text-[#1F1F29]">
            {subject || "Untitled"}
          </p>
        </ReviewSection>

        <ReviewSection title="Content" onEdit={onEditContent}>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <div className="h-28 w-24 shrink-0 rounded-lg border border-[#DADDE6] bg-[#FAFAFC] p-2">
              <div className="mb-2 h-2.5 w-12 rounded-full bg-[#C7CBD7]" />
              <div className="mb-2 h-8 rounded bg-[#DADDE6]" />
              <div className="mb-1.5 h-1.5 rounded-full bg-[#C7CBD7]" />
              <div className="mb-1.5 h-1.5 rounded-full bg-[#DADDE6]" />
              <div className="h-1.5 w-2/3 rounded-full bg-[#DADDE6]" />
            </div>
            <div className="min-w-0">
              <p className="mb-2 mt-0 text-base font-semibold text-[#1F1F29]">
                Sending an email which uses the Plain template
              </p>
              <div className="mb-3 grid gap-1 text-sm text-[#626270]">
                {previewLines.map((line) => (
                  <span key={line} className="truncate">
                    {line}
                  </span>
                ))}
              </div>
              <button
                type="button"
                onClick={onPreview}
                className="text-sm font-semibold text-[#6F4BD8] hover:underline">
                Preview
              </button>
            </div>
          </div>
        </ReviewSection>
      </div>
    </section>
  );
}

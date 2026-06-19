import { useState } from "react";
import type { FocusEvent } from "react";

export type SelectFieldOption = {
  value: string;
  label: string;
};

type SelectFieldProps = {
  ariaLabel: string;
  value: string;
  options: SelectFieldOption[];
  onChange?: (value: string) => void;
  className?: string;
};

export default function SelectField({
  ariaLabel,
  value,
  options,
  onChange,
  className = "field"
}: SelectFieldProps) {
  const [open, setOpen] = useState(false);
  const selected = options.find((option) => option.value === value) ?? options[0];

  function closeWhenFocusLeaves(event: FocusEvent<HTMLDivElement>) {
    const nextFocus = event.relatedTarget;
    if (!(nextFocus instanceof Node) || !event.currentTarget.contains(nextFocus)) {
      setOpen(false);
    }
  }

  return (
    <div className="relative" onBlur={closeWhenFocusLeaves}>
      <button
        type="button"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className={[
          className,
          "flex min-h-12 items-center justify-between gap-3 text-left",
          open ? "rounded-b-none border-b-app-border" : ""
        ].join(" ")}>
        <span className="truncate">{selected?.label || ariaLabel}</span>
        <span
          aria-hidden="true"
          className={[
            "grid h-4 w-4 shrink-0 place-items-center transition-transform",
            open ? "rotate-180" : ""
          ].join(" ")}>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round">
            <path d="m6 9 6 6 6-6" />
          </svg>
        </span>
      </button>

      {open && (
        <div
          role="listbox"
          aria-label={ariaLabel}
          className="absolute left-0 right-0 top-full z-30 overflow-hidden rounded-b-lg border border-t-0 border-app-border bg-app-surface shadow-lg">
          {options.map((option) => {
            return (
              <button
                key={option.value || "all"}
                type="button"
                role="option"
                aria-selected={option.value === value}
                onClick={() => {
                  onChange?.(option.value);
                  setOpen(false);
                }}
                className="block w-full px-3 py-2.5 text-left text-sm font-bold text-app-text transition hover:bg-app-panel">
                {option.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

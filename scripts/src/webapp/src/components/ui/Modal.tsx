import { useEffect, useRef, type ReactNode } from "react";

interface ModalProps {
  title: string;
  eyebrow?: string;
  open: boolean;
  children: ReactNode;
  onClose: () => void;
}

export function Modal({ title, eyebrow, open, children, onClose }: ModalProps) {
  const sheetRef = useRef<HTMLElement>(null);

  // Escape-to-close.
  useEffect(() => {
    if (!open) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  // Move focus into the sheet on open; restore it to the trigger on close.
  useEffect(() => {
    if (!open) {
      return;
    }
    const previouslyFocused = document.activeElement as HTMLElement | null;
    sheetRef.current?.focus();
    return () => previouslyFocused?.focus?.();
  }, [open]);

  if (!open) {
    return null;
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        ref={sheetRef}
        aria-label={title}
        aria-modal="true"
        className="modal-sheet"
        role="dialog"
        tabIndex={-1}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <div>
            {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
            <h2>{title}</h2>
          </div>
          <button className="button button--ghost" onClick={onClose} type="button">
            Close
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

interface OptionCardProps {
  title: string;
  meta?: string;
  selected?: boolean;
  disabled?: boolean;
  onClick: () => void;
}

export function OptionCard({ title, meta, selected, disabled, onClick }: OptionCardProps) {
  return (
    <button
      className={`option-card ${selected ? "option-card--selected" : ""}`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <strong>{title}</strong>
      {meta ? <span>{meta}</span> : null}
    </button>
  );
}

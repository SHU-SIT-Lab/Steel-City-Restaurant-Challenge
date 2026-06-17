import type { ReactNode } from "react";

interface ModalProps {
  title: string;
  eyebrow?: string;
  open: boolean;
  children: ReactNode;
  onClose: () => void;
}

export function Modal({ title, eyebrow, open, children, onClose }: ModalProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        aria-modal="true"
        className="modal-sheet"
        role="dialog"
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

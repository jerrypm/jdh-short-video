import { X, LoaderCircle } from "lucide-react";
import { useEffect, useRef } from "react";
export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    const dialog = ref.current;
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={wide ? "modal wide" : "modal"}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <div className="modal-head">
        <h2>{title}</h2>
        <button className="icon" onClick={onClose} aria-label="Tutup">
          <X size={17} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
export function Busy({ text }: { text: string }) {
  return (
    <span className="busy">
      <LoaderCircle size={15} className="spin" />
      {text}
    </span>
  );
}
export function Brand() {
  return (
    <div className="brand">
      <span>JDH</span>
      <strong>Shorts Studio</strong>
    </div>
  );
}
export function Status({
  children,
  kind = "idle",
}: {
  children: React.ReactNode;
  kind?: string;
}) {
  return <span className={`badge ${kind}`}>{children}</span>;
}

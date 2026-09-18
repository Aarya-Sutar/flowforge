import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

interface BaseFieldProps {
  label: string;
  error?: string;
  hint?: string;
}

function FieldWrapper({ label, error, hint, children }: BaseFieldProps & { children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-gray-500 dark:text-gray-400">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-red-600 dark:text-red-400">{error}</span>}
    </label>
  );
}

const inputClasses =
  "w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100";

export function InputField({
  label,
  error,
  hint,
  ...props
}: BaseFieldProps & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <FieldWrapper label={label} error={error} hint={hint}>
      <input className={`${inputClasses} ${error ? "border-red-400" : ""}`} {...props} />
    </FieldWrapper>
  );
}

export function TextareaField({
  label,
  error,
  hint,
  ...props
}: BaseFieldProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <FieldWrapper label={label} error={error} hint={hint}>
      <textarea className={`${inputClasses} ${error ? "border-red-400" : ""}`} {...props} />
    </FieldWrapper>
  );
}

export function SelectField({
  label,
  error,
  hint,
  children,
  ...props
}: BaseFieldProps & { children: ReactNode } & React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <FieldWrapper label={label} error={error} hint={hint}>
      <select className={`${inputClasses} ${error ? "border-red-400" : ""}`} {...props}>
        {children}
      </select>
    </FieldWrapper>
  );
}

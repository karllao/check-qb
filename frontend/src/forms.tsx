import { Field } from "./components";
export function SectionTitle({
  number,
  title,
  description,
}: {
  number: string;
  title: string;
  description: string;
}) {
  return (
    <div className="section-title">
      <span>{number}</span>
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
    </div>
  );
}
export function NumberField({
  label,
  value,
  min,
  step = 0.01,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <Field label={label}>
      <input
        required
        type="number"
        min={min}
        step={step}
        value={value}
        onChange={(e) => onChange(+e.target.value)}
      />
    </Field>
  );
}

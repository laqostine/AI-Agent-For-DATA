import type { MissingField } from '@/lib/types';

interface MissingFieldsFormProps {
  fields: MissingField[];
  values: Record<string, string | number>;
  onChange: (field: string, value: string | number) => void;
}

export default function MissingFieldsForm({
  fields,
  values,
  onChange,
}: MissingFieldsFormProps) {
  if (fields.length === 0) return null;

  return (
    <div className="card p-6">
      <h3 className="text-lg font-semibold text-gray-100 mb-1">Missing Information</h3>
      <p className="text-sm text-gray-500 mb-4">
        Please fill in the details our AI could not confidently determine.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {fields.map((field) => {
          const currentValue =
            values[field.field_name] ?? field.agent_guess ?? field.default_value ?? '';

          return (
            <div key={field.field_name}>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                {field.label}
                {field.required && <span className="text-danger ml-1">*</span>}
              </label>

              {field.field_type === 'select' && field.options ? (
                <select
                  className="input-field"
                  value={String(currentValue)}
                  onChange={(e) => onChange(field.field_name, e.target.value)}
                >
                  <option value="">Select...</option>
                  {field.options.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              ) : field.field_type === 'number' ? (
                <input
                  type="number"
                  className="input-field"
                  value={currentValue}
                  onChange={(e) =>
                    onChange(field.field_name, parseFloat(e.target.value) || 0)
                  }
                  step="0.1"
                />
              ) : (
                <input
                  type="text"
                  className="input-field"
                  value={String(currentValue)}
                  onChange={(e) => onChange(field.field_name, e.target.value)}
                  placeholder={`Enter ${field.label.toLowerCase()}`}
                />
              )}

              {field.agent_guess !== undefined && (
                <p className="text-xs text-accent/70 mt-1">
                  AI suggestion: {String(field.agent_guess)}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

import type { Field } from "./models";
import UploadedFileCards from "./UploadedFileCards";
import type { Translations } from "@/translations/en";

interface SchemaFormInputProps {
  field: Field;
  value?: any;
  readOnly?: boolean;
  messages: Translations["SchemaForm"];
}

const defaultRows = 8;

/** SchemaFormInput is responsible for rendering the actual input component. */
function SchemaFormInput({
  field,
  value,
  messages,
  readOnly: elementReadOnly = false,
}: SchemaFormInputProps) {
  const {
    slug,
    type,
    required,
    htmlType,
    readOnly: fieldReadOnly = false,
  } = field;
  const readOnly = elementReadOnly || fieldReadOnly;

  // TODO: make id unique in a deterministic fashion
  switch (type) {
    case "Spacer":
    case "Divider":
    case "StaticText":
      return null;
    case "SingleLineText":
      return (
        <input
          className="form-control"
          type={htmlType ?? "text"}
          defaultValue={value}
          required={required}
          readOnly={readOnly}
          id={slug}
          name={slug}
        />
      );
    case "MultiLineText":
      return (
        <textarea
          className="form-control"
          rows={field.rows ?? defaultRows}
          defaultValue={value}
          required={required}
          readOnly={readOnly}
          id={slug}
          name={slug}
        />
      );
    case "NumberField":
    case "DecimalField":
      return (
        <input
          className="form-control"
          type="number"
          defaultValue={value}
          required={required}
          readOnly={readOnly}
          id={slug}
          name={slug}
          step={field.decimalPlaces ? 1 / 10 ** field.decimalPlaces : 1}
          inputMode={field.decimalPlaces ? "decimal" : "numeric"}
          min={field.minValue}
          max={field.maxValue}
        />
      );
    case "SingleCheckbox":
      // FIXME: Required checkboxes fail in a funny way.
      return (
        <input
          className="form-check-input"
          type="checkbox"
          defaultChecked={!!value}
          required={required}
          disabled={readOnly}
          id={slug}
          name={slug}
        />
      );
    case "SingleSelect":
      let choices = field.choices ?? [];

      switch (field.presentation) {
        case "dropdown":
          choices = [{ slug: "", title: "" }, ...field.choices];

          return (
            <select
              className="form-select"
              required={required}
              disabled={readOnly}
              id={slug}
              name={slug}
              defaultValue={value}
            >
              {choices.map((choice) => (
                <option value={choice.slug} key={choice.slug}>
                  {choice.title}
                </option>
              ))}
            </select>
          );
        default:
          // radio button group
          return (
            <>
              {choices.map((choice) => (
                <div key={choice.slug} className="mb-2">
                  <input
                    className="form-check-input"
                    type="radio"
                    required={required}
                    disabled={readOnly}
                    id={choice.slug}
                    name={slug}
                    value={choice.slug}
                    defaultChecked={choice.slug === value}
                  />{" "}
                  <label htmlFor={choice.slug} className="form-check-label">
                    {choice.title}
                  </label>
                </div>
              ))}
            </>
          );
      }
    case "MultiSelect":
      return (
        <>
          {field.choices?.map((choice) => {
            const name = `${field.slug}.${choice.slug}`;
            return (
              <div key={choice.slug} className="mb-2">
                <input
                  className="form-check-input"
                  type="checkbox"
                  defaultChecked={value?.includes(choice.slug)}
                  disabled={readOnly}
                  id={name}
                  name={name}
                />{" "}
                <label htmlFor={name} className="form-check-label">
                  {choice.title}
                </label>
              </div>
            );
          })}
        </>
      );
    case "RadioMatrix":
      const questions = field.questions ?? [];
      return (
        <table className="table table-striped">
          <thead>
            <tr>
              <th></th>
              {field.choices?.map((choice) => (
                <th key={choice.slug} scope="col">
                  {choice.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {questions.map((question) => (
              <tr key={question.slug}>
                <td scope="row">{question.title}</td>
                {field.choices?.map((choice) => (
                  <td key={choice.slug}>
                    <input
                      className="form-check-input"
                      type="radio"
                      required={required}
                      disabled={readOnly}
                      name={`${field.slug}.${question.slug}`}
                      value={choice.slug}
                      defaultChecked={choice.slug === value?.[question.slug]}
                      title={`${choice.title}`}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      );
    case "FileUpload":
      if (readOnly) {
        return <UploadedFileCards urls={value} messages={messages} />;
      } else {
        // TODO what if readOnly or value but not both?
        return (
          <input
            className="form-control"
            type="file"
            id={slug}
            name={slug}
            required={required}
            multiple={field.multiple}
          />
        );
      }
  }
}

export default SchemaFormInput;
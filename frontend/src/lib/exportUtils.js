function timestampSlug() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function downloadBlob(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function downloadJson(name, data) {
  downloadBlob(
    `${name}-${timestampSlug()}.json`,
    JSON.stringify(data, null, 2),
    "application/json",
  );
}

export function downloadCsv(name, rows) {
  const normalizedRows = rows || [];
  const keys = [...new Set(normalizedRows.flatMap((row) => Object.keys(row || {})))];
  const lines = [
    keys.join(","),
    ...normalizedRows.map((row) => keys.map((key) => csvCell(row?.[key])).join(",")),
  ];
  downloadBlob(`${name}-${timestampSlug()}.csv`, lines.join("\n"), "text/csv");
}

export function flattenForCsv(value, prefix = "") {
  if (value === null || value === undefined) return {};
  if (Array.isArray(value)) return { [prefix || "value"]: value.join("|") };
  if (typeof value !== "object") return { [prefix || "value"]: value };
  return Object.entries(value).reduce((acc, [key, item]) => {
    const nextKey = prefix ? `${prefix}.${key}` : key;
    if (item && typeof item === "object" && !Array.isArray(item)) {
      Object.assign(acc, flattenForCsv(item, nextKey));
    } else {
      acc[nextKey] = Array.isArray(item) ? item.join("|") : item;
    }
    return acc;
  }, {});
}

function csvCell(value) {
  if (value === null || value === undefined) return "";
  const text = String(value).replaceAll('"', '""');
  return /[",\n]/.test(text) ? `"${text}"` : text;
}

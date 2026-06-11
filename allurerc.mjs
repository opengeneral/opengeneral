// Allure 3 report configuration (consumed by `allure generate`).
// A plain object (defineConfig is only a type helper, so no import of `allure` is
// needed — which keeps it resolvable when the CLI is run via npx / a global install).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const iconSvg = readFileSync(join(here, "logos", "opengeneral-icon.svg"), "utf8");
// Embed the brand icon as a data URI so it travels with the report (no hosting /
// custom-domain dependency, and it works in nested per-run report folders).
const logo = "data:image/svg+xml;base64," + Buffer.from(iconSvg).toString("base64");

export default {
  name: "OpenGeneral cross-platform tests",
  output: "report",
  historyPath: "history.jsonl",
  plugins: {
    awesome: {
      options: {
        reportName: "OpenGeneral cross-platform tests",
        logo,
        // Lead the tree with the OS so per-platform results read at a glance, then
        // product domain (epic) then component (feature).
        groupBy: ["os", "epic", "feature"],
        theme: "auto",
      },
    },
  },
};

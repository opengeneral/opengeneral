// Allure 3 report configuration (consumed by `allure generate`).
// A plain object (defineConfig is only a type helper, so no import is needed —
// which keeps it resolvable when the CLI is run via npx).
export default {
  name: "OpenGeneral cross-platform tests",
  output: "report",
  historyPath: "history.jsonl",
  plugins: {
    awesome: {
      options: {
        reportName: "OpenGeneral cross-platform tests",
        // Group the test tree by product domain (epic) then component (feature).
        groupBy: ["epic", "feature"],
        theme: "auto",
      },
    },
  },
};

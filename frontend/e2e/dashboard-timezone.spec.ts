import { expect, test } from "@playwright/test";

const cases = [
  {
    timezone: "Asia/Hong_Kong",
    date: "2026-10-25",
    start: "2026-10-24T16:00:00.000Z",
    end: "2026-10-25T15:59:59.000Z",
  },
  {
    timezone: "UTC",
    date: "2026-10-25",
    start: "2026-10-25T00:00:00.000Z",
    end: "2026-10-25T23:59:59.000Z",
  },
  {
    timezone: "America/New_York",
    date: "2026-03-08",
    start: "2026-03-08T05:00:00.000Z",
    end: "2026-03-09T03:59:59.000Z",
  },
  {
    timezone: "America/New_York",
    date: "2026-11-01",
    start: "2026-11-01T04:00:00.000Z",
    end: "2026-11-02T04:59:59.000Z",
  },
];

for (const scenario of cases) {
  test.describe(`${scenario.timezone} ${scenario.date}`, () => {
    test.use({ timezoneId: scenario.timezone });

    test("converts local day boundaries to UTC, including DST transitions", async ({ page }) => {
      await page.route("**/__timezone_fixture", (route) =>
        route.fulfill({ contentType: "text/html", body: "<html></html>" }),
      );
      await page.goto("/__timezone_fixture");
      const boundaries = await page.evaluate(
        async ({ date, modulePath }) => {
          const { toIsoDateTime } = await import(modulePath);
          return {
            start: toIsoDateTime(date, "start"),
            end: toIsoDateTime(date, "end"),
            empty: toIsoDateTime(undefined, "start"),
          };
        },
        { date: scenario.date, modulePath: "/src/features/dashboard/lib/dashboard-formatters.ts" },
      );
      expect(boundaries).toEqual({ start: scenario.start, end: scenario.end, empty: undefined });
    });
  });
}

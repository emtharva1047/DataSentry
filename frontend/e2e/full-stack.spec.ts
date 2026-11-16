import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

const apiBase = "http://127.0.0.1:8000";
const filename = "datasentry-e2e-" + randomUUID() + ".csv";

function buildCsv(): string {
  const rows = ["record_id,age,income,city,segment,score"];
  const classes = ["alpha", "beta", "gamma"];
  for (let index = 0; index < 60; index += 1) {
    const age = index === 3 ? "" : String(21 + ((index * 7) % 35));
    const income = String(30_000 + ((index * 137) % 40_000));
    const city = index % 3 === 0 ? "North " : index % 3 === 1 ? "South" : "West";
    const segment = classes[index % classes.length];
    const score = String(((index * 19) % 37) + ((index * 7) % 13) * 0.17);
    rows.push([index + 1, age, income, city, segment, score].join(","));
  }
  rows.push(rows[6]);
  return rows.join("\n") + "\n";
}

test("browser completes the upload-to-baseline workflow against FastAPI", async ({ page, request }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  const health = await request.get(apiBase + "/api/health");
  expect(health.status()).toBe(200);
  expect((await health.json()).status).toBe("ok");

  const overviewBefore = await request.get(apiBase + "/api/overview");
  expect(overviewBefore.status()).toBe(200);
  const countBefore = (await overviewBefore.json()).dataset_count as number;

  await page.goto("/");
  await expect(page.getByText("Database engine")).toBeVisible();
  await page.locator("#dataset-file").setInputFiles({
    name: filename,
    mimeType: "text/csv",
    buffer: Buffer.from(buildCsv(), "utf-8"),
  });

  const uploadResponsePromise = page.waitForResponse((response) =>
    response.url().endsWith("/api/datasets/upload") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Upload dataset" }).click();
  const uploadResponse = await uploadResponsePromise;
  expect(uploadResponse.status()).toBe(201);
  const uploaded = await uploadResponse.json();
  expect(uploaded.filename).toBe(filename);
  expect(uploaded.original_path).toBeUndefined();
  expect(uploaded.sha256_hash).toMatch(/^[a-f0-9]{64}$/);
  await expect(page.getByText(filename + " was uploaded successfully.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Data Quality Report" })).toBeVisible();

  const datasetId = uploaded.id as number;
  const detailBefore = await request.get(apiBase + "/api/datasets/" + datasetId);
  expect(detailBefore.status()).toBe(200);
  const originalMetadata = await detailBefore.json();
  expect(originalMetadata.original_path).toBeUndefined();
  expect(originalMetadata.sha256_hash).toBe(uploaded.sha256_hash);

  const overviewAfter = await request.get(apiBase + "/api/overview");
  expect((await overviewAfter.json()).dataset_count).toBe(countBefore + 1);
  const listing = await request.get(apiBase + "/api/datasets");
  expect(listing.status()).toBe(200);
  expect((await listing.json()).some((item: { id: number }) => item.id === datasetId)).toBe(true);

  await page.getByRole("button", { name: "Run quality check for " + filename }).click();
  await expect(page.getByText("Overall DQS")).toBeVisible();

  const schemaResponse = await request.post(apiBase + "/api/datasets/" + datasetId + "/quality/validate", {
    data: {
      columns: {
        age: { type: "number", required: false, minimum: 0 },
        segment: { type: "string", required: true, allowed_values: ["alpha", "beta", "gamma"] },
      },
      allow_extra_columns: true,
    },
  });
  expect(schemaResponse.status()).toBe(200);

  await page.getByRole("button", { name: "Run anomaly scan for " + filename }).click();
  await expect(page.getByText("Unique rows flagged")).toBeVisible();

  await page.getByRole("button", { name: "Review cleaning for " + filename }).click();
  await expect(page.getByRole("heading", { name: "Cleaning recommendations & version history" })).toBeVisible();
  const previewButton = page.getByRole("button", { name: "Preview selected changes" });
  await expect(previewButton).toBeEnabled();
  await previewButton.click();
  await expect(page.getByRole("heading", { name: "Review the proposed result" })).toBeVisible();
  await page.getByLabel(/I reviewed the proposed row and cell changes/).check();

  const applyResponsePromise = page.waitForResponse((response) =>
    response.url().includes("/api/datasets/" + datasetId + "/cleaning/apply") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Confirm and create new dataset version" }).click();
  const applyResponse = await applyResponsePromise;
  expect(applyResponse.status()).toBe(201);
  await expect(page.getByText("Version 1 created successfully")).toBeVisible();
  await expect(page.getByText("Version DQS")).toBeVisible();

  const versionsResponse = await request.get(apiBase + "/api/datasets/" + datasetId + "/cleaning/versions");
  expect(versionsResponse.status()).toBe(200);
  const versions = await versionsResponse.json();
  expect(versions).toHaveLength(1);
  expect(versions[0].parent_version_id).toBeNull();
  expect(versions[0].rows_count).toBe(60);

  const detailAfter = await request.get(apiBase + "/api/datasets/" + datasetId);
  expect((await detailAfter.json()).sha256_hash).toBe(originalMetadata.sha256_hash);

  await page.getByRole("button", { name: "Open ML readiness for " + filename }).click();
  await expect(page.locator("#ml-target")).toBeVisible();
  await page.locator("#ml-task").selectOption("classification");
  await page.locator("#ml-target").selectOption("segment");
  await page.getByRole("button", { name: "Assess ML readiness" }).click();
  await expect(page.getByText("Readiness status")).toBeVisible();
  await expect(page.getByRole("button", { name: "Train baseline" })).toBeEnabled();

  const classificationPromise = page.waitForResponse((response) =>
    response.url().includes("/api/datasets/" + datasetId + "/baseline-model") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Train baseline" }).click();
  const classificationResponse = await classificationPromise;
  expect(classificationResponse.status()).toBe(200);
  const classification = await classificationResponse.json();
  expect(classification.model).toBe("logistic_regression");
  expect(classification.preprocessing.fit_scope).toBe("training_partition_only");
  expect(classification.preprocessing.test_partition_used_to_fit_preprocessing).toBe(false);
  expect(Number.isFinite(classification.metrics.macro_f1)).toBe(true);
  await expect(page.getByText("Baseline evaluation")).toBeVisible();
  await expect(page.getByText("Macro F1")).toBeVisible();

  await page.locator("#ml-task").selectOption("regression");
  await page.locator("#ml-target").selectOption("score");
  const regressionReadinessPromise = page.waitForResponse((response) =>
    response.url().includes("/api/datasets/" + datasetId + "/ml-readiness") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Assess ML readiness" }).click();
  const regressionReadinessResponse = await regressionReadinessPromise;
  expect(regressionReadinessResponse.status()).toBe(200);
  const regressionReadiness = await regressionReadinessResponse.json();
  expect(regressionReadiness.readiness_status).not.toBe("blocked");

  const regressionPromise = page.waitForResponse((response) =>
    response.url().includes("/api/datasets/" + datasetId + "/baseline-model") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Train baseline" }).click();
  const regressionResponse = await regressionPromise;
  expect(regressionResponse.status()).toBe(200);
  const regression = await regressionResponse.json();
  expect(regression.model).toBe("ridge_regression");
  expect(regression.preprocessing.test_partition_used_to_fit_preprocessing).toBe(false);
  expect(Number.isFinite(regression.metrics.mae)).toBe(true);
  expect(Number.isFinite(regression.metrics.rmse)).toBe(true);
  await expect(page.getByText("MAE", { exact: true })).toBeVisible();

  expect(pageErrors).toEqual([]);
});

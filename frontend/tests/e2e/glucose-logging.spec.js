
import { test, expect } from '@playwright/test';

test('select patient, log glucose, and update chart', async ({ page }) => {
  // 1. Load the dashboard.
  await page.goto('http://localhost:5173/');

  await expect(
    page.getByRole('heading', { name: 'GlucoTrack' })
  ).toBeVisible();

  // 2. Select a patient.
  const patientSelect = page.getByLabel('Select Patient');
  await expect(patientSelect).toBeEnabled();

  const options = patientSelect.locator('option');
  await expect(options).not.toHaveCount(0);

  const patientId = await options.first().getAttribute('value');
  expect(patientId).toBeTruthy();

  // Explicitly select a patient.
  if (await options.count() > 1) {
    const secondId = await options.nth(1).getAttribute('value');
    await patientSelect.selectOption(secondId);
  }
  await patientSelect.selectOption(patientId);
  await expect(patientSelect).toHaveValue(patientId);

  // 3. Wait for the chart and record its initial reading count.
  const chart = page.locator('.chart-card').filter({
    has: page.getByRole('heading', { name: 'Glucose History' }),
  });

  await expect(chart).toBeVisible();

  const sourceNote = chart.getByText(/^Sources?:/);
  await expect(sourceNote).toBeVisible();

  const originalText = await sourceNote.innerText();

  // 4. Log a glucose reading.
  const glucoseValue = 233;
  const measuredAt = new Date().toISOString().slice(0, 16);

  await page.getByLabel('Blood Glucose (mg/dL)')
    .fill(String(glucoseValue));

  await page.getByLabel('Date and Time').fill(measuredAt);
  await page.getByLabel('Meal Context').selectOption('fasting');

  const saveResponse = page.waitForResponse(response =>
    response.url().includes(`/api/patients/${patientId}/glucose`) &&
    response.request().method() === 'POST'
  );

  await page.getByRole('button', {
    name: 'Save Glucose Reading',
  }).click();

  expect((await saveResponse).ok()).toBeTruthy();

  await expect(
    page.getByRole('status').filter({
      hasText: 'Glucose reading saved.',
    })
  ).toBeVisible();

  // 5. Verify that the chart refreshes with an updated reading count.
  await expect(sourceNote).not.toHaveText(originalText, {
    timeout: 15000,
  });
});

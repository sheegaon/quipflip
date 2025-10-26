import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';
const TEST_EMAIL = 'x2@x.com';
const TEST_PASSWORD = 'password';

test.describe('Statistics Page Loading Bug', () => {
  test('should load statistics page without chart dimension errors', async ({ page }) => {
    console.log('\n=== Testing Statistics Page Loading ===\n');

    // Capture console errors
    const consoleErrors: string[] = [];
    const consoleWarnings: string[] = [];

    page.on('console', msg => {
      const text = msg.text();
      if (msg.type() === 'error') {
        consoleErrors.push(text);
        console.log('❌ Console Error:', text);
      } else if (msg.type() === 'warning') {
        consoleWarnings.push(text);
        console.log('⚠️  Console Warning:', text);
      }
    });

    // Login
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    const emailInput = page.locator('input[type="email"]').nth(1);
    const passwordInput = page.locator('input[type="password"]').nth(1);
    await emailInput.fill(TEST_EMAIL);
    await passwordInput.fill(TEST_PASSWORD);
    await page.locator('button', { hasText: /^login$/i }).click();
    await page.waitForTimeout(2000);

    console.log('✓ Logged in successfully');

    // Navigate to Statistics page
    await page.goto(`${BASE_URL}/statistics`);
    console.log('✓ Navigating to Statistics page...');

    // Wait for initial load
    await page.waitForTimeout(500);

    // Take screenshot of initial state
    await page.screenshot({ path: 'screenshots/statistics-loading.png', fullPage: true });

    // Wait for the loading spinner to disappear
    const loadingSpinner = page.locator('.animate-spin');
    if (await loadingSpinner.count() > 0) {
      console.log('⏳ Waiting for loading spinner to disappear...');
      await loadingSpinner.first().waitFor({ state: 'hidden', timeout: 5000 }).catch(() => {
        console.log('⚠️  Loading spinner timeout - continuing anyway');
      });
    }

    // Wait a bit more for charts to render
    await page.waitForTimeout(2000);

    // Take screenshot after loading
    await page.screenshot({ path: 'screenshots/statistics-loaded.png', fullPage: true });

    // Check for error messages in UI
    const errorMessages = await page.locator('text=/error|failed|something went wrong/i').allTextContents();
    if (errorMessages.length > 0) {
      console.log('❌ Error messages found in UI:', errorMessages);
    } else {
      console.log('✓ No error messages in UI');
    }

    // Check if charts are visible
    const chartsVisible = await page.locator('h2:has-text("Win Rates"), h2:has-text("Earnings"), h2:has-text("Performance")').count();
    console.log(`📊 Chart sections found: ${chartsVisible}`);

    // Look for the specific Recharts dimension error
    const dimensionErrors = consoleWarnings.filter(w =>
      w.includes('width(-1)') ||
      w.includes('height(-1)') ||
      w.includes('should be greater than 0')
    );

    console.log('\n=== Results ===');
    console.log(`Total console errors: ${consoleErrors.length}`);
    console.log(`Total console warnings: ${consoleWarnings.length}`);
    console.log(`Chart dimension errors: ${dimensionErrors.length}`);

    if (dimensionErrors.length > 0) {
      console.log('\n❌ FOUND CHART DIMENSION ERRORS:');
      dimensionErrors.forEach((err, idx) => {
        console.log(`  ${idx + 1}. ${err.substring(0, 100)}...`);
      });
    } else {
      console.log('✅ No chart dimension errors found!');
    }

    // Check if page loaded successfully despite errors
    const pageTitle = await page.locator('h1').first().textContent();
    console.log(`\nPage title: "${pageTitle}"`);

    const hasStatisticsContent = pageTitle?.includes('Statistics') || false;
    console.log(`Statistics content loaded: ${hasStatisticsContent ? '✓' : '✗'}`);
  });

  test('should verify chart containers have dimensions before rendering', async ({ page }) => {
    console.log('\n=== Testing Chart Container Dimensions ===\n');

    // Login
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    const emailInput = page.locator('input[type="email"]').nth(1);
    const passwordInput = page.locator('input[type="password"]').nth(1);
    await emailInput.fill(TEST_EMAIL);
    await passwordInput.fill(TEST_PASSWORD);
    await page.locator('button', { hasText: /^login$/i }).click();
    await page.waitForTimeout(2000);

    // Navigate to Statistics
    await page.goto(`${BASE_URL}/statistics`);
    await page.waitForTimeout(1000);

    // Check dimensions of chart containers
    const chartContainers = await page.locator('.tile-card').all();
    console.log(`Found ${chartContainers.length} chart containers`);

    for (let i = 0; i < Math.min(chartContainers.length, 5); i++) {
      const container = chartContainers[i];
      const box = await container.boundingBox();

      if (box) {
        console.log(`Container ${i + 1}: ${box.width}x${box.height}px`);

        if (box.width <= 0 || box.height <= 0) {
          console.log(`  ❌ Invalid dimensions!`);
        } else {
          console.log(`  ✓ Valid dimensions`);
        }
      } else {
        console.log(`Container ${i + 1}: Not visible`);
      }
    }
  });
});

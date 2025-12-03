import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';
const TEST_EMAIL = `test_${Date.now()}@example.com`;
const TEST_PASSWORD = 'TestPass123!';

test.describe('Quipflip Interactive Tests', () => {
  test('should complete registration and explore dashboard', async ({ page }) => {
    console.log('\n=== Starting Interactive Test ===\n');

    // Navigate to app
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    console.log('✓ Loaded landing page');

    // Take screenshot of landing page
    await page.screenshot({ path: 'screenshots/01-landing.png', fullPage: true });

    // Fill registration form
    const emailInputs = await page.locator('input[type="email"]').all();
    if (emailInputs.length >= 1) {
      await emailInputs[0].fill(TEST_EMAIL);
      console.log(`✓ Filled email: ${TEST_EMAIL}`);
    }

    const passwordInputs = await page.locator('input[type="password"]').all();
    if (passwordInputs.length >= 1) {
      await passwordInputs[0].fill(TEST_PASSWORD);
      console.log('✓ Filled password');
    }

    await page.screenshot({ path: 'screenshots/02-registration-filled.png', fullPage: true });

    // Click create account button
    const createAccountBtn = page.locator('button', { hasText: /create new account/i });
    if (await createAccountBtn.count() > 0) {
      console.log('✓ Found Create Account button, clicking...');
      await createAccountBtn.click();
      await page.waitForTimeout(2000); // Wait for response

      await page.screenshot({ path: 'screenshots/03-after-registration.png', fullPage: true });

      // Check if we're on dashboard or got an error
      const currentUrl = page.url();
      console.log(`Current URL: ${currentUrl}`);

      // Look for dashboard elements
      const hasDashboard = await page.locator('text=/dashboard|balance|bonus/i').count() > 0;
      const hasRounds = await page.locator('button', { hasText: /prompt|copy|vote/i }).count() > 0;

      if (hasDashboard || hasRounds) {
        console.log('✓ Successfully registered and reached dashboard!');

        // Explore dashboard
        await exploreDashboard(page);
      } else {
        // Check for error messages
        const errorText = await page.locator('text=/error|invalid|failed/i').allTextContents();
        if (errorText.length > 0) {
          console.log('Registration error:', errorText);
        } else {
          console.log('Still on registration page or unknown state');
        }
      }
    }
  });

  test('should explore existing login', async ({ page }) => {
    console.log('\n=== Testing Login Interface ===\n');

    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Scroll to login section
    await page.locator('text=/returning player|login/i').first().scrollIntoViewIfNeeded();
    await page.screenshot({ path: 'screenshots/04-login-section.png', fullPage: true });

    // Check login form structure
    const loginEmailInput = await page.locator('input[type="email"]').nth(1);
    const loginPasswordInput = await page.locator('input[type="password"]').nth(1);

    if (await loginEmailInput.count() > 0) {
      console.log('✓ Login email field found');
    }
    if (await loginPasswordInput.count() > 0) {
      console.log('✓ Login password field found');
    }

    // Look for "How to Play" section
    const howToPlay = await page.locator('text=/how to play/i').allTextContents();
    if (howToPlay.length > 0) {
      console.log('✓ Found "How to Play" instructions');
    }

    // Extract game instructions
    const instructions = await page.locator('text=/submit|copy|vote/i').allTextContents();
    console.log('\nGame Instructions:');
    instructions.forEach((instr, idx) => {
      console.log(`  ${idx + 1}. ${instr}`);
    });
  });

  test('should check branding and styling', async ({ page }) => {
    console.log('\n=== Checking Branding and Styling ===\n');

    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Check for logo/branding
    const images = await page.locator('img').all();
    console.log(`Found ${images.length} image(s)`);

    for (let i = 0; i < images.length; i++) {
      const src = images[i].getAttribute('src');
      const alt = images[i].getAttribute('alt');
      console.log(`  Image ${i + 1}: ${alt || 'no alt'} - ${src}`);
    }

    // Check color scheme
    const body = await page.locator('body').first();
    const bgColor = await body.evaluate(el => window.getComputedStyle(el).backgroundColor);
    console.log(`\nBackground color: ${bgColor}`);

    // Check for gradient background (common in the design)
    const hasGradient = await page.locator('[class*="gradient"]').count() > 0;
    console.log(`Gradient elements: ${hasGradient ? '✓ Found' : '✗ None'}`);

    await page.screenshot({ path: 'screenshots/05-branding-check.png', fullPage: true });
  });

  test('should check responsive behavior', async ({ page }) => {
    console.log('\n=== Testing Responsive Design ===\n');

    const viewports = [
      { name: 'Mobile', width: 375, height: 667 },
      { name: 'Tablet', width: 768, height: 1024 },
      { name: 'Desktop', width: 1440, height: 900 },
    ];

    for (const viewport of viewports) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto(BASE_URL);
      await page.waitForLoadState('networkidle');

      const buttons = await page.locator('button:visible').count();
      const inputs = await page.locator('input:visible').count();

      console.log(`${viewport.name} (${viewport.width}x${viewport.height}):`);
      console.log(`  Visible buttons: ${buttons}`);
      console.log(`  Visible inputs: ${inputs}`);

      await page.screenshot({
        path: `screenshots/06-${viewport.name.toLowerCase()}-responsive.png`,
        fullPage: true
      });
    }
  });
});

async function exploreDashboard(page: any) {
  console.log('\n=== Exploring Dashboard ===\n');

  // Take screenshot
  await page.screenshot({ path: 'screenshots/dashboard-main.png', fullPage: true });

  // Look for balance display
  const balanceText = await page.locator('text=/balance|coins|points/i').allTextContents();
  if (balanceText.length > 0) {
    console.log('Balance display:', balanceText);
  }

  // Look for round buttons
  const roundButtons = await page.locator('button').allTextContents();
  console.log('\nAvailable buttons:');
  roundButtons.forEach(btn => {
    if (btn.trim()) console.log(`  - ${btn}`);
  });

  // Look for daily bonus
  const bonusBtn = page.locator('button', { hasText: /bonus|claim/i });
  if (await bonusBtn.count() > 0) {
    console.log('\n✓ Found daily bonus button');
  }

  // Check for navigation elements
  const navElements = await page.locator('nav, [role="navigation"]').count();
  console.log(`Navigation elements: ${navElements}`);

  // Look for round type indicators
  const roundTypes = await page.locator('text=/prompt|copy|vote/i').allTextContents();
  console.log('\nRound types available:');
  roundTypes.forEach(type => {
    if (type.trim()) console.log(`  - ${type}`);
  });
}

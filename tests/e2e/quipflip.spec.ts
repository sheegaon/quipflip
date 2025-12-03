import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';
const API_URL = 'http://localhost:8000/qf';

test.describe('Quipflip Frontend E2E Tests', () => {
  test('should load the landing page', async ({ page }) => {
    await page.goto(BASE_URL);

    // Wait for the page to load
    await page.waitForLoadState('networkidle');

    // Take a screenshot
    await page.screenshot({ path: 'screenshots/landing-page.png', fullPage: true });

    // Check for key elements on the landing page
    const pageContent = await page.content();
    console.log('Page loaded successfully');

    // Look for login/register elements
    const hasLoginForm = await page.locator('input[type="email"], input[type="text"]').count() > 0;
    const hasPasswordInput = await page.locator('input[type="password"]').count() > 0;

    console.log('Has login form:', hasLoginForm);
    console.log('Has password input:', hasPasswordInput);
  });

  test('should display registration form', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Look for registration-related elements
    const buttons = await page.locator('button').allTextContents();
    console.log('Available buttons:', buttons);

    // Try to find register/sign up button
    const registerButton = page.locator('button', { hasText: /register|sign up|create account/i }).first();
    if (await registerButton.count() > 0) {
      await registerButton.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: 'screenshots/register-form.png', fullPage: true });
      console.log('Registration form displayed');
    }
  });

  test('should navigate and explore the app structure', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Get all interactive elements
    const links = await page.locator('a').allTextContents();
    const buttons = await page.locator('button').allTextContents();
    const inputs = await page.locator('input').count();

    console.log('\n=== App Structure ===');
    console.log('Links found:', links.filter(l => l.trim()));
    console.log('Buttons found:', buttons.filter(b => b.trim()));
    console.log('Input fields:', inputs);

    // Check the page title
    const title = await page.title();
    console.log('Page title:', title);

    // Take full page screenshot
    await page.screenshot({ path: 'screenshots/full-page.png', fullPage: true });
  });

  test('should test responsive design', async ({ page }) => {
    // Test mobile view
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'screenshots/mobile-view.png', fullPage: true });
    console.log('Mobile view captured');

    // Test tablet view
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'screenshots/tablet-view.png', fullPage: true });
    console.log('Tablet view captured');

    // Test desktop view
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'screenshots/desktop-view.png', fullPage: true });
    console.log('Desktop view captured');
  });

  test('should check for key UI components', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Check for various elements mentioned in the README
    const checks = {
      'Email input': await page.locator('input[type="email"]').count() > 0,
      'Password input': await page.locator('input[type="password"]').count() > 0,
      'Buttons': await page.locator('button').count() > 0,
      'Forms': await page.locator('form').count() > 0,
      'Images': await page.locator('img').count() > 0,
    };

    console.log('\n=== UI Components Check ===');
    for (const [component, found] of Object.entries(checks)) {
      console.log(`${component}: ${found ? '✓' : '✗'}`);
    }
  });

  test('should attempt login flow', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Look for email/username input
    const emailInput = page.locator('input[type="email"]').first();
    const passwordInput = page.locator('input[type="password"]').first();

    if (await emailInput.count() > 0 && await passwordInput.count() > 0) {
      // Fill in test credentials
      await emailInput.fill('test@example.com');
      await passwordInput.fill('testpassword123');

      await page.screenshot({ path: 'screenshots/login-filled.png', fullPage: true });
      console.log('Login form filled with test credentials');

      // Look for submit button
      const submitButton = page.locator('button[type="submit"]').first();
      if (await submitButton.count() > 0) {
        console.log('Submit button found');
        // Note: Not actually clicking to avoid creating test data
      }
    }
  });

  test('should check for Tailwind CSS styling', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Check if Tailwind classes are present
    const bodyClasses = page.locator('body').getAttribute('class');
    const hasElements = await page.locator('[class*="bg-"], [class*="text-"], [class*="p-"], [class*="m-"]').count();

    console.log('\n=== Styling Check ===');
    console.log('Body classes:', bodyClasses);
    console.log('Elements with Tailwind classes:', hasElements);
    console.log('Tailwind CSS appears to be:', hasElements > 0 ? '✓ Active' : '✗ Not detected');
  });

  test('should check console for errors', async ({ page }) => {
    const consoleMessages: string[] = [];
    const errors: string[] = [];

    page.on('console', msg => {
      consoleMessages.push(`${msg.type()}: ${msg.text()}`);
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    console.log('\n=== Console Messages ===');
    if (errors.length > 0) {
      console.log('Errors found:');
      errors.forEach(err => console.log('  ❌', err));
    } else {
      console.log('✓ No console errors detected');
    }
  });
});

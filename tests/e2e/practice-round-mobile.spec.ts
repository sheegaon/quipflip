import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';
const TEST_EMAIL = `practice_test_${Date.now()}@example.com`;
const TEST_PASSWORD = 'TestPass123!';

// Mobile viewport dimensions (iPhone 12/13/14)
const MOBILE_VIEWPORT = { width: 390, height: 844 };

// Configure mobile viewport at top level
test.use({
  viewport: MOBILE_VIEWPORT,
});

test.describe('Practice Round Mobile Flow', () => {

  test('should complete full practice round on mobile', async ({ page }) => {
    console.log('\n=== Starting Practice Round Mobile Test ===\n');

    // Step 1: Register a new account
    console.log('Step 1: Registering new account');
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    await page.screenshot({
      path: 'screenshots/mobile/01-landing-page.png',
      fullPage: true
    });
    console.log('✓ Screenshot: Landing page');

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

    await page.screenshot({
      path: 'screenshots/mobile/02-registration-filled.png',
      fullPage: true
    });
    console.log('✓ Screenshot: Registration form filled');

    // Submit registration
    const createAccountBtn = page.locator('button', { hasText: /create new account/i });
    if (await createAccountBtn.count() > 0) {
      await createAccountBtn.click();
      await page.waitForTimeout(2000);
      console.log('✓ Submitted registration');
    }

    // Step 2: Navigate to dashboard
    console.log('\nStep 2: Navigating to dashboard');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    await page.waitForLoadState('networkidle');

    await page.screenshot({
      path: 'screenshots/mobile/03-dashboard.png',
      fullPage: true
    });
    console.log('✓ Screenshot: Dashboard');

    // Check for balance display
    const balanceVisible = await page.locator('text=/balance|coins/i').isVisible().catch(() => false);
    if (balanceVisible) {
      console.log('✓ Balance display found');
    }

    // Step 3: Handle tutorial welcome overlay
    console.log('\nStep 3: Handling tutorial welcome overlay');

    // Wait a moment for the welcome overlay to appear
    await page.waitForTimeout(1500);

    // Check for and dismiss tutorial welcome modal
    const skipForNowBtn = page.locator('button:has-text("Skip for Now")').first();
    if (await skipForNowBtn.isVisible().catch(() => false)) {
      await skipForNowBtn.click();
      await page.waitForTimeout(1500);
      console.log('✓ Dismissed tutorial welcome overlay');
    }

    await page.screenshot({
      path: 'screenshots/mobile/04-dashboard-no-tutorial.png',
      fullPage: true
    });
    console.log('✓ Screenshot: Dashboard without tutorial');

    // Step 4: Navigate to practice mode and start prompt round
    console.log('\nStep 4: Starting practice prompt round');

    // Switch to practice mode if needed
    const practiceModeToggle = page.locator('button[aria-label*="practice"]').first();
    if (await practiceModeToggle.isVisible().catch(() => false)) {
      await practiceModeToggle.click();
      await page.waitForTimeout(1000);
      console.log('✓ Switched to practice mode');
    }

    await page.screenshot({
      path: 'screenshots/mobile/05-round-selection.png',
      fullPage: true
    });
    console.log('✓ Screenshot: Round selection');

    // Click "Start Prompt Round" button
    const startPromptButton = page.locator('button:has-text("Start Prompt Round")').first();
    if (await startPromptButton.isVisible().catch(() => false)) {
      await startPromptButton.click();
      await page.waitForTimeout(2000);
      console.log('✓ Clicked Start Prompt Round');
    }

    await page.screenshot({
      path: 'screenshots/mobile/06-practice-prompt-active.png',
      fullPage: true
    });
    console.log('✓ Screenshot: Practice prompt round active');

    // Step 5: Submit a prompt response
    console.log('\nStep 5: Submitting prompt response');

    // Look for the prompt text
    const promptText = await page.locator('text=/what|how|why|describe/i').first().textContent().catch(() => 'Not found');
    console.log(`Prompt: ${promptText}`);

    // Find and fill the response textarea
    const textarea = page.locator('textarea').first();
    if (await textarea.count() > 0) {
      const testResponse = 'This is a creative practice response for testing!';
      await textarea.fill(testResponse);
      console.log(`✓ Filled response: "${testResponse}"`);

      await page.screenshot({
        path: 'screenshots/mobile/07-prompt-filled.png',
        fullPage: true
      });
      console.log('✓ Screenshot: Prompt filled');

      // Submit the response
      const submitButton = page.locator('button', { hasText: /submit|next|continue/i }).first();
      if (await submitButton.count() > 0) {
        await submitButton.click();
        await page.waitForTimeout(2000);
        console.log('✓ Submitted prompt response');
      }
    }

    // Step 6: Practice copy round
    console.log('\nStep 6: Starting practice copy round');

    // Wait for navigation or manually navigate
    await page.waitForTimeout(1500);

    // Check if we're on the copy round selection page
    const startCopyButton = page.locator('button:has-text("Start Copy Round")').first();
    if (await startCopyButton.isVisible().catch(() => false)) {
      await page.screenshot({
        path: 'screenshots/mobile/08-copy-round-selection.png',
        fullPage: true
      });
      console.log('✓ Screenshot: Copy round selection');

      await startCopyButton.click();
      await page.waitForTimeout(2000);
      console.log('✓ Clicked Start Copy Round');
    }

    await page.screenshot({
      path: 'screenshots/mobile/09-practice-copy-active.png',
      fullPage: true
    });
    console.log('✓ Screenshot: Practice copy round active');

    // Look for prompt to copy
    const originalPrompt = await page.locator('text=/original|prompt/i').first().textContent().catch(() => '');
    console.log(`Original prompt visible: ${originalPrompt.substring(0, 50)}...`);

    // Submit a copy response
    const copyTextarea = page.locator('textarea').first();
    if (await copyTextarea.count() > 0) {
      const testCopy = 'This is my creative copy response for the practice round!';
      await copyTextarea.fill(testCopy);
      console.log(`✓ Filled copy: "${testCopy}"`);

      await page.screenshot({
        path: 'screenshots/mobile/10-copy-filled.png',
        fullPage: true
      });
      console.log('✓ Screenshot: Copy filled');

      const submitButton = page.locator('button', { hasText: /submit|next|continue/i }).first();
      if (await submitButton.count() > 0) {
        await submitButton.click();
        await page.waitForTimeout(2000);
        console.log('✓ Submitted copy response');
      }
    }

    // Step 7: Practice vote round
    console.log('\nStep 7: Starting practice vote round');

    // Wait for navigation
    await page.waitForTimeout(1500);

    // Check if we're on the vote round selection page
    const startVoteButton = page.locator('button:has-text("Start Vote Round")').first();
    if (await startVoteButton.isVisible().catch(() => false)) {
      await page.screenshot({
        path: 'screenshots/mobile/11-vote-round-selection.png',
        fullPage: true
      });
      console.log('✓ Screenshot: Vote round selection');

      await startVoteButton.click();
      await page.waitForTimeout(2000);
      console.log('✓ Clicked Start Vote Round');
    }

    await page.screenshot({
      path: 'screenshots/mobile/12-practice-vote-active.png',
      fullPage: true
    });
    console.log('✓ Screenshot: Practice vote round active');

    // Look for voting options
    const voteButtons = await page.locator('button:has-text("Vote")').count();
    console.log(`Vote buttons found: ${voteButtons}`);

    // Try to vote (if buttons available)
    if (voteButtons > 0) {
      const firstVoteButton = page.locator('button:has-text("Vote")').first();
      await firstVoteButton.click();
      await page.waitForTimeout(1500);
      console.log('✓ Cast vote');

      await page.screenshot({
        path: 'screenshots/mobile/13-vote-submitted.png',
        fullPage: true
      });
      console.log('✓ Screenshot: Vote submitted');
    }

    // Step 8: Check for results/completion
    console.log('\nStep 8: Checking for results');

    // Wait for any redirect or results screen
    await page.waitForTimeout(2000);

    await page.screenshot({
      path: 'screenshots/mobile/14-practice-complete.png',
      fullPage: true
    });
    console.log('✓ Screenshot: Practice complete');

    // Try to navigate back to dashboard
    const dashboardLink = page.locator('a[href="/dashboard"]').first();
    if (await dashboardLink.count() > 0) {
      await dashboardLink.click();
      await page.waitForTimeout(1500);
    } else {
      await page.goto(`${BASE_URL}/dashboard`);
    }

    await page.waitForLoadState('networkidle');
    await page.screenshot({
      path: 'screenshots/mobile/15-back-to-dashboard.png',
      fullPage: true
    });
    console.log('✓ Screenshot: Back to dashboard');

    console.log('\n=== Practice Round Mobile Test Complete ===\n');
    console.log('All screenshots saved to screenshots/mobile/');
  });

  test('should test different mobile orientations', async ({ page }) => {
    console.log('\n=== Testing Mobile Orientations ===\n');

    // Portrait mode (default)
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${BASE_URL}/practice/prompt`);
    await page.waitForLoadState('networkidle');

    await page.screenshot({
      path: 'screenshots/mobile/portrait-practice.png',
      fullPage: true
    });
    console.log('✓ Screenshot: Portrait mode');

    // Landscape mode
    await page.setViewportSize({ width: 844, height: 390 });
    await page.reload();
    await page.waitForLoadState('networkidle');

    await page.screenshot({
      path: 'screenshots/mobile/landscape-practice.png',
      fullPage: true
    });
    console.log('✓ Screenshot: Landscape mode');
  });

  test('should capture practice round UI elements on mobile', async ({ page }) => {
    console.log('\n=== Capturing Practice UI Elements ===\n');

    // Set mobile viewport
    await page.setViewportSize(MOBILE_VIEWPORT);

    // Go directly to practice prompt (assuming user is logged in from previous test)
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Quick login for standalone test
    const emailInput = page.locator('input[type="email"]').nth(1); // Login form
    const passwordInput = page.locator('input[type="password"]').nth(1);

    if (await emailInput.count() > 0) {
      await emailInput.fill(TEST_EMAIL);
      await passwordInput.fill(TEST_PASSWORD);

      const loginButton = page.locator('button', { hasText: /login|sign in/i }).first();
      if (await loginButton.count() > 0) {
        await loginButton.click();
        await page.waitForTimeout(2000);
      }
    }

    // Navigate to practice
    await page.goto(`${BASE_URL}/practice/prompt`);
    await page.waitForLoadState('networkidle');

    // Capture different UI states
    await page.screenshot({
      path: 'screenshots/mobile/ui-elements-default.png',
      fullPage: true
    });

    // Scroll to show different parts
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
    await page.screenshot({
      path: 'screenshots/mobile/ui-elements-scrolled.png',
      fullPage: true
    });

    console.log('✓ UI element screenshots captured');
  });
});

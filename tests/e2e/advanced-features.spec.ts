import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';
const TEST_EMAIL = `advanced_test_${Date.now()}@example.com`;
const TEST_PASSWORD = 'TestPass123!';

// Helper to register and login
async function registerAndLogin(page: any) {
  await page.goto(BASE_URL);
  await page.waitForLoadState('networkidle');

  const emailInput = page.locator('input[type="email"]').first();
  const passwordInput = page.locator('input[type="password"]').first();

  await emailInput.fill(TEST_EMAIL);
  await passwordInput.fill(TEST_PASSWORD);
  await page.locator('button', { hasText: /create new account/i }).click();
  await page.waitForTimeout(2000);

  // Skip tutorial if it appears
  const skipBtn = page.locator('button', { hasText: /skip for now/i });
  if (await skipBtn.count() > 0) {
    await skipBtn.click();
    await page.waitForTimeout(1000);
  }

  return { email: TEST_EMAIL, password: TEST_PASSWORD };
}

test.describe('Advanced Quipflip Features', () => {
  test('should navigate and explore Settings page', async ({ page }) => {
    console.log('\n=== Settings Page Test ===\n');

    await registerAndLogin(page);

    // Navigate to settings (look for settings link/button)
    const settingsLink = page.locator('a[href*="settings"], button:has-text("Settings")').first();

    if (await settingsLink.count() > 0) {
      console.log('✓ Settings link found, navigating...');
      await settingsLink.click();
      await page.waitForTimeout(1000);
    } else {
      // Try direct navigation
      console.log('⚠ Settings link not found, navigating directly to /settings');
      await page.goto(`${BASE_URL}/settings`);
      await page.waitForLoadState('networkidle');
    }

    await page.screenshot({ path: 'screenshots/settings-page.png', fullPage: true });

    // Check for Settings page elements
    const pageTitle = await page.locator('h1, h2').filter({ hasText: /settings/i }).count();
    console.log(`${pageTitle > 0 ? '✓' : '✗'} Settings page title found`);

    // Look for account information sections
    const sections = {
      'Account Information': await page.locator('text=/account information/i').count() > 0,
      'Balance Information': await page.locator('text=/balance|current balance/i').count() > 0,
      'Tutorial Management': await page.locator('text=/tutorial|reset tutorial/i').count() > 0,
      'Admin Access': await page.locator('text=/admin/i').count() > 0,
    };

    console.log('\nSettings Sections:');
    for (const [section, found] of Object.entries(sections)) {
      console.log(`  ${found ? '✓' : '✗'} ${section}`);
    }

    // Check for player info displays
    const hasUsername = await page.locator('text=/username/i').count() > 0;
    const hasEmail = await page.locator('text=/email/i').count() > 0;

    console.log('\nPlayer Information:');
    console.log(`  ${hasUsername ? '✓' : '✗'} Username field`);
    console.log(`  ${hasEmail ? '✓' : '✗'} Email field`);

    // Look for Reset Tutorial button
    const resetTutorialBtn = page.locator('button', { hasText: /reset tutorial/i });
    if (await resetTutorialBtn.count() > 0) {
      console.log('\n✓ Reset Tutorial button found');
      await resetTutorialBtn.scrollIntoViewIfNeeded();
      await page.screenshot({ path: 'screenshots/settings-reset-tutorial.png', fullPage: true });

      // Try clicking it
      console.log('  Clicking Reset Tutorial button...');
      await resetTutorialBtn.click();
      await page.waitForTimeout(2000);

      // Check for success message
      const successMsg = await page.locator('text=/success|reset/i').count();
      console.log(`  ${successMsg > 0 ? '✓' : '✗'} Tutorial reset confirmation`);
    }

    // Look for Admin Access section
    const adminAccessBtn = page.locator('button', { hasText: /access admin|admin panel/i });
    if (await adminAccessBtn.count() > 0) {
      console.log('\n✓ Admin Access button found');
      await adminAccessBtn.scrollIntoViewIfNeeded();
      await page.screenshot({ path: 'screenshots/settings-admin-section.png', fullPage: true });
    }
  });

  test('should navigate and explore Quests page', async ({ page }) => {
    console.log('\n=== Quests Page Test ===\n');

    await registerAndLogin(page);

    // Navigate to quests/rewards page
    const questsLink = page.locator('a[href*="quest"], a[href*="reward"], button:has-text("Quest"), button:has-text("Reward")').first();

    if (await questsLink.count() > 0) {
      console.log('✓ Quests link found, navigating...');
      await questsLink.click();
      await page.waitForTimeout(1000);
    } else {
      console.log('⚠ Quests link not found, trying direct navigation');
      await page.goto(`${BASE_URL}/quests`);
      await page.waitForLoadState('networkidle');
    }

    await page.screenshot({ path: 'screenshots/quests-page.png', fullPage: true });

    // Check for Quests page elements
    const pageTitle = await page.locator('h1, h2').filter({ hasText: /quest|reward/i }).count();
    console.log(`${pageTitle > 0 ? '✓' : '✗'} Quests page title found`);

    // Look for Daily Bonus section
    const dailyBonusSection = await page.locator('text=/daily bonus/i').count() > 0;
    console.log(`${dailyBonusSection ? '✓' : '✗'} Daily Bonus section found`);

    if (dailyBonusSection) {
      const claimBonusBtn = page.locator('button', { hasText: /claim bonus/i });
      const bonusAvailable = await claimBonusBtn.count() > 0 && !await claimBonusBtn.isDisabled();

      if (bonusAvailable) {
        console.log('✓ Daily bonus is available');
        await claimBonusBtn.scrollIntoViewIfNeeded();
        await page.screenshot({ path: 'screenshots/quests-daily-bonus-available.png', fullPage: true });

        // Try claiming the bonus
        console.log('  Clicking Claim Bonus button...');
        await claimBonusBtn.click();
        await page.waitForTimeout(2000);

        // Check for success message
        const successMsg = await page.locator('text=/claimed|bonus/i').count();
        console.log(`  ${successMsg > 0 ? '✓' : '✗'} Bonus claim confirmation`);
        await page.screenshot({ path: 'screenshots/quests-bonus-claimed.png', fullPage: true });
      } else {
        console.log('✗ Daily bonus already claimed or not available');
      }
    }

    // Check for quest categories
    const categories = {
      'Streaks': await page.locator('text=/streak/i').count() > 0,
      'Quality': await page.locator('text=/quality/i').count() > 0,
      'Activity': await page.locator('text=/activity/i').count() > 0,
      'Milestones': await page.locator('text=/milestone/i').count() > 0,
    };

    console.log('\nQuest Categories:');
    for (const [category, found] of Object.entries(categories)) {
      console.log(`  ${found ? '✓' : '✗'} ${category}`);
    }

    // Check for quest stats
    const hasClaimable = await page.locator('text=/claimable/i').count() > 0;
    const hasActive = await page.locator('text=/active quest/i').count() > 0;

    console.log('\nQuest Stats:');
    console.log(`  ${hasClaimable ? '✓' : '✗'} Claimable quests section`);
    console.log(`  ${hasActive ? '✓' : '✗'} Active quests section`);
  });

  test('should navigate to Results page', async ({ page }) => {
    console.log('\n=== Results Page Test ===\n');

    await registerAndLogin(page);

    // Navigate to results page
    const resultsLink = page.locator('a[href*="result"], button:has-text("Result")').first();

    if (await resultsLink.count() > 0) {
      console.log('✓ Results link found, navigating...');
      await resultsLink.click();
      await page.waitForTimeout(1000);
    } else {
      console.log('⚠ Results link not found, trying direct navigation');
      await page.goto(`${BASE_URL}/results`);
      await page.waitForLoadState('networkidle');
    }

    await page.screenshot({ path: 'screenshots/results-page.png', fullPage: true });

    // Check for Results page content
    const pageTitle = await page.locator('h1, h2').filter({ hasText: /result/i }).count();
    console.log(`${pageTitle > 0 ? '✓' : '✗'} Results page title found`);

    // Check for "No Results" message (expected for new user)
    const noResults = await page.locator('text=/no results/i').count() > 0;
    if (noResults) {
      console.log('✓ "No Results Available" message displayed (expected for new user)');
      const encouragementMsg = await page.locator('text=/complete some rounds/i').count() > 0;
      console.log(`  ${encouragementMsg ? '✓' : '✗'} Encouragement message found`);
    } else {
      console.log('✓ Results are available');

      // Look for result details
      const hasPendingResults = await page.locator('text=/pending result/i').count() > 0;
      const hasPromptText = await page.locator('text=/prompt/i').count() > 0;
      const hasVoteResults = await page.locator('text=/vote/i').count() > 0;

      console.log('\nResult Details:');
      console.log(`  ${hasPendingResults ? '✓' : '✗'} Pending results list`);
      console.log(`  ${hasPromptText ? '✓' : '✗'} Prompt text displayed`);
      console.log(`  ${hasVoteResults ? '✓' : '✗'} Vote results shown`);
    }
  });

  test('should start and complete a Prompt Round', async ({ page }) => {
    console.log('\n=== Prompt Round Test ===\n');

    await registerAndLogin(page);

    // Go to dashboard
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Find and click Start Prompt Round button
    const promptBtn = page.locator('button', { hasText: /start prompt round/i });
    if (await promptBtn.count() === 0) {
      console.log('✗ Prompt Round button not found');
      return;
    }

    console.log('✓ Clicking Start Prompt Round...');
    await promptBtn.click();
    await page.waitForTimeout(2000);

    // Should be on prompt round page
    const currentUrl = page.url();
    console.log(`Current URL: ${currentUrl}`);

    await page.screenshot({ path: 'screenshots/prompt-round-active.png', fullPage: true });

    // Check for prompt round elements
    const hasPromptTitle = await page.locator('h1', { hasText: /prompt round/i }).count() > 0;
    const hasTimer = await page.locator('text=/time|timer|expires/i').count() > 0;
    const hasPromptText = await page.locator('text=/.+/').count() > 3; // Some text content
    const hasInputField = await page.locator('input[type="text"], textarea').count() > 0;

    console.log('\nPrompt Round Elements:');
    console.log(`  ${hasPromptTitle ? '✓' : '✗'} Prompt Round title`);
    console.log(`  ${hasTimer ? '✓' : '✗'} Timer displayed`);
    console.log(`  ${hasPromptText ? '✓' : '✗'} Prompt text displayed`);
    console.log(`  ${hasInputField ? '✓' : '✗'} Input field available`);

    // Try to submit a phrase
    const phraseInput = page.locator('input[type="text"], textarea').first();
    if (await phraseInput.count() > 0) {
      console.log('\n✓ Filling in test phrase...');
      await phraseInput.fill('test answer phrase');
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'screenshots/prompt-round-filled.png', fullPage: true });

      const submitBtn = page.locator('button[type="submit"], button:has-text("Submit")').first();
      if (await submitBtn.count() > 0 && !await submitBtn.isDisabled()) {
        console.log('✓ Clicking Submit button...');
        await submitBtn.click();
        await page.waitForTimeout(3000);

        await page.screenshot({ path: 'screenshots/prompt-round-submitted.png', fullPage: true });

        const finalUrl = page.url();
        console.log(`Final URL: ${finalUrl}`);

        const backToDashboard = finalUrl.includes('/dashboard');
        console.log(`${backToDashboard ? '✓' : '⚠'} Returned to dashboard`);
      }
    }
  });

  test('should start and complete a Vote Round', async ({ page }) => {
    console.log('\n=== Vote Round Test ===\n');

    await registerAndLogin(page);

    // Go to dashboard
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Find and click Start Vote Round button
    const voteBtn = page.locator('button', { hasText: /start vote round/i });
    if (await voteBtn.count() === 0) {
      console.log('✗ Vote Round button not found');
      return;
    }

    const isDisabled = await voteBtn.isDisabled();
    if (isDisabled) {
      console.log('✗ Vote Round button is disabled (no quiz sets available)');
      return;
    }

    console.log('✓ Clicking Start Vote Round...');
    await voteBtn.click();
    await page.waitForTimeout(2000);

    const currentUrl = page.url();
    console.log(`Current URL: ${currentUrl}`);

    await page.screenshot({ path: 'screenshots/vote-round-active.png', fullPage: true });

    // Check for vote round elements
    const hasVoteTitle = await page.locator('h1', { hasText: /vote round/i }).count() > 0;
    const hasTimer = await page.locator('text=/time|timer|expires/i').count() > 0;
    const hasPrompt = await page.locator('text=/prompt/i').count() > 0;
    const hasChoices = await page.locator('button').count() >= 3;

    console.log('\nVote Round Elements:');
    console.log(`  ${hasVoteTitle ? '✓' : '✗'} Vote Round title`);
    console.log(`  ${hasTimer ? '✓' : '✗'} Timer displayed`);
    console.log(`  ${hasPrompt ? '✓' : '✗'} Prompt displayed`);
    console.log(`  ${hasChoices ? '✓' : '✗'} Phrase choices (3+)`);

    // Get all vote choice buttons (exclude nav buttons)
    const choiceButtons = await page.locator('button:not(:has(svg))').all();
    const voteChoices = [];

    for (const btn of choiceButtons) {
      const text = await btn.textContent();
      if (text && text.length > 10 && !text.match(/back|submit|dashboard|time/i)) {
        voteChoices.push(text.trim());
      }
    }

    console.log(`\nFound ${voteChoices.length} vote choices`);
    voteChoices.forEach((choice, idx) => {
      console.log(`  ${idx + 1}. "${choice.substring(0, 50)}..."`);
    });

    // Click the first valid choice
    if (voteChoices.length > 0) {
      console.log('\n✓ Clicking first vote choice...');
      const firstChoiceBtn = page.locator('button', { hasText: voteChoices[0] }).first();
      await firstChoiceBtn.click();
      await page.waitForTimeout(3000);

      await page.screenshot({ path: 'screenshots/vote-round-submitted.png', fullPage: true });

      // Check for result feedback
      const hasResult = await page.locator('text=/correct|incorrect|original phrase/i').count() > 0;
      console.log(`${hasResult ? '✓' : '✗'} Vote result displayed`);
    }
  });
});

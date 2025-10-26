import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';
const TEST_EMAIL = `tutorial_test_${Date.now()}@example.com`;
const TEST_PASSWORD = 'TestPass123!';

test.describe('QuipFlip Tutorial and Round Interaction', () => {
  test('should complete tutorial and start a round', async ({ page }) => {
    console.log('\n=== Tutorial and Round Interaction Test ===\n');

    // Register new user
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Fill registration
    const emailInput = page.locator('input[type="email"]').first();
    const passwordInput = page.locator('input[type="password"]').first();

    await emailInput.fill(TEST_EMAIL);
    await passwordInput.fill(TEST_PASSWORD);

    console.log(`✓ Registering user: ${TEST_EMAIL}`);

    await page.locator('button', { hasText: /create new account/i }).click();
    await page.waitForTimeout(2000);

    // Should see welcome modal
    const welcomeModal = page.locator('text=/welcome to quipflip/i');
    if (await welcomeModal.count() > 0) {
      console.log('✓ Welcome modal appeared');
      await page.screenshot({ path: 'screenshots/tutorial-01-welcome.png', fullPage: true });

      // Check tutorial content
      const tutorialText = await page.locator('text=/create quips|copy phrases|vote/i').allTextContents();
      console.log('\nTutorial Content:');
      tutorialText.forEach(text => console.log(`  - ${text}`));

      // Skip the tutorial to dismiss the welcome modal
      console.log('\n✓ Skipping tutorial from welcome modal...');
      const skipForNowBtn = page.locator('button', { hasText: /skip for now/i });
      if (await skipForNowBtn.count() > 0) {
        await page.screenshot({ path: 'screenshots/tutorial-02-before-skip.png', fullPage: true });
        await skipForNowBtn.click();
        await page.waitForTimeout(1000);
        console.log('✓ Tutorial skipped, welcome modal dismissed');
      } else {
        console.log('⚠ Skip button not found, looking for alternative dismiss method');
      }
    }

    // Now on main dashboard without tutorial overlay
    console.log('\n=== Exploring Round Options ===\n');
    await page.waitForTimeout(500); // Wait for overlay to fully dismiss
    await page.screenshot({ path: 'screenshots/tutorial-03-dashboard.png', fullPage: true });

    // Check available rounds
    const promptRound = page.locator('button', { hasText: /start prompt round/i });
    const copyRound = page.locator('button', { hasText: /start copy round/i });
    const voteRound = page.locator('button', { hasText: /start vote round/i });

    const roundStatus = {
      'Prompt Round': await promptRound.count() > 0,
      'Copy Round': await copyRound.count() > 0,
      'Vote Round': await voteRound.count() > 0,
    };

    console.log('Available Rounds:');
    for (const [round, available] of Object.entries(roundStatus)) {
      console.log(`  ${available ? '✓' : '✗'} ${round}`);
    }

    // Try to start a round (if available)
    if (await voteRound.count() > 0) {
      console.log('\n✓ Attempting to start Vote Round...');
      await voteRound.click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'screenshots/tutorial-04-vote-round.png', fullPage: true });

      // Check if we're on the vote round page
      const currentUrl = page.url();
      console.log(`Current URL: ${currentUrl}`);

      // Look for vote round elements
      const hasVoteOptions = await page.locator('button, input[type="radio"]').count();
      console.log(`Interactive elements found: ${hasVoteOptions}`);
    } else if (await copyRound.count() > 0) {
      console.log('\n✓ Attempting to start Copy Round...');
      await copyRound.click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'screenshots/tutorial-04-copy-round.png', fullPage: true });
    } else if (await promptRound.count() > 0) {
      console.log('\n✓ Attempting to start Prompt Round...');
      await promptRound.click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'screenshots/tutorial-04-prompt-round.png', fullPage: true });
    }

    // Check for timer elements (mentioned in README)
    const hasTimer = await page.locator('text=/time|timer|expires|seconds|minutes/i').count() > 0;
    console.log(`\n${hasTimer ? '✓' : '✗'} Timer element detected`);

    // Check for navigation back to dashboard
    const dashboardLink = await page.locator('a[href*="dashboard"], button:has-text("dashboard")').count() > 0;
    console.log(`${dashboardLink ? '✓' : '✗'} Dashboard navigation available`);
  });

  test('should check phraseset tracking feature', async ({ page }) => {
    console.log('\n=== Phraseset Tracking Test ===\n');

    // Use existing registered user - just go to dashboard
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForTimeout(1000);

    // Look for phraseset tracking link/button
    const phrasesetLink = page.locator('text=/phraseset|tracking|history|my phrases/i');

    if (await phrasesetLink.count() > 0) {
      console.log('✓ Phraseset tracking feature found');
      await phrasesetLink.first().click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: 'screenshots/phraseset-tracking.png', fullPage: true });

      const currentUrl = page.url();
      console.log(`Navigated to: ${currentUrl}`);
    } else {
      console.log('✗ Phraseset tracking not immediately visible (may require navigation)');
    }
  });

  test('should verify balance display and daily bonus', async ({ page }) => {
    console.log('\n=== Balance and Bonus Test ===\n');

    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForTimeout(1000);

    // Look for balance display
    const balanceElements = await page.locator('text=/5000|balance|coins/i').allTextContents();
    console.log('Balance-related text:');
    balanceElements.forEach(text => console.log(`  - ${text}`));

    // Look for daily bonus button
    const bonusBtn = page.locator('button', { hasText: /claim|bonus|daily/i });
    if (await bonusBtn.count() > 0) {
      console.log('\n✓ Daily bonus button found');
      await page.screenshot({ path: 'screenshots/daily-bonus.png', fullPage: true });

      // Try to claim bonus (might be already claimed)
      const bonusText = await bonusBtn.textContent();
      console.log(`Bonus button text: "${bonusText}"`);
    } else {
      console.log('\n✗ Daily bonus button not visible (might be already claimed)');
    }

    // Check for coin icon/imagery
    const hasCoinIcon = await page.locator('[alt*="coin" i], [src*="coin" i], .coin').count() > 0;
    console.log(`${hasCoinIcon ? '✓' : '✗'} Coin icon/imagery detected`);
  });

  test('should navigate through tutorial steps', async ({ page }) => {
    console.log('\n=== Complete Tutorial Navigation Test ===\n');

    // Register new user to see fresh tutorial
    const testEmail = `tutorial_nav_${Date.now()}@example.com`;
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Register
    await page.locator('input[type="email"]').first().fill(testEmail);
    await page.locator('input[type="password"]').first().fill(TEST_PASSWORD);
    await page.locator('button', { hasText: /create new account/i }).click();
    await page.waitForTimeout(2000);

    console.log('✓ User registered, checking for welcome modal...');

    // Welcome modal should appear
    const welcomeModal = page.locator('text=/welcome to quipflip/i');
    if (await welcomeModal.count() > 0) {
      await page.screenshot({ path: 'screenshots/tutorial-flow-01-welcome.png', fullPage: true });
      console.log('✓ Welcome modal visible');

      // Click "Start Tutorial"
      await page.locator('button', { hasText: /start tutorial/i }).click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: 'screenshots/tutorial-flow-02-step1.png', fullPage: true });
      console.log('✓ Tutorial started - Step 1 (Your Dashboard)');

      // Click "Next" to see if there are more steps
      const nextBtn = page.locator('button', { hasText: /^next$/i });
      if (await nextBtn.count() > 0) {
        console.log('✓ "Next" button found, attempting to navigate...');

        // Try clicking next a few times to navigate through tutorial
        for (let i = 0; i < 5; i++) {
          const nextStillExists = await nextBtn.count() > 0;
          if (nextStillExists) {
            await nextBtn.click();
            await page.waitForTimeout(1000);
            await page.screenshot({
              path: `screenshots/tutorial-flow-step-${i + 2}.png`,
              fullPage: true
            });
            console.log(`✓ Navigated to tutorial step ${i + 2}`);
          } else {
            console.log('✓ Tutorial completed, no more "Next" button');
            break;
          }
        }
      }

      // Check if tutorial is now dismissed
      const tutorialStillVisible = await page.locator('text=/your dashboard/i').count() > 0;
      if (!tutorialStillVisible) {
        console.log('✓ Tutorial successfully dismissed after completion');
        await page.screenshot({ path: 'screenshots/tutorial-flow-completed.png', fullPage: true });
      } else {
        // Skip remaining tutorial if still active
        const skipBtn = page.locator('button', { hasText: /skip tutorial/i });
        if (await skipBtn.count() > 0) {
          console.log('✓ Skipping remaining tutorial steps...');
          await skipBtn.click();
          await page.waitForTimeout(1000);
        }
      }

      // Verify we can now interact with dashboard
      const voteBtn = page.locator('button', { hasText: /start vote round/i });
      const isClickable = await voteBtn.count() > 0;
      console.log(`\n${isClickable ? '✓' : '✗'} Round buttons are now clickable`);
    } else {
      console.log('✗ Welcome modal did not appear');
    }
  });
});

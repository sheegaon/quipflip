 I've completed a systematic review of the implementation against the game
  rules. Here's what I found:

  ✅ Correctly Implemented

  Section 4.1-4.2: Round Start & Caption Selection

  - Image selection (backend/services/mm/game_service.py:153-207): ✓
  Correctly filters for active images with sufficient unseen captions
  - Caption selection (backend/services/mm/game_service.py:209-283): ✓
  Implements weighted random selection by quality_score
  - Entry fee (backend/services/mm/game_service.py:86-124): ✓ Properly
  charges and validates balance

  Section 5.2: Riff Detection

  - Cosine similarity (backend/services/mm/caption_service.py:199-254): ✓
  Correctly uses SIM_THRESHOLD = 0.5
  - Riff/original classification: ✓ Properly implemented

  Section 7.1: Quality Score

  - Formula (backend/services/mm/scoring_service.py:19-34): ✓ Correctly
  implements (picks + 1) / (shows + 3)

  Riff Split Ratio

  - 60/40 split (backend/services/mm/scoring_service.py:50-82): ✓ Correct

  ---
  ⚠️ Issues Found

  🔴 CRITICAL ISSUE #1: Timing of shows and seen_captions Updates

  Location: backend/services/mm/game_service.py:140-142

  Rules say (Section 4.4):
  Once they vote:
  - shows is incremented for all 5 captions.
  - picks is incremented for the chosen caption.
  - seen_captions[player, image] is updated with the 5 caption IDs.

  Implementation:
  - shows is incremented in start_vote_round() (BEFORE vote)
  - seen_captions is updated in start_vote_round() (BEFORE vote)
  - Only picks is correctly updated during vote submission

  Impact:
  - Players who start a round but never vote still increment shows counters
  - Captions are marked "seen" even if player doesn't vote
  - This inflates shows counts and can lead to players exhausting captions
  without voting
  - Affects quality score calculations: quality_score = (picks + 1) / (shows 
  + 3)

  ---
  🔴 CRITICAL ISSUE #2: Writer Bonus Multiplier (3×) Missing

  Location: backend/services/mm/vote_service.py:163-275

  Rules say (Section 4.6):
  WRITER_BONUS_MULTIPLIER = 3

  For each winning vote, the system mints an additional writer bonus:
  - writer_bonus_total = 3 * 5 = 15 MC minted
  - Split across authors in same proportions as base payout

  Implementation:
  Only distributes the entry_cost (5 MC). The 3× bonus (15 MC) is completely 
  missing.

  Impact:
  - Caption authors receive only 5 MC instead of 20 MC (5 + 15) per vote
  - This is a massive reduction in earnings (75% less than intended)
  - Fundamentally breaks the game economy

  ---
  🔴 CRITICAL ISSUE #3: Wallet/Vault Split Logic Incorrect

  Location: backend/services/mm/scoring_service.py:85-122

  Rules say (Section 6):
  For each caption, the first 100 MC of gross earnings are credited entirely 
  to player wallets.
  After lifetime_earnings_gross >= 100 MC, future earnings are split:
  - 50% to wallets
  - 50% to vault

  Implementation:
  Uses a per-transaction net profit calculation instead:
  def calculate_wallet_vault_split(gross_payout, entry_cost, vault_pct):
      net_profit = gross_payout - entry_cost
      if net_profit <= 0:
          return gross_payout, 0  # Everything to wallet
      vault_amount = int(net_profit * vault_pct)
      wallet_amount = gross_payout - vault_amount
      return wallet_amount, vault_amount

  Problems:
  1. Uses entry_cost parameter which doesn't apply to caption authors (they
  don't pay entry fees)
  2. Uses vault_pct (30%) instead of the 50% specified in rules
  3. Doesn't track per-caption lifetime thresholds
  4. Doesn't check caption.lifetime_earnings_gross against the 100 MC
  threshold

  Impact:
  - Caption earnings distribution is completely wrong
  - Authors may get more/less vault contribution than intended
  - The 100 MC threshold mechanic doesn't exist

  ---
  🟡 ISSUE #4: "Local Crowd Favorite" Bonus Not Implemented

  Location: N/A (feature missing)

  Rules say (Section 4.7.1):
  Player receives a 3 MC bonus (2 to wallet, 1 to vault) for picking the 
  caption with the highest global vote count among the 5 shown, if:
  - At least 3 of the 5 captions have global_vote_count > 0
  - There is a strictly unique maximum (no tie)

  Implementation:
  This feature is completely missing from vote_service.py.

  ---
  🟡 ISSUE #5: First Vote Bonus Amount Wrong

  Location: backend/services/mm/vote_service.py:297

  Rules say (Section 4.7.2):
  First player to vote on a caption gets 2 MC to wallet

  Implementation:
  bonus_amount = await self.config_service.get_config_value(
      "mm_first_vote_bonus_amount", default=10
  )

  Default is 10 MC instead of 2 MC (5× higher than intended).

  ---
  🟡 ISSUE #6: Caption Submission Cost Wrong

  Location: backend/services/mm/caption_service.py:99-101

  Rules say (Section 5.1):
  CAPTION_SUBMISSION_COST = 100 MC

  Implementation:
  cost = await self.config_service.get_config_value(
      "mm_caption_submission_cost", default=10
  )

  Default is 10 MC instead of 100 MC (10× cheaper than intended).

  Impact:
  - Captions are far too cheap to submit
  - Could lead to spam/low-quality submissions
  - Breaks economic balance

  ---
  🟡 ISSUE #7: Caption Retirement Not Implemented

  Location: N/A (feature missing)

  Rules say (Section 7.2):
  Parameters:
  - CAPTION_MIN_SHOWS_BEFORE_RETIREMENT = 5
  - CAPTION_MIN_QUALITY = 0.05

  When shows >= 5 and (picks == 0 or quality_score < 0.05), mark 
  caption.status = retired

  Implementation:
  No retirement logic found in any service.

  Impact:
  - Low-quality captions continue to be shown indefinitely
  - Database clutter and degraded player experience

  ---
  📊 Summary

  | Category              | Status           |
  |-----------------------|------------------|
  | Critical Issues       | 3                |
  | Medium Issues         | 4                |
  | Correctly Implemented | 5 major features |

  Priority Fixes

  1. Implement writer bonus multiplier (Issue #2) - Most impactful for game
  economy
  2. Fix wallet/vault split logic (Issue #3) - Core economic mechanic
  3. Fix shows/seen timing (Issue #1) - Affects data integrity
  4. Correct config defaults (Issues #5, #6) - Quick fixes with big impact
  5. Implement missing features (Issues #4, #7) - Complete the game rules

⏺ Detailed Code References

  Issue #2: Missing Writer Bonus

  Where to add: backend/services/mm/vote_service.py:163-275 in
  _distribute_caption_payouts()

  Current code:
  gross_payout = entry_cost  # Line 194

  Should be:
  # Base payout from entry cost
  base_payout = entry_cost

  # Writer bonus (3× entry cost, minted by system)
  writer_bonus_multiplier = await self.config_service.get_config_value(
      "mm_writer_bonus_multiplier", default=3
  )
  writer_bonus = entry_cost * writer_bonus_multiplier

  gross_payout = base_payout + writer_bonus

  Issue #3: Wallet/Vault Split

  Where to fix: backend/services/mm/scoring_service.py:85-122

  Should implement:
  def calculate_wallet_vault_split_per_caption(
      caption: MMCaption,
      payout_amount: int,
      threshold: int = 100,
      post_threshold_vault_pct: float = 0.5
  ) -> tuple[int, int]:
      """Calculate wallet/vault split based on caption's lifetime 
  earnings."""
      earned_so_far = caption.lifetime_earnings_gross
      room_to_threshold = max(0, threshold - earned_so_far)

      # Amount that stays below threshold goes 100% to wallet
      wallet_part = min(payout_amount, room_to_threshold)

      # Amount above threshold is split according to post_threshold_vault_pct
      amount_above_threshold = max(0, payout_amount - room_to_threshold)
      wallet_part += int(amount_above_threshold * (1 -
  post_threshold_vault_pct))
      vault_part = payout_amount - wallet_part

      return wallet_part, vault_part

  Would you like me to create detailed fix implementations for any of these
  issues?
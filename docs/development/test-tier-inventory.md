# Test Tier Inventory

> **Owner:** Platform engineering
> **Runtime budgets:** deterministic 5 minutes, SQLite integration 3 minutes,
> smoke 10 minutes, stress 20 minutes, external 10 minutes.

Pytest assigns one tier and one owner marker to every collected test in
`tests/conftest.py`. Marker registration is strict, so misspelled or undeclared
tiers fail collection.

| Match | Tier | Owner |
| --- | --- | --- |
| `tests/sqlite_integration/**` | `sqlite_integration` | Platform unless explicitly marked |
| `tests/test_stress_localhost.py` | `stress`, `localhost` | QuipFlip |
| `tests/test_*localhost*.py` | `smoke`, `localhost` | QuipFlip |
| `tests/test_tl_similarity_debug.py` | `external` | ThinkLink |
| Explicit `external` marker | `external` | Explicit subsystem marker |
| `tests/party/**`, `test_*party*.py` | `deterministic` | Party |
| `test_mm_*.py` | `deterministic` | MemeMint |
| `test_ir_*.py` | `deterministic` | Initial Reaction |
| `test_tl_*.py` | `deterministic` | ThinkLink |
| Shared database/config/cache/tooling files listed in `tests/conftest.py` | `deterministic` | Platform |
| Remaining tests | `deterministic` | QuipFlip |

The deterministic tier blocks socket connections, seeds Python randomness from
`CROWDCRAFT_TEST_SEED`[... ELLIPSIZATION ...]stream-B2EBfvIQ.js                      2.05 kB │ gzip:   1.06 kB
       dist/assets/LoadingSpinner-C8Av0G8X.js                 2.91 kB │ gzip:   1.40 kB
       dist/assets/PromptRoundReview-DD4oxIo2.js              3.38 kB │ gzip:   1.30 kB
       dist/assets/PhrasesetReview-B0asAFtT.js                3.55 kB │ gzip:   1.41 kB
       dist/assets/VoteRoundReview-qF7FZxK_.js                4.27 kB │ gzip:   1.50 kB
       dist/assets/CopyRoundReview-CqUsOlzT.js                4.96 kB │ gzip:   1.77 kB
       dist/assets/OnlineUsers-Cljsvjhm.js                    5.23 kB │ gzip:   1.83 kB
       dist/assets/Completed-B76R3xWA.js                      5.90 kB │ gzip:   1.86 kB
       dist/assets/usePartyNavigation-CZSV3rg6.js             6.11 kB │ gzip:   2.19 kB
       dist/assets/PartyMode-Cdfw_2QC.js                      6.30 kB │ gzip:   2.15 kB
       dist/assets/Leaderboard-CoFert0G.js                    6.73 kB │ gzip:   2.28 kB
       dist/assets/AdminFlagged-BH1-Z0g_.js                   6.99 kB │ gzip:   2.14 kB
       dist/assets/Landing-DOAKmiUD.js                        7.79 kB │ gzip:   2.43 kB
       dist/assets/PartyResults-CMM2nv7W.js                   7.83 kB │ gzip:   2.05 kB
       dist/assets/PromptRound-8lY5AcoW.js                    8.53 kB │ gzip:   3.21 kB
       dist/assets/PartyLobby-Ce2iRdb2.js                     9.72 kB │ gzip:   3.14 kB
       dist/assets/BetaSurveyPage-DdIBPXqX.js                10.41 kB │ gzip:   3.28 kB
       dist/assets/VoteRound-Da_wPgm1.js                     13.13 kB │ gzip:   4.02 kB
       dist/assets/Quests-D1vTd2Jg.js                        13.98 kB │ gzip:   3.87 kB
       dist/assets/Settings-CGGtTeoW.js                      15.18 kB │ gzip:   3.34 kB
       dist/assets/Results-Bv6DyC1a.js                       16.31 kB │ gzip:   4.55 kB
       dist/assets/CopyRound-Cid-yXxR.js                     21.25 kB │ gzip:   6.27 kB
       dist/assets/Tracking-C3cynPWT.js                      21.28 kB │ gzip:   5.52 kB
       dist/assets/Dashboard-DHuJcib1.js                     28.31 kB │ gzip:   8.07 kB
       dist/assets/Admin-1OFvTJKs.js                         37.76 kB │ gzip:   7.60 kB
       dist/assets/Statistics-DEu3NWJu.js                    48.73 kB │ gzip:  13.99 kB
       dist/assets/index-BTGXo43a.js                        348.87 kB │ gzip: 108.27 kB
       dist/assets/Header-BzaELAmF.js                       379.88 kB │ gzip: 111.68 kB
       ✓ built in 1.54s
       
       ==> frontend/mm: npm run lint
       
       > mememint-frontend@1.0.0 lint
       > eslint .
       
       
       ==> frontend/mm: npm run typecheck
       
       > mememint-frontend@1.0.0 typecheck
       > tsc -b
       
       ==> frontend/mm: npm run build
       
       > mememint-frontend@1.0.0 build
       > tsc -b && vite build
       
       vite v5.4.21 building for production...
       transforming...
       Browserslist: browsers data (caniuse-lite) is 6 months old. Please run:
       npx update-browserslist-db@latest
       Why you should do it regularly: https://github.com/browserslist/update-db#readme
       ✓ 882 modules transformed.
       rendering chunks...
       computing gzip size...
       dist/index.html                            1.51 kB │ gzip:   0.68 kB
       dist/assets/Dashboard-DSKdo8oP.css         2.53 kB │ gzip:   0.85 kB
       dist/assets/index-CzHIn1uq.css            46.55 kB │ gzip:   8.54 kB
       dist/assets/CurrencyDisplay-CqFJFD0Z.js    0.37 kB │ gzip:   0.27 kB
       dist/assets/LoadingSpinner-DYcmcCsh.js     2.91 kB │ gzip:   1.40 kB
       dist/assets/OnlineUsers-AoTNZlOp.js        5.01 kB │ gzip:   1.77 kB
       dist/assets/VoteRound-heHKcWcw.js          5.45 kB │ gzip:   2.09 kB
       dist/assets/CircleDetails-Crurt57l.js      5.52 kB │ gzip:   1.65 kB
       dist/assets/Results-FuhxDYEV.js            5.73 kB │ gzip:   1.97 kB
       dist/assets/Circles-CrYlYvOp.js            6.29 kB │ gzip:   1.92 kB
       dist/assets/Leaderboard-Nat-7BBe.js        6.31 kB │ gzip:   2.23 kB
       dist/assets/CaptionRound-BogD-YIi.js       6.94 kB │ gzip:   2.69 kB
       dist/assets/Landing-sPu0adnc.js            7.82 kB │ gzip:   2.46 kB
       dist/assets/GameHistory-BTe22ogO.js        8.78 kB │ gzip:   2.95 kB
       dist/assets/BetaSurveyPage-BiQ_3IcH.js    10.27 kB │ gzip:   3.23 kB
       dist/assets/Dashboard-RJV8MsYH.js         11.87 kB │ gzip:   3.91 kB
       dist/assets/Quests-C25ktRzg.js            13.92 kB │ gzip:   3.84 kB
       dist/assets/Settings-DSvOsbMQ.js          15.12 kB │ gzip:   3.31 kB
       dist/assets/Admin-CKsf9YZY.js             37.93 kB │ gzip:   7.72 kB
       dist/assets/Statistics-C2tKfEhh.js        48.44 kB │ gzip:  13.96 kB
       dist/assets/index-SuoRTU8-.js            716.66 kB │ gzip: 217.26 kB
       
       (!) Some chunks are larger than 500 kB after minification. Consider:
       - Using dynamic import() to code-split the application
       - Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
       - Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
       ✓ built in 1.37s
       
       ==> frontend/ir: npm run lint
       
       > initial-reaction-frontend@1.0.0 lint
       > eslint .
       
       /private/tmp/quipflip-pr.HE1NiW/frontend/ir/src/pages/SetTracking.tsx
         82:6  warning  React Hook useEffect has a missing dependency: 'fetchSetStatus'. Either include it or remove the dependency array  react-hooks/exhaustive-deps
       
       /private/tmp/quipflip-pr.HE1NiW/frontend/ir/src/pages/Voting.tsx
         109:6  warning  React Hook useEffect has a missing dependency: 'fetchSetDetails'. Either include it or remove the dependency array  react-hooks/exhaustive-deps
       
       ✖ 2 problems (0 errors, 2 warnings)
       
       
       ==> frontend/ir: npm run typecheck
       
       > initial-reaction-frontend@1.0.0 typecheck
       > tsc -b
       
       
       ==> frontend/ir: npm run build
       
       > initial-reaction-frontend@1.0.0 build
       > tsc -b && vite build
       
       vite v5.4.21 building for production...
       transforming...
       Browserslist: browsers data (caniuse-lite) is 6 months old. Please run:
       npx update-browserslist-db@latest
       Why you should do it regularly: https://github.com/browserslist/update-db#readme
       ✓ 143 modules transformed.
       rendering chunks...
       computing gzip size...
       dist/index.html                   1.31 kB │ gzip:   0.64 kB
       dist/assets/index-DjdzF6zA.css   34.70 kB │ gzip:   7.10 kB
       dist/assets/index-4YSHGTRd.js   334.99 kB │ gzip: 101.03 kB
       ✓ built in 717ms
       
       ==> frontend/tl: npm run lint
       
       > thinlink-frontend@1.0.0 lint
       > eslint .
       
       
       ==> frontend/tl: npm run typecheck
       
       > thinlink-frontend@1.0.0 typecheck
       > tsc -b
       
       ==> frontend/tl: npm run build
       
       > thinlink-frontend@1.0.0 build
       > tsc -b && vite build
       
       vite v5.4.21 building for production...
       transforming...
       Browserslist: browsers data (caniuse-lite) is 6 months old. Please run:
       npx update-browserslist-db@latest
       Why you should do it regularly: https://github.com/browserslist/update-db#readme
       ✓ 881 modules transformed.
       rendering chunks...
       computing gzip size...
       dist/index.html                                  1.28 kB │ gzip:   0.63 kB
       dist/assets/Dashboard-DSKdo8oP.css               2.53 kB │ gzip:   0.85 kB
       dist/assets/index-Bup4kjQd.css                  50.59 kB │ gzip:   9.06 kB
       dist/assets/CurrencyDisplay-CXSERj29.js          0.37 kB │ gzip:   0.27 kB
       dist/assets/LoadingSpinner-hrbcuS_z.js           2.50 kB │ gzip:   1.21 kB
       dist/assets/OnlineUsers-Bs_GaybM.js              5.01 kB │ gzip:   1.77 kB
       dist/assets/RoundResults-DELaOywr.js             5.25 kB │ gzip:   1.20 kB
       dist/assets/Leaderboard-CCQmrvdp.js              6.65 kB │ gzip:   2.25 kB
       dist/assets/Landing-DfzefTZt.js                  7.78 kB │ gzip:   2.44 kB
       dist/assets/BetaSurveyPage-DBJrx9qP.js          10.29 kB │ gzip:   3.24 kB
       dist/assets/RoundPlay-BC3r_bDM.js               11.36 kB │ gzip:   4.08 kB
       dist/assets/GameHistory-5gc_VAEf.js             11.76 kB │ gzip:   2.63 kB
       dist/assets/Dashboard-5c08ZbmE.js               12.10 kB │ gzip:   3.95 kB
       dist/assets/Quests-wIZpygx5.js                  13.93 kB │ gzip:   3.85 kB
       dist/assets/Settings-Bp3G2smH.js                15.13 kB │ gzip:   3.31 kB
       dist/assets/Admin-Do-mTEZo.js                   37.92 kB │ gzip:   7.72 kB
       dist/assets/Statistics-2j1sDCvU.js              48.68 kB │ gzip:  13.97 kB
       dist/assets/index-Ck64ugKL.js                  347.94 kB │ gzip: 107.53 kB
       dist/assets/HistoricalTrendsChart-Be8ANd5c.js  358.80 kB │ gzip: 106.05 kB
       ✓ built in 1.34s
       
       All frontend lint, typecheck, and build checks passed.
       
       ==> secret scan: /private/tmp/quipflip-pr.HE1NiW/.venv/bin/python scripts/scan_secrets.py
       Secret scan passed.
       
       Verification failures: backend deterministic
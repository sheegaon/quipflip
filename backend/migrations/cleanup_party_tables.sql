-- Cleanup script for partial Party Mode migration
-- Run this if you get "table already exists" errors

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS party_phrasesets;
DROP TABLE IF EXISTS party_rounds;
DROP TABLE IF EXISTS party_participants;
DROP TABLE IF EXISTS party_sessions;

-- Drop any indexes that might still exist
DROP INDEX IF EXISTS idx_party_sessions_code;
DROP INDEX IF EXISTS idx_party_sessions_status;
DROP INDEX IF EXISTS idx_party_sessions_host;
DROP INDEX IF EXISTS idx_party_participants_session;
DROP INDEX IF EXISTS idx_party_participants_player;
DROP INDEX IF EXISTS idx_party_participants_status;
DROP INDEX IF EXISTS idx_party_participants_inactive;
DROP INDEX IF EXISTS idx_party_rounds_session;
DROP INDEX IF EXISTS idx_party_rounds_participant;
DROP INDEX IF EXISTS idx_party_rounds_round;
DROP INDEX IF EXISTS idx_party_phrasesets_session;
DROP INDEX IF EXISTS idx_party_phrasesets_phraseset;

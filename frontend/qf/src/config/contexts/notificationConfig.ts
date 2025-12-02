import { NotificationContextConfig } from '@crowdcraft/contexts/NotificationContext';
import { usePartyMode } from '@/contexts/PartyModeContext';
import { usePartyWebSocket } from '@/hooks/usePartyWebSocket';

export const notificationConfig: NotificationContextConfig = {
  notificationsEnabled: () => true,
  onlineUsersEnabled: () => true,
  partyPageContext: 'other',
  usePartySessionId: () => usePartyMode().state.sessionId ?? '',
  usePartyWebSocket,
};

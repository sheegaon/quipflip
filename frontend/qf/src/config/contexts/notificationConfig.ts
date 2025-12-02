import { NotificationContextConfig } from '@crowdcraft/contexts/NotificationContext';
import { usePartyMode } from '@/contexts/PartyModeContext';
import { usePartyWebSocket } from '@/hooks/usePartyWebSocket';

export const notificationConfig: NotificationContextConfig = {
  notificationsEnabled: () => true,
  onlineUsersEnabled: () => true,
  notificationsWsPath: '/qf/notifications/ws',
  onlineUsersWsPath: '/qf/users/online/ws',
  partyPageContext: 'other',
  usePartySessionId: () => usePartyMode().state.sessionId ?? '',
  usePartyWebSocket,
};

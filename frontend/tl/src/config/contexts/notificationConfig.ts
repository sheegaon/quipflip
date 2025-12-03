import { NotificationContextConfig } from '@crowdcraft/contexts/NotificationContext';

export const notificationConfig: NotificationContextConfig = {
  notificationsEnabled: () => true,
  onlineUsersEnabled: () => true,
  notificationsWsPath: '/notifications/ws',
  onlineUsersWsPath: '/users/online/ws',
};

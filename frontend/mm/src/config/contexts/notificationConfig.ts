import { NotificationContextConfig } from '@crowdcraft/contexts/NotificationContext';

export const notificationConfig: NotificationContextConfig = {
  notificationsEnabled: () => import.meta.env.VITE_ENABLE_NOTIFICATIONS !== 'false',
  onlineUsersEnabled: () => import.meta.env.VITE_ENABLE_ONLINE_USERS !== 'false',
};

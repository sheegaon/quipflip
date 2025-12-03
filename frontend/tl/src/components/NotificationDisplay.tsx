import { FC } from 'react';
import { useNavigate } from 'react-router-dom';
import NotificationDisplayBase from '@crowdcraft/components/NotificationDisplay.tsx';
import { useNotifications } from '../contexts/NotificationContext';

const NotificationDisplay: FC = () => {
  const { notifications, removeNotification } = useNotifications();
  const navigate = useNavigate();

  return (
    <NotificationDisplayBase
      notifications={notifications}
      onDismiss={removeNotification}
      actionLabel="Visit history page"
      onAction={() => navigate('/game/history')}
    />
  );
};

export default NotificationDisplay;

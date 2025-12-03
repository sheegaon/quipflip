import React from 'react';
import NotificationToastBase, {
  type NotificationToastProps as BaseProps,
} from '@crowdcraft/components/NotificationToast.tsx';
import { useNavigate } from 'react-router-dom';

export type NotificationToastProps = Omit<BaseProps, 'onAction' | 'actionLabel'>;

const NotificationToast: React.FC<NotificationToastProps> = (props) => {
  const navigate = useNavigate();

  return (
    <NotificationToastBase
      {...props}
      actionLabel="Visit history page"
      onAction={() => navigate('/game/history')}
    />
  );
};

export default NotificationToast;

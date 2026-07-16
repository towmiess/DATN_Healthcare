import React from 'react';
import { useLocation } from 'react-router-dom';
import FloatingChatWidget from '@/components/chatWidget/FloatingChatWidget';
import DashboardShell from '@/layouts/shared/DashboardShell';

const UserLayout: React.FC = () => {
  const location = useLocation();
  const isFullChatPage = location.pathname.startsWith('/user/chat');

  return (
    <>
      <DashboardShell homePath="/user" />
      {!isFullChatPage && <FloatingChatWidget />}
    </>
  );
};

export default UserLayout;

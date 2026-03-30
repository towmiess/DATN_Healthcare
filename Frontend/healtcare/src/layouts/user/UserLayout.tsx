import React from 'react';
import DashboardShell from '@/layouts/shared/DashboardShell';

const UserLayout: React.FC = () => {
  return <DashboardShell homePath="/user" roleLabel="User" />;
};

export default UserLayout;

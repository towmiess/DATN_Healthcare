import React from 'react';
import DashboardShell from '@/layouts/shared/DashboardShell';

const AdminLayout: React.FC = () => {
  return <DashboardShell homePath="/admin" roleLabel="Admin" />;
};

export default AdminLayout;

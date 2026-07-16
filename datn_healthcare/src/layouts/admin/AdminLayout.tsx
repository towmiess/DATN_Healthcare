import React, { CSSProperties, useEffect, useState } from 'react';
import { Bell, CalendarDays, ChevronDown, Search } from 'lucide-react';
import { Outlet, useNavigate } from 'react-router-dom';
import AdminSidebar from '@/components/admin/AdminSidebar';
import { logout } from '@/services/authservices/logout';
import { clearAuth, getLoginRedirectPath, getRefreshToken } from '@/utils/auth';
import './AdminLayout.scss';

const AdminLayout: React.FC = () => {
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  const handleLogout = async () => {
    const refreshToken = getRefreshToken();

    try {
      if (refreshToken) {
        await logout({ refreshToken });
      }
    } catch {
      // Ignore logout failures and clear local auth state anyway.
    } finally {
      clearAuth();
      navigate(getLoginRedirectPath(), { replace: true });
    }
  };

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, []);

  return (
    <div
      className="admin-layout"
      style={
        {
          '--admin-sidebar-width': collapsed ? '80px' : '260px',
        } as CSSProperties
      }
    >
      <AdminSidebar
        collapsed={collapsed}
        onToggleCollapsed={() => setCollapsed((prev) => !prev)}
        onLogout={handleLogout}
      />

      <div className="admin-layout__main">
        <header className="admin-topbar">
          <label className="admin-topbar__search">
            <Search size={17} />
            <input placeholder="Tìm kiếm đơn hàng, khách hàng..." />
          </label>

          <div className="admin-topbar__actions">
            <button type="button" className="admin-topbar__icon-btn" aria-label="Thông báo">
              <Bell size={18} />
              <span className="admin-topbar__dot" />
            </button>

            <button type="button" className="admin-topbar__icon-btn" aria-label="Lịch">
              <CalendarDays size={18} />
            </button>

            <button type="button" className="admin-topbar__profile">
              <span className="admin-topbar__avatar">MH</span>
              <span className="admin-topbar__profile-text">Tài khoản</span>
              <ChevronDown size={16} />
            </button>
          </div>
        </header>

        <main className="admin-layout__content">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AdminLayout;

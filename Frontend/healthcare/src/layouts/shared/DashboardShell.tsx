import React from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Activity, ChevronDown, Clock, LayoutDashboard, Stethoscope, UserCircle2 } from 'lucide-react';
import brandLogo from '@/assets/logo.png';
import { logout } from '@/services/authservices/logout';
import { clearAuth, getLoginRedirectPath, getRefreshToken } from '@/utils/auth';
import FloatingChatWidget from '@/components/chatWidget/FloatingChatWidget';
import './DashboardShell.scss';

type DashboardShellProps = {
  homePath: string;
};

const DashboardShell: React.FC<DashboardShellProps> = ({ homePath }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const showFloatingChat = homePath === '/user' && location.pathname !== '/user/chat';

  const handleLogout = async () => {
    const refreshToken = getRefreshToken();

    try {
      if (refreshToken) {
        await logout({ refreshToken });
      }
    } catch (error) {
    } finally {
      clearAuth();
      navigate(getLoginRedirectPath(), { replace: true });
    }
  };

  return (
    <div className="login-page dashboard-page">
      <header className="login-nav dashboard-nav">
        <div className="login-nav__content dashboard-nav__content">
          <div className="dashboard-nav__brand">
            <img src={brandLogo} alt="Healthcare Diabetes" className="login-nav__logo" />
          </div>

          <nav className="login-nav__links dashboard-nav__links">
            <NavLink
              end
              to={homePath}
              className={({ isActive }) =>
                `login-nav__item dashboard-nav__item${isActive ? ' dashboard-nav__item--active' : ''}`
              }
            >
              <LayoutDashboard size={16} />
              <span>Tổng quan</span>
            </NavLink>

            <button type="button" className="login-nav__item dashboard-nav__button">
              <Activity size={16} />
              <span>Ghi nhận</span>
            </button>

            <button type="button" className="login-nav__item dashboard-nav__button">
              <Clock size={16} />
              <span>Lịch sử</span>
            </button>

            {homePath === '/user' && (
              <NavLink
                to="/user/chat"
                className={({ isActive }) =>
                  `login-nav__item dashboard-nav__item${isActive ? ' dashboard-nav__item--active' : ''}`
                }
              >
                <Stethoscope  size={16} />
                <span>Trợ lý AI</span>
              </NavLink>
            )}
          </nav>

          <div className="dashboard-profile">
            <button
              type="button"
              className="dashboard-profile__trigger"
              aria-haspopup="menu"
              aria-expanded="false"
            >
              <UserCircle2 size={20} />
              <span>Tài khoản</span>
              <ChevronDown size={16} />
            </button>

            <div className="dashboard-profile__menu" role="menu" aria-label="Tài khoản">
              <NavLink to="/change-password" className="dashboard-profile__item" role="menuitem">
                Đổi mật khẩu
              </NavLink>
              <button
                type="button"
                className="dashboard-profile__item dashboard-profile__item--danger"
                role="menuitem"
                onClick={handleLogout}
              >
                Đăng xuất
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="dashboard-main">
        <div className="dashboard-main__content">
          <Outlet />
        </div>
      </main>

      {showFloatingChat && <FloatingChatWidget />}
    </div>
  );
};

export default DashboardShell;

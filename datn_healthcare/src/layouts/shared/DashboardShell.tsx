import React from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity,
  ChevronDown,
  Clock,
  FileText,
  LayoutDashboard,
  Stethoscope,
  UtensilsCrossed,
  UserCircle2,
} from 'lucide-react';
import brandLogo from '@/assets/logo.png';
import { logout } from '@/services/authservices/logout';
import { clearAuth, getLoginRedirectPath, getRefreshToken } from '@/utils/auth';
import './DashboardShell.scss';

type DashboardShellProps = {
  homePath: string;
};

const DashboardShell: React.FC<DashboardShellProps> = ({ homePath }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const isChatPage = location.pathname.startsWith('/user/chat');

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

  return (
    <div className={`login-page dashboard-page${isChatPage ? ' dashboard-page--chat' : ''}`}>
      <header className="app-header dashboard-header">
        <div className="dashboard-nav__brand">
          <img src={brandLogo} alt="Healthcare Diabetes" className="login-nav__logo" />
        </div>

        <nav className="main-nav dashboard-nav__links" aria-label="Điều hướng chính">
          <NavLink
            end
            to={homePath}
            className={({ isActive }) =>
              `dashboard-nav__item${isActive ? ' dashboard-nav__item--active' : ''}`
            }
          >
            <LayoutDashboard size={16} />
            <span>Tổng quan</span>
          </NavLink>

          <NavLink
            to="/user/recommendations"
            className={({ isActive }) =>
              `dashboard-nav__item${isActive ? ' dashboard-nav__item--active' : ''}`
            }
          >
            <UtensilsCrossed size={16} />
            <span>Món ăn</span>
          </NavLink>

          <NavLink
            to="/user/chat"
            className={({ isActive }) =>
              `dashboard-nav__item${isActive ? ' dashboard-nav__item--active' : ''}`
            }
          >
            <Stethoscope size={16} />
            <span>Trợ lý AI</span>
          </NavLink>

          <NavLink
            to="/user/diagnosis"
            className={({ isActive }) =>
              `dashboard-nav__item${isActive ? ' dashboard-nav__item--active' : ''}`
            }
          >
            <Activity size={16} />
            <span>Chẩn đoán</span>
          </NavLink>

          <NavLink
            to="/user/history"
            className={({ isActive }) =>
              `dashboard-nav__item${isActive ? ' dashboard-nav__item--active' : ''}`
            }
          >
            <Clock size={16} />
            <span>Lịch sử</span>
          </NavLink>
          <NavLink
            to="/user/reports"
            className={({ isActive }) =>
              `dashboard-nav__item${isActive ? ' dashboard-nav__item--active' : ''}`
            }
          >
            <FileText size={16} />
            <span>Báo cáo</span>
          </NavLink>
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
      </header>

      <main className="dashboard-main">
        <div className="dashboard-main__content">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default DashboardShell;

import React, { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  LogOut,
  Leaf,
  UtensilsCrossed,
  ShoppingCart,
  Sparkles,
  UserCog,
  Users,
} from 'lucide-react';
import { ADMIN_SECTIONS, type AdminSection } from '@/layouts/admin/adminTypes';
import './AdminSidebar.scss';

type AdminSidebarProps = {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onLogout: () => void;
};

const iconMap: Record<AdminSection, React.ReactNode> = {
  dashboard: <LayoutDashboard size={18} />,
  orders: <ShoppingCart size={18} />,
  customers: <Users size={18} />,
  reports: <Leaf size={18} />,
  products: <UtensilsCrossed size={18} />,
  settings: <UserCog size={18} />,
};

const AdminSidebar: React.FC<AdminSidebarProps> = ({ collapsed, onToggleCollapsed, onLogout }) => {
  const location = useLocation();
  const asideRef = useRef<HTMLElement | null>(null);
  const navRef = useRef<HTMLElement | null>(null);
  const itemRefs = useRef<Partial<Record<AdminSection, HTMLAnchorElement | null>>>({});
  const [indicatorStyle, setIndicatorStyle] = useState({
    transform: 'translateY(0px)',
    height: 0,
    opacity: 0,
  });

  const navItems = useMemo(
    () => ADMIN_SECTIONS.map((item) => ({ ...item, icon: iconMap[item.value] })),
    []
  );

  const activeItem = useMemo(() => {
    const exact = navItems.find((item) => location.pathname === item.path || location.pathname === `${item.path}/`);
    if (exact) return exact;
    return navItems.find((item) => item.path !== '/admin' && location.pathname.startsWith(item.path)) ?? navItems[0];
  }, [location.pathname, navItems]);

  useLayoutEffect(() => {
    const navEl = navRef.current;

    const update = () => {
      const activeEl = itemRefs.current[activeItem.value];
      if (!navEl || !activeEl) return;
      const navRect = navEl.getBoundingClientRect();
      const activeRect = activeEl.getBoundingClientRect();
      setIndicatorStyle({
        transform: `translateY(${activeRect.top - navRect.top + navEl.scrollTop}px)`,
        height: collapsed ? 40 : activeRect.height,
        opacity: 1,
      });
    };

    update();

    // ResizeObserver bắt các thay đổi kích thước "giữa chừng" trong lúc
    // sidebar đang co giãn (transition width 0.28s) -> kích thước đo được
    // lúc đó có thể chưa phải kích thước cuối cùng, gây lệch/phình indicator.
    const resizeObserver = new ResizeObserver(update);
    resizeObserver.observe(navEl!);
    Object.values(itemRefs.current).forEach((el) => el && resizeObserver.observe(el));
    window.addEventListener('resize', update);

    // Fix: đo lại chắc chắn MỘT LẦN NỮA khi animation width của sidebar
    // (thu gọn/mở rộng) đã kết thúc hẳn, để chốt đúng kích thước cuối cùng.
    const sidebarEl = asideRef.current ?? navEl?.closest('.admin-sidebar') ?? null;
    const handleTransitionEnd = (e: TransitionEvent) => {
      if (e.propertyName === 'width' || e.propertyName === 'min-width') {
        update();
      }
    };
    sidebarEl?.addEventListener('transitionend', handleTransitionEnd as EventListener);

    // Fallback an toàn: nếu vì lý do gì đó transitionend không bắn
    // (ví dụ prefers-reduced-motion tắt transition), vẫn đo lại sau
    // đúng thời lượng transition khai báo trong SCSS (0.28s).
    const fallbackTimeout = setTimeout(update, 300);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', update);
      sidebarEl?.removeEventListener('transitionend', handleTransitionEnd as EventListener);
      clearTimeout(fallbackTimeout);
    };
  }, [activeItem.value, collapsed]);

  return (
    <aside ref={asideRef} className={`admin-sidebar${collapsed ? ' admin-sidebar--collapsed' : ''}`}>
      <button
        type="button"
        className="admin-sidebar__toggle"
        onClick={onToggleCollapsed}
        aria-label={collapsed ? 'Mở rộng sidebar' : 'Thu gọn sidebar'}
      >
        {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>

      <div className="admin-sidebar__brand">
        <div className="admin-sidebar__brand-mark" aria-hidden="true">
          <Sparkles size={18} />
        </div>
        <div className="admin-sidebar__brand-text">
          <div className="admin-sidebar__brand-top">Nova Admin</div>
          <div className="admin-sidebar__brand-sub">Bảng điều khiển</div>
        </div>
      </div>

      <nav className="admin-sidebar__nav" aria-label="Điều hướng quản trị" ref={navRef}>
        <div className="admin-sidebar__indicator" style={indicatorStyle} />

        <div className="admin-sidebar__group-label">TỔNG QUAN</div>
        {navItems
          .filter((item) => item.section === 'overview')
          .map((item) => (
            <NavLink
              key={item.value}
              to={item.path}
              end={item.path === '/admin'}
              className={({ isActive }) =>
                `admin-sidebar__item${isActive ? ' admin-sidebar__item--active' : ''}`
              }
              ref={(node) => {
                itemRefs.current[item.value] = node;
              }}
            >
              <span className="admin-sidebar__item-icon">{item.icon}</span>
              <span className="admin-sidebar__item-label">{item.label}</span>
            </NavLink>
          ))}

        <div className="admin-sidebar__group-label">PHÂN TÍCH</div>
        {navItems
          .filter((item) => item.section === 'analysis')
          .map((item) => (
            <NavLink
              key={item.value}
              to={item.path}
              className={({ isActive }) =>
                `admin-sidebar__item${isActive ? ' admin-sidebar__item--active' : ''}`
              }
              ref={(node) => {
                itemRefs.current[item.value] = node;
              }}
            >
              <span className="admin-sidebar__item-icon">{item.icon}</span>
              <span className="admin-sidebar__item-label">{item.label}</span>
            </NavLink>
          ))}

        <div className="admin-sidebar__group-label">HỆ THỐNG</div>
        {navItems
          .filter((item) => item.section === 'system')
          .map((item) => (
            <NavLink
              key={item.value}
              to={item.path}
              className={({ isActive }) =>
                `admin-sidebar__item${isActive ? ' admin-sidebar__item--active' : ''}`
              }
              ref={(node) => {
                itemRefs.current[item.value] = node;
              }}
            >
              <span className="admin-sidebar__item-icon">{item.icon}</span>
              <span className="admin-sidebar__item-label">{item.label}</span>
            </NavLink>
          ))}

        <button type="button" className="admin-sidebar__item admin-sidebar__item--logout" onClick={onLogout}>
          <span className="admin-sidebar__item-icon">
            <LogOut size={18} />
          </span>
          <span className="admin-sidebar__item-label">Đăng xuất</span>
        </button>
      </nav>

      <div className="admin-sidebar__footer">
        <div className="admin-sidebar__avatar">MH</div>
        <div className="admin-sidebar__profile">
          <div className="admin-sidebar__profile-name">Minh Hoàng</div>
          <div className="admin-sidebar__profile-role">Quản trị viên</div>
        </div>
      </div>
    </aside>
  );
};

export default AdminSidebar;

import React from 'react';
import {
  ArrowDownRight,
  ArrowUpRight,
  CircleDollarSign,
  Clock3,
  Package2,
  ShoppingCart,
  Sparkles,
  TrendingUp,
  Users,
} from 'lucide-react';
import type { AdminSection } from '@/layouts/admin/adminTypes';

type AdminHomeProps = {
  section: AdminSection;
  sectionTitle: string;
};

const stats = [
  { label: 'Doanh thu', value: '482.6M', delta: '+12.4%', direction: 'up' as const, tone: 'green' },
  { label: 'Đơn hàng', value: '2,148', delta: '+8.1%', direction: 'up' as const, tone: 'blue' },
  { label: 'Khách hàng mới', value: '356', delta: '-2.3%', direction: 'down' as const, tone: 'amber' },
  { label: 'Tỷ lệ chuyển đổi', value: '4.62%', delta: '+0.8%', direction: 'up' as const, tone: 'rose' },
];

const bestSellers = [
  { name: 'Áo khoác Denim Basic', value: '86.2M', pct: 92 },
  { name: 'Giày Sneaker Urban', value: '74.5M', pct: 80 },
  { name: 'Túi xách Mini Canvas', value: '58.1M', pct: 63 },
  { name: 'Đồng hồ Classic Steel', value: '41.9M', pct: 45 },
];

const orders = [
  { name: 'Nguyễn Thị Lan', code: '#DH-4821', item: 'Áo khoác Denim', money: '1.240.000', status: 'done' as const },
  { name: 'Trần Văn Minh', code: '#DH-4820', item: 'Giày Sneaker Urban', money: '890.000', status: 'pending' as const },
  { name: 'Lê Hoàng Anh', code: '#DH-4819', item: 'Túi xách Mini', money: '650.000', status: 'done' as const },
  { name: 'Phạm Thu Hà', code: '#DH-4818', item: 'Đồng hồ Classic', money: '2.150.000', status: 'cancel' as const },
];

const customers = [
  { name: 'Nguyễn Thị Lan', tag: 'VIP', spent: '18.4M', color: '#00C9A7' },
  { name: 'Trần Văn Minh', tag: 'Thường xuyên', spent: '9.2M', color: '#4F5AFF' },
  { name: 'Lê Hoàng Anh', tag: 'Mới', spent: '1.1M', color: '#FF6B6B' },
  { name: 'Phạm Thu Hà', tag: 'VIP', spent: '22.7M', color: '#FFB74D' },
];

const quickCards = [
  {
    title: 'Gần đây',
    value: '2 món ăn hôm nay',
    accent: 'mango',
    icon: <Clock3 size={18} />,
  },
  {
    title: 'Ảnh bữa ăn',
    value: 'Đã lưu 2 ảnh gần nhất',
    accent: 'blue',
    icon: <CircleDollarSign size={18} />,
  },
  {
    title: 'Tổng quan nhanh',
    value: '482.6M doanh thu tháng này',
    accent: 'green',
    icon: <TrendingUp size={18} />,
  },
];

const AdminHome: React.FC<AdminHomeProps> = ({ section, sectionTitle }) => {
  if (section === 'orders') {
    return (
      <section className="admin-page">
        <div className="admin-page__head">
          <div>
            <div className="admin-page__eyebrow">
              <Sparkles size={14} />
              Đơn hàng
            </div>
            <h1 className="admin-page__title">{sectionTitle}</h1>
            <p className="admin-page__sub">Quản lý và theo dõi toàn bộ đơn hàng của hệ thống.</p>
          </div>
        </div>

        <div className="admin-panel">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Khách hàng</th>
                <th>Mã đơn</th>
                <th>Sản phẩm</th>
                <th>Số tiền</th>
                <th>Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.code}>
                  <td>{order.name}</td>
                  <td className="admin-mono">{order.code}</td>
                  <td>{order.item}</td>
                  <td className="admin-mono">{order.money}</td>
                  <td>
                    <span className={`admin-status admin-status--${order.status}`}>
                      {order.status === 'done' ? 'Hoàn tất' : order.status === 'pending' ? 'Đang xử lý' : 'Đã hủy'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    );
  }

  if (section === 'customers') {
    return (
      <section className="admin-page">
        <div className="admin-page__head">
          <div>
            <div className="admin-page__eyebrow">
              <Sparkles size={14} />
              Khách hàng
            </div>
            <h1 className="admin-page__title">{sectionTitle}</h1>
            <p className="admin-page__sub">356 khách hàng mới trong tháng này.</p>
          </div>
        </div>

        <div className="admin-grid admin-grid--stats">
          {customers.map((customer) => (
            <article className="admin-stat-card" key={customer.name}>
              <div className="admin-stat-card__avatar" style={{ background: customer.color }}>
                {customer.name
                  .split(' ')
                  .slice(-2)
                  .map((word) => word[0])
                  .join('')}
              </div>
              <div className="admin-tag">{customer.tag}</div>
              <div className="admin-stat-card__name">{customer.name}</div>
              <div className="admin-stat-card__value">{customer.spent} đ</div>
            </article>
          ))}
        </div>
      </section>
    );
  }

  if (section === 'reports') {
    return (
      <section className="admin-page">
        <div className="admin-page__head">
          <div>
            <div className="admin-page__eyebrow">
              <Sparkles size={14} />
              Báo cáo
            </div>
            <h1 className="admin-page__title">{sectionTitle}</h1>
            <p className="admin-page__sub">Phân tích lưu lượng và hiệu suất bán hàng.</p>
          </div>
        </div>

        <div className="admin-grid admin-grid--two">
          <div className="admin-panel">
            <div className="admin-panel__head">
              <h3>Lưu lượng truy cập theo kênh</h3>
              <span className="admin-chip">12 tháng qua</span>
            </div>
            <div className="admin-bar-chart">
              {[
                { label: 'Tìm kiếm', value: 420, color: '#00C9A7' },
                { label: 'Mạng xã hội', value: 310, color: '#4F5AFF' },
                { label: 'Email', value: 180, color: '#FFB74D' },
                { label: 'Giới thiệu', value: 260, color: '#FF6B6B' },
                { label: 'Trực tiếp', value: 150, color: '#8C6BFF' },
              ].map((item) => (
                <div key={item.label} className="admin-bar-chart__row">
                  <span>{item.label}</span>
                  <div className="admin-bar-chart__track">
                    <span className="admin-bar-chart__fill" style={{ width: `${item.value / 4}%`, background: item.color }} />
                  </div>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>
          </div>

          <div className="admin-panel">
            <div className="admin-panel__head">
              <h3>Xu hướng</h3>
            </div>
            <div className="admin-trend-card">
              <TrendingUp size={26} />
              <div>
                <strong>Doanh thu đang tăng ổn định</strong>
                <p>Biểu đồ mô phỏng theo dữ liệu dashboard mẫu.</p>
              </div>
            </div>
          </div>
        </div>
      </section>
    );
  }

  if (section === 'products') {
    return (
      <section className="admin-page">
        <div className="admin-page__head">
          <div>
            <div className="admin-page__eyebrow">
              <Sparkles size={14} />
              Sản phẩm
            </div>
            <h1 className="admin-page__title">{sectionTitle}</h1>
            <p className="admin-page__sub">Danh mục và tồn kho sản phẩm.</p>
          </div>
        </div>

        <div className="admin-empty">
          <Package2 size={48} />
          <strong>Chưa có bộ lọc nào được áp dụng</strong>
          <span>Thêm sản phẩm đầu tiên để bắt đầu quản lý kho hàng.</span>
        </div>
      </section>
    );
  }

  if (section === 'settings') {
    return (
      <section className="admin-page">
        <div className="admin-page__head">
          <div>
            <div className="admin-page__eyebrow">
              <Sparkles size={14} />
              Hệ thống
            </div>
            <h1 className="admin-page__title">{sectionTitle}</h1>
            <p className="admin-page__sub">Cập nhật thông tin tài khoản và tùy chọn hệ thống.</p>
          </div>
        </div>

        <div className="admin-panel">
          <div className="admin-settings">
            <label>
              <span>Họ và tên</span>
              <input defaultValue="Quản trị viên" />
            </label>
            <label>
              <span>Email</span>
              <input defaultValue="admin@healthcare.vn" />
            </label>
            <label>
              <span>Số điện thoại</span>
              <input defaultValue="+84 900 000 000" />
            </label>
            <label>
              <span>Vai trò</span>
              <input defaultValue="ADMIN" disabled />
            </label>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="admin-page">
      <div className="admin-hero-grid">
        <div className="admin-hero card">
          <div className="admin-page__eyebrow">
            <Sparkles size={14} />
            LỊCH SỬ BÁN HÀNG
          </div>
          <h1 className="admin-hero__title">Chào buổi sáng, Minh 👋</h1>
          <p className="admin-hero__sub">
            Đây là tình hình của cửa hàng của bạn hôm nay, 05/07/2026.
          </p>
          <button type="button" className="admin-hero__cta">
            <Sparkles size={16} />
            Tạo đơn hàng
          </button>
        </div>

        <div className="admin-side-stack">
          {quickCards.map((item) => (
            <div key={item.title} className={`admin-mini-card admin-mini-card--${item.accent}`}>
              <span className="admin-mini-card__icon">{item.icon}</span>
              <div>
                <h3>{item.title}</h3>
                <p>{item.value}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="admin-grid admin-grid--stats">
        {stats.map((stat) => (
          <article className="admin-stat" key={stat.label}>
            <div className="admin-stat__top">
              <div>
                <div className="admin-stat__label">{stat.label}</div>
                <div className="admin-stat__value">{stat.value}</div>
              </div>
              <div className={`admin-stat__icon admin-stat__icon--${stat.tone}`}>
                {stat.label === 'Doanh thu' ? (
                  <CircleDollarSign size={20} />
                ) : stat.label === 'Đơn hàng' ? (
                  <ShoppingCart size={20} />
                ) : stat.label === 'Khách hàng mới' ? (
                  <Users size={20} />
                ) : (
                  <TrendingUp size={20} />
                )}
              </div>
            </div>
            <div className={`admin-stat__delta admin-stat__delta--${stat.direction}`}>
              {stat.direction === 'up' ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
              {stat.delta} so với tuần trước
            </div>
          </article>
        ))}
      </div>

      <div className="admin-grid admin-grid--two">
        <div className="admin-panel">
          <div className="admin-panel__head">
            <h3>Doanh thu theo tháng</h3>
            <span className="admin-chip">12 tháng qua</span>
          </div>

          <div className="admin-sparkline" aria-hidden="true">
            {[42, 48, 46, 56, 60, 58, 68, 72, 70, 79, 86, 96].map((value, index) => (
              <span key={index} style={{ height: `${value}%` }} />
            ))}
          </div>
        </div>

        <div className="admin-panel">
          <div className="admin-panel__head">
            <h3>Sản phẩm bán chạy</h3>
            <span className="admin-chip">Tuần này</span>
          </div>

          <div className="admin-rank">
            {bestSellers.map((item, index) => (
              <div className="admin-rank__row" key={item.name}>
                <div className="admin-rank__num">{index + 1}</div>
                <div className="admin-rank__info">
                  <div className="admin-rank__name">{item.name}</div>
                  <div className="admin-rank__track">
                    <span style={{ width: `${item.pct}%` }} />
                  </div>
                </div>
                <strong className="admin-mono">{item.value}</strong>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="admin-panel">
        <div className="admin-panel__head">
          <h3>Đơn hàng gần đây</h3>
          <span className="admin-chip">Xem tất cả</span>
        </div>

        <table className="admin-table">
          <thead>
            <tr>
              <th>Khách hàng</th>
              <th>Mã đơn</th>
              <th>Sản phẩm</th>
              <th>Số tiền</th>
              <th>Trạng thái</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.code}>
                <td>
                  <div className="admin-person">
                    <span className="admin-person__avatar">
                      {order.name
                        .split(' ')
                        .slice(-2)
                        .map((word) => word[0])
                        .join('')}
                    </span>
                    {order.name}
                  </div>
                </td>
                <td className="admin-mono">{order.code}</td>
                <td>{order.item}</td>
                <td className="admin-mono">{order.money}</td>
                <td>
                  <span className={`admin-status admin-status--${order.status}`}>
                    {order.status === 'done' ? 'Hoàn tất' : order.status === 'pending' ? 'Đang xử lý' : 'Đã hủy'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};

export default AdminHome;

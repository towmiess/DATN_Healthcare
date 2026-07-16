import React from "react";
import { Link } from "react-router-dom";
import { BadgeCheck, CalendarDays, Flame, Sparkles, UtensilsCrossed } from "lucide-react";
import "./UserHome.scss";

const UserHome: React.FC = () => {
  return (
    <section className="user-home">
      <header className="user-home__hero">
        <div className="user-home__copy">
          <p className="user-home__eyebrow">
            <BadgeCheck size={16} />
            Dashboard tổng quan
          </p>
          <h1 className="user-home__title">Chào mừng bạn quay lại</h1>
          <p className="user-home__description">
            Đây là trang tổng quan sau khi đăng nhập. Từ thanh header, bạn có thể mở trang gợi ý món ăn để
            xem danh sách món phù hợp từ nutrition-service.
          </p>

          <div className="user-home__actions">
            <Link to="/user/recommendations" className="user-home__cta">
              <Sparkles size={16} />
              Mở gợi ý món ăn
            </Link>
          </div>
        </div>

        <div className="user-home__stats">
          <article className="user-home-card">
            <Flame size={18} />
            <span>Quản lý dinh dưỡng</span>
          </article>
          <article className="user-home-card">
            <CalendarDays size={18} />
            <span>Theo dõi bữa ăn</span>
          </article>
          <article className="user-home-card">
            <UtensilsCrossed size={18} />
            <span>Khám phá món phù hợp</span>
          </article>
        </div>
      </header>
    </section>
  );
};

export default UserHome;

import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useForm, type SubmitHandler } from 'react-hook-form';
import { Activity, Clock, Heart, Plus, Shield } from 'lucide-react';
import brandLogo from '@/assets/logo.png';
import iconGreen from '@/assets/icon-green.svg';
import loginIcon from '@/assets/icon-login.png';
import './CheckEmail.scss';
import { checkmail } from '@/services/authservices/checkmail';
import axios from 'axios';
import { BaseResponse } from '@/types/BaseType';
import { toast } from 'sonner';

type CheckEmailFormValues = {
  email: string;
};

const CheckEmail: React.FC = () => {
  const navigate = useNavigate();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CheckEmailFormValues>({
    defaultValues: {
      email: '',
    },
    mode: 'onSubmit',
  });

  const onSubmit: SubmitHandler<CheckEmailFormValues> = async (data) => {
    try {
      const response = await checkmail({ email: data.email.trim() });
      sessionStorage.setItem('resetPasswordUserId', String(response.data.userId));
      toast.success("Đã gửi OTP đến email của bạn.");
      navigate('/verify-otp');
    } catch (error) {
      const errorResponse: BaseResponse<null> | null = axios.isAxiosError<BaseResponse<null>>(error)
        ? error.response?.data ?? null
        : null;

      toast.error("Email không tồn tại.");
      console.error('Check email error:', errorResponse);
    }
  };

  return (
    <div className="login-page check-email-page">
      <header className="login-nav">
        <div className="login-nav__content">
          <img src={brandLogo} alt="Healthcare Diabetes" className="login-nav__logo" />
          <nav className="login-nav__links">
            <NavLink className="login-nav__item" to="#">
              <img src={iconGreen} alt="" aria-hidden="true" className="login-nav__item-icon" />
              <span>Tổng quan</span>
            </NavLink>
            <NavLink className="login-nav__item" to="#">
              <Plus size={16} />
              <span>Ghi nhận</span>
            </NavLink>
            <NavLink className="login-nav__item" to="#">
              <Clock size={16} />
              <span>Lịch sử</span>
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="login-main">
        <div className="login-card">
          <div className="login-card__header">
            <div className="login-card__logo">
              <img src={loginIcon} alt="" aria-hidden="true" className="login-card__logo-img" />
            </div>
            <h1 className="login-card__title">Check Email</h1>
            <p className="login-card__subtitle">Nhập email để nhận mã OTP đặt lại mật khẩu</p>
          </div>

          <form className="login-form" onSubmit={handleSubmit(onSubmit)} noValidate autoComplete="off">
            <div className="login-form__field">
              <label htmlFor="email" className="login-form__label">
                Email
              </label>
              <input
                id="email"
                type="email"
                placeholder="email@example.com"
                autoComplete="email"
                className={`login-form__input ${errors.email ? 'login-form__input--error' : ''}`}
                aria-invalid={errors.email ? 'true' : 'false'}
                aria-describedby={errors.email ? 'email-error' : undefined}
                {...register('email', {
                  required: 'Vui lòng nhập email.',
                  pattern: {
                    value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                    message: 'Email không hợp lệ.',
                  },
                })}
              />
              {errors.email && (
                <p id="email-error" className="login-form__error" role="alert">
                  {errors.email.message}
                </p>
              )}
            </div>

            <button type="submit" className="login-form__submit" disabled={isSubmitting}>
              {isSubmitting ? 'Đang xử lý...' : 'Gửi OTP'}
            </button>
          </form>

          <div className="login-card__footer">
            <span>Đã nhớ mật khẩu? </span>
            <NavLink to="/login" className="login-card__footer-link">
              Đăng nhập
            </NavLink>
          </div>

          <div className="login-features">
            <div className="login-features__item">
              <span className="login-features__icon login-features__icon--blue">
                <Activity size={18} />
              </span>
              <p className="login-features__text">Theo dõi sức khỏe</p>
            </div>
            <div className="login-features__item">
              <span className="login-features__icon login-features__icon--green">
                <Heart size={18} />
              </span>
              <p className="login-features__text">Chăm sóc tận tâm</p>
            </div>
            <div className="login-features__item">
              <span className="login-features__icon login-features__icon--purple">
                <Shield size={18} />
              </span>
              <p className="login-features__text">Bảo mật cao</p>
            </div>
          </div>
        </div>
      </main>

      <footer className="login-footnote">
         Lưu ý: Đây là công cụ hỗ trợ theo dõi. Vui lòng tham khảo ý kiến bác sĩ cho chẩn đoán và điều trị.
      </footer>
    </div>
  );
};

export default CheckEmail;

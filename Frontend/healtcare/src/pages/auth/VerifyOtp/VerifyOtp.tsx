import React from 'react';
import { NavLink } from 'react-router-dom';
import { useForm, type SubmitHandler } from 'react-hook-form';
import { Activity, Clock, Heart, Plus, Shield } from 'lucide-react';
import brandLogo from '@/assets/logo.png';
import iconGreen from '@/assets/icon-green.svg';
import loginIcon from '@/assets/icon-login.png';
import './VerifyOtp.scss';

type VerifyOtpFormValues = {
  otp: string;
};

const VerifyOtp: React.FC = () => {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<VerifyOtpFormValues>({
    defaultValues: {
      otp: '',
    },
    mode: 'onSubmit',
  });

  const onSubmit: SubmitHandler<VerifyOtpFormValues> = (data) => {
    console.log('Verify OTP data:', data);
  };

  return (
    <div className="login-page verify-otp-page">
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
            <h1 className="login-card__title">Verify OTP</h1>
            <p className="login-card__subtitle">Nhập mã OTP đã được gửi về email của bạn</p>
          </div>

          <form className="login-form" onSubmit={handleSubmit(onSubmit)} noValidate autoComplete="off">
            <div className="login-form__field">
              <label htmlFor="otp" className="login-form__label">
                Nhập OTP
              </label>
              <input
                id="otp"
                type="text"
                inputMode="numeric"
                placeholder="Nhập mã OTP"
                autoComplete="one-time-code"
                className={`login-form__input ${errors.otp ? 'login-form__input--error' : ''}`}
                aria-invalid={errors.otp ? 'true' : 'false'}
                aria-describedby={errors.otp ? 'otp-error' : undefined}
                {...register('otp', {
                  required: 'Vui lòng nhập OTP.',
                  pattern: {
                    value: /^\d{4,6}$/,
                    message: 'OTP phải gồm 4-6 chữ số.',
                  },
                })}
              />
              {errors.otp && (
                <p id="otp-error" className="login-form__error" role="alert">
                  {errors.otp.message}
                </p>
              )}
            </div>

            <button type="submit" className="login-form__submit" disabled={isSubmitting}>
              {isSubmitting ? 'Đang xử lý...' : 'Gửi OTP'}
            </button>
          </form>

          <div className="login-card__footer">
            <span>Chưa nhận được OTP? </span>
            <NavLink to="/check-email" className="login-card__footer-link">
              Gửi lại
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

export default VerifyOtp;

import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useForm, type SubmitHandler } from 'react-hook-form';
import { Activity, Clock, Eye, EyeOff, Heart, Plus, Shield } from 'lucide-react';
import brandLogo from '@/assets/logo.png';
import iconGreen from '@/assets/icon-green.svg';
import loginIcon from '@/assets/icon-login.png';
import './SignUp.scss';

type SignUpFormValues = {
  fullName: string;
  phoneNumber: string;
  email: string;
  password: string;
  confirmPassword: string;
  agree: boolean;
};

const SignUp: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<SignUpFormValues>({
    defaultValues: {
      fullName: '',
      phoneNumber: '',
      email: '',
      password: '',
      confirmPassword: '',
      agree: false,
    },
    mode: 'onSubmit',
  });

  const passwordValue = watch('password');

  const onSubmit: SubmitHandler<SignUpFormValues> = (data) => {
    console.log('SignUp data:', data);
  };

  return (
    <div className="login-page signup-page">
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
              {/* <NavLink className="login-nav__cta" to="/signin">
                <User size={16} />
                <span>Đăng nhập</span>
              </NavLink> */}
          </nav>
        </div>
      </header>

      <main className="login-main">
        <div className="login-card">
          <div className="login-card__header">
            <div className="login-card__logo">
              <img src={loginIcon} alt="" aria-hidden="true" className="login-card__logo-img" />
            </div>
            <h1 className="login-card__title">Sign Up</h1>
            <p className="login-card__subtitle">Tạo tài khoản để bắt đầu chăm sóc sức khỏe</p>
          </div>

          <form className="login-form" onSubmit={handleSubmit(onSubmit)} noValidate autoComplete="off">
            <div className="login-form__field">
              <label htmlFor="fullName" className="login-form__label">
                Họ và tên
              </label>
              <input
                id="fullName"
                type="text"
                placeholder="Nguyễn Văn A"
                autoComplete="name"
                className={`login-form__input ${errors.fullName ? 'login-form__input--error' : ''}`}
                aria-invalid={errors.fullName ? 'true' : 'false'}
                aria-describedby={errors.fullName ? 'fullname-error' : undefined}
                {...register('fullName', {
                  required: 'Vui lòng nhập họ và tên.',
                  minLength: {
                    value: 2,
                    message: 'Họ và tên tối thiểu 2 ký tự.',
                  },
                })}
              />
              {errors.fullName && (
                <p id="fullname-error" className="login-form__error" role="alert">
                  {errors.fullName.message}
                </p>
              )}
            </div>

            <div className="login-form__field">
              <label htmlFor="phoneNumber" className="login-form__label">
                Số điện thoại
              </label>
              <input
                id="phoneNumber"
                type="tel"
                placeholder="0901234567"
                autoComplete="tel"
                className={`login-form__input ${errors.phoneNumber ? 'login-form__input--error' : ''}`}
                aria-invalid={errors.phoneNumber ? 'true' : 'false'}
                aria-describedby={errors.phoneNumber ? 'phone-error' : undefined}
                {...register('phoneNumber', {
                  required: 'Vui lòng nhập số điện thoại.',
                  pattern: {
                    value: /^\+?\d{9,15}$/,
                    message: 'Số điện thoại không hợp lệ.',
                  },
                })}
              />
              {errors.phoneNumber && (
                <p id="phone-error" className="login-form__error" role="alert">
                  {errors.phoneNumber.message}
                </p>
              )}
            </div>

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

            <div className="login-form__field">
              <label htmlFor="password" className="login-form__label">
                Mật khẩu
              </label>
              <div className="login-form__password">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="password"
                  autoComplete="new-password"
                  className={`login-form__input login-form__input--password ${errors.password ? 'login-form__input--error' : ''}`}
                  aria-invalid={errors.password ? 'true' : 'false'}
                  aria-describedby={errors.password ? 'password-error' : undefined}
                  {...register('password', {
                    required: 'Vui lòng nhập mật khẩu.',
                    minLength: {
                      value: 6,
                      message: 'Mật khẩu tối thiểu 6 ký tự.',
                    },
                  })}
                />
                <button
                  type="button"
                  className="login-form__toggle"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {errors.password && (
                <p id="password-error" className="login-form__error" role="alert">
                  {errors.password.message}
                </p>
              )}
            </div>

            <div className="login-form__field">
              <label htmlFor="confirmPassword" className="login-form__label">
                Xác nhận mật khẩu
              </label>
              <div className="login-form__password">
                <input
                  id="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  placeholder="confirm password"
                  autoComplete="new-password"
                  className={`login-form__input login-form__input--password ${
                    errors.confirmPassword ? 'login-form__input--error' : ''
                  }`}
                  aria-invalid={errors.confirmPassword ? 'true' : 'false'}
                  aria-describedby={errors.confirmPassword ? 'confirm-password-error' : undefined}
                  {...register('confirmPassword', {
                    required: 'Vui lòng xác nhận mật khẩu.',
                    validate: (value) =>
                      value === passwordValue || 'Mật khẩu xác nhận không khớp.',
                  })}
                />
                <button
                  type="button"
                  className="login-form__toggle"
                  onClick={() => setShowConfirmPassword((prev) => !prev)}
                  aria-label={showConfirmPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                >
                  {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {errors.confirmPassword && (
                <p id="confirm-password-error" className="login-form__error" role="alert">
                  {errors.confirmPassword.message}
                </p>
              )}
            </div>

            <div className="login-form__row">
              <label className="checkbox">
                <input
                  type="checkbox"
                  {...register('agree', {
                    required: 'Vui lòng đồng ý với điều khoản.',
                  })}
                />
                <span className="checkbox__box" />
                <span className="checkbox__label">Tôi đồng ý điều khoản</span>
              </label>
            </div>
            {errors.agree && (
              <p id="agree-error" className="login-form__error" role="alert">
                {errors.agree.message}
              </p>
            )}

            <button type="submit" className="login-form__submit" disabled={isSubmitting}>
              {isSubmitting ? 'Đang xử lý...' : 'Đăng ký'}
            </button>
          </form>

          <div className="login-card__footer">
            <span>Đã có tài khoản? </span>
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

export default SignUp;

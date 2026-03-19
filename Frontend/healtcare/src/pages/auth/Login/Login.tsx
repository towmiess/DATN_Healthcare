import React, { useEffect, useState } from 'react';
import { useForm, type SubmitHandler } from 'react-hook-form';
import { Activity, Clock, Eye, EyeOff, Heart, Plus, Shield, User } from 'lucide-react';
import brandLogo from '@/assets/logo.png';
import iconGreen from '@/assets/icon-green.svg';
import loginIcon from '@/assets/icon-login.png';
import './Login.scss';

type LoginFormValues = {
  email: string;
  password: string;
  remember: boolean;
};

const REMEMBER_KEY = 'healthcare_login_remember';

const Login: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    defaultValues: {
      email: '',
      password: '',
      remember: false,
    },
    mode: 'onSubmit',
  });

  useEffect(() => {
    const saved = localStorage.getItem(REMEMBER_KEY);
    if (!saved) return;
    try {
      const parsed = JSON.parse(saved) as { email?: string; password?: string };
      if (parsed.email && parsed.password) {
        setValue('email', parsed.email);
        setValue('password', parsed.password);
        setValue('remember', true);
      }
    } catch {
      localStorage.removeItem(REMEMBER_KEY);
    }
  }, [setValue]);

  const onSubmit: SubmitHandler<LoginFormValues> = (data) => {
    console.log('Login data:', data);
    if (data.remember) {
      localStorage.setItem(
        REMEMBER_KEY,
        JSON.stringify({ email: data.email.trim(), password: data.password })
      );
    } else {
      localStorage.removeItem(REMEMBER_KEY);
    }
  };

  return (
    <div className="login-page">
      <header className="login-nav">
        <div className="login-nav__content">
          <img src={brandLogo} alt="Healthcare Diabetes" className="login-nav__logo" />
          <nav className="login-nav__links">
            <a className="login-nav__item" href="#">
              <img src={iconGreen} alt="" aria-hidden="true" className="login-nav__item-icon" />
              <span>Tổng quan</span>
            </a>
            <a className="login-nav__item" href="#">
              <Plus size={16} />
              <span>Ghi nhận</span>
            </a>
            <a className="login-nav__item" href="#">
              <Clock size={16} />
              <span>Lịch sử</span>
            </a>
            <a className="login-nav__cta" href="#">
              <User size={16} />
              <span>Login</span>
            </a>
          </nav>
        </div>
      </header>

      <main className="login-main">
        <div className="login-card">
          <div className="login-card__header">
            <div className="login-card__logo">
              <img src={loginIcon} alt="" aria-hidden="true" className="login-card__logo-img" />
            </div>
            <h1 className="login-card__title">Login</h1>
            <p className="login-card__subtitle">Đăng nhập để tiếp tục chăm sóc sức khỏe</p>
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
                autoComplete="off"
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
                  placeholder="********"
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

            <div className="login-form__row">
              <label className="checkbox">
                <input type="checkbox" {...register('remember')} />
                <span className="checkbox__box" />
                <span className="checkbox__label">Ghi nhớ đăng nhập</span>
              </label>
              <a className="login-form__link" href="#">
                Quên mật khẩu?
              </a>
            </div>

            <button type="submit" className="login-form__submit" disabled={isSubmitting}>
              {isSubmitting ? 'Đang xử lý...' : 'Đăng nhập'}
            </button>
          </form>

          <div className="login-card__footer">
            <span>Chưa có tài khoản? </span>
            <a href="#" className="login-card__footer-link">
              Đăng ký ngay
            </a>
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

export default Login;

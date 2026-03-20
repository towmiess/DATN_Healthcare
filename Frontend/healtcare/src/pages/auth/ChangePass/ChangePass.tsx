import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useForm, type SubmitHandler } from 'react-hook-form';
import { Activity, Clock, Eye, EyeOff, Heart, Plus, Shield } from 'lucide-react';
import brandLogo from '@/assets/logo.png';
import iconGreen from '@/assets/icon-green.svg';
import loginIcon from '@/assets/icon-login.png';
import './ChangePass.scss';

type ChangePassFormValues = {
  oldPassword: string;
  newPassword: string;
  newPasswordConfirm: string;
};

const ChangePass: React.FC = () => {
  const [showOldPassword, setShowOldPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<ChangePassFormValues>({
    defaultValues: {
      oldPassword: '',
      newPassword: '',
      newPasswordConfirm: '',
    },
    mode: 'onSubmit',
  });

  const newPasswordValue = watch('newPassword');

  const onSubmit: SubmitHandler<ChangePassFormValues> = (data) => {
    console.log('Change password data:', data);
  };

  return (
    <div className="login-page change-pass-page">
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
            <h1 className="login-card__title">Change Password</h1>
            <p className="login-card__subtitle">Cập nhật mật khẩu mới cho tài khoản của bạn</p>
          </div>

          <form className="login-form" onSubmit={handleSubmit(onSubmit)} noValidate autoComplete="off">
            <div className="login-form__field">
              <label htmlFor="oldPassword" className="login-form__label">
                Old Password
              </label>
              <div className="login-form__password">
                <input
                  id="oldPassword"
                  type={showOldPassword ? 'text' : 'password'}
                  placeholder="old password"
                  autoComplete="current-password"
                  className={`login-form__input login-form__input--password ${errors.oldPassword ? 'login-form__input--error' : ''}`}
                  aria-invalid={errors.oldPassword ? 'true' : 'false'}
                  aria-describedby={errors.oldPassword ? 'old-password-error' : undefined}
                  {...register('oldPassword', {
                    required: 'Vui lòng nhập mật khẩu cũ.',
                  })}
                />
                <button
                  type="button"
                  className="login-form__toggle"
                  onClick={() => setShowOldPassword((prev) => !prev)}
                  aria-label={showOldPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                >
                  {showOldPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {errors.oldPassword && (
                <p id="old-password-error" className="login-form__error" role="alert">
                  {errors.oldPassword.message}
                </p>
              )}
            </div>

            <div className="login-form__field">
              <label htmlFor="newPassword" className="login-form__label">
                New Password
              </label>
              <div className="login-form__password">
                <input
                  id="newPassword"
                  type={showNewPassword ? 'text' : 'password'}
                  placeholder="new password"
                  autoComplete="new-password"
                  className={`login-form__input login-form__input--password ${errors.newPassword ? 'login-form__input--error' : ''}`}
                  aria-invalid={errors.newPassword ? 'true' : 'false'}
                  aria-describedby={errors.newPassword ? 'new-password-error' : undefined}
                  {...register('newPassword', {
                    required: 'Vui lòng nhập mật khẩu mới.',
                    minLength: {
                      value: 6,
                      message: 'Mật khẩu tối thiểu 6 ký tự.',
                    },
                  })}
                />
                <button
                  type="button"
                  className="login-form__toggle"
                  onClick={() => setShowNewPassword((prev) => !prev)}
                  aria-label={showNewPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                >
                  {showNewPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {errors.newPassword && (
                <p id="new-password-error" className="login-form__error" role="alert">
                  {errors.newPassword.message}
                </p>
              )}
            </div>

            <div className="login-form__field">
              <label htmlFor="newPasswordConfirm" className="login-form__label">
                New Password Confirm
              </label>
              <div className="login-form__password">
                <input
                  id="newPasswordConfirm"
                  type={showConfirmPassword ? 'text' : 'password'}
                  placeholder="confirm new password"
                  autoComplete="new-password"
                  className={`login-form__input login-form__input--password ${
                    errors.newPasswordConfirm ? 'login-form__input--error' : ''
                  }`}
                  aria-invalid={errors.newPasswordConfirm ? 'true' : 'false'}
                  aria-describedby={errors.newPasswordConfirm ? 'confirm-password-error' : undefined}
                  {...register('newPasswordConfirm', {
                    required: 'Vui lòng xác nhận mật khẩu mới.',
                    validate: (value) =>
                      value === newPasswordValue || 'Mật khẩu xác nhận không khớp.',
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
              {errors.newPasswordConfirm && (
                <p id="confirm-password-error" className="login-form__error" role="alert">
                  {errors.newPasswordConfirm.message}
                </p>
              )}
            </div>

            <button type="submit" className="login-form__submit" disabled={isSubmitting}>
              {isSubmitting ? 'Đang xử lý...' : 'Change Password'}
            </button>
          </form>

          <div className="login-card__footer">
            <span>Quay lại </span>
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

export default ChangePass;

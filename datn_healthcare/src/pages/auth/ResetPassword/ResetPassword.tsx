import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useForm, type SubmitHandler } from 'react-hook-form';
import { Activity, Clock, Eye, EyeOff, Heart, Plus, Shield } from 'lucide-react';
import brandLogo from '@/assets/logo.png';
import iconGreen from '@/assets/icon-green.svg';
import loginIcon from '@/assets/icon-login.png';
import './ResetPassword.scss';
import axios from 'axios';
import { BaseResponse } from '@/types/BaseType';
import { toast } from 'sonner';
import { resetPassword } from '@/services/authservices/resetpassword';
import { ResetPasswordRequest } from '@/types/AuthType';

type ResetPasswordFormValues = {
  password: string;
};

const ResetPassword: React.FC = () => {
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordFormValues>({
    defaultValues: {
      password: '',
    },
    mode: 'onSubmit',
  });

  const onSubmit: SubmitHandler<ResetPasswordFormValues> =async (data) => {
    const requestData: ResetPasswordRequest = {
      token: String(sessionStorage.getItem('resetPasswordToken')),
      newPassword: data.password.trim(),
      userId: Number(sessionStorage.getItem('resetPasswordUserId')),
    };

    try{
      await resetPassword(requestData);
      toast.success("Đặt lại mật khẩu thành công");
      sessionStorage.clear();
      navigate('/login');
    }catch (error) {
      const errorResponse: BaseResponse<null> | null = axios.isAxiosError<BaseResponse<null>>(error)
        ? error.response?.data ?? null
        : null;
      toast.error("Đặt lại mật khẩu thất bại. Vui lòng thử lại.");
      console.error('Reset password error:', errorResponse);
    }
  };

  return (
    <div className="login-page reset-password-page">
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
            <h1 className="login-card__title">Reset Password</h1>
            <p className="login-card__subtitle">Tạo mật khẩu mới cho tài khoản của bạn</p>
          </div>

          <form className="login-form" onSubmit={handleSubmit(onSubmit)} noValidate autoComplete="off">
            <div className="login-form__field">
              <label htmlFor="password" className="login-form__label">
                New Password
              </label>
              <div className="login-form__password">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="new password"
                  autoComplete="new-password"
                  className={`login-form__input login-form__input--password ${errors.password ? 'login-form__input--error' : ''}`}
                  aria-invalid={errors.password ? 'true' : 'false'}
                  aria-describedby={errors.password ? 'password-error' : undefined}
                  {...register('password', {
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

            <button type="submit" className="login-form__submit" disabled={isSubmitting}>
              {isSubmitting ? 'Đang xử lý...' : 'Reset Password'}
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

export default ResetPassword;

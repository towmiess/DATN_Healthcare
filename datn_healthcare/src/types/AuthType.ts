export interface SignUpRequest {
  fullName: string;
  phoneNumber: string;
  email: string;
  password: string;
  confirmPassword: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
}

export interface LogoutRequest {
  refreshToken: string;
}

export interface CheckEmailRequest {
  email: string;
}

export interface CheckEmailResponse {
  userId: number;
}

export interface CheckOTPRequest {
  userId: number;
  otp: string;
}

export interface CheckOTPResponse {
  token: string;
  userId: number;
}

export interface ResetPasswordRequest {
  token: string;
  newPassword: string;
  userId: number;
}

export interface ChangePasswordRequest {
  oldPassword: string;
  newPassword: string;
  newPasswordConfirm: string;
}

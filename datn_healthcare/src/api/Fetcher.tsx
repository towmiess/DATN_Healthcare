import { API_URL } from "@/config";
import { BaseResponse } from "@/types/BaseType";
import {
  clearAuth,
  getAccessToken,
  getLoginRedirectPath,
  getRefreshToken,
} from "@/utils/auth";
import axios, { AxiosError, AxiosHeaders, AxiosRequestConfig } from "axios";

type FetcherConfig = AxiosRequestConfig & {
  unwrapData?: boolean;
};

const normalizeApiBase = (raw?: string) => {
  const trimmed = (raw ?? "").replace(/\/$/, "");
  if (!trimmed) return "";
  return trimmed.endsWith("/api") ? trimmed : `${trimmed}/api`;
};

const API_BASE_URL = normalizeApiBase(API_URL);
const AUTH_EXEMPT_PATHS = [
  "/auth/signin",
  "/auth/signup",
  "/auth/check-mail",
  "/auth/check-otp",
  "/auth/reset-password",
  "/auth/change-pass",
  "/auth/logout",
];
const REFRESH_PATH = "/auth/refresh-token";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000
});

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();

  if (token) {
    const headers = AxiosHeaders.from(config.headers);
    headers.set("Authorization", `Bearer ${token}`);
    config.headers = headers;
  }

  return config;
});

const isAuthExemptRequest = (url?: string) => {
  if (!url) return false;
  return AUTH_EXEMPT_PATHS.some((path) => url.includes(path));
};

const isRefreshRequest = (url?: string) => {
  if (!url) return false;
  return url.includes(REFRESH_PATH);
};

const getResponseMessage = (error: AxiosError<any>) => {
  const data = error.response?.data;
  if (!data || typeof data !== "object") return "";
  const message = (data as { message?: unknown }).message;
  return typeof message === "string" ? message : "";
};

const isAuthFailureResponse = (error: AxiosError<any>) => {
  const status = error.response?.status;
  if (status !== 401) return false;

  const message = getResponseMessage(error).toLowerCase();
  if (!message) return true;

  return [
    "unauthorized",
    "invalid token",
    "expired token",
    "token expired",
    "invalid or expired token",
    "token revoked",
    "missing authenticated user",
    "missing user id",
    "phiên đăng nhập",
  ].some((keyword) => message.includes(keyword));
};

const forceLogout = () => {
  clearAuth();
  window.location.replace(getLoginRedirectPath());
};

let isRefreshing = false;
let failedQueue: {
  resolve: (token: string) => void;
  reject: (error: any) => void;
}[] = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    error ? prom.reject(error) : prom.resolve(token!);
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,

  async (error: AxiosError<any>) => {
    const originalRequest: any = error.config;
    const status = error.response?.status;
    const requestUrl = originalRequest?.url as string | undefined;
    const isUnauthorized = isAuthFailureResponse(error);
    const isForbidden = status === 403;

    if (isUnauthorized && isRefreshRequest(requestUrl)) {
      processQueue(error, null);
      forceLogout();
      return Promise.reject(error);
    }

    if (isUnauthorized && !originalRequest._retry && !isAuthExemptRequest(requestUrl)) {
      originalRequest._retry = true;

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
              const headers = AxiosHeaders.from(originalRequest.headers ?? {});
              headers.set("Authorization", `Bearer ${token}`);
              originalRequest.headers = headers;
              resolve(apiClient(originalRequest));
            },
            reject,
          });
        });
      }

      isRefreshing = true;

      try {
        const refreshToken = getRefreshToken();

        if (!refreshToken) {
          throw new Error("No refresh token");
        }

        const res = await apiClient.post<BaseResponse<{ accessToken: string }>>(
          "/auth/refresh-token",
          { refreshToken }
        );

        const newAccessToken = res.data?.data?.accessToken;
        if (!newAccessToken) {
          throw new Error("No access token in refresh response");
        }

        sessionStorage.setItem("accessToken", newAccessToken);

        processQueue(null, newAccessToken);

        {
          const headers = AxiosHeaders.from(originalRequest.headers ?? {});
          headers.set("Authorization", `Bearer ${newAccessToken}`);
          originalRequest.headers = headers;
        }
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);

        forceLogout();

        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    if (isForbidden) {
      return Promise.reject(error);
    }

    if (isUnauthorized && !isAuthExemptRequest(requestUrl)) {
      forceLogout();
      return Promise.reject(error);
    }

    return Promise.reject(error);
  }
);

export const fetcher = async <T,>(
  config: FetcherConfig
): Promise<T> => {
  const { unwrapData = false, ...requestConfig } = config;
  const response = await apiClient.request(requestConfig);
  const payload = response.data;

  if (!unwrapData) {
    return payload as T;
  }

  if (payload && typeof payload === "object" && "data" in payload) {
    return (payload as BaseResponse<T>).data as T;
  }
  return payload as T;
};

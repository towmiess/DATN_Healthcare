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

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();

  if (token) {
    config.headers = new AxiosHeaders({
      ...config.headers,
      Authorization: `Bearer ${token}`,
    });
  }

  return config;
});

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

    if (
      status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/refresh-token")
    ) {
      originalRequest._retry = true;

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
              originalRequest.headers = originalRequest.headers ?? {};
              originalRequest.headers.Authorization = `Bearer ${token}`;
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

        localStorage.setItem("accessToken", newAccessToken);

        processQueue(null, newAccessToken);

        originalRequest.headers = originalRequest.headers ?? {};
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);

        clearAuth();
        window.location.href = getLoginRedirectPath();

        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
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

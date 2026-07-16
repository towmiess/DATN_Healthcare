import axios from "axios";

export const getApiErrorMessage = (
  error: unknown,
  fallbackMessage: string,
  options?: {
    forbiddenMessage?: string;
    unauthorizedMessage?: string;
  }
) => {
  const forbiddenMessage = options?.forbiddenMessage ?? "Bạn không có quyền truy cập.";
  const unauthorizedMessage = options?.unauthorizedMessage ?? "Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.";

  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const responseMessage = (error.response?.data as { message?: string } | undefined)?.message;

    if (status === 403) {
      return responseMessage || forbiddenMessage;
    }

    if (status === 401) {
      return responseMessage || unauthorizedMessage;
    }
  }

  return fallbackMessage;
};

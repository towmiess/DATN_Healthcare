import { fetcher } from "@/api/Fetcher";

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
}

export const login = (data: LoginRequest) => {
  return fetcher<LoginResponse>({
    url: "/auth/signin",
    method: "POST",
    data,
  });
};

import { fetcher } from "@/api/Fetcher";
import { LoginRequest, LoginResponse } from "@/types/AuthType";
import { BaseResponse } from "@/types/BaseType";

export const login = (data: LoginRequest) => {
  return fetcher<BaseResponse<LoginResponse>>({
    url: "/auth/signin",
    method: "POST",
    data,
  });
};

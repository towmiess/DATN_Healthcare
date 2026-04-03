import { fetcher } from "@/api/Fetcher";
import { LogoutRequest } from "@/types/AuthType";
import { BaseResponse } from "@/types/BaseType";

export const logout = (data: LogoutRequest) => {
  return fetcher<BaseResponse<null>>({
    url: "/auth/logout",
    method: "POST",
    data,
  });
};

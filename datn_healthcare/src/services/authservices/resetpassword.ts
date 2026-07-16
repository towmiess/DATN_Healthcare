import { fetcher } from "@/api/Fetcher";
import { ResetPasswordRequest } from "@/types/AuthType";
import { BaseResponse } from "@/types/BaseType";

export const resetPassword = (data: ResetPasswordRequest) => {
  return fetcher<BaseResponse<null>>({
    url: "/auth/reset-password", 
    method: "POST",
    data,
  });
}
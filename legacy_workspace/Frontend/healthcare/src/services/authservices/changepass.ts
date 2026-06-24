import { fetcher } from "@/api/Fetcher";
import { ChangePasswordRequest } from "@/types/AuthType";
import { BaseResponse } from "@/types/BaseType";

export const changePassword = (data: ChangePasswordRequest) =>{
  return fetcher<BaseResponse<null>>({
    url: "/auth/change-pass",
    method: "POST",
    data,
  });
}
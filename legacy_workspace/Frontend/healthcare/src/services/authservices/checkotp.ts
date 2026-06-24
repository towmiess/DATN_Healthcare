import { fetcher } from "@/api/Fetcher";
import { CheckOTPRequest, CheckOTPResponse } from "@/types/AuthType";
import { BaseResponse } from "@/types/BaseType";

export const checkotp = (data : CheckOTPRequest) => {
  return fetcher<BaseResponse<CheckOTPResponse>>({
    url: "/auth/check-otp",
    method: "POST",
    data
  });
}
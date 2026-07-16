import { fetcher } from "@/api/Fetcher";
import { CheckEmailRequest, CheckEmailResponse } from "@/types/AuthType";
import { BaseResponse } from "@/types/BaseType";

export const checkmail = (data : CheckEmailRequest) => {
  return fetcher<BaseResponse<CheckEmailResponse>>({
    url: "/auth/check-mail",  
    method: "POST",
    data,
  });
}
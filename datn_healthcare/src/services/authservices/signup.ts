import { fetcher } from "@/api/Fetcher";
import { BaseResponse } from "@/types/BaseType";
import { SignUpRequest } from "@/types/AuthType";

export const signup = (data: SignUpRequest) => {
  return fetcher<BaseResponse<null>>({
    url: "/auth/signup",
    method: "POST",
    data,
  });
};

export interface BaseResponse<T> {
  code?: string;
  message: string;
  data: T;
}

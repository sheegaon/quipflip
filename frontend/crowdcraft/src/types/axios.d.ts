import 'axios';

declare module 'axios' {
  interface AxiosRequestConfig {
    /**
     * Skip automatic auth header injection for endpoints like login/refresh.
     */
    skipAuth?: boolean;
  }
}

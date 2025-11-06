// Version injected at build time from package.json
// This ensures the version is always available even if the backend API is unreachable
declare const __APP_VERSION__: string;

export const APP_VERSION = __APP_VERSION__;

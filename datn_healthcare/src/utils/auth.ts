export const getAccessToken = () => {
  const token = sessionStorage.getItem("accessToken");
  if (!token || token === "null" || token === "undefined") return null;
  return token;
};

export const getRefreshToken = () => {
  const token = sessionStorage.getItem("refreshToken");
  if (!token || token === "null" || token === "undefined") return null;
  return token;
};

const decodeBase64Url = (input: string) => {
  const padded = input.replace(/-/g, "+").replace(/_/g, "/");
  const padLength = (4 - (padded.length % 4)) % 4;
  const base64 = padded + "=".repeat(padLength);
  try {
    return atob(base64);
  } catch {
    return null;
  }
};

const getJwtPayload = (token: string | null): Record<string, unknown> | null => {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length < 2) return null;
  const decoded = decodeBase64Url(parts[1]);
  if (!decoded) return null;
  try {
    const payload = JSON.parse(decoded) as Record<string, unknown>;
    return payload;
  } catch {
    return null;
  }
};

const getRolesFromToken = (token: string | null): string[] => {
  const payload = getJwtPayload(token);
  if (!payload) return [];
  if (Array.isArray(payload.roles)) {
    return payload.roles.map((r) => String(r));
  }
  return [];
};

const getTokenExpMs = (token: string | null): number | null => {
  const payload = getJwtPayload(token);
  if (!payload) return null;

  const exp = payload.exp;
  if (typeof exp === "number" && Number.isFinite(exp)) {
    return exp * 1000;
  }

  if (typeof exp === "string" && exp.trim() !== "") {
    const parsed = Number(exp);
    if (Number.isFinite(parsed)) {
      return parsed * 1000;
    }
  }

  return null;
};

export const getRoles = (): string[] => {
  const roles = sessionStorage.getItem("roles");
  if (roles) {
    try {
      return JSON.parse(roles);
    } catch {
      return [];
    }
  }
  return getRolesFromToken(getAccessToken());
};

const normalizeRole = (role: string) =>
  role.replace(/^ROLE_/i, "").trim().toUpperCase();

export const hasRole = (requiredRoles: string[]) => {
  const roles = getRoles().map(normalizeRole);
  const required = requiredRoles.map(normalizeRole);
  return required.some((r) => roles.includes(r));
};

export const clearAuth = () => {
  sessionStorage.removeItem("accessToken");
  sessionStorage.removeItem("refreshToken");
  sessionStorage.removeItem("roles");
};

export const isAccessTokenExpired = () => {
  const expMs = getTokenExpMs(getAccessToken());
  if (!expMs) return false;
  return Date.now() >= expMs;
};

export const hasValidAccessToken = () => {
  return Boolean(getAccessToken()) && !isAccessTokenExpired();
};

export const getLoginRedirectPath = () => {
  return "/login";
};

export const getHomePathForRoles = () => {
  if (hasRole(["ADMIN"])) return "/admin";
  if (hasRole(["USER"])) return "/user";
  return getLoginRedirectPath();
};

export const getAccessToken = () => {
  const token = localStorage.getItem("accessToken");
  if (!token || token === "null" || token === "undefined") return null;
  return token;
};

export const getRefreshToken = () => {
  const token = localStorage.getItem("refreshToken");
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

const getRolesFromToken = (token: string | null): string[] => {
  if (!token) return [];
  const parts = token.split(".");
  if (parts.length < 2) return [];
  const decoded = decodeBase64Url(parts[1]);
  if (!decoded) return [];
  try {
    const payload = JSON.parse(decoded) as { roles?: unknown };
    if (Array.isArray(payload.roles)) {
      return payload.roles.map((r) => String(r));
    }
  } catch {
    return [];
  }
  return [];
};

export const getRoles = (): string[] => {
  const roles = localStorage.getItem("roles");
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
  localStorage.removeItem("accessToken");
  localStorage.removeItem("refreshToken");
  localStorage.removeItem("roles");
};

export const getLoginRedirectPath = () => {
  return "/login";
};

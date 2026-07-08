import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import Login from "@/pages/auth/Login/Login";
import SignUp from "@/pages/auth/SignUp/SignUp";
import CheckEmail from "@/pages/auth/CheckEmail/CheckEmail";
import VerifyOtp from "@/pages/auth/VerifyOtp/VerifyOtp";
import ResetPassword from "@/pages/auth/ResetPassword/ResetPassword";
import ChangePass from "@/pages/auth/ChangePass/ChangePass";
import AdminLayout from "@/layouts/admin/AdminLayout";
import UserLayout from "@/layouts/user/UserLayout";
import DashboardShell from "@/layouts/shared/DashboardShell";
import AdminHome from "@/pages/admin/AdminHome";
import PeriodicReportDashboard from "@/pages/reports/PeriodicReportDashboard";
import UserHome from "@/pages/user/UserHome";
import { getAccessToken, getLoginRedirectPath, hasRole } from "@/utils/auth";

const getDefaultPathForRoles = () => {
  if (hasRole(["ADMIN"])) return "/admin";
  if (hasRole(["USER"])) return "/user";
  return getLoginRedirectPath();
};

const PublicRoutes = () => {
  const token = getAccessToken();
  if (token && (hasRole(["ADMIN"]) || hasRole(["USER"]))) {
    return <Navigate to={getDefaultPathForRoles()} replace />;
  }
  return <Outlet />;
};

const RequireAuth = () => {
  const token = getAccessToken();
  if (!token) return <Navigate to={getLoginRedirectPath()} replace />;
  return <Outlet />;
};

const RequireRole = ({ roles }: { roles: string[] }) => {
  const token = getAccessToken();
  if (!token) return <Navigate to={getLoginRedirectPath()} replace />;
  if (!hasRole(roles)) return <Navigate to={getDefaultPathForRoles()} replace />;
  return <Outlet />;
};

const RoleRedirect = () => {
  return <Navigate to={getDefaultPathForRoles()} replace />;
};

const AppRoutes = () => {
  const isAuthed = Boolean(getAccessToken());

  return (
    <Routes>
      <Route element={<PublicRoutes />}>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<SignUp />} />
        <Route path="/check-email" element={<CheckEmail />} />
        <Route path="/verify-otp" element={<VerifyOtp />} />
        <Route path="/reset-password" element={<ResetPassword />} />
      </Route>

      <Route element={<RequireAuth />}>
        <Route index element={<RoleRedirect />} />

        <Route path="/diagnosis" element={<DashboardShell homePath="/diagnosis" />}>
          <Route index element={<UserHome />} />
        </Route>

        <Route path="/reports" element={<DashboardShell homePath="/reports" />}>
          <Route index element={<PeriodicReportDashboard />} />
        </Route>

        <Route element={<RequireRole roles={["ADMIN"]} />}>
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<AdminHome />} />
          </Route>
        </Route>

        <Route element={<RequireRole roles={["USER"]} />}>
          <Route path="/user" element={<UserLayout />}>
            <Route index element={<UserHome />} />
          </Route>
        </Route>
        <Route path="/change-password" element={<ChangePass />} />
      </Route>
      
      <Route
        path="*"
        element={
          <Navigate
            to={isAuthed ? getDefaultPathForRoles() : getLoginRedirectPath()}
            replace
          />
        }
      />
    </Routes>
  );
};

export default AppRoutes;

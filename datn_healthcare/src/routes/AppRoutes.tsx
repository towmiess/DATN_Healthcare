import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import Login from "@/pages/auth/Login/Login";
import SignUp from "@/pages/auth/SignUp/SignUp";
import CheckEmail from "@/pages/auth/CheckEmail/CheckEmail";
import VerifyOtp from "@/pages/auth/VerifyOtp/VerifyOtp";
import ResetPassword from "@/pages/auth/ResetPassword/ResetPassword";
import ChangePass from "@/pages/auth/ChangePass/ChangePass";
import AdminLayout from "@/layouts/admin/AdminLayout";
import UserLayout from "@/layouts/user/UserLayout";
import AdminHome from "@/pages/admin/AdminHome";
import AdminMeals from "@/pages/admin/AdminMeals";
import AdminIngredients from "@/pages/admin/AdminIngredients";
import AdminUsers from "@/pages/admin/AdminUsers";
import UserHome from "@/pages/user/UserHome";
import MealRecommendations from "@/pages/user/MealRecommendations";
import MealHistory from "@/pages/user/MealHistory";
import DiagnosisPage from "@/pages/user/DiagnosisPage";
import Chatbot from "@/pages/user/Chatbot/Chatbot";
import PeriodicReportDashboard from "@/pages/reports/PeriodicReportDashboard";
import { getHomePathForRoles, getLoginRedirectPath, hasRole, hasValidAccessToken } from "@/utils/auth";

const PublicRoutes = () => {
  if (hasValidAccessToken() && (hasRole(["ADMIN"]) || hasRole(["USER"]))) {
    return <Navigate to={getHomePathForRoles()} replace />;
  }
  return <Outlet />;
};

const RequireAuth = () => {
  if (!hasValidAccessToken()) return <Navigate to={getLoginRedirectPath()} replace />;
  return <Outlet />;
};

const RequireRole = ({ roles }: { roles: string[] }) => {
  if (!hasValidAccessToken()) return <Navigate to={getLoginRedirectPath()} replace />;
  if (!hasRole(roles)) return <Navigate to={getHomePathForRoles()} replace />;
  return <Outlet />;
};

const RoleRedirect = () => {
  return <Navigate to={getHomePathForRoles()} replace />;
};

const AppRoutes = () => {
  const isAuthed = hasValidAccessToken();

  return (
    <Routes>
      <Route element={<PublicRoutes />}>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<SignUp />} />
        <Route path="/check-email" element={<CheckEmail />} />
        <Route path="/verify-otp" element={<VerifyOtp />} />
        <Route path="/reset-password" element={<ResetPassword />} />
      </Route>

      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<AdminHome section="dashboard" sectionTitle="Bảng điều khiển" />} />
        <Route path="orders" element={<AdminHome section="orders" sectionTitle="Quản lý đơn hàng" />} />
        <Route path="customers" element={<AdminHome section="customers" sectionTitle="Quản lý khách hàng" />} />
        <Route path="reports" element={<Navigate to="/admin/ingredients" replace />} />
        <Route path="ingredients" element={<AdminIngredients />} />
        <Route path="products" element={<AdminMeals />} />
        <Route path="settings" element={<AdminUsers />} />
      </Route>

      <Route element={<RequireAuth />}>
        <Route index element={<RoleRedirect />} />

        <Route element={<RequireRole roles={["USER"]} />}>
          <Route path="/user" element={<UserLayout />}>
            <Route index element={<UserHome />} />
            <Route path="recommendations" element={<MealRecommendations />} />
            <Route path="history" element={<MealHistory />} />
            <Route path="diagnosis" element={<DiagnosisPage />} />
            <Route path="chat" element={<Chatbot />} />
            <Route path="reports" element={<PeriodicReportDashboard />} />
          </Route>
        </Route>
        <Route path="/change-password" element={<ChangePass />} />
      </Route>

      <Route
        path="*"
        element={<Navigate to={isAuthed ? getHomePathForRoles() : getLoginRedirectPath()} replace />}
      />
    </Routes>
  );
};

export default AppRoutes;

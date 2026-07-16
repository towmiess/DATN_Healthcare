export type AdminSection =
  | "dashboard"
  | "orders"
  | "customers"
  | "reports"
  | "products"
  | "settings";

export const ADMIN_SECTIONS: {
  label: string;
  value: AdminSection;
  path: string;
  section: "overview" | "analysis" | "system";
}[] = [
  { label: "Dashboard", value: "dashboard", path: "/admin", section: "overview" },
  { label: "Đơn hàng", value: "orders", path: "/admin/orders", section: "overview" },
  { label: "Khách hàng", value: "customers", path: "/admin/customers", section: "overview" },
  { label: "Nguyên liệu", value: "reports", path: "/admin/ingredients", section: "analysis" },
  { label: "Món ăn", value: "products", path: "/admin/products", section: "analysis" },
  { label: "Người dùng", value: "settings", path: "/admin/settings", section: "system" },
];

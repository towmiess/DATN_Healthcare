import { Outlet } from "react-router-dom";

const AdminLayout = () => {
  return (
    <div>
      <header>Admin Layout</header>
      <main>
        <Outlet />
      </main>
    </div>
  );
};

export default AdminLayout;

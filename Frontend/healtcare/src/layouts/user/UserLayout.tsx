import { Outlet } from "react-router-dom";

const UserLayout = () => {
  return (
    <div>
      <header>User Layout</header>
      <main>
        <Outlet />
      </main>
    </div>
  );
};

export default UserLayout;

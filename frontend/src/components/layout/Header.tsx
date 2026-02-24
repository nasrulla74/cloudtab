import { useState } from "react";
import { useAuth } from "../../contexts/AuthContext";
import ChangePasswordModal from "../shared/ChangePasswordModal";

export default function Header() {
  const { user, logout } = useAuth();
  const [showChangePassword, setShowChangePassword] = useState(false);

  return (
    <>
      <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6">
        <div />
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-600">{user?.email}</span>
          <button
            onClick={() => setShowChangePassword(true)}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Change Password
          </button>
          <button
            onClick={logout}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Logout
          </button>
        </div>
      </header>
      <ChangePasswordModal
        open={showChangePassword}
        onClose={() => setShowChangePassword(false)}
      />
    </>
  );
}

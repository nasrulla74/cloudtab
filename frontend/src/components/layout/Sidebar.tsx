import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Server,
  PanelLeftClose,
  PanelLeftOpen,
  type LucideIcon,
} from "lucide-react";

const links: { to: string; label: string; icon: LucideIcon }[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/servers", label: "Servers", icon: Server },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`${
        collapsed ? "w-16" : "w-60"
      } bg-gray-900 text-white min-h-screen p-4 flex flex-col transition-all duration-300`}
    >
      {/* Header: brand + toggle button */}
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-xl font-bold px-2 whitespace-nowrap overflow-hidden">
          {collapsed ? "CT" : "CloudTab"}
        </h1>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-center p-1.5 rounded-md text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeftOpen size={18} />
          ) : (
            <PanelLeftClose size={18} />
          )}
        </button>
      </div>

      <nav className="space-y-1 flex-1">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            title={collapsed ? link.label : undefined}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? "bg-gray-700 text-white"
                  : "text-gray-300 hover:bg-gray-800 hover:text-white"
              }`
            }
          >
            <link.icon size={20} className="shrink-0" />
            {!collapsed && <span>{link.label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

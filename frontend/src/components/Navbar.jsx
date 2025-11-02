import { Link, useLocation } from 'react-router-dom';
import darkWordmark from '../assets/Dark Mode Wordmark.png';

const Navbar = () => {
  const location = useLocation();

  const navItems = [
    { path: '/dashboard', label: 'Dashboard' },
    { path: '/insights', label: 'Insights' },
    { path: '/settings', label: 'Settings' },
  ];

  return (
    <nav className="border-b border-gray-800 bg-gray-900">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link to="/dashboard" className="flex items-center">
            <img src={darkWordmark} alt="Northstar" className="h-6" />
          </Link>

          {/* Navigation Tabs */}
          <div className="flex items-center gap-1">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path || (location.pathname === '/' && item.path === '/dashboard');
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`rounded px-4 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-gray-800 text-white'
                      : 'text-gray-300 hover:text-white hover:bg-gray-800/50'
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;


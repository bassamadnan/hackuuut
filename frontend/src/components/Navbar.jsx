import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import ThemeSelector from "./ThemeSelector";

const Navbar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const isHome = location.pathname === '/';

  return (
    <div className="navbar bg-base-100 shadow-md border-b border-base-300">
      <div className="navbar-start">
        <ul className="menu menu-horizontal px-1">
          {!isHome && (
            <>
              <li>
                <a onClick={() => navigate('/tools')}>Tool Generator</a>
              </li>
              <li>
                <a onClick={() => navigate('/chat')}>Chat</a>
              </li>
              <li>
                <a onClick={() => navigate('/agent-demo')} className="flex items-center gap-1">
                  <span>AWS Demo</span>
                  <span className="badge badge-sm badge-accent">New</span>
                </a>
              </li>
              <li>
                <a onClick={() => navigate('/simple-agent-demo')} className="flex items-center gap-1">
                  <span>Customer Returns Demo</span>
                  <span className="badge badge-sm badge-success">New</span>
                </a>
              </li>
            </>
          )}
        </ul>
      </div>
      <div className="navbar-center">
        <a 
          className="btn btn-ghost text-xl"
          onClick={() => navigate('/')}
        >
          moya
        </a>
      </div>
      <div className="navbar-end">
        <ul className="menu menu-horizontal px-1">
          <li>
            <a onClick={() => navigate('/about')}>About</a>
          </li>
        </ul>
        <ThemeSelector />
      </div>
    </div>
  );
};

export default Navbar;
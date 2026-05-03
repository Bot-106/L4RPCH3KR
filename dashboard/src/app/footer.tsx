"use client";

import { createContext, useContext, useState, ReactNode } from "react";

// Admin context to control UI visibility across the app
const AdminContext = createContext<{ isAdmin: boolean; setIsAdmin: (val: boolean) => void } | null>(null);

export function AdminProvider({ children }: { children: ReactNode }) {
  const [isAdmin, setIsAdmin] = useState(false);

  return (
    <AdminContext.Provider value={{ isAdmin, setIsAdmin }}>
      {children}
    </AdminContext.Provider>
  );
}

export function useAdmin() {
  const context = useContext(AdminContext);
  if (!context) {
    throw new Error("useAdmin must be used within AdminProvider");
  }
  return context;
}

export default function Footer() {
  return (
    <footer className="border-t border-stone-200 bg-stone-50 py-6 px-4 mt-auto">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col items-center justify-between gap-4 text-center text-sm text-stone-600">
          <p>
            If you want your data removed, please email{" "}
            <a href="mailto:arnnav0kudale@gmail.com" className="font-semibold text-orange-600 hover:underline">
              arnnav0kudale@gmail.com
            </a>
          </p>
          <AdminButton />
        </div>
      </div>
    </footer>
  );
}

function AdminButton() {
  const { isAdmin, setIsAdmin } = useAdmin();
  const [isOpen, setIsOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handlePasswordSubmit = () => {
    if (password === "389179") {
      setIsAdmin(true);
      setError("");
      setPassword("");
      setIsOpen(false);
    } else {
      setError("Incorrect password");
      setPassword("");
    }
  };

  const handleLogout = () => {
    setIsAdmin(false);
    setPassword("");
    setError("");
  };

  if (isAdmin) {
    return (
      <button
        onClick={handleLogout}
        className="text-xs font-semibold px-3 py-1 bg-orange-600 text-white rounded hover:bg-orange-700"
      >
        Admin Mode (logout)
      </button>
    );
  }

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="text-xs font-semibold text-stone-500 hover:text-stone-700 underline"
      >
        admin
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full">
            <h1 className="text-2xl font-black mb-4">Admin Login</h1>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handlePasswordSubmit()}
              placeholder="Enter password"
              className="w-full px-4 py-2 border border-stone-300 rounded-lg mb-4"
              autoFocus
            />
            {error && <p className="text-red-600 text-sm mb-4">{error}</p>}
            <div className="flex gap-2">
              <button
                onClick={handlePasswordSubmit}
                className="flex-1 px-4 py-2 bg-orange-600 text-white font-bold rounded-lg hover:bg-orange-700"
              >
                Submit
              </button>
              <button
                onClick={() => {
                  setIsOpen(false);
                  setPassword("");
                  setError("");
                }}
                className="flex-1 px-4 py-2 bg-stone-300 text-black font-bold rounded-lg hover:bg-stone-400"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

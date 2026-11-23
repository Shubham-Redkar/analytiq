"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, displayName: string) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const defaultAuthContext: AuthContextType = {
  user: null,
  loading: false,
  login: async () => ({
    id: "",
    email: "",
    display_name: "",
    is_active: false,
    created_at: "",
  }),
  register: async () => ({
    id: "",
    email: "",
    display_name: "",
    is_active: false,
    created_at: "",
  }),
  logout: async () => {},
  refresh: async () => {},
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const refresh = useCallback(async () => {
    try {
      const currentUser = await api.getMe();
      setUser(currentUser);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    async function checkAuth() {
      try {
        const currentUser = await api.getMe();
        if (!ignore) {
          setUser(currentUser);
        }
      } catch {
        if (!ignore) {
          setUser(null);
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }
    void checkAuth();
    return () => {
      ignore = true;
    };
  }, []);

  const login = async (email: string, password: string): Promise<User> => {
    const loggedInUser = await api.login({ email, password });
    setUser(loggedInUser);
    return loggedInUser;
  };

  const register = async (
    email: string,
    password: string,
    displayName: string
  ): Promise<User> => {
    await api.register({
      email,
      password,
      display_name: displayName,
    });
    // Automatically log in after registration
    const loggedInUser = await api.login({ email, password });
    setUser(loggedInUser);
    return loggedInUser;
  };

  const logout = async (): Promise<void> => {
    try {
      await api.logout();
    } finally {
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        refresh,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    return defaultAuthContext;
  }
  return context;
}

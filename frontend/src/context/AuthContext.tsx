import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import { jwtDecode } from 'jwt-decode';
import api from '../services/api';

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  role: 'student' | 'placement_officer' | 'admin';
}

interface JwtPayload {
  user_id: number;
  role: string;
  exp: number;
}

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;          // ← NEW: true while restoring session
  login: (email: string, password: string) => Promise<AuthUser>;
  logout: () => void;
  register: (name: string, email: string, phone: string, password: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function isTokenValid(token: string): boolean {
  try {
    const decoded = jwtDecode<JwtPayload>(token);
    return decoded.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

function restoreSession(): { user: AuthUser; token: string } | null {
  const token = localStorage.getItem('token');
  const userJson = localStorage.getItem('user');
  if (!token || !userJson || !isTokenValid(token)) {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    return null;
  }
  try {
    const user: AuthUser = JSON.parse(userJson);
    return { user, token };
  } catch {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true); // ← starts true

  // Restore session on mount — set isLoading=false when done
  useEffect(() => {
    const session = restoreSession();
    if (session) {
      setUser(session.user);
      setToken(session.token);
    }
    setIsLoading(false); // ← always mark done
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<AuthUser> => {
    const response = await api.post('/auth/login', { email, password });
    const { token: newToken, user: userData } = response.data;

    const authUser: AuthUser = {
      id: userData.id,
      name: userData.name,
      email: userData.email,
      role: userData.role,
    };

    localStorage.setItem('token', newToken);
    localStorage.setItem('user', JSON.stringify(authUser));
    setToken(newToken);
    setUser(authUser);

    return authUser;
  }, []);

  const logout = useCallback(() => {
    if (token) {
      api.post('/auth/logout').catch(() => { });
    }
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
    window.location.assign('/');
  }, [token]);

  const register = useCallback(async (
    name: string, email: string, phone: string, password: string
  ): Promise<void> => {
    await api.post('/auth/register', { name, email, phone, password });
  }, []);

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated: !!user && !!token,
    isLoading,
    login,
    logout,
    register,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export interface CustomerSession {
  token: string;
  email: string;
  canPlay?: boolean;
  nextPlayAvailableAt?: string | null;
}

function getApiUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : '/' + path;
  if (typeof window !== 'undefined') {
    // In browser (desktop, LAN IP, or mobile), always use relative /api
    // Next.js rewrites this server-side to http://127.0.0.1:8000/api
    return `/api${cleanPath}`;
  }
  const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
  const cleanBase = base.endsWith('/') ? base.slice(0, -1) : base;
  return `${cleanBase}${cleanPath}`;
}

export async function request(path: string, options: RequestInit = {}, token?: string) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  const authToken = token || getCustomerToken();
  if (authToken) {
    headers['X-Customer-Token'] = authToken;
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const url = getApiUrl(path);
  const res = await fetch(url, {
    ...options,
    headers,
    cache: 'no-store',
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const errorMsg = data.error || data.detail || `Request failed (${res.status})`;
    const err: any = new Error(errorMsg);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export function getCustomerToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('rayara_customer_token');
}

export function getCustomerEmail(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('rayara_customer_email');
}

export function saveCustomerSession(token: string, email: string) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('rayara_customer_token', token);
  localStorage.setItem('rayara_customer_email', email);
}

export function clearCustomerSession() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('rayara_customer_token');
  localStorage.removeItem('rayara_customer_email');
}

export async function sendOtp(email: string) {
  return request('/customer/send-otp/', {
    method: 'POST',
    body: JSON.stringify({ email: email.trim().toLowerCase() }),
  });
}

export async function verifyOtp(email: string, otp: string) {
  const data = await request('/customer/verify-otp/', {
    method: 'POST',
    body: JSON.stringify({ email: email.trim().toLowerCase(), otp }),
  });
  if (data?.token) {
    saveCustomerSession(data.token, data.customer?.email || email);
  }
  return data;
}

export async function getCustomerMe(token?: string) {
  return request('/customer/me/', { method: 'GET' }, token);
}

export async function customerLogout() {
  try {
    await request('/customer/logout/', { method: 'POST' });
  } catch {
    // Ignore network error during logout
  } finally {
    clearCustomerSession();
  }
}

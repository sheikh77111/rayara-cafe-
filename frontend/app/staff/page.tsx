'use client';
import { useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export default function Staff() {
  const [user, setUser] = useState('');
  const [pass, setPass] = useState('');
  const [code, setCode] = useState('');
  const [bill, setBill] = useState('');
  const [msg, setMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [busy, setBusy] = useState(false);

  async function redeem() {
    setBusy(true);
    setMsg('');
    setErrorMsg('');
    try {
      const r = await fetch(`${API}/staff/redeem/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Basic ' + btoa(`${user}:${pass}`)
        },
        body: JSON.stringify({ code, bill_amount: bill })
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || 'Request failed');
      const custInfo = d.customer_email || d.customer_phone ? ` (${d.customer_email || d.customer_phone})` : '';
      setMsg(`✓ Coupon redeemed for Customer${custInfo}! Discount: ₹${d.discount_amount}. Collect: ₹${d.payable}.`);
      setCode('');
      setBill('');
    } catch (e: any) {
      setErrorMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen travertine-bg p-5 text-stone-900">
      <div className="max-w-md mx-auto pt-8">
        <a href="/" className="text-bronze text-sm font-semibold hover:underline flex items-center gap-1">
          ← Back to Rayara Café App
        </a>
        <div className="bg-bronze text-sand-100 rounded-3xl p-6 mt-4 shadow-backlit border border-amber-warm/30 relative overflow-hidden">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-12 h-12 rounded-full overflow-hidden border border-amber-warm/60 shadow-[0_0_12px_rgba(229,154,56,0.4)]">
              <img src="/rayara-logo.jpg" alt="Logo" className="w-full h-full object-cover scale-110" />
            </div>
            <div>
              <p className="text-amber-glow tracking-widest text-xs font-semibold backlit-glow">رايارة · RAYARA CAFÉ</p>
              <h1 className="serif text-2xl font-bold text-white">Staff Counter</h1>
            </div>
          </div>
          <p className="text-sand-200/80 text-xs mt-1">Validate and redeem customer coupons linked to their email.</p>
        </div>

        <div className="bg-white/95 rounded-2xl p-5 mt-5 space-y-3 border border-sand-300 shadow-sm">
          <label className="block text-sm font-semibold text-stone-700">
            Staff username
            <input
              className="w-full border border-sand-300 rounded-lg p-3 mt-1 outline-none focus:border-amber-warm focus:ring-2 focus:ring-amber-warm/20"
              value={user}
              onChange={e => setUser(e.target.value)}
              placeholder="e.g. staff1"
            />
          </label>
          <label className="block text-sm font-semibold text-stone-700">
            Password
            <input
              type="password"
              className="w-full border border-sand-300 rounded-lg p-3 mt-1 outline-none focus:border-amber-warm focus:ring-2 focus:ring-amber-warm/20"
              value={pass}
              onChange={e => setPass(e.target.value)}
              placeholder="••••••••"
            />
          </label>
          <label className="block text-sm font-semibold text-stone-700">
            Coupon code
            <input
              className="w-full border border-sand-300 rounded-lg p-3 mt-1 uppercase font-mono tracking-wider outline-none focus:border-amber-warm focus:ring-2 focus:ring-amber-warm/20"
              value={code}
              onChange={e => setCode(e.target.value.toUpperCase())}
              placeholder="RAYA-XXXX"
            />
          </label>
          <label className="block text-sm font-semibold text-stone-700">
            Bill amount (₹)
            <input
              type="number"
              className="w-full border border-sand-300 rounded-lg p-3 mt-1 outline-none focus:border-amber-warm focus:ring-2 focus:ring-amber-warm/20"
              value={bill}
              onChange={e => setBill(e.target.value)}
              placeholder="250"
            />
          </label>
          <button
            disabled={busy || !user || !pass || !code || !bill}
            onClick={redeem}
            className="w-full bg-bronze hover:bg-bronze-light text-sand-50 rounded-xl p-4 font-bold disabled:opacity-50 shadow-backlit hover:opacity-95 transition border border-amber-warm/40"
          >
            {busy ? 'Processing…' : 'Validate & Redeem'}
          </button>

          {msg && (
            <div className="bg-olive-bg text-olive-dark border border-olive/30 p-3.5 rounded-xl text-sm font-medium">
              {msg}
            </div>
          )}
          {errorMsg && (
            <div className="bg-red-50 text-red-800 border border-red-200 p-3.5 rounded-xl text-sm">
              {errorMsg}
            </div>
          )}
        </div>
        <p className="text-xs text-stone-500 mt-4 text-center">
          Use staff credentials created by the owner. Counter access requires authorized login.
        </p>
      </div>
    </main>
  );
}

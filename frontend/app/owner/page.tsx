'use client';
import { useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export default function Owner() {
  const [user, setUser] = useState('');
  const [pass, setPass] = useState('');
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setError('');
    try {
      const r = await fetch(`${API}/admin/dashboard/`, {
        headers: { 'Authorization': 'Basic ' + btoa(`${user}:${pass}`) }
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || 'Owner login failed');
      setData(d);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen travertine-bg p-5 text-stone-900">
      <div className="max-w-xl mx-auto pt-8">
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
              <h1 className="serif text-2xl font-bold text-white">Owner Dashboard</h1>
            </div>
          </div>
          <p className="text-sand-200/80 text-xs mt-1">Private business analytics & customer rewards performance.</p>
        </div>

        <div className="bg-white/95 rounded-2xl p-5 mt-5 space-y-3 border border-sand-300 shadow-sm">
          <label className="block text-sm font-semibold text-stone-700">
            Owner username
            <input
              className="w-full border border-sand-300 rounded-lg p-3 mt-1 outline-none focus:border-amber-warm focus:ring-2 focus:ring-amber-warm/20"
              value={user}
              onChange={e => setUser(e.target.value)}
              placeholder="e.g. admin"
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
          <button
            onClick={load}
            disabled={busy || !user || !pass}
            className="w-full bg-bronze hover:bg-bronze-light text-sand-50 rounded-xl p-4 font-bold disabled:opacity-50 shadow-backlit hover:opacity-95 transition border border-amber-warm/40"
          >
            {busy ? 'Loading…' : 'Sign in & View Dashboard'}
          </button>
          {error && <p className="text-red-700 text-sm mt-2">{error}</p>}
        </div>

        {data && (
          <div className="mt-6 space-y-4">
            <div className="grid grid-cols-2 gap-3">
              {[
                ['Total Plays', data.total_plays],
                ['Registered Customers', data.unique_customers || 0],
                ['Coupons Issued', data.coupons_issued],
                ['Coupons Redeemed', data.coupons_redeemed],
                ['Total Discount Given', `₹${data.discount_given}`],
                ['Active Unused Coupons', Math.max(0, (data.coupons_issued || 0) - (data.coupons_redeemed || 0))],
              ].map(([k, v]) => (
                <div key={String(k)} className="bg-white/95 rounded-2xl p-4 border border-sand-300 shadow-sm">
                  <p className="text-stone-500 text-xs font-semibold">{k}</p>
                  <p className="text-bronze text-2xl font-bold mt-1">{v}</p>
                </div>
              ))}
            </div>

            {data.recent_redemptions && data.recent_redemptions.length > 0 && (
              <div className="bg-white/95 rounded-2xl p-4 border border-sand-300 shadow-sm">
                <h3 className="font-bold text-bronze text-sm mb-3">Recent Redemptions</h3>
                <div className="divide-y text-xs">
                  {data.recent_redemptions.map((r: any, idx: number) => (
                    <div key={idx} className="py-2.5 flex justify-between items-center">
                      <div>
                        <span className="font-semibold text-stone-800">
                          {r.coupon__customer_email || r.coupon__phone_number || 'Customer'}
                        </span>
                        <p className="text-stone-400 text-[10px]">
                          {new Date(r.redeemed_at).toLocaleString('en-IN')}
                        </p>
                      </div>
                      <div className="text-right">
                        <span className="text-olive font-bold">
                          -₹{r.discount_amount}
                        </span>
                        <p className="text-stone-500 text-[10px]">
                          Bill: ₹{r.bill_amount}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

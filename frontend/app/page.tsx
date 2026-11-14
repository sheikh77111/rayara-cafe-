'use client';

import { useEffect, useState, useMemo, useRef } from 'react';
import {
  Coffee, Utensils, Gift, Ticket, ArrowRight, Gamepad2, RotateCw,
  Sparkles, ChevronLeft, Mail, ShieldCheck, CheckCircle2, Clock,
  LogOut, AlertCircle, X, KeyRound, ExternalLink, HeartCrack, Check,
  FileText, Receipt, QrCode
} from 'lucide-react';
import {
  request, sendOtp, verifyOtp, getCustomerMe, customerLogout, getCustomerBills,
  getCustomerToken, getCustomerEmail, clearCustomerSession
} from '../lib/api';

type Screen = 'home' | 'menu' | 'games' | 'play' | 'coupon' | 'rewards' | 'bills';

interface CustomerState {
  isLoggedIn: boolean;
  email: string;
  canPlay: boolean;
  nextPlayAvailableAt: string | null;
}

interface CouponItem {
  id: number;
  code: string;
  percentage: number;
  minimum_spend: string;
  max_discount: string;
  issued_at: string;
  valid_from: string;
  expires_at: string;
  status: string;
}

interface PlayResult {
  game: string;
  reward: number;
  is_unlucky?: boolean;
  coupon_code?: string | null;
  coupon?: CouponItem | null;
  can_play?: boolean;
  next_play_available_at?: string;
  message?: string;
}

// Exactly 20 options matching Rayara Backlit Bronze & Travertine Theme:
// Below 10% (88% chance): 6 of 1% (35%), 4 of 2% (22%), 2 of 3% (12%), 1 of 5% (8%), 1 of 8% (6%), 1 of Unlucky (5%)
// 10% & Above (12% chance): 1 of 10% (4%), 1 of 12% (3%), 1 of 15% (2%), 1 of 20% (1%), 1 of 25% ★ (2% Rare Jackpot)
interface Slice {
  id: number;
  label: string;
  value: number;
  color: string;
  textColor: string;
  isRare?: boolean;
}

const WHEEL_SLICES: Slice[] = [
  { id: 0, label: '1%', value: 1, color: '#f7f1e8', textColor: '#2a1810' },
  { id: 1, label: '5%', value: 5, color: '#4e5d42', textColor: '#ffffff' }, // Mediterranean Olive
  { id: 2, label: '2%', value: 2, color: '#9e6b52', textColor: '#ffffff' }, // Terracotta Clay
  { id: 3, label: '8%', value: 8, color: '#382013', textColor: '#f5a623' }, // Deep Bronze & Amber
  { id: 4, label: '1%', value: 1, color: '#f7f1e8', textColor: '#2a1810' },
  { id: 5, label: '3%', value: 3, color: '#b87556', textColor: '#ffffff' }, // Warm Terracotta
  { id: 6, label: '12%', value: 12, color: '#5c6e4e', textColor: '#ffffff' }, // Olive Leaf
  { id: 7, label: '2%', value: 2, color: '#9e6b52', textColor: '#ffffff' }, // Terracotta Clay
  { id: 8, label: '1%', value: 1, color: '#f7f1e8', textColor: '#2a1810' },
  { id: 9, label: '10%', value: 10, color: '#634832', textColor: '#f5e6d3' }, // Rich Bronze
  { id: 10, label: '25% ★', value: 25, color: '#e59a38', textColor: '#1c100a', isRare: true }, // Backlit Gold (2% Rare Jackpot)
  { id: 11, label: '1%', value: 1, color: '#f7f1e8', textColor: '#2a1810' },
  { id: 12, label: '2%', value: 2, color: '#9e6b52', textColor: '#ffffff' }, // Terracotta Clay
  { id: 13, label: '15%', value: 15, color: '#d97d26', textColor: '#ffffff' }, // Radiant Amber
  { id: 14, label: '1%', value: 1, color: '#f7f1e8', textColor: '#2a1810' },
  { id: 15, label: '3%', value: 3, color: '#b87556', textColor: '#ffffff' }, // Warm Terracotta
  { id: 16, label: '20%', value: 20, color: '#c26514', textColor: '#ffffff' }, // Deep Amber
  { id: 17, label: '2%', value: 2, color: '#9e6b52', textColor: '#ffffff' }, // Terracotta Clay
  { id: 18, label: 'Unlucky', value: 0, color: '#1e1109', textColor: '#dfd2c0' }, // Dark Espresso (5%)
  { id: 19, label: '1%', value: 1, color: '#f7f1e8', textColor: '#2a1810' },
];

export default function Home() {
  const [screen, setScreen] = useState<Screen>('home');
  const [menu, setMenu] = useState<any[]>([]);
  const [game, setGame] = useState('spin');
  const [result, setResult] = useState<PlayResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [coupons, setCoupons] = useState<CouponItem[]>([]);
  const [scratch, setScratch] = useState(false);
  const [answer, setAnswer] = useState('');
  const [bills, setBills] = useState<any[]>([]);
  const [tableParam, setTableParam] = useState<string>('');

  // Wheel Physics State
  const [wheelRotation, setWheelRotation] = useState(0);
  const [isSpinning, setIsSpinning] = useState(false);
  const [spinWonBanner, setSpinWonBanner] = useState<{ title: string; subtitle: string } | null>(null);
  const spinCountRef = useRef(0);

  // Customer auth state (Email based)
  const [customer, setCustomer] = useState<CustomerState>({
    isLoggedIn: false,
    email: '',
    canPlay: true,
    nextPlayAvailableAt: null,
  });

  // Login Modal State
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [otpStep, setOtpStep] = useState<'email' | 'otp'>('email');
  const [inputEmail, setInputEmail] = useState('');
  const [inputOtp, setInputOtp] = useState('');
  const [otpLoading, setOtpLoading] = useState(false);
  const [otpError, setOtpError] = useState('');
  const [otpSuccessMsg, setOtpSuccessMsg] = useState('');
  const [cooldownSecs, setCooldownSecs] = useState(0);

  // Pending action after login
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  // Initialize customer session on load & detect table QR
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const tbl = params.get('table');
      if (tbl) {
        const cleanT = tbl.toUpperCase().startsWith('T') ? tbl.toUpperCase() : `T${tbl}`;
        setTableParam(cleanT);
        sessionStorage.setItem('rayara_table', cleanT);
      } else {
        const saved = sessionStorage.getItem('rayara_table');
        if (saved) setTableParam(saved);
      }
    }

    const token = getCustomerToken();
    const email = getCustomerEmail();
    if (token && email) {
      setCustomer(prev => ({ ...prev, isLoggedIn: true, email }));
      getCustomerMe(token)
        .then(data => {
          if (data?.customer) {
            setCustomer({
              isLoggedIn: true,
              email: data.customer.email,
              canPlay: data.customer.can_play,
              nextPlayAvailableAt: data.customer.next_play_available_at,
            });
          }
        })
        .catch(() => {
          clearCustomerSession();
          setCustomer({ isLoggedIn: false, email: '', canPlay: true, nextPlayAvailableAt: null });
        });
    }
  }, []);

  // Cooldown timer for OTP resend
  useEffect(() => {
    if (cooldownSecs <= 0) return;
    const interval = setInterval(() => {
      setCooldownSecs(s => Math.max(0, s - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [cooldownSecs]);

  // Compute remaining time until next play
  const timeUntilPlay = useMemo(() => {
    if (customer.canPlay || !customer.nextPlayAvailableAt) return null;
    const diff = new Date(customer.nextPlayAvailableAt).getTime() - Date.now();
    if (diff <= 0) return 'Available now';
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    return `${hours}h ${mins}m`;
  }, [customer.canPlay, customer.nextPlayAvailableAt]);

  async function openMenu() {
    setError('');
    try {
      const d = await request('/menu/');
      setMenu(d);
      setScreen('menu');
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function openRewards() {
    setError('');
    if (!customer.isLoggedIn) {
      setPendingAction('rewards');
      setShowLoginModal(true);
      return;
    }
    try {
      const d = await request('/coupons/');
      setCoupons(d);
      setScreen('rewards');
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function openBills() {
    setError('');
    if (!customer.isLoggedIn) {
      setPendingAction('bills');
      setShowLoginModal(true);
      return;
    }
    try {
      const d = await getCustomerBills(customer.email);
      setBills(d);
      setScreen('bills');
    } catch (e: any) {
      setError(e.message);
    }
  }

  function handlePlayClick(gameKey?: string) {
    setError('');
    if (!customer.isLoggedIn) {
      setPendingAction(gameKey ? `play:${gameKey}` : 'games');
      setShowLoginModal(true);
      return;
    }
    if (gameKey) {
      setGame(gameKey);
      setResult(null);
      setScreen('play');
    } else {
      setScreen('games');
    }
  }

  async function handleSendOtp() {
    setOtpError('');
    setOtpSuccessMsg('');
    const cleaned = inputEmail.trim().toLowerCase();
    if (!cleaned || !cleaned.includes('@') || !cleaned.includes('.')) {
      setOtpError('Please enter a valid email address (e.g. yourname@gmail.com).');
      return;
    }
    setOtpLoading(true);
    try {
      const res = await sendOtp(cleaned);
      setOtpStep('otp');
      setOtpSuccessMsg(res.message || 'Verification code sent to your email!');
      setCooldownSecs(30);
    } catch (e: any) {
      setOtpError(e.message || 'Failed to send verification code.');
    } finally {
      setOtpLoading(false);
    }
  }

  async function handleVerifyOtp() {
    setOtpError('');
    if (!inputOtp || inputOtp.trim().length < 4) {
      setOtpError('Please enter the 6-digit code sent to your email.');
      return;
    }
    setOtpLoading(true);
    try {
      const cleaned = inputEmail.trim().toLowerCase();
      const res = await verifyOtp(cleaned, inputOtp.trim());
      const custData = res.customer;
      setCustomer({
        isLoggedIn: true,
        email: custData.email,
        canPlay: custData.can_play,
        nextPlayAvailableAt: custData.next_play_available_at,
      });
      setShowLoginModal(false);
      setOtpStep('email');
      setInputOtp('');

      if (pendingAction === 'games') {
        setScreen('games');
      } else if (pendingAction?.startsWith('play:')) {
        const key = pendingAction.split(':')[1];
        setGame(key);
        setResult(null);
        setScreen('play');
      } else if (pendingAction === 'rewards') {
        const d = await request('/coupons/');
        setCoupons(d);
        setScreen('rewards');
      } else if (pendingAction === 'bills') {
        const b = await getCustomerBills(custData.email);
        setBills(b);
        setScreen('bills');
      }
      setPendingAction(null);
    } catch (e: any) {
      setOtpError(e.message || 'Verification failed. Please try again.');
    } finally {
      setOtpLoading(false);
    }
  }

  async function handleLogout() {
    await customerLogout();
    setCustomer({ isLoggedIn: false, email: '', canPlay: true, nextPlayAvailableAt: null });
    setScreen('home');
    setError('');
  }

  async function playGame(key: string) {
    if (!customer.isLoggedIn) {
      setPendingAction(`play:${key}`);
      setShowLoginModal(true);
      return;
    }

    if (!customer.canPlay) {
      setError(`This email has already played. Next play available in ${timeUntilPlay || '24 hours'}.`);
      return;
    }

    setGame(key);
    setError('');
    setLoading(true);

    try {
      const d: PlayResult = await request('/game/play/', {
        method: 'POST',
        body: JSON.stringify({
          game: key,
          answer: key === 'quiz' ? answer : undefined,
        }),
      });

      // Special Physics Animation for Lucky Spin!
      if (key === 'spin') {
        setIsSpinning(true);
        const matchingSlices = WHEEL_SLICES.filter(s => s.value === d.reward);
        const targetSlice = matchingSlices.length > 0
          ? matchingSlices[Math.floor(Math.random() * matchingSlices.length)]
          : WHEEL_SLICES[0];

        // Needle is at top (12 o'clock, 270 deg)
        // Slice i center is at i * 18 + 9
        const sliceCenter = targetSlice.id * 18 + 9;
        const targetStopAngle = (270 - sliceCenter + 360) % 360;

        spinCountRef.current += 1;
        const currentAngle = wheelRotation % 360;
        const delta = (targetStopAngle - currentAngle + 360) % 360;
        const extraRotations = 360 * (6 + (spinCountRef.current % 2));
        const newRotation = wheelRotation + extraRotations + delta;

        setWheelRotation(newRotation);

        // Wait 4.5 seconds for wheel deceleration and landing
        setTimeout(() => {
          setIsSpinning(false);
          setLoading(false);
          setResult(d);
          setCustomer(prev => ({
            ...prev,
            canPlay: false,
            nextPlayAvailableAt: d.next_play_available_at || null,
          }));
          if (d.coupon && typeof window !== 'undefined') {
            localStorage.setItem('rayara_coupon_' + d.coupon.id, d.coupon_code || '');
          }

          // Show celebration badge over the wheel
          if (d.reward > 0) {
            setSpinWonBanner({
              title: `🎉 ${d.reward}% DISCOUNT WON!`,
              subtitle: `Landed on slice ${targetSlice.label}. Coupon ready!`,
            });
          } else {
            setSpinWonBanner({
              title: `💔 Unlucky This Time`,
              subtitle: `Landed on Unlucky slice. Play again in 24 hours!`,
            });
          }

          // Transition to coupon card after 2 seconds
          setTimeout(() => {
            setSpinWonBanner(null);
            setScreen('coupon');
          }, 2000);
        }, 4500);
        return;
      }

      // Mystery Scratch & Quiz (Immediate)
      setResult(d);
      setCustomer(prev => ({
        ...prev,
        canPlay: false,
        nextPlayAvailableAt: d.next_play_available_at || null,
      }));
      if (d.coupon && typeof window !== 'undefined') {
        localStorage.setItem('rayara_coupon_' + d.coupon.id, d.coupon_code || '');
      }
      setScreen('coupon');
    } catch (e: any) {
      setError(e.message);
      if (e.status === 429) {
        setCustomer(prev => ({
          ...prev,
          canPlay: false,
          nextPlayAvailableAt: e.data?.next_play_available_at || prev.nextPlayAvailableAt,
        }));
      }
      setScreen('play');
    } finally {
      if (key !== 'spin') {
        setLoading(false);
      }
    }
  }

  const back = () => {
    setError('');
    setScreen('home');
  };

  return (
    <main className="min-h-screen pb-16 travertine-bg text-stone-900">
      {/* Header with Rayara Illuminated Backlit Sign Theme */}
      <header className="bg-bronze text-sand-100 px-5 pt-7 pb-6 rounded-b-[36px] shadow-backlit border-b-2 border-amber-warm/40 relative overflow-hidden">
        {/* Subtle Ambient Backlight Halo Circles */}
        <div className="absolute -right-16 -top-16 w-56 h-56 rounded-full bg-amber-warm/10 blur-2xl pointer-events-none" />
        <div className="absolute -left-16 top-10 w-44 h-44 rounded-full bg-amber-glow/10 blur-xl pointer-events-none" />

        <div className="relative max-w-xl mx-auto text-center">
          {/* Authentic Illuminated Signage Emblem */}
          <div className="relative mx-auto w-24 h-24 rounded-full overflow-hidden border-2 border-amber-warm/80 shadow-[0_0_28px_rgba(229,154,56,0.55)] mb-3 bg-[#1e1109] group">
            <img
              src="/rayara-logo.jpg"
              alt="Rayara Café Signage"
              className="w-full h-full object-cover scale-110 group-hover:scale-125 transition duration-500"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent pointer-events-none" />
          </div>

          {/* Arabic Calligraphy matching the Backlit Sign */}
          <div className="text-amber-glow text-3xl font-bold mb-0.5 backlit-glow tracking-wide select-none">
            رايارة
          </div>

          {/* High-Contrast Serif Brand Title */}
          <div className="serif tracking-[0.26em] text-3xl font-bold text-white drop-shadow-[0_2px_10px_rgba(0,0,0,0.8)]">
            RAYARA
          </div>

          {/* Subtitle with dashes */}
          <div className="text-amber-warm tracking-[0.55em] text-xs font-semibold mt-1">
            — C A F É —
          </div>

          <div className="goldline my-3.5 max-w-xs mx-auto" />
          <p className="serif text-xl font-light text-sand-100/90 italic">Good food. Great moments.</p>
          <div className="flex items-center justify-center gap-2 text-sand-200/80 text-[11px] mt-1 tracking-wider uppercase">
            <span>🌿 Freshly made</span>
            <span>•</span>
            <span>Warmly served</span>
            <span>•</span>
            <span>Daily Rewards</span>
          </div>

          {/* Customer Auth Ribbon in Header */}
          <div className="mt-4 pt-3 border-t border-amber-warm/20 flex items-center justify-between text-xs">
            {customer.isLoggedIn ? (
              <div className="flex items-center justify-between w-full bg-black/40 backdrop-blur-md rounded-full px-4 py-2 border border-amber-warm/40 shadow-sm">
                <div className="flex items-center gap-2 text-left truncate max-w-[280px]">
                  <Mail size={14} className="text-amber-warm shrink-0" />
                  <span className="font-semibold text-sand-100 truncate">{customer.email}</span>
                  {customer.canPlay ? (
                    <span className="bg-olive text-sand-50 text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 shrink-0 border border-olive-light/50">
                      <Sparkles size={10} /> 1 Play Ready
                    </span>
                  ) : (
                    <span className="bg-[#422213] text-amber-warm text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1 shrink-0 border border-amber-warm/30">
                      <Clock size={10} /> Played ({timeUntilPlay})
                    </span>
                  )}
                </div>
                <button
                  onClick={handleLogout}
                  className="text-sand-300 hover:text-white flex items-center gap-1 ml-2 text-[11px] underline shrink-0 transition"
                >
                  <LogOut size={12} /> Logout
                </button>
              </div>
            ) : (
              <button
                onClick={() => {
                  setPendingAction(null);
                  setShowLoginModal(true);
                }}
                className="w-full flex items-center justify-center gap-2 bg-amber-warm/20 hover:bg-amber-warm/30 text-amber-glow border border-amber-warm/50 rounded-full py-2.5 px-4 transition font-semibold shadow-sm"
              >
                <Mail size={14} />
                <span>Sign in with Email</span>
                <span className="text-[10px] bg-amber-warm text-bronze-dark font-bold px-2 py-0.5 rounded-full ml-1">
                  1 Play / 24h
                </span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="max-w-xl mx-auto px-4">
        {screen !== 'home' && (
          <button onClick={back} className="mt-5 flex items-center gap-1.5 text-bronze text-sm font-semibold hover:text-amber-deep transition">
            <ChevronLeft size={18} /> Back to Home
          </button>
        )}

        {error && (
          <div className="mt-4 rounded-2xl border border-red-300 bg-red-50/90 p-3.5 text-sm text-red-900 flex items-start gap-2 shadow-sm">
            <AlertCircle size={18} className="shrink-0 mt-0.5 text-red-600" />
            <div>{error}</div>
          </div>
        )}

        {/* HOME SCREEN */}
        {screen === 'home' && (
          <>
            {/* Real Rayara Illuminated Wall Sign Showcase Banner */}
            <div className="mt-5 rounded-3xl overflow-hidden shadow-backlit border border-sand-300 relative group">
              <div className="relative h-56 w-full overflow-hidden bg-bronze">
                <img
                  src="/rayara-sign.jpg"
                  alt="Rayara Café Wall Sign"
                  className="w-full h-full object-cover object-center group-hover:scale-105 transition duration-700"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/40 to-transparent" />
                <div className="absolute bottom-0 left-0 right-0 p-5 text-sand-50">
                  <div className="inline-flex items-center gap-1.5 bg-amber-warm/90 text-bronze-dark text-[10px] font-bold px-2.5 py-0.5 rounded-full mb-2 uppercase tracking-wider">
                    <Sparkles size={11} /> Mediterranean Sanctuary
                  </div>
                  <h2 className="serif text-2xl font-bold text-white drop-shadow">A little taste of happiness</h2>
                  <p className="text-xs text-sand-200 mt-0.5">
                    Shawarma, grills, artisanal drinks & 20 daily wheel surprises.
                  </p>
                </div>
              </div>
            </div>

            {/* Play Status Alert on Home */}
            {customer.isLoggedIn && !customer.canPlay && (
              <div className="mt-4 bg-amber-50 border border-amber-300 rounded-2xl p-4 flex items-center gap-3">
                <Clock className="text-amber-700 shrink-0" size={24} />
                <div className="text-xs text-amber-900">
                  <b>Daily play recorded for {customer.email}.</b>
                  <p className="text-amber-700 mt-0.5">
                    Each email can play once every 24 hours. Your next play unlocks in <b>{timeUntilPlay || '24h'}</b>.
                  </p>
                </div>
              </div>
            )}

            <div className="grid gap-3 mt-5">
              <button
                onClick={openMenu}
                className="bg-white rounded-2xl p-5 flex items-center gap-4 text-left shadow-sm border border-[#eadcc9] hover:border-gold/60 transition"
              >
                <span className="bg-cream p-3 rounded-xl text-wine"><Utensils /></span>
                <span className="flex-1">
                  <b className="block text-wine text-base">Explore Menu</b>
                  <small className="text-stone-500">Shawarma, grills, evening snacks, tea & coffee</small>
                </span>
                <ArrowRight className="text-gold" />
              </button>

              <button
                onClick={() => handlePlayClick()}
                className="bg-wine text-cream rounded-2xl p-5 flex items-center gap-4 text-left shadow-glow hover:opacity-95 transition relative overflow-hidden"
              >
                <div className="absolute right-0 top-0 bottom-0 w-24 bg-gradient-to-l from-gold/10 to-transparent pointer-events-none" />
                <span className="bg-white/10 p-3 rounded-xl text-gold"><Gamepad2 /></span>
                <span className="flex-1">
                  <div className="flex items-center gap-2">
                    <b className="text-base">Play & Win</b>
                    <span className="bg-gold text-wine text-[10px] font-bold px-2 py-0.5 rounded-full">
                      20 Wheel Options
                    </span>
                  </div>
                  <small className="text-cream/80 block mt-0.5">
                    {customer.isLoggedIn && !customer.canPlay
                      ? `Played today • Next in ${timeUntilPlay || '24h'}`
                      : 'Spin the 20-slice wheel: win up to 25% off next visit'}
                  </small>
                </span>
                <ArrowRight className="text-gold" />
              </button>

              <button
                onClick={openRewards}
                className="bg-white rounded-2xl p-5 flex items-center gap-4 text-left shadow-sm border border-[#eadcc9] hover:border-gold/60 transition"
              >
                <span className="bg-cream p-3 rounded-xl text-wine"><Ticket /></span>
                <span className="flex-1">
                  <b className="block text-wine text-base">My Rewards</b>
                  <small className="text-stone-500">
                    {customer.isLoggedIn
                      ? `Saved coupons for ${customer.email}`
                      : 'Sign in to view coupons saved to your email'}
                  </small>
                </span>
                <ArrowRight className="text-gold" />
              </button>

              <button
                onClick={openBills}
                className="bg-white rounded-2xl p-5 flex items-center gap-4 text-left shadow-sm border border-[#eadcc9] hover:border-gold/60 transition"
              >
                <span className="bg-cream p-3 rounded-xl text-wine"><FileText /></span>
                <span className="flex-1">
                  <b className="block text-wine text-base">My Digital Bills</b>
                  <small className="text-stone-500">
                    {customer.isLoggedIn
                      ? `View past dining receipts & invoices for ${customer.email}`
                      : 'Sign in to view your dining receipts'}
                  </small>
                </span>
                <ArrowRight className="text-gold" />
              </button>
            </div>

            {/* Admin & Staff Portal Dedicated Links */}
            <div className="mt-8 border-t border-[#eadcc9] pt-4 flex flex-wrap items-center justify-center gap-3 text-[11px] text-stone-500">
              <a
                href="http://localhost:8000/pos/tablet/"
                target="_blank"
                rel="noreferrer"
                className="hover:text-wine font-semibold flex items-center gap-1 bg-cream/70 px-2.5 py-1 rounded-full border border-sand-300"
              >
                <ExternalLink size={11} /> Staff Tablet POS
              </a>
              <span>•</span>
              <a
                href="http://localhost:8000/pos/billing/"
                target="_blank"
                rel="noreferrer"
                className="hover:text-wine font-semibold flex items-center gap-1 bg-cream/70 px-2.5 py-1 rounded-full border border-sand-300"
              >
                <ExternalLink size={11} /> Billing Counter
              </a>
              <span>•</span>
              <a
                href="http://localhost:8000/pos/admin/"
                target="_blank"
                rel="noreferrer"
                className="hover:text-wine font-semibold flex items-center gap-1 bg-cream/70 px-2.5 py-1 rounded-full border border-sand-300"
              >
                <ExternalLink size={11} /> Owner Analytics
              </a>
            </div>

            <p className="text-center text-xs text-stone-400 mt-2">
              Scan QR • Sign In Email • Play Once Daily • Enjoy Fresh Delights
            </p>
          </>
        )}

        {/* MENU SCREEN */}
        {screen === 'menu' && (
          <section className="mt-5">
            <h1 className="serif text-3xl text-wine font-bold">Our Menu</h1>
            <p className="text-stone-500 text-sm mt-1">Made fresh, served with care.</p>
            {menu.map((cat: any) => (
              <div key={cat.id} className="mt-6 bg-white p-5 rounded-2xl border border-[#eadcc9] shadow-sm">
                <h2 className="font-bold text-wine text-lg border-b border-gold/40 pb-2 flex items-center justify-between">
                  <span>{cat.name}</span>
                  <span className="text-xs text-gold font-normal">{cat.items.length} items</span>
                </h2>
                <div className="divide-y divide-[#eadcc9]">
                  {cat.items.map((item: any) => (
                    <div key={item.id} className="py-3.5 flex justify-between gap-3 items-center">
                      <div>
                        <b className="text-stone-900">{item.name}</b>
                        {item.description && (
                          <p className="text-xs text-stone-500 mt-0.5">{item.description}</p>
                        )}
                      </div>
                      <b className="text-wine whitespace-nowrap text-base">₹{item.price}</b>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            <p className="text-xs text-stone-500 mt-4 text-center">
              Prices and availability are confirmed at the café counter.
            </p>
          </section>
        )}

        {/* GAMES SELECTION SCREEN */}
        {screen === 'games' && (
          <section className="mt-5">
            <h1 className="serif text-3xl text-wine font-bold">Choose your game</h1>
            <p className="text-sm text-stone-500 mt-1">
              Select one game to play. Each email address gets <b>1 play every 24 hours</b>.
            </p>

            {/* Play Status Notice */}
            {!customer.canPlay && (
              <div className="mt-4 bg-amber-50 border border-amber-300 rounded-2xl p-4 text-amber-900 text-xs">
                <p className="font-bold flex items-center gap-1.5 text-sm">
                  <Clock size={16} /> Daily Play Limit Reached
                </p>
                <p className="mt-1">
                  Email <b>{customer.email}</b> has already played in the last 24 hours.
                </p>
                <p className="mt-1 text-amber-800">
                  Next play unlocks in <b>{timeUntilPlay || '24 hours'}</b>.
                </p>
                <button
                  onClick={openRewards}
                  className="mt-3 inline-block bg-amber-800 text-cream px-3 py-1.5 rounded-lg font-semibold text-xs"
                >
                  View Won Rewards
                </button>
              </div>
            )}

            <div className="grid gap-3 mt-5">
              {[
                { key: 'spin', name: 'Lucky Spin (20 Options)', desc: '20 slices: 1%, 2%, 3%, 5%, 8%, 10%, 12%, 15%, 20%, 25% or Unlucky', icon: <RotateCw /> },
                { key: 'scratch', name: 'Mystery Scratch', desc: 'Scratch the card to reveal your surprise', icon: <Sparkles /> },
                { key: 'quiz', name: 'Rayara Food Quiz', desc: 'Answer a quick food question to win', icon: <Gift /> },
              ].map(g => (
                <button
                  key={g.key}
                  onClick={() => handlePlayClick(g.key)}
                  className={`p-5 rounded-2xl bg-white border border-[#eadcc9] flex gap-4 items-center text-left transition shadow-sm ${
                    !customer.canPlay ? 'opacity-70' : 'hover:border-gold hover:shadow-md'
                  }`}
                >
                  <span className="p-3 bg-cream rounded-xl text-wine">{g.icon}</span>
                  <span className="flex-1">
                    <b className="text-wine text-base">{g.name}</b>
                    <small className="block text-stone-500">{g.desc}</small>
                  </span>
                  <ArrowRight className="text-gold" />
                </button>
              ))}
            </div>

            <div className="mt-6 bg-[#eee4d6] rounded-2xl p-4 text-xs text-stone-600 space-y-1">
              <p className="font-semibold text-stone-800 flex items-center gap-1">
                <ShieldCheck size={14} className="text-wine" /> Verified Wheel Probabilities
              </p>
              <p>
                • <b>Win Rates</b>: Below 10%: 88% chance (1%: 35%, 2%: 22%, 3%: 12%, 5%: 8%, 8%: 6%, Unlucky: 5%). 10% &amp; Above: 12% chance (10%: 4%, 12%: 3%, 15%: 2%, 20%: 1%, 25% ★: 2%).
              </p>
              <p>
                • <b>20 Total Slices</b>: 6× 1%, 4× 2%, 2× 3%, 1× 5%, 1× Unlucky, 1× 8%, 1× 10%, 1× 12%, 1× 15%, 1× 20%, 1× 25% ★ (Rare Jackpot).
              </p>
            </div>
          </section>
        )}

        {/* PLAY SCREEN */}
        {screen === 'play' && (
          <section className="mt-5">
            <div className="bg-bronze rounded-3xl p-6 text-sand-100 text-center shadow-backlit relative border border-amber-warm/30">
              <div className="text-amber-glow tracking-widest text-xs font-semibold backlit-glow">RAYARA PLAY & DINE</div>
              <h1 className="serif text-3xl mt-2 font-bold text-white drop-shadow">
                {game === 'spin' ? 'Lucky Spin' : game === 'scratch' ? 'Mystery Scratch' : 'Food Quiz'}
              </h1>

              {/* Already played warning */}
              {!customer.canPlay && (
                <div className="mt-4 bg-[#3a1e12] border border-amber-warm/40 rounded-xl p-3 text-xs text-amber-200 text-left flex items-start gap-2 shadow-inner">
                  <Clock size={16} className="shrink-0 mt-0.5 text-amber-glow" />
                  <div>
                    <b>Daily Play Limit:</b> Email <b>{customer.email}</b> already played. Next chance in <b>{timeUntilPlay}</b>.
                  </div>
                </div>
              )}

              {/* 20-OPTION INTERACTIVE REAL SVG SPIN WHEEL */}
              {game === 'spin' && (
                <div className="relative mx-auto my-6 w-80 h-80 flex items-center justify-center">
                  {/* Top Pointer Needle at 12 o'clock pointing down */}
                  <div className={`absolute top-0 left-1/2 -translate-x-1/2 -mt-1 z-30 filter drop-shadow(0 3px 6px rgba(0,0,0,0.6)) ${isSpinning ? 'needle-ticking' : ''}`}>
                    <svg width="34" height="38" viewBox="0 0 34 38">
                      <polygon points="17,36 3,4 31,4" fill="#e59a38" stroke="#1c100a" strokeWidth="2.5" />
                      <circle cx="17" cy="11" r="4" fill="#1c100a" />
                    </svg>
                  </div>

                  {/* Outer Golden & Bronze Rim */}
                  <div className="w-[316px] h-[316px] rounded-full p-2 bg-gradient-to-tr from-[#3a2214] via-[#e59a38] to-[#1c100a] shadow-backlit-lg flex items-center justify-center border-4 border-[#1c100a]">
                    {/* SVG Wheel with 20 Slices */}
                    <div
                      style={{
                        transform: `rotate(${wheelRotation}deg)`,
                        transition: 'transform 4.5s cubic-bezier(0.15, 0.9, 0.2, 1.0)',
                        willChange: 'transform',
                      }}
                      className="w-[290px] h-[290px] rounded-full overflow-hidden"
                    >
                      <svg width="290" height="290" viewBox="0 0 320 320" className="w-full h-full select-none">
                        <circle cx="160" cy="160" r="158" fill="#1c100a" />
                        {WHEEL_SLICES.map((slice, i) => {
                          const midAngle = i * 18 + 9;
                          return (
                            <g key={slice.id} transform={`rotate(${midAngle}, 160, 160)`}>
                              {/* 18 deg slice path */}
                              <path
                                d="M 160 160 L 308.15 136.53 A 150 150 0 0 1 308.15 183.47 Z"
                                fill={slice.color}
                                stroke="#2a1810"
                                strokeWidth="1"
                              />
                              {/* Radial text label */}
                              <text
                                x="245"
                                y="164"
                                textAnchor="middle"
                                fill={slice.textColor}
                                fontSize={slice.value === 0 ? "9" : slice.isRare ? "12" : "11"}
                                fontWeight={slice.isRare ? "900" : "bold"}
                                fontFamily="sans-serif"
                                letterSpacing={slice.value === 0 ? "-0.5px" : "0px"}
                              >
                                {slice.label}
                              </text>
                            </g>
                          );
                        })}
                        {/* Outer circular gold border ring */}
                        <circle cx="160" cy="160" r="150" fill="none" stroke="#e59a38" strokeWidth="3" />
                      </svg>
                    </div>

                    {/* Center Hub with Rayara Calligraphy & Glow */}
                    <div className="absolute w-20 h-20 rounded-full bg-gradient-to-br from-[#3a2214] to-[#1c100a] border-4 border-amber-warm shadow-[0_0_20px_rgba(229,154,56,0.5)] flex items-center justify-center z-20 pointer-events-none">
                      <div className="text-center">
                        <span className="text-amber-glow text-[11px] font-bold block leading-none backlit-glow">رايارة</span>
                        <span className="serif text-white text-[10px] font-bold tracking-widest block mt-0.5">RAYARA</span>
                        <span className="text-[8px] text-amber-warm font-semibold uppercase">{isSpinning ? 'SPIN' : 'GO'}</span>
                      </div>
                    </div>
                  </div>

                  {/* Celebration Popover when wheel lands */}
                  {spinWonBanner && (
                    <div className="absolute inset-0 z-40 bg-black/80 backdrop-blur-xs rounded-full flex flex-col items-center justify-center p-4 text-center animate-in zoom-in duration-300 border-2 border-amber-warm shadow-backlit-lg">
                      <Sparkles className="text-amber-glow mb-1 animate-bounce" size={32} />
                      <div className="serif text-xl font-bold text-amber-glow">{spinWonBanner.title}</div>
                      <div className="text-xs text-sand-100 mt-1 max-w-[200px]">{spinWonBanner.subtitle}</div>
                      <button
                        onClick={() => {
                          setSpinWonBanner(null);
                          setScreen('coupon');
                        }}
                        className="mt-3 bg-amber-warm hover:bg-amber-glow text-bronze-dark font-bold text-xs px-4 py-2 rounded-xl shadow-lg transition"
                      >
                        Claim Reward →
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* SCRATCH CARD */}
              {game === 'scratch' && (
                <button
                  onClick={() => setScratch(true)}
                  className="my-7 w-full rounded-2xl bg-gold text-wine p-10 font-bold tracking-wide shadow-md hover:bg-gold/90 transition text-base"
                >
                  {scratch ? '✨ SURPRISE REVEALED! CLICK REVEAL BELOW' : '👉 TAP & SCRATCH HERE ✦'}
                </button>
              )}

              {/* FOOD QUIZ */}
              {game === 'quiz' && (
                <div className="my-6 bg-white/10 p-5 rounded-2xl text-left">
                  <p className="font-semibold text-sm">
                    Which delicious item is traditionally cooked on a vertical rotisserie?
                  </p>
                  <div className="grid gap-2 mt-4">
                    {['Shawarma', 'Samosa', 'Tea'].map(a => (
                      <button
                        key={a}
                        onClick={() => setAnswer(a)}
                        className={`p-3 rounded-xl border text-left text-sm font-semibold transition ${
                          answer === a
                            ? 'bg-gold text-wine border-gold shadow'
                            : 'border-white/30 text-white hover:bg-white/5'
                        }`}
                      >
                        {a}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <p className="text-cream/70 text-xs mt-2 truncate">
                Verified email: <b>{customer.email || 'Not signed in'}</b> • 1 play every 24 hours.
              </p>

              <button
                disabled={loading || isSpinning || !customer.canPlay || (game === 'quiz' && !answer)}
                onClick={() => playGame(game)}
                className="mt-5 w-full bg-cream text-wine font-bold rounded-xl py-4 disabled:opacity-40 disabled:cursor-not-allowed shadow-md hover:bg-white transition text-base"
              >
                {isSpinning
                  ? 'WHEEL SPINNING…'
                  : loading
                  ? 'SELECTING REWARD…'
                  : !customer.canPlay
                  ? `PLAYED TODAY (NEXT IN ${timeUntilPlay || '24H'})`
                  : game === 'spin'
                  ? 'SPIN NOW'
                  : game === 'scratch'
                  ? 'REVEAL MY REWARD'
                  : 'SUBMIT & WIN'}
              </button>
            </div>
          </section>
        )}

        {/* COUPON WIN / UNLUCKY SCREEN */}
        {screen === 'coupon' && result && (
          <section className="mt-6">
            {result.is_unlucky || result.reward === 0 ? (
              // CASE 1: UNLUCKY RESULT
              <div className="bg-white border-2 border-stone-300 rounded-3xl p-6 text-center shadow-glow">
                <div className="w-16 h-16 bg-stone-100 text-stone-500 rounded-full flex items-center justify-center mx-auto mb-3 border border-stone-300">
                  <HeartCrack size={32} />
                </div>
                <p className="uppercase tracking-[.2em] text-xs text-stone-400 font-semibold">
                  Rayara Play & Dine
                </p>
                <h2 className="serif text-3xl text-wine font-bold mt-2">Better Luck Next Time!</h2>
                <div className="goldline my-4" />
                <p className="text-stone-600 text-sm mt-2 leading-relaxed">
                  You landed on an Unlucky slice today. Thank you for dining with us!
                </p>
                <div className="mt-4 p-3.5 bg-[#fbf6ed] rounded-xl text-xs text-stone-700 text-left space-y-1">
                  <p>✉️ Registered Email: <b>{customer.email}</b></p>
                  <p>⏰ Next play unlocks in: <b>{timeUntilPlay || '24 hours'}</b></p>
                  <p className="text-stone-500">Each email address gets 1 play every 24 hours.</p>
                </div>
                <button
                  onClick={back}
                  className="w-full mt-5 bg-wine text-cream rounded-xl py-3.5 font-bold shadow hover:opacity-90 transition text-sm"
                >
                  BACK TO HOME
                </button>
              </div>
            ) : (
              // CASE 2: WINNING COUPON RESULT
              result.coupon && (
                <div className="bg-white border-2 border-dashed border-gold rounded-3xl p-6 text-center shadow-glow">
                  <div className="text-gold">
                    <Gift size={46} className="mx-auto" />
                  </div>
                  <p className="uppercase tracking-[.2em] text-xs text-stone-500 mt-3 font-semibold">
                    Congratulations
                  </p>
                  <div className="serif text-6xl text-wine mt-2 font-bold">
                    {result.reward}%
                  </div>
                  <h2 className="text-wine font-bold tracking-wide mt-1">OFF YOUR NEXT VISIT</h2>
                  <div className="goldline my-4" />

                  <p className="text-xs text-stone-500 uppercase tracking-wider">YOUR RAYARA COUPON CODE</p>
                  <div className="font-mono text-2xl tracking-widest text-wine bg-cream p-3 rounded-xl mt-2 font-bold border border-gold/40 select-all">
                    {result.coupon_code}
                  </div>

                  <div className="mt-4 p-3 bg-[#fbf6ed] rounded-xl text-xs text-stone-700 space-y-1 text-left">
                    <p>
                      ✉️ Linked to Email: <b>{customer.email}</b>
                    </p>
                    <p>
                      📅 Valid from: <b>{new Date(result.coupon.valid_from).toLocaleDateString('en-IN')}</b> until <b>{new Date(result.coupon.expires_at).toLocaleDateString('en-IN')}</b>
                    </p>
                    <p>
                      💰 Minimum bill: <b>₹{result.coupon.minimum_spend}</b> • Maximum discount: <b>₹{result.coupon.max_discount}</b>
                    </p>
                  </div>

                  <div className="mt-4 bg-wine text-cream rounded-xl p-3 text-xs leading-relaxed">
                    Show this code or your registered email at the counter on your next visit to redeem!
                  </div>

                  <button
                    onClick={openRewards}
                    className="w-full mt-4 bg-wine text-cream rounded-xl py-4 font-bold shadow hover:opacity-90 transition"
                  >
                    VIEW ALL MY REWARDS
                  </button>
                </div>
              )
            )}
          </section>
        )}

        {/* REWARDS SCREEN */}
        {screen === 'rewards' && (
          <section className="mt-5">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="serif text-3xl text-wine font-bold">My Rewards</h1>
                <p className="text-stone-500 text-xs mt-0.5 truncate max-w-[260px]">
                  Saved coupons for <b>{customer.email}</b>
                </p>
              </div>
              <button
                onClick={openRewards}
                className="text-xs text-wine font-semibold border border-wine/30 px-3 py-1.5 rounded-lg bg-white"
              >
                Refresh
              </button>
            </div>

            {coupons.length === 0 ? (
              <div className="mt-6 bg-white p-8 rounded-2xl text-center border border-[#eadcc9]">
                <Ticket className="mx-auto text-gold mb-2" size={36} />
                <p className="font-semibold text-stone-700">No coupons saved yet</p>
                <p className="text-xs text-stone-500 mt-1">
                  Play Lucky Spin, Mystery Scratch, or Food Quiz to win a reward!
                </p>
                <button
                  onClick={() => handlePlayClick()}
                  className="mt-4 bg-wine text-cream px-5 py-2.5 rounded-xl font-bold text-xs"
                >
                  Play a Game Now
                </button>
              </div>
            ) : (
              <div className="space-y-3 mt-4">
                {coupons.map((c: any) => {
                  const storedCode = typeof window !== 'undefined' ? localStorage.getItem('rayara_coupon_' + c.id) : null;
                  const displayCode = storedCode || (c.code ? `****${c.code}` : 'COUPON');
                  const isRedeemed = c.status === 'redeemed';
                  const isExpired = c.status === 'expired';

                  return (
                    <div
                      key={c.id}
                      className={`bg-white border rounded-2xl p-4 shadow-sm relative overflow-hidden ${
                        isRedeemed || isExpired ? 'opacity-60 border-stone-200' : 'border-gold/60'
                      }`}
                    >
                      <div className="flex justify-between items-center">
                        <b className="text-wine text-lg">{c.percentage}% OFF</b>
                        <span
                          className={`text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full ${
                            c.status === 'active'
                              ? 'bg-emerald-100 text-emerald-800'
                              : isRedeemed
                              ? 'bg-stone-100 text-stone-600'
                              : 'bg-red-100 text-red-700'
                          }`}
                        >
                          {c.status}
                        </span>
                      </div>

                      <div className="mt-2 flex items-center justify-between bg-cream/60 p-2.5 rounded-lg">
                        <span className="text-xs text-stone-600">Code:</span>
                        <span className="font-mono font-bold text-sm tracking-wider text-wine">
                          {displayCode}
                        </span>
                      </div>

                      <div className="text-[11px] text-stone-500 mt-2 space-y-0.5">
                        <p>Valid from: {new Date(c.valid_from).toLocaleDateString('en-IN')} to {new Date(c.expires_at).toLocaleDateString('en-IN')}</p>
                        <p>Min bill ₹{c.minimum_spend} • Max discount ₹{c.max_discount}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        )}

        {/* DIGITAL BILLS & RECEIPT SCREEN */}
        {screen === 'bills' && (
          <section className="mt-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h1 className="serif text-3xl text-wine font-bold">My Digital Bills</h1>
                <p className="text-stone-500 text-xs mt-0.5 truncate max-w-[260px]">
                  Official invoices for <b>{customer.email}</b>
                </p>
              </div>
              <button
                onClick={openBills}
                className="text-xs text-wine font-semibold border border-wine/30 px-3 py-1.5 rounded-lg bg-white shadow-sm"
              >
                Refresh
              </button>
            </div>

            {bills.length === 0 ? (
              <div className="mt-6 bg-white p-8 rounded-2xl text-center border border-[#eadcc9] shadow-sm">
                <FileText className="mx-auto text-gold mb-2" size={36} />
                <p className="font-semibold text-stone-700">No dining bills recorded yet</p>
                <p className="text-xs text-stone-500 mt-1">
                  When you settle your bill at the counter or show your rewards, your official digital receipts will appear here automatically.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {bills.map((b: any, idx: number) => (
                  <div key={idx} className="bg-white border-2 border-[#dfd2c0] rounded-2xl p-5 shadow-sm">
                    {/* Header */}
                    <div className="flex justify-between items-start border-b border-[#dfd2c0] pb-3">
                      <div>
                        <span className="text-[10px] bg-wine text-cream font-bold px-2 py-0.5 rounded-full uppercase">
                          {b.order_type} {b.table ? `· Table ${b.table}` : ''}
                        </span>
                        <h3 className="font-bold text-wine text-base mt-1.5">Receipt #{b.receipt_number}</h3>
                        <p className="text-[11px] text-stone-500">Order #{b.order_number} · {b.date}</p>
                      </div>
                      <div className="text-right">
                        <span className="text-xs text-stone-500 block">Grand Total</span>
                        <span className="text-xl font-bold text-wine">₹{parseFloat(b.grand_total).toFixed(2)}</span>
                      </div>
                    </div>

                    {/* Items */}
                    <div className="py-3 divide-y divide-[#f2e9dc] text-xs">
                      {b.items.map((it: any, iIdx: number) => (
                        <div key={iIdx} className="py-1.5 flex justify-between items-center text-stone-700">
                          <span>{it.qty}x {it.name}</span>
                          <span className="font-semibold text-stone-900">₹{parseFloat(it.total).toFixed(2)}</span>
                        </div>
                      ))}
                    </div>

                    {/* Financials Breakdown */}
                    <div className="border-t border-[#dfd2c0] pt-3 text-xs space-y-1 text-stone-600 bg-cream/40 p-3 rounded-xl">
                      <div className="flex justify-between">
                        <span>Subtotal:</span>
                        <span>₹{parseFloat(b.subtotal).toFixed(2)}</span>
                      </div>
                      {parseFloat(b.discount) > 0 && (
                        <div className="flex justify-between text-emerald-700 font-semibold">
                          <span>Coupon Discount {b.coupon_code ? `(${b.coupon_code})` : ''}:</span>
                          <span>-₹{parseFloat(b.discount).toFixed(2)}</span>
                        </div>
                      )}
                      <div className="flex justify-between">
                        <span>Taxes (CGST + SGST):</span>
                        <span>₹{parseFloat(b.tax).toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between font-bold text-wine text-sm pt-1 border-t border-[#dfd2c0]">
                        <span>Paid via {b.payment_method}:</span>
                        <span>₹{parseFloat(b.grand_total).toFixed(2)}</span>
                      </div>
                    </div>

                    <div className="mt-3 text-center">
                      <button
                        onClick={() => window.print()}
                        className="text-xs text-wine font-semibold underline hover:opacity-80"
                      >
                        Print / Download Digital Tax Invoice
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </div>

      {/* LOGIN MODAL */}
      {showLoginModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-[#faf6f0] rounded-3xl p-6 w-full max-w-sm shadow-backlit-lg border-2 border-amber-warm/40 relative">
            <button
              onClick={() => {
                setShowLoginModal(false);
                setOtpError('');
                setOtpStep('email');
              }}
              className="absolute right-4 top-4 text-stone-400 hover:text-bronze p-1 transition"
            >
              <X size={20} />
            </button>

            <div className="text-center mb-5">
              <div className="w-14 h-14 bg-bronze text-amber-glow rounded-full flex items-center justify-center mx-auto mb-2 border-2 border-amber-warm/60 shadow-[0_0_18px_rgba(229,154,56,0.45)]">
                {otpStep === 'email' ? <Mail size={24} /> : <KeyRound size={24} />}
              </div>
              <h2 className="serif text-2xl text-bronze font-bold">
                {otpStep === 'email' ? 'Customer Sign In' : 'Enter Verification Code'}
              </h2>
              <p className="text-stone-600 text-xs mt-1">
                {otpStep === 'email'
                  ? 'Sign in with your email to receive a verification code. 1 play per 24 hours.'
                  : `Enter the 6-digit code sent to ${inputEmail.trim()}`}
              </p>
            </div>

            {otpError && (
              <div className="mb-4 bg-red-50 text-red-800 text-xs p-3 rounded-xl border border-red-200 flex items-start gap-1.5 shadow-sm">
                <AlertCircle size={15} className="shrink-0 mt-0.5" />
                <div>{otpError}</div>
              </div>
            )}

            {otpSuccessMsg && otpStep === 'otp' && (
              <div className="mb-4 bg-emerald-50 text-emerald-800 text-xs p-3 rounded-xl border border-emerald-200 flex items-center gap-1.5 shadow-sm">
                <CheckCircle2 size={15} className="shrink-0 text-emerald-600" />
                <div>{otpSuccessMsg}</div>
              </div>
            )}

            {/* STEP 1: ENTER EMAIL */}
            {otpStep === 'email' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-stone-700 mb-1">
                    Email Address
                  </label>
                  <div className="flex rounded-xl border border-sand-300 overflow-hidden focus-within:border-amber-warm focus-within:ring-2 focus-within:ring-amber-warm/30 bg-white shadow-inner">
                    <span className="bg-sand-100 px-3 py-3 text-stone-500 border-r border-sand-200 flex items-center justify-center">
                      <Mail size={16} />
                    </span>
                    <input
                      type="email"
                      autoFocus
                      placeholder="yourname@gmail.com"
                      value={inputEmail}
                      onChange={e => setInputEmail(e.target.value)}
                      className="flex-1 px-3 py-3 text-sm outline-none"
                    />
                  </div>
                  <p className="text-[11px] text-stone-500 mt-1">
                    We'll email you a 6-digit verification code.
                  </p>
                </div>

                <button
                  disabled={otpLoading || !inputEmail.trim().includes('@')}
                  onClick={handleSendOtp}
                  className="w-full bg-bronze hover:bg-bronze-light text-sand-50 py-3.5 rounded-xl font-bold text-sm shadow-backlit hover:opacity-95 disabled:opacity-40 transition flex items-center justify-center gap-2 border border-amber-warm/40"
                >
                  {otpLoading ? 'Sending Code…' : 'Send Verification Code'}
                </button>
              </div>
            )}

            {/* STEP 2: ENTER OTP */}
            {otpStep === 'otp' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-stone-700 mb-1">
                    6-Digit Verification Code
                  </label>
                  <input
                    type="text"
                    maxLength={6}
                    autoFocus
                    placeholder="Enter 6-digit code"
                    value={inputOtp}
                    onChange={e => setInputOtp(e.target.value.replace(/\D/g, ''))}
                    className="w-full text-center tracking-widest text-xl font-bold font-mono py-3 border border-sand-300 rounded-xl focus:border-amber-warm focus:ring-2 focus:ring-amber-warm/30 outline-none bg-white shadow-inner"
                  />

                  <p className="text-center text-[12px] text-stone-600 mt-2.5">
                    We've emailed your 6-digit verification code. Check your inbox &amp; spam folder.
                  </p>
                </div>

                <button
                  disabled={otpLoading || inputOtp.trim().length < 4}
                  onClick={handleVerifyOtp}
                  className="w-full bg-bronze hover:bg-bronze-light text-sand-50 py-3.5 rounded-xl font-bold text-sm shadow-backlit hover:opacity-95 disabled:opacity-40 transition flex items-center justify-center gap-2 border border-amber-warm/40"
                >
                  {otpLoading ? 'Verifying…' : 'Verify & Continue'}
                </button>

                <div className="flex items-center justify-between text-xs pt-1">
                  <button
                    onClick={() => {
                      setOtpStep('email');
                      setOtpError('');
                    }}
                    className="text-stone-500 hover:text-stone-800"
                  >
                    Change Email
                  </button>
                  <button
                    disabled={cooldownSecs > 0 || otpLoading}
                    onClick={handleSendOtp}
                    className="text-amber-deep font-semibold disabled:text-stone-400 hover:underline"
                  >
                    {cooldownSecs > 0 ? `Resend in ${cooldownSecs}s` : 'Resend Code'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <footer className="text-center mt-12 text-xs text-stone-500">
        © Rayara Café · Good food. Great moments.
      </footer>
    </main>
  );
}

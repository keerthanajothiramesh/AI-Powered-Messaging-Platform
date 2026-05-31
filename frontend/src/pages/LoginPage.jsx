import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { MessageSquare, Globe, Sparkles } from 'lucide-react'
import toast from 'react-hot-toast'
import { GoogleLogin } from '@react-oauth/google'
import client from '../api/client'
import { useAuthStore } from '../store/authStore'

export default function LoginPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)
  const [tab, setTab] = useState('login')
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({
    email: '', password: '', display_name: '', language_preference: 'en',
  })

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const handleGoogleSuccess = async (credentialResponse) => {
    try {
      const res = await client.post('/auth/google', { credential: credentialResponse.credential })
      login(res.data.access_token, {
        user_id: res.data.user_id,
        display_name: res.data.display_name,
        email: res.data.email,
      })
      toast.success(`Welcome, ${res.data.display_name}!`)
      navigate('/')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Google sign-in failed')
    }
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await client.post('/auth/login', { email: form.email, password: form.password })
      login(res.data.access_token, {
        user_id: res.data.user_id,
        display_name: res.data.display_name,
        email: res.data.email,
      })
      toast.success(t('auth.loginSuccess'))
      navigate('/')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await client.post('/auth/register', form)
      login(res.data.access_token, {
        user_id: res.data.user_id,
        display_name: res.data.display_name,
        email: res.data.email,
      })
      toast.success(t('auth.registerSuccess'))
      navigate('/')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  const hasGoogle = !!import.meta.env.VITE_GOOGLE_CLIENT_ID

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden"
         style={{ background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 30%, #4c1d95 60%, #2e1065 100%)' }}>
      {/* Decorative blobs */}
      <div className="absolute top-0 left-0 w-96 h-96 rounded-full blur-3xl opacity-30"
           style={{ background: 'radial-gradient(circle, #818cf8, transparent)' }} />
      <div className="absolute bottom-0 right-0 w-80 h-80 rounded-full blur-3xl opacity-20"
           style={{ background: 'radial-gradient(circle, #a78bfa, transparent)' }} />
      <div className="absolute top-1/2 left-1/2 w-64 h-64 rounded-full blur-3xl opacity-10 -translate-x-1/2 -translate-y-1/2"
           style={{ background: 'radial-gradient(circle, #c4b5fd, transparent)' }} />

      <div className="absolute top-4 right-4 z-10">
        <button
          onClick={() => i18n.changeLanguage(i18n.language === 'en' ? 'ja' : 'en')}
          className="flex items-center gap-2 px-3 py-2 bg-white/10 backdrop-blur-sm rounded-xl text-sm text-white hover:bg-white/20 border border-white/20 transition-all"
        >
          <Globe size={15} />
          {i18n.language === 'en' ? '🇬🇧 EN' : '🇯🇵 JA'}
        </button>
      </div>

      <div className="w-full max-w-md relative z-10">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-18 h-18 mb-5">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center shadow-2xl shadow-violet-900/50"
                 style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}>
              <MessageSquare size={30} className="text-white" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">{t('app.name')}</h1>
          <p className="text-indigo-200/80 text-sm mt-1.5 flex items-center justify-center gap-1.5">
            <Sparkles size={13} className="text-violet-300" />
            {t('app.tagline')}
          </p>
        </div>

        <div className="bg-white/10 backdrop-blur-xl rounded-2xl shadow-2xl overflow-hidden border border-white/20">
          {hasGoogle && (
            <div className="p-6 border-b border-white/10">
              <div className="bg-white rounded-xl p-3 flex justify-center shadow-sm">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() => toast.error('Google sign-in failed')}
                  theme="outline"
                  size="large"
                  width="340"
                  text="continue_with"
                  shape="rectangular"
                />
              </div>
              <div className="relative my-4">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-white/15" />
                </div>
                <div className="relative flex justify-center">
                  <span className="px-3 text-xs text-white/40" style={{ background: 'transparent' }}>or use email</span>
                </div>
              </div>
            </div>
          )}

          <div className="flex border-b border-white/10">
            {['login', 'register'].map((t_) => (
              <button
                key={t_}
                onClick={() => setTab(t_)}
                className={`flex-1 py-3.5 text-sm font-medium transition-all ${
                  tab === t_
                    ? 'text-white border-b-2 border-violet-400 bg-white/5'
                    : 'text-white/50 hover:text-white/80 hover:bg-white/5'
                }`}
              >
                {t_ === 'login' ? t('auth.signIn') : t('auth.createAccount')}
              </button>
            ))}
          </div>

          <div className="p-6">
            {tab === 'login' ? (
              <form onSubmit={handleLogin} className="space-y-4">
                <GlassInputField label={t('auth.email')} name="email" type="email" value={form.email} onChange={handleChange} />
                <GlassInputField label={t('auth.password')} name="password" type="password" value={form.password} onChange={handleChange} />
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-60 shadow-lg"
                  style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
                >
                  {loading ? t('common.loading') : t('auth.signIn')}
                </button>
                <p className="text-center text-xs text-white/30">
                  Demo: priya.sharma0@company.com / Test@1234
                </p>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="space-y-4">
                <GlassInputField label={t('auth.displayName')} name="display_name" value={form.display_name} onChange={handleChange} />
                <GlassInputField label={t('auth.email')} name="email" type="email" value={form.email} onChange={handleChange} />
                <GlassInputField label={t('auth.password')} name="password" type="password" value={form.password} onChange={handleChange} />
                <div>
                  <label className="block text-sm font-medium text-white/70 mb-1.5">{t('auth.language')}</label>
                  <select
                    name="language_preference"
                    value={form.language_preference}
                    onChange={handleChange}
                    className="w-full px-3 py-2.5 bg-white/10 border border-white/20 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-violet-400/50 focus:border-violet-400/70 transition-all"
                  >
                    <option value="en" style={{ background: '#312e81', color: 'white' }}>🇬🇧 English</option>
                    <option value="ja" style={{ background: '#312e81', color: 'white' }}>🇯🇵 日本語</option>
                  </select>
                </div>
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-60 shadow-lg"
                  style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
                >
                  {loading ? t('common.loading') : t('auth.createAccount')}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function GlassInputField({ label, name, type = 'text', value, onChange }) {
  return (
    <div>
      <label className="block text-sm font-medium text-white/70 mb-1.5">{label}</label>
      <input
        type={type}
        name={name}
        value={value}
        onChange={onChange}
        required
        className="w-full px-4 py-2.5 bg-white/10 border border-white/20 rounded-xl text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-violet-400/50 focus:border-violet-400/70 transition-all"
      />
    </div>
  )
}

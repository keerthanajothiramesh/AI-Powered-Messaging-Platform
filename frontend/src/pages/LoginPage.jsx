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
         style={{ background: 'linear-gradient(135deg, #f0f4ff 0%, #f8f7ff 50%, #fdf4ff 100%)' }}>

      {/* Soft decorative blobs */}
      <div className="absolute top-[-80px] left-[-80px] w-80 h-80 rounded-full blur-3xl opacity-30"
           style={{ background: 'radial-gradient(circle, #c4b5fd, transparent)' }} />
      <div className="absolute bottom-[-60px] right-[-60px] w-72 h-72 rounded-full blur-3xl opacity-20"
           style={{ background: 'radial-gradient(circle, #a5b4fc, transparent)' }} />

      {/* Language toggle */}
      <div className="absolute top-4 right-4 z-10">
        <button
          onClick={() => i18n.changeLanguage(i18n.language === 'en' ? 'ja' : 'en')}
          className="flex items-center gap-2 px-3 py-2 bg-white border border-slate-200 rounded-xl text-sm text-slate-600 hover:bg-slate-50 shadow-sm transition-all"
        >
          <Globe size={15} />
          {i18n.language === 'en' ? '🇬🇧 EN' : '🇯🇵 JA'}
        </button>
      </div>

      <div className="w-full max-w-md relative z-10">
        {/* Branding */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-16 h-16 mb-4 rounded-2xl shadow-lg"
               style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}>
            <MessageSquare size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{t('app.name')}</h1>
          <p className="text-violet-500 text-sm mt-1.5 flex items-center justify-center gap-1.5 font-medium">
            <Sparkles size={13} />
            {t('app.tagline')}
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden border border-slate-100">
          {hasGoogle && (
            <div className="p-6 border-b border-slate-100">
              <div className="flex justify-center">
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
                  <div className="w-full border-t border-slate-200" />
                </div>
                <div className="relative flex justify-center">
                  <span className="px-3 text-xs text-slate-400 bg-white">or use email</span>
                </div>
              </div>
            </div>
          )}

          {/* Tabs */}
          <div className="flex border-b border-slate-100">
            {['login', 'register'].map((t_) => (
              <button
                key={t_}
                onClick={() => setTab(t_)}
                className={`flex-1 py-3.5 text-sm font-semibold transition-all ${
                  tab === t_
                    ? 'text-violet-600 border-b-2 border-violet-500 bg-violet-50/40'
                    : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                }`}
              >
                {t_ === 'login' ? t('auth.signIn') : t('auth.createAccount')}
              </button>
            ))}
          </div>

          {/* Form */}
          <div className="p-6">
            {tab === 'login' ? (
              <form onSubmit={handleLogin} className="space-y-4">
                <LightInputField label={t('auth.email')} name="email" type="email" value={form.email} onChange={handleChange} />
                <LightInputField label={t('auth.password')} name="password" type="password" value={form.password} onChange={handleChange} />
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-60 shadow-md hover:shadow-lg hover:opacity-95"
                  style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
                >
                  {loading ? t('common.loading') : t('auth.signIn')}
                </button>
                <p className="text-center text-xs text-slate-400">
                  Demo: priya.sharma0@company.com / Test@1234
                </p>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="space-y-4">
                <LightInputField label={t('auth.displayName')} name="display_name" value={form.display_name} onChange={handleChange} />
                <LightInputField label={t('auth.email')} name="email" type="email" value={form.email} onChange={handleChange} />
                <LightInputField label={t('auth.password')} name="password" type="password" value={form.password} onChange={handleChange} />
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-1.5">{t('auth.language')}</label>
                  <select
                    name="language_preference"
                    value={form.language_preference}
                    onChange={handleChange}
                    className="w-full px-3 py-2.5 bg-white border border-slate-200 rounded-xl text-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-300 focus:border-violet-400 transition-all"
                  >
                    <option value="en">🇬🇧 English</option>
                    <option value="ja">🇯🇵 日本語</option>
                  </select>
                </div>
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 rounded-xl font-semibold text-white transition-all disabled:opacity-60 shadow-md hover:shadow-lg hover:opacity-95"
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

function LightInputField({ label, name, type = 'text', value, onChange }) {
  return (
    <div>
      <label className="block text-sm font-semibold text-slate-700 mb-1.5">{label}</label>
      <input
        type={type}
        name={name}
        value={value}
        onChange={onChange}
        required
        className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-slate-800 placeholder:text-slate-300 focus:outline-none focus:ring-2 focus:ring-violet-300 focus:border-violet-400 transition-all"
      />
    </div>
  )
}

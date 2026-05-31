import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { MessageSquare, Globe } from 'lucide-react'
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
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-4">
      <div className="absolute top-4 right-4">
        <button
          onClick={() => i18n.changeLanguage(i18n.language === 'en' ? 'ja' : 'en')}
          className="flex items-center gap-2 px-3 py-2 bg-white rounded-lg shadow-sm text-sm hover:bg-gray-50 transition-colors"
        >
          <Globe size={16} />
          {i18n.language === 'en' ? '🇬🇧 EN' : '🇯🇵 JA'}
        </button>
      </div>

      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary rounded-2xl mb-4 shadow-lg">
            <MessageSquare size={32} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{t('app.name')}</h1>
          <p className="text-gray-500 text-sm mt-1">{t('app.tagline')}</p>
        </div>

        <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
          {/* Google Sign-In (shown when configured) */}
          {hasGoogle && (
            <div className="p-6 border-b border-gray-100">
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
                  <div className="w-full border-t border-gray-100" />
                </div>
                <div className="relative flex justify-center">
                  <span className="bg-white px-3 text-xs text-gray-400">or use email</span>
                </div>
              </div>
            </div>
          )}

          {/* Email/Password tabs */}
          <div className="flex border-b border-gray-100">
            {['login', 'register'].map((t_) => (
              <button
                key={t_}
                onClick={() => setTab(t_)}
                className={`flex-1 py-3 text-sm font-medium transition-colors ${
                  tab === t_
                    ? 'text-primary border-b-2 border-primary'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {t_ === 'login' ? t('auth.signIn') : t('auth.createAccount')}
              </button>
            ))}
          </div>

          <div className="p-6">
            {tab === 'login' ? (
              <form onSubmit={handleLogin} className="space-y-4">
                <InputField label={t('auth.email')} name="email" type="email" value={form.email} onChange={handleChange} />
                <InputField label={t('auth.password')} name="password" type="password" value={form.password} onChange={handleChange} />
                <button type="submit" disabled={loading} className="w-full py-3 bg-primary text-white rounded-xl font-medium hover:bg-primary-dark transition-colors disabled:opacity-60">
                  {loading ? t('common.loading') : t('auth.signIn')}
                </button>
                <p className="text-center text-xs text-gray-400">
                  Demo: priya.sharma0@company.com / Test@1234
                </p>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="space-y-4">
                <InputField label={t('auth.displayName')} name="display_name" value={form.display_name} onChange={handleChange} />
                <InputField label={t('auth.email')} name="email" type="email" value={form.email} onChange={handleChange} />
                <InputField label={t('auth.password')} name="password" type="password" value={form.password} onChange={handleChange} />
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('auth.language')}</label>
                  <select
                    name="language_preference"
                    value={form.language_preference}
                    onChange={handleChange}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                  >
                    <option value="en">🇬🇧 English</option>
                    <option value="ja">🇯🇵 日本語</option>
                  </select>
                </div>
                <button type="submit" disabled={loading} className="w-full py-3 bg-primary text-white rounded-xl font-medium hover:bg-primary-dark transition-colors disabled:opacity-60">
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

function InputField({ label, name, type = 'text', value, onChange }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <input
        type={type}
        name={name}
        value={value}
        onChange={onChange}
        required
        className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-colors"
      />
    </div>
  )
}

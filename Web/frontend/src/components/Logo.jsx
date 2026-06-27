import { useNavigate } from 'react-router-dom'

export default function Logo() {
  const navigate = useNavigate()
  return (
    <button
      onClick={() => navigate('/')}
      className="text-2xl font-extrabold text-brand-600 tracking-tight"
    >
      Shortify
    </button>
  )
}

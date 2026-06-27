export default function PrimaryButton({ children, onClick, disabled = false, className = '' }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={
        'w-full rounded-2xl font-bold py-4 transition flex items-center justify-center gap-2 ' +
        (disabled
          ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
          : 'bg-brand-600 hover:bg-brand-700 text-white shadow-lg shadow-brand-600/25 ') +
        className
      }
    >
      {children}
    </button>
  )
}

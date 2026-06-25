import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { ShortifyProvider } from './context/ShortifyContext.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <ShortifyProvider>
        <App />
      </ShortifyProvider>
    </BrowserRouter>
  </React.StrictMode>,
)

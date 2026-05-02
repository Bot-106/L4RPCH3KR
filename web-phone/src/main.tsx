import React from 'react'
import ReactDOM from 'react-dom/client'
import { App } from './App'
import { injectTokens } from './theme/tokens'
import './index.css'

injectTokens()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

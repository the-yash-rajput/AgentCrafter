import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { Dashboard } from './components/pages/Dashboard'
import { GraphEditor } from './components/pages/GraphEditor'

export default function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: '#1a2235',
            color: '#e2e8f0',
            border: '1px solid #2d3f5c',
            fontFamily: 'IBM Plex Sans, sans-serif',
            fontSize: '13px',
          },
          success: { iconTheme: { primary: '#10b981', secondary: '#fff' } },
          error: { iconTheme: { primary: '#ef4444', secondary: '#fff' } },
        }}
      />
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/agents/:agentId/edit" element={<GraphEditor />} />
      </Routes>
    </BrowserRouter>
  )
}

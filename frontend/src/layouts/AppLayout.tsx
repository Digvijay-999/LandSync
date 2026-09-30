import React from 'react'
import { Outlet } from 'react-router-dom'
import { Navbar } from '../components/layout/Navbar'
import { Sidebar } from '../components/layout/Sidebar'
import { AssistantDrawer } from '../components/assistant/AssistantDrawer'
import { useAppStore } from '../stores/useAppStore'
import { X, CheckCircle, AlertTriangle, Info } from 'lucide-react'
import { cn } from '../lib/utils'

export const AppLayout: React.FC = () => {
  const notification = useAppStore((state) => state.notification)
  const clearNotification = useAppStore((state) => state.clearNotification)

  return (
    <div className="flex flex-col h-screen bg-background text-slate-100 font-sans">
      <Navbar />

      <div className="flex flex-1 overflow-hidden relative">
        <Sidebar />

        <main className="flex-1 overflow-y-auto p-6 bg-surface-950/40">
          {notification && (
            <div
              className={cn(
                'mb-4 px-4 py-2.5 rounded border text-xs font-mono flex items-center justify-between transition-all',
                notification.type === 'success' && 'bg-emerald-950/40 border-emerald-800 text-emerald-300',
                notification.type === 'error' && 'bg-rose-950/40 border-rose-800 text-rose-300',
                notification.type === 'info' && 'bg-cyan-950/40 border-cyan-800 text-cyan-300'
              )}
            >
              <div className="flex items-center gap-2">
                {notification.type === 'success' && <CheckCircle className="w-4 h-4 text-emerald-400" />}
                {notification.type === 'error' && <AlertTriangle className="w-4 h-4 text-rose-400" />}
                {notification.type === 'info' && <Info className="w-4 h-4 text-cyan-400" />}
                <span>{notification.message}</span>
              </div>
              <button
                onClick={clearNotification}
                className="hover:opacity-80 p-0.5 rounded"
                title="Dismiss"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <Outlet />
        </main>

        {/* Global AI Assistant Drawer */}
        <AssistantDrawer />
      </div>
    </div>
  )
}

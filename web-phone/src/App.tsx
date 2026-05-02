import { createBrowserRouter, RouterProvider, Navigate, Outlet } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'

import { SignInScreen } from '@/screens/onboarding/SignInScreen'
import { GithubConnectScreen } from '@/screens/onboarding/GithubConnectScreen'
import { PiPairScreen } from '@/screens/onboarding/PiPairScreen'
import { LiveScreen } from '@/screens/live/LiveScreen'
import { ShowQrScreen } from '@/screens/pair/ShowQrScreen'
import { ScanQrScreen } from '@/screens/pair/ScanQrScreen'
import { RecapScreen } from '@/screens/recap/RecapScreen'
import { AuthCallbackScreen } from '@/screens/AuthCallbackScreen'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
})

function RequireAuth() {
  const isAuthed = useAuthStore((s) => s.isAuthed)
  if (!isAuthed) return <Navigate to="/onboarding/signin" replace />
  return <Outlet />
}

function RootRedirect() {
  const { isAuthed, user } = useAuthStore()
  if (!isAuthed) return <Navigate to="/onboarding/signin" replace />
  if (!user?.github_login) return <Navigate to="/onboarding/github" replace />
  return <Navigate to="/live" replace />
}

const router = createBrowserRouter([
  { path: '/', element: <RootRedirect /> },
  { path: '/auth/callback', element: <AuthCallbackScreen /> },
  { path: '/onboarding/signin', element: <SignInScreen /> },
  {
    element: <RequireAuth />,
    children: [
      { path: '/onboarding/github', element: <GithubConnectScreen /> },
      { path: '/onboarding/pair', element: <PiPairScreen /> },
      { path: '/live', element: <LiveScreen /> },
      { path: '/pair/show', element: <ShowQrScreen /> },
      { path: '/pair/scan', element: <ScanQrScreen /> },
      { path: '/recap/:sessionId', element: <RecapScreen /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}

import { Route, Routes } from 'react-router-dom'
import Home from './pages/Home'
import ProtectedRoute from './components/ProtectedRoutes'
import Login from './pages/Login'
import Signup from './pages/SignUp'
import Landing from './pages/Landing'
import Dashboard from './pages/Dashboard'
import ExperimentDetails from './pages/ExperimentDetails'
import Insights from './pages/Insights'
import Settings from './pages/Settings'
import Layout from './components/Layout'

function App() {

  return (
    <>
      <Routes>
        <Route path="/login" element={<Login/>} />
        <Route path="/signup" element={<Signup/>} />
        
        {/* Landing page without layout */}
        <Route path="/" element={<Landing />} />
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <Layout>
              <Dashboard />
            </Layout>
          </ProtectedRoute>
        }/>
        <Route path="/experiments/:id" element={
          <ProtectedRoute>
            <Layout>
              <ExperimentDetails />
            </Layout>
          </ProtectedRoute>
        }/>
        <Route path="/insights" element={
          <ProtectedRoute>
            <Layout>
              <Insights />
            </Layout>
          </ProtectedRoute>
        }/>
        <Route path="/settings" element={
          <ProtectedRoute>
            <Layout>
              <Settings />
            </Layout>
          </ProtectedRoute>
        }/>
      </Routes>
    </>
  )
}

export default App

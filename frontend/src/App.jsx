import { Route, Routes } from 'react-router-dom'
import Home from './pages/Home'
import ProtectedRoute from './components/ProtectedRoutes'
import Login from './pages/Login'
import Signup from './pages/SIgnUp'
import Landing from './pages/Landing'


function App() {

  return (
    <>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/home" element={
            <ProtectedRoute>
              <Home />
            </ProtectedRoute>
          }/>
        <Route path="/login" element={
          <Login/>
        }/>
        <Route path="/signup" element={
          <Signup/>
        }/>
      </Routes>
    </>
  )
}

export default App

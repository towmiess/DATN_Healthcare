import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'
import AppRoutes from './routes/AppRoutes'

function App() {

  return (
    <>
      <BrowserRouter>
        <AppRoutes />
        <Toaster position="bottom-right" richColors />
      </BrowserRouter>
    </>
  )
}

export default App

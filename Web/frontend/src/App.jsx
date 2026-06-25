import { Routes, Route, Navigate } from 'react-router-dom'
import Landing from './screens/Landing'
import Options from './screens/Options'
import Analyzing from './screens/Analyzing'
import Results from './screens/Results'
import Edit from './screens/Edit'
import Done from './screens/Done'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/options" element={<Options />} />
      <Route path="/analyzing" element={<Analyzing />} />
      <Route path="/results" element={<Results />} />
      <Route path="/edit" element={<Edit />} />
      <Route path="/done" element={<Done />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

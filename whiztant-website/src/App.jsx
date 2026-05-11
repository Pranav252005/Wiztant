import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ScrollToTop from './components/ScrollToTop'
import Home from './pages/Home'
import FeaturesOverview from './pages/FeaturesOverview'
import RePrompt from './pages/RePrompt'
import Dictation from './pages/Dictation'
import Agent from './pages/Agent'
import TaskStack from './pages/TaskStack'

import HowItWorks from './pages/HowItWorks'
import Pricing from './pages/Pricing'
import Download from './pages/Download'
import About from './pages/About'
import Contact from './pages/Contact'
import Docs from './pages/Docs'
import Changelog from './pages/Changelog'
import Privacy from './pages/Privacy'
import Terms from './pages/Terms'
import Settings from './pages/Settings'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <>
      <ScrollToTop />
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/features" element={<FeaturesOverview />} />
          <Route path="/features/reprompt" element={<RePrompt />} />
          <Route path="/features/dictation" element={<Dictation />} />
          <Route path="/features/agent" element={<Agent />} />
          <Route path="/features/taskstack" element={<TaskStack />} />
  
          <Route path="/how-it-works" element={<HowItWorks />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/download" element={<Download />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/about" element={<About />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/docs" element={<Docs />} />
          <Route path="/changelog" element={<Changelog />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/terms" element={<Terms />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </>
  )
}

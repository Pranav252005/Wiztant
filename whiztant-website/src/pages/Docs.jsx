import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { BookOpen, Search, ChevronRight, Zap, Mic, Bot, ListTodo, Sparkles, Download, Keyboard, CreditCard, Monitor, AlertTriangle, CheckCircle2, Terminal } from 'lucide-react'
import Particles from '../components/Particles'
import AnimatedSection from '../components/AnimatedSection'
import Aurora from '../components/Aurora'

const docSections = [
  {
    id: 'getting-started',
    title: 'Getting Started',
    icon: Download,
    items: [
      {
        title: 'Installation',
        content: (
          <div className="space-y-4">
            <p>Wiztant is distributed as a portable executable. No installation wizard required.</p>
            <ol className="list-decimal list-inside space-y-2 text-text-secondary">
              <li>Download the latest build from the <Link to="/download" className="text-primary hover:underline">download page</Link>.</li>
              <li>Move <code className="bg-white/5 px-1.5 py-0.5 rounded text-sm">Wiztant-Portable.exe</code> to your preferred location.</li>
              <li>Double-click to run. Windows Defender may show a SmartScreen warning — click "More info" then "Run anyway."</li>
              <li>Wiztant will appear in your system tray.</li>
            </ol>
            <div className="rounded-xl border border-warning/20 bg-warning/5 p-4 flex gap-3">
              <AlertTriangle size={18} className="text-warning shrink-0 mt-0.5" />
              <p className="text-sm text-text-secondary">If you see a missing DLL error, install the <a href="#" className="text-primary hover:underline">Visual C++ Redistributable</a> and restart.</p>
            </div>
          </div>
        )
      },
      {
        title: 'System Requirements',
        content: (
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <p className="font-medium text-text-primary mb-2">Windows</p>
                <ul className="space-y-1 text-sm text-text-secondary">
                  <li>Windows 10 (1903+) or Windows 11</li>
                  <li>64-bit processor</li>
                  <li>4 GB RAM minimum (8 GB recommended)</li>
                  <li>500 MB free disk space</li>
                  <li>Internet connection for cloud features</li>
                </ul>
              </div>
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <p className="font-medium text-text-primary mb-2">Linux</p>
                <ul className="space-y-1 text-sm text-text-secondary">
                  <li>Ubuntu 20.04+, Fedora 35+, or Arch</li>
                  <li>64-bit processor</li>
                  <li>4 GB RAM minimum (8 GB recommended)</li>
                  <li>500 MB free disk space</li>
                  <li>X11 or Wayland display server</li>
                </ul>
              </div>
            </div>
          </div>
        )
      },
      {
        title: 'First Launch',
        content: (
          <div className="space-y-4">
            <p>On first launch, Wiztant will:</p>
            <ol className="list-decimal list-inside space-y-2 text-text-secondary">
              <li>Create a config folder in <code className="bg-white/5 px-1.5 py-0.5 rounded text-sm">%APPDATA%\Wiztant</code> (Windows) or <code className="bg-white/5 px-1.5 py-0.5 rounded text-sm">~/.config/wiztant</code> (Linux).</li>
              <li>Prompt you to set your API key (optional — Dictation works without one).</li>
              <li>Register global hotkeys. You may need to grant accessibility permissions on Linux.</li>
            </ol>
            <div className="rounded-xl border border-success/20 bg-success/5 p-4 flex gap-3">
              <CheckCircle2 size={18} className="text-success shrink-0 mt-0.5" />
              <p className="text-sm text-text-secondary">Pro tip: Keep Wiztant in your Startup folder so it launches with Windows.</p>
            </div>
          </div>
        )
      }
    ]
  },
  {
    id: 'features',
    title: 'Features',
    icon: Zap,
    items: [
      {
        title: 'Hotkey Reference',
        content: (
          <div className="space-y-4">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th className="text-left py-2 pr-4 text-text-primary">Feature</th>
                    <th className="text-left py-2 pr-4 text-text-primary">Hotkey</th>
                    <th className="text-left py-2 text-text-primary">Description</th>
                  </tr>
                </thead>
                <tbody className="text-text-secondary">
                  <tr className="border-b border-white/[0.03]"><td className="py-2 pr-4">Dictation</td><td className="py-2 pr-4 font-mono">F9</td><td>Start/stop voice input</td></tr>
                  <tr className="border-b border-white/[0.03]"><td className="py-2 pr-4">Agent</td><td className="py-2 pr-4 font-mono">F9 x2</td><td>Launch autonomous task mode</td></tr>
                  <tr className="border-b border-white/[0.03]"><td className="py-2 pr-4">RePrompt</td><td className="py-2 pr-4 font-mono">Ctrl+Space</td><td>Rewrite selected text</td></tr>
                  <tr className="border-b border-white/[0.03]"><td className="py-2 pr-4">TaskStack</td><td className="py-2 pr-4 font-mono">F10</td><td>Open task manager</td></tr>
                  <tr className="border-b border-white/[0.03]"><td className="py-2 pr-4">RePrompt</td><td className="py-2 pr-4 font-mono">Ctrl+Shift+P</td><td>Optimize your prompt</td></tr>
                  <tr><td className="py-2 pr-4">Settings</td><td className="py-2 pr-4 font-mono">Ctrl+Shift+S</td><td>Open configuration</td></tr>
                </tbody>
              </table>
            </div>
            <p className="text-text-secondary">All hotkeys are customizable in Settings → Hotkeys.</p>
          </div>
        )
      },
      {
        title: 'Dictation Deep Dive',
        content: (
          <div className="space-y-4">
            <p>Dictation transcribes your speech into text at the cursor position in any application.</p>
            <h4 className="font-medium text-text-primary mt-4">Voice Commands</h4>
            <ul className="space-y-1 text-sm text-text-secondary list-disc list-inside">
              <li><code className="bg-white/5 px-1.5 py-0.5 rounded text-sm">"new line"</code> — Insert line break</li>
              <li><code className="bg-white/5 px-1.5 py-0.5 rounded text-sm">"delete that"</code> — Remove last phrase</li>
              <li><code className="bg-white/5 px-1.5 py-0.5 rounded text-sm">"comma" / "period"</code> — Insert punctuation</li>
              <li><code className="bg-white/5 px-1.5 py-0.5 rounded text-sm">"capitalize"</code> — Capitalize next word</li>
            </ul>
            <h4 className="font-medium text-text-primary mt-4">Offline Mode</h4>
            <p className="text-text-secondary">Download the Whisper model in Settings → Dictation → "Enable offline mode" for transcription without internet.</p>
          </div>
        )
      },
      {
        title: 'Agent Access Tiers',
        content: (
          <div className="space-y-4">
            <p>Agent has three access levels depending on the task complexity and your subscription:</p>
            <div className="space-y-3">
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <p className="font-medium text-text-primary">Standard Access</p>
                <p className="text-sm text-text-secondary mt-1">Clicks, typing, and basic navigation within the active window. Available on all tiers.</p>
              </div>
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <p className="font-medium text-text-primary">System Access</p>
                <p className="text-sm text-text-secondary mt-1">Cross-application workflows, file operations, and system settings. Requires Pro.</p>
              </div>
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <p className="font-medium text-text-primary">Deep Access</p>
                <p className="text-sm text-text-secondary mt-1">Full system control including elevated permissions and background processes. Power tier only.</p>
              </div>
            </div>
          </div>
        )
      }
    ]
  },
  {
    id: 'troubleshooting',
    title: 'Troubleshooting',
    icon: AlertTriangle,
    items: [
      {
        title: 'Hotkeys Not Working',
        content: (
          <div className="space-y-4">
            <ol className="list-decimal list-inside space-y-2 text-text-secondary">
              <li>Check if another app is using the same hotkey. Common conflicts: Discord (Overlay), NVIDIA Overlay, Steam.</li>
              <li>Run Wiztant as Administrator (Windows) or check accessibility permissions (Linux).</li>
              <li>Restart Wiztant after changing hotkeys in Settings.</li>
              <li>Check the log file at <code className="bg-white/5 px-1.5 py-0.5 rounded text-sm">%APPDATA%\Wiztant\logs\latest.log</code> for errors.</li>
            </ol>
          </div>
        )
      },
      {
        title: 'Dictation Not Transcribing',
        content: (
          <div className="space-y-4">
            <ol className="list-decimal list-inside space-y-2 text-text-secondary">
              <li>Ensure your microphone is set as the default recording device in Windows settings.</li>
              <li>Check microphone permissions for Wiztant in Windows Privacy settings.</li>
              <li>Test with the built-in mic tester in Settings → Dictation → "Test Microphone".</li>
              <li>If using offline mode, verify the Whisper model downloaded completely (~150 MB).</li>
            </ol>
          </div>
        )
      },
      {
        title: 'Agent Fails to Click',
        content: (
          <div className="space-y-4">
            <ol className="list-decimal list-inside space-y-2 text-text-secondary">
              <li>Ensure the target window is visible and not minimized. Agent cannot interact with hidden windows.</li>
              <li>Some fullscreen applications block synthetic input. Try windowed or borderless mode.</li>
              <li>Run Wiztant as Administrator if interacting with elevated applications.</li>
              <li>UI scaling above 150% may cause coordinate misalignment. Adjust in Settings → Agent → "Display Scaling".</li>
            </ol>
          </div>
        )
      }
    ]
  },
  {
    id: 'api',
    title: 'API & Integration',
    icon: Terminal,
    items: [
      {
        title: 'Local API Server',
        content: (
          <div className="space-y-4">
            <p>Wiztant exposes a local REST API on <code className="bg-white/5 px-1.5 py-0.5 rounded text-sm">localhost:8765</code> for custom integrations.</p>
            <div className="rounded-xl border border-white/[0.06] bg-bg-dark p-4 font-mono text-xs text-text-secondary overflow-x-auto">
              <p className="text-primary mb-2">POST /api/v1/dictate</p>
              <p>{`{`}</p>
              <p className="pl-4">"audio": "base64-encoded-audio",</p>
              <p className="pl-4">"language": "en"</p>
              <p>{`}`}</p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-bg-dark p-4 font-mono text-xs text-text-secondary overflow-x-auto">
              <p className="text-primary mb-2">POST /api/v1/agent/task</p>
              <p>{`{`}</p>
              <p className="pl-4">"instruction": "Open Chrome and search for weather",</p>
              <p className="pl-4">"access_level": "standard"</p>
              <p>{`}`}</p>
            </div>
            <p className="text-text-secondary">Enable the API in Settings → Advanced → "Local API Server".</p>
          </div>
        )
      }
    ]
  }
]

export default function Docs() {
  const [activeSection, setActiveSection] = useState('getting-started')
  const [activeItem, setActiveItem] = useState('Installation')
  const [search, setSearch] = useState('')

  const currentSection = docSections.find(s => s.id === activeSection)
  const currentItem = currentSection?.items.find(i => i.title === activeItem)

  const filteredSections = search
    ? docSections.map(s => ({
        ...s,
        items: s.items.filter(i => i.title.toLowerCase().includes(search.toLowerCase()))
      })).filter(s => s.items.length > 0)
    : docSections

  return (
    <div>
      <section className="relative flex min-h-[40vh] flex-col items-center justify-center overflow-hidden px-6 text-center">
        <Aurora />
        <Particles count={15} />
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1 }}
          className="relative z-10 max-w-4xl"
        >
          <p className="eyebrow mb-6">Documentation</p>
          <h1 className="font-display text-4xl font-bold text-text-primary md:text-5xl">
            Everything you need to <span className="text-gradient-primary">know</span>
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-text-secondary">
            Guides, references, and troubleshooting for Wiztant.
          </p>
        </motion.div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-12">
        <div className="grid gap-8 lg:grid-cols-4">
          {/* Sidebar */}
          <AnimatedSection direction="left" className="lg:col-span-1">
            <div className="sticky top-24 space-y-6">
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search docs..."
                  className="w-full rounded-xl border border-white/10 bg-bg-dark pl-9 pr-4 py-2.5 text-sm text-text-primary outline-none transition-colors focus:border-primary"
                />
              </div>

              <div className="space-y-1">
                {filteredSections.map((section) => (
                  <div key={section.id}>
                    <button
                      onClick={() => { setActiveSection(section.id); setActiveItem(section.items[0]?.title) }}
                      className={`w-full flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                        activeSection === section.id ? 'bg-primary/10 text-primary' : 'text-text-secondary hover:text-text-primary hover:bg-white/[0.03]'
                      }`}
                    >
                      <section.icon size={16} />
                      {section.title}
                    </button>
                    {activeSection === section.id && section.items.length > 0 && (
                      <div className="ml-6 mt-1 space-y-0.5 border-l border-white/[0.06] pl-3">
                        {section.items.map((item) => (
                          <button
                            key={item.title}
                            onClick={() => setActiveItem(item.title)}
                            className={`block w-full text-left rounded-md px-2 py-1.5 text-xs transition-colors ${
                              activeItem === item.title ? 'text-primary bg-primary/5' : 'text-text-secondary hover:text-text-primary'
                            }`}
                          >
                            {item.title}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </AnimatedSection>

          {/* Content */}
          <AnimatedSection direction="right" className="lg:col-span-3">
            <AnimatePresence mode="wait">
              {currentItem && (
                <motion.div
                  key={currentItem.title}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.2 }}
                  className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8"
                >
                  <h2 className="font-display text-2xl font-bold text-text-primary mb-6">{currentItem.title}</h2>
                  <div className="prose-dark text-sm leading-relaxed space-y-4">
                    {currentItem.content}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </AnimatedSection>
        </div>
      </section>
    </div>
  )
}

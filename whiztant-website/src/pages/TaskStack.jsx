import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ListTodo, ArrowRight, Check, Plus, Trash2, Bell, Clock, Calendar } from 'lucide-react'
import AnimatedSection from '../components/AnimatedSection'
import Grainient from '../components/Grainient'
import Particles from '../components/Particles'

function TaskStackDemo() {
  const [tasks, setTasks] = useState([
    { id: 1, text: 'Review pull request #234', time: '10:00 AM', priority: 'high', done: false },
    { id: 2, text: 'Write unit tests for auth module', time: '2:00 PM', priority: 'medium', done: false },
    { id: 3, text: 'Update API documentation', time: '4:30 PM', priority: 'low', done: true },
  ])
  const [input, setInput] = useState('')
  const [isAdding, setIsAdding] = useState(false)

  const addTask = () => {
    if (!input.trim()) return
    const newTask = {
      id: Date.now(),
      text: input,
      time: 'Soon',
      priority: 'medium',
      done: false,
    }
    setTasks((prev) => [...prev, newTask])
    setInput('')
    setIsAdding(false)
  }

  const toggleTask = (id) => {
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, done: !t.done } : t)))
  }

  const removeTask = (id) => {
    setTasks((prev) => prev.filter((t) => t.id !== id))
  }

  return (
    <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6 md:p-8">
      <div className="flex items-center gap-2 mb-6">
        <ListTodo size={18} className="text-primary" />
        <span className="text-sm font-medium text-text-secondary">TaskStack Demo</span>
      </div>

      <div className="space-y-3 mb-6">
        <AnimatePresence>
          {tasks.map((task) => (
            <motion.div
              key={task.id}
              layout
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className={`flex items-center gap-3 rounded-xl border px-4 py-3 transition-all ${
                task.done
                  ? 'border-white/[0.03] bg-white/[0.01] opacity-50'
                  : 'border-white/[0.06] bg-white/[0.02]'
              }`}
            >
              <button
                onClick={() => toggleTask(task.id)}
                className={`shrink-0 w-5 h-5 rounded-full border flex items-center justify-center transition-colors ${
                  task.done ? 'bg-primary border-primary' : 'border-white/20 hover:border-primary'
                }`}
              >
                {task.done && <Check size={12} className="text-bg-dark" />}
              </button>
              <div className="flex-1 min-w-0">
                <p className={`text-sm ${task.done ? 'line-through text-text-secondary' : 'text-text-primary'}`}>
                  {task.text}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <Clock size={10} className="text-text-secondary" />
                  <span className="text-xs text-text-secondary">{task.time}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    task.priority === 'high' ? 'bg-primary/10 text-primary' :
                    task.priority === 'medium' ? 'bg-warm/10 text-warm' :
                    'bg-white/5 text-text-secondary'
                  }`}>
                    {task.priority}
                  </span>
                </div>
              </div>
              <button onClick={() => removeTask(task.id)} className="shrink-0 text-text-secondary hover:text-error transition-colors">
                <Trash2 size={14} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {isAdding ? (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="flex gap-2 mb-4"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addTask()}
            className="flex-1 rounded-xl border border-white/10 bg-bg-dark px-4 py-2 text-sm text-text-primary outline-none focus:border-primary"
            placeholder="Add a task..."
            autoFocus
          />
          <button onClick={addTask} className="rounded-xl bg-primary px-4 py-2 text-sm font-medium text-bg-dark">
            Add
          </button>
        </motion.div>
      ) : (
        <button
          onClick={() => setIsAdding(true)}
          className="w-full rounded-xl border border-dashed border-white/10 px-4 py-3 text-sm text-text-secondary transition-colors hover:border-primary/30 hover:text-primary flex items-center justify-center gap-2"
        >
          <Plus size={14} />
          Add a task
        </button>
      )}
    </div>
  )
}

export default function TaskStack() {
  return (
    <div>
      {/* Hero */}
      <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 text-center">
        <div className="absolute inset-0 z-[1]">
          <Grainient
            color1="#d3baad"
            color2="#ff6060"
            color3="#07070f"
            timeSpeed={0.15}
            colorBalance={0}
            warpStrength={0.8}
            warpFrequency={5}
            warpSpeed={1.2}
            warpAmplitude={70}
            blendAngle={5}
            blendSoftness={0.05}
            rotationAmount={600}
            noiseScale={2.5}
            grainAmount={0.05}
            grainScale={2}
            grainAnimated={false}
            contrast={1.2}
            gamma={1.15}
            saturation={0.9}
            centerX={-0.03}
            centerY={0.03}
            zoom={0.95}
          />
        </div>
        <Particles count={20} />
        <div className="absolute inset-0" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)', backgroundSize: '60px 60px' }} />

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1 }}
          className="relative z-10 max-w-4xl"
        >
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-2 mb-8">
            <ListTodo size={14} className="text-primary" />
            <span className="text-xs font-medium text-primary">F10</span>
          </div>
          <h1 className="font-display text-5xl font-bold leading-tight text-text-primary md:text-7xl">
            Never lose track{' '}
            <span className="text-gradient-primary">of a task</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary drop-shadow-lg">
            Dump your tasks anytime with a single hotkey. TaskStack sorts, schedules, and reminds you so nothing slips through the cracks.
          </p>
        </motion.div>
      </section>

      {/* Demo */}
      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          <AnimatedSection direction="left">
            <TaskStackDemo />
          </AnimatedSection>

          <AnimatedSection direction="right">
            <h2 className="font-display text-3xl font-bold text-text-primary md:text-4xl">
              Your tasks, organized automatically
            </h2>
            <p className="mt-4 text-text-secondary leading-relaxed">
              Press F10 anytime, speak or type your tasks. TaskStack uses AI to prioritize, schedule, and set reminders. You stay focused, it handles the rest.
            </p>
            <ul className="mt-8 space-y-4">
              {[
                'Dump tasks anytime with natural language',
                'AI sorts and prioritizes automatically',
                'Set reminders with phrases like "remind me at 3pm"',
                'Never miss a deadline, everything stays organized',
              ].map((item) => (
                <li key={item} className="flex items-start gap-3 text-text-secondary">
                  <Check size={18} className="mt-0.5 shrink-0 text-primary" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <Link to="/download" className="btn-primary mt-8">
              Try TaskStack <ArrowRight size={16} />
            </Link>
          </AnimatedSection>
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-7xl px-6 py-20">
        <AnimatedSection className="text-center mb-16">
          <h2 className="font-display text-3xl font-bold text-text-primary">How it works</h2>
        </AnimatedSection>
        <div className="grid gap-8 md:grid-cols-3">
          {[
            { step: '01', title: 'Press F10', desc: 'Hit the hotkey from anywhere. TaskStack opens instantly.' },
            { step: '02', title: 'Dump your tasks', desc: 'Speak or type everything on your mind. No structure needed.' },
            { step: '03', title: 'Stay on track', desc: 'AI sorts, schedules, and reminds you. You just execute.' },
          ].map((item, i) => (
            <AnimatedSection key={item.step} delay={i * 0.15}>
              <div className="card text-center">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full border border-primary/20 bg-primary/5 text-primary font-display font-bold mb-4">
                  {item.step}
                </div>
                <h3 className="font-display text-lg font-semibold text-text-primary">{item.title}</h3>
                <p className="mt-2 text-sm text-text-secondary">{item.desc}</p>
              </div>
            </AnimatedSection>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-7xl px-6 py-20 text-center">
        <AnimatedSection>
          <h2 className="font-display text-2xl font-bold text-text-primary">
            TaskStack unlocks with Pro
          </h2>
          <p className="mt-3 text-text-secondary">
            Included in Pro and Power tiers. Start your free trial today.
          </p>
          <Link to="/pricing" className="btn-primary mt-8">
            View Pricing <ArrowRight size={16} />
          </Link>
        </AnimatedSection>
      </section>
    </div>
  )
}

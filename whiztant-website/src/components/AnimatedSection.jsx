import { useRef, useEffect } from 'react'
import { motion, useInView } from 'framer-motion'

export default function AnimatedSection({ children, className = '', delay = 0, direction = 'up' }) {
  const ref = useRef(null)
  const isInView = useInView(ref, { once: true, margin: '-100px' })

  const x = direction === 'left' ? -50 : direction === 'right' ? 50 : 0
  const y = direction === 'up' ? 50 : direction === 'down' ? -50 : 0

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, x, y }}
      animate={isInView ? { opacity: 1, x: 0, y: 0 } : {}}
      transition={{ duration: 0.8, delay, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

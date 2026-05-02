import { useEffect, useRef, useState } from 'react'

export default function TextReveal({ children, className = '', delay = 0 }) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setTimeout(() => setVisible(true), delay)
          observer.disconnect()
        }
      },
      { threshold: 0.2 }
    )
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [delay])

  return (
    <span ref={ref} className={className}>
      {children.split('').map((char, i) => (
        <span
          key={i}
          className="inline-block transition-all duration-500"
          style={{
            transform: visible ? 'translateY(0)' : 'translateY(100%)',
            opacity: visible ? 1 : 0,
            transitionDelay: `${i * 20}ms`,
          }}
        >
          {char === ' ' ? '\u00A0' : char}
        </span>
      ))}
    </span>
  )
}

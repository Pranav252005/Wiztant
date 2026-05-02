import { useRef, useEffect, useCallback } from 'react'

export default function SplitText({ text, className = '', delay = 0, as: Tag = 'span' }) {
  const ref = useRef(null)
  const words = text.split(' ')

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const chars = el.querySelectorAll('.split-char')
    chars.forEach((char, i) => {
      char.style.transition = `transform 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94) ${delay + i * 0.03}s, opacity 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94) ${delay + i * 0.03}s`
      char.style.transform = 'translateY(0)'
      char.style.opacity = '1'
    })
  }, [delay])

  return (
    <Tag className={className} ref={ref}>
      {words.map((word, wi) => (
        <span key={wi} className="inline-block mr-[0.3em] last:mr-0">
          {word.split('').map((char, ci) => (
            <span
              key={ci}
              className="split-char inline-block"
              style={{ transform: 'translateY(100%)', opacity: 0 }}
            >
              {char}
            </span>
          ))}
        </span>
      ))}
    </Tag>
  )
}

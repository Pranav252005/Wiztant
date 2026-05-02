import { useEffect, useRef } from 'react'

export default function ScrollVelocity({ text, className = '', velocity = 50 }) {
  const containerRef = useRef(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const content = container.querySelector('.scroll-content')
    if (!content) return

    let position = 0
    let animationId

    const animate = () => {
      position -= velocity * 0.016
      if (Math.abs(position) >= content.scrollWidth / 2) {
        position = 0
      }
      content.style.transform = `translateX(${position}px)`
      animationId = requestAnimationFrame(animate)
    }
    animate()

    return () => cancelAnimationFrame(animationId)
  }, [velocity])

  return (
    <div ref={containerRef} className={`overflow-hidden whitespace-nowrap ${className}`}>
      <div className="scroll-content inline-flex">
        <span className="inline-flex shrink-0">{text}</span>
        <span className="inline-flex shrink-0">{text}</span>
        <span className="inline-flex shrink-0">{text}</span>
        <span className="inline-flex shrink-0">{text}</span>
      </div>
    </div>
  )
}

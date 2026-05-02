import { useRef, useEffect } from 'react'

export default function Aurora({ className = '' }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let animationId
    let time = 0

    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio
      canvas.height = canvas.offsetHeight * window.devicePixelRatio
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
    }
    resize()
    window.addEventListener('resize', resize)

    const draw = () => {
      const w = canvas.offsetWidth
      const h = canvas.offsetHeight
      ctx.clearRect(0, 0, w, h)

      for (let i = 0; i < 3; i++) {
        const x = w * 0.5 + Math.sin(time * 0.0008 + i * 2) * w * 0.3
        const y = h * 0.5 + Math.cos(time * 0.0006 + i * 1.5) * h * 0.3
        const gradient = ctx.createRadialGradient(x, y, 0, x, y, w * 0.4)
        const colors = [
          'rgba(232, 93, 74, 0.08)',
          'rgba(255, 138, 101, 0.06)',
          'rgba(255, 213, 79, 0.04)',
        ]
        gradient.addColorStop(0, colors[i])
        gradient.addColorStop(1, 'transparent')
        ctx.fillStyle = gradient
        ctx.fillRect(0, 0, w, h)
      }

      time += 16
      animationId = requestAnimationFrame(draw)
    }
    draw()

    return () => {
      cancelAnimationFrame(animationId)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className={`absolute inset-0 w-full h-full pointer-events-none ${className}`}
      style={{ width: '100%', height: '100%' }}
    />
  )
}

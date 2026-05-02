import { useEffect, useState } from 'react'

const defaultWords = ['AI', 'your', 'voice', 'screen', 'tasks']

export default function RotatingText({ words = defaultWords, className = '', mainClassName = '' }) {
  const [index, setIndex] = useState(0)
  const [isAnimating, setIsAnimating] = useState(false)

  useEffect(() => {
    const interval = setInterval(() => {
      setIsAnimating(true)
      setTimeout(() => {
        setIndex((prev) => (prev + 1) % words.length)
        setIsAnimating(false)
      }, 400)
    }, 2500)
    return () => clearInterval(interval)
  }, [words.length])

  return (
    <span className={`inline-flex overflow-hidden ${className}`}>
      <span
        className={`transition-all duration-400 ${
          isAnimating ? '-translate-y-full opacity-0' : 'translate-y-0 opacity-100'
        } ${mainClassName}`}
      >
        {words[index]}
      </span>
    </span>
  )
}

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export default function TypingText({ words = [], className = '', cursorColor = 'text-primary' }) {
  const [wordIndex, setWordIndex] = useState(0)
  const [charIndex, setCharIndex] = useState(0)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isPaused, setIsPaused] = useState(false)

  const currentWord = words[wordIndex]
  const displayText = currentWord.substring(0, charIndex)

  useEffect(() => {
    if (isPaused) return

    const timeout = setTimeout(() => {
      if (!isDeleting) {
        if (charIndex < currentWord.length) {
          setCharIndex((prev) => prev + 1)
        } else {
          setIsPaused(true)
          setTimeout(() => {
            setIsPaused(false)
            setIsDeleting(true)
          }, 2000)
        }
      } else {
        if (charIndex > 0) {
          setCharIndex((prev) => prev - 1)
        } else {
          setIsDeleting(false)
          setWordIndex((prev) => (prev + 1) % words.length)
        }
      }
    }, isDeleting ? 40 : 80)

    return () => clearTimeout(timeout)
  }, [charIndex, isDeleting, isPaused, currentWord, words.length])

  return (
    <span className={className}>
      <span className="text-gradient-primary">{displayText}</span>
      <span className={`inline-block w-0.5 h-[1em] ml-1 animate-pulse ${cursorColor} bg-current`} />
    </span>
  )
}

import { useCallback, useEffect, useRef, useState } from 'react'
import { processDictation } from '../lib/dictationProcessor'

// ============================================================================
// Feature Detection
// ============================================================================

const SpeechRecognitionAPI =
  window.SpeechRecognition || window.webkitSpeechRecognition

function isSupported() {
  return !!SpeechRecognitionAPI
}

// ============================================================================
// Hook
// ============================================================================

/**
 * @typedef {Object} DictationState
 * @property {boolean} isRecording
 * @property {boolean} isSupported
 * @property {string} transcript - Final processed text accumulated so far.
 * @property {string} interimTranscript - Live raw preview of current utterance.
 * @property {string} error - Error message, if any.
 * @property {number[]} audioLevels - Array of 40 frequency bins (0-255) for visualization.
 */

/**
 * @typedef {Object} DictationControls
 * @property {() => void} start
 * @property {() => void} stop
 * @property {() => void} toggle
 * @property {() => void} clear
 */

/**
 * React hook for in-browser dictation using the Web Speech API and Web Audio API.
 *
 * @param {Object} [options={}]
 * @param {string} [options.lang='en-US'] - BCP 47 language tag.
 * @param {boolean} [options.continuous=true] - Keep listening after a pause.
 * @param {boolean} [options.interimResults=true] - Show live preview.
 * @param {boolean} [options.autoProcess=true] - Run post-processing on final results.
 * @param {import('../lib/dictationProcessor').ProcessOptions} [options.processOptions] - Overrides for post-processing stages.
 *
 * @returns {[DictationState, DictationControls]}
 */
export function useDictation(options = {}) {
  const {
    lang = 'en-US',
    continuous = true,
    interimResults = true,
    autoProcess = true,
    processOptions = {},
  } = options

  const [isRecording, setIsRecording] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [interimTranscript, setInterimTranscript] = useState('')
  const [error, setError] = useState('')
  const [audioLevels, setAudioLevels] = useState(Array(40).fill(0))

  // Refs for mutable state without re-renders
  const recognitionRef = useRef(null)
  const audioContextRef = useRef(null)
  const analyserRef = useRef(null)
  const sourceRef = useRef(null)
  const rafRef = useRef(null)
  const streamRef = useRef(null)
  const finalBufferRef = useRef('')

  // --------------------------------------------------------------------------
  // Audio Visualizer Loop
  // --------------------------------------------------------------------------

  const startVisualizer = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const audioCtx = new (window.AudioContext || window.webkitAudioContext)()
      audioContextRef.current = audioCtx

      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 128 // 64 bins, we'll use 40
      analyser.smoothingTimeConstant = 0.85
      analyserRef.current = analyser

      const source = audioCtx.createMediaStreamSource(stream)
      source.connect(analyser)
      sourceRef.current = source

      const dataArray = new Uint8Array(analyser.frequencyBinCount)

      const tick = () => {
        if (!analyserRef.current) return
        analyserRef.current.getByteFrequencyData(dataArray)

        // Sample 40 bins evenly across the frequency spectrum
        const binCount = dataArray.length
        const levels = Array(40)
          .fill(0)
          .map((_, i) => {
            const idx = Math.floor((i / 40) * binCount)
            return dataArray[idx] || 0
          })

        setAudioLevels(levels)
        rafRef.current = requestAnimationFrame(tick)
      }

      rafRef.current = requestAnimationFrame(tick)
    } catch (err) {
      console.error('Visualizer error:', err)
      // Non-fatal: we can still transcribe without visualization
    }
  }, [])

  const stopVisualizer = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
    if (sourceRef.current) {
      try {
        sourceRef.current.disconnect()
      } catch (_) { /* noop */ }
      sourceRef.current = null
    }
    if (audioContextRef.current) {
      try {
        audioContextRef.current.close()
      } catch (_) { /* noop */ }
      audioContextRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    setAudioLevels(Array(40).fill(0))
  }, [])

  // --------------------------------------------------------------------------
  // Speech Recognition Lifecycle
  // --------------------------------------------------------------------------

  const stopRecognition = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch (_) { /* noop */ }
      recognitionRef.current = null
    }
    setIsRecording(false)
    setInterimTranscript('')
    stopVisualizer()
  }, [stopVisualizer])

  const startRecognition = useCallback(() => {
    if (!SpeechRecognitionAPI) {
      setError('Speech recognition is not supported in this browser.')
      return
    }

    setError('')
    setInterimTranscript('')

    const recognition = new SpeechRecognitionAPI()
    recognition.lang = lang
    recognition.continuous = continuous
    recognition.interimResults = interimResults
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setIsRecording(true)
      startVisualizer()
    }

    recognition.onend = () => {
      // If we are still in recording state, it means the engine stopped
      // unexpectedly (e.g. silence timeout). Restart if continuous.
      if (isRecording && continuous) {
        // Small delay to avoid rapid restart loops
        setTimeout(() => {
          if (isRecording) {
            try {
              const newRec = new SpeechRecognitionAPI()
              newRec.lang = lang
              newRec.continuous = continuous
              newRec.interimResults = interimResults
              // Copy handlers
              newRec.onstart = recognition.onstart
              newRec.onend = recognition.onend
              newRec.onresult = recognition.onresult
              newRec.onerror = recognition.onerror
              recognitionRef.current = newRec
              newRec.start()
            } catch (err) {
              setIsRecording(false)
              stopVisualizer()
            }
          }
        }, 300)
      } else {
        setIsRecording(false)
        stopVisualizer()
      }
    }

    recognition.onresult = (event) => {
      let interim = ''
      let final = ''

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        const transcriptPiece = result[0].transcript
        if (result.isFinal) {
          final += transcriptPiece + ' '
        } else {
          interim += transcriptPiece
        }
      }

      if (final) {
        const raw = finalBufferRef.current + final
        finalBufferRef.current = autoProcess
          ? processDictation(raw, processOptions)
          : raw
        setTranscript(finalBufferRef.current)
      }

      if (interim) {
        setInterimTranscript(interim)
      }
    }

    recognition.onerror = (event) => {
      // 'no-speech' and 'audio-capture' are common and usually transient;
      // don't kill the session for them.
      const transientErrors = ['no-speech', 'audio-capture', 'network']
      if (!transientErrors.includes(event.error)) {
        setError(
          event.error === 'not-allowed'
            ? 'Microphone access denied. Please allow microphone permissions.'
            : `Speech recognition error: ${event.error}`
        )
        setIsRecording(false)
        stopVisualizer()
      }
    }

    recognitionRef.current = recognition

    try {
      recognition.start()
    } catch (err) {
      setError('Failed to start speech recognition.')
      setIsRecording(false)
    }
  }, [
    lang,
    continuous,
    interimResults,
    autoProcess,
    processOptions,
    isRecording,
    startVisualizer,
    stopVisualizer,
  ])

  // --------------------------------------------------------------------------
  // Controls
  // --------------------------------------------------------------------------

  const start = useCallback(() => {
    if (isRecording) return
    finalBufferRef.current = transcript // preserve existing text
    startRecognition()
  }, [isRecording, transcript, startRecognition])

  const stop = useCallback(() => {
    stopRecognition()
  }, [stopRecognition])

  const toggle = useCallback(() => {
    if (isRecording) {
      stop()
    } else {
      start()
    }
  }, [isRecording, start, stop])

  const clear = useCallback(() => {
    finalBufferRef.current = ''
    setTranscript('')
    setInterimTranscript('')
    setError('')
  }, [])

  // --------------------------------------------------------------------------
  // Cleanup on unmount
  // --------------------------------------------------------------------------

  useEffect(() => {
    return () => {
      stopRecognition()
    }
  }, [stopRecognition])

  const state = {
    isRecording,
    isSupported: isSupported(),
    transcript,
    interimTranscript,
    error,
    audioLevels,
  }

  const controls = {
    start,
    stop,
    toggle,
    clear,
  }

  return [state, controls]
}

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Upload, User, Image as ImageIcon, Video, Loader2, Star, MessageSquare } from 'lucide-react'
import { supabase } from '../lib/supabase'
import AnimatedSection from './AnimatedSection'

function ReviewModal({ review, onClose }) {
  if (!review) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex items-center justify-center p-4"
        onClick={onClose}
      >
        <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          transition={{ duration: 0.25 }}
          className="relative z-10 w-full max-w-md rounded-2xl border border-white/[0.08] bg-bg-dark p-6 shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={onClose}
            className="absolute right-4 top-4 rounded-full p-1 text-text-secondary transition-colors hover:text-text-primary hover:bg-white/5"
          >
            <X size={18} />
          </button>

          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 font-display text-sm font-bold text-primary">
              {review.name?.split(' ').map(n => n[0]).join('') || '?'}
            </div>
            <div>
              <p className="text-sm font-medium text-text-primary">{review.name}</p>
              <p className="text-xs text-text-secondary">{review.role || 'User'}</p>
            </div>
          </div>

          {review.media_url && (
            <div className="mb-4 rounded-xl overflow-hidden border border-white/[0.06]">
              {review.media_type?.startsWith('video') ? (
                <video
                  src={review.media_url}
                  controls
                  className="w-full max-h-64 object-contain bg-black"
                />
              ) : (
                <img
                  src={review.media_url}
                  alt="Review media"
                  className="w-full max-h-64 object-contain bg-black"
                />
              )}
            </div>
          )}

          <p className="text-sm leading-relaxed text-text-secondary">
            "{review.text}"
          </p>

          <p className="mt-4 text-xs text-text-secondary/60">
            {review.created_at
              ? new Date(review.created_at).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                })
              : ''}
          </p>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

export default function ReviewsSection() {
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [selectedReview, setSelectedReview] = useState(null)
  const [showForm, setShowForm] = useState(false)

  const [formData, setFormData] = useState({
    name: '',
    role: '',
    text: '',
  })
  const [mediaFile, setMediaFile] = useState(null)
  const [mediaPreview, setMediaPreview] = useState(null)

  const fetchReviews = useCallback(async () => {
    if (!supabase) return
    setLoading(true)
    const { data, error } = await supabase
      .from('reviews')
      .select('*')
      .order('created_at', { ascending: false })

    if (!error && data) {
      setReviews(data)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    fetchReviews()
  }, [fetchReviews])

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (!file) return
    if (file.size > 50 * 1024 * 1024) {
      alert('File size must be under 50MB')
      return
    }
    setMediaFile(file)
    setMediaPreview(URL.createObjectURL(file))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!supabase) {
      alert('Supabase is not configured. Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.')
      return
    }
    if (!formData.name.trim() || !formData.text.trim()) {
      alert('Please enter your name and review text.')
      return
    }

    setSubmitting(true)

    try {
      let mediaUrl = null
      let mediaType = null

      if (mediaFile) {
        const ext = mediaFile.name.split('.').pop()
        const fileName = `${Date.now()}_${Math.random().toString(36).slice(2)}.${ext}`

        const { error: uploadError } = await supabase.storage
          .from('review-media')
          .upload(fileName, mediaFile, {
            cacheControl: '3600',
            upsert: false,
          })

        if (uploadError) {
          console.error('Upload error:', uploadError)
          alert('Failed to upload media. Please try again.')
          setSubmitting(false)
          return
        }

        const { data: urlData } = supabase.storage
          .from('review-media')
          .getPublicUrl(fileName)

        mediaUrl = urlData?.publicUrl || null
        mediaType = mediaFile.type
      }

      const { error: insertError } = await supabase.from('reviews').insert({
        name: formData.name.trim(),
        role: formData.role.trim() || 'User',
        text: formData.text.trim(),
        media_url: mediaUrl,
        media_type: mediaType,
      })

      if (insertError) {
        console.error('Insert error:', insertError)
        alert('Failed to submit review. Please try again.')
        setSubmitting(false)
        return
      }

      setFormData({ name: '', role: '', text: '' })
      setMediaFile(null)
      setMediaPreview(null)
      setShowForm(false)
      await fetchReviews()
    } catch (err) {
      console.error('Submit error:', err)
      alert('Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="mx-auto max-w-7xl px-6 py-28">
      <AnimatedSection className="mb-16 text-center">
        <h2 className="font-display text-3xl font-bold text-text-primary md:text-4xl">
          Loved by productive people
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-text-secondary">
          See what users say about working with Wiztant. Share your own experience.
        </p>
      </AnimatedSection>

      {/* Submit Review Toggle */}
      <div className="mb-12 flex justify-center">
        <button
          onClick={() => setShowForm(!showForm)}
          className="inline-flex items-center gap-2 rounded-full bg-primary/10 border border-primary/20 px-6 py-3 text-sm font-medium text-primary transition-all hover:bg-primary/20"
        >
          <MessageSquare size={16} />
          {showForm ? 'Cancel' : 'Write a Review'}
        </button>
      </div>

      {/* Review Form */}
      <AnimatePresence>
        {showForm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="mb-16 overflow-hidden"
          >
            <div className="mx-auto max-w-xl rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6 md:p-8">
              <h3 className="font-display text-lg font-semibold text-text-primary mb-6">Share your experience</h3>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-text-secondary">Name *</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      placeholder="Your name"
                      className="w-full rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-text-primary placeholder:text-text-secondary/40 outline-none focus:border-primary/40 transition-colors"
                      required
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-text-secondary">Role / Title</label>
                    <input
                      type="text"
                      value={formData.role}
                      onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                      placeholder="e.g. Software Engineer"
                      className="w-full rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-text-primary placeholder:text-text-secondary/40 outline-none focus:border-primary/40 transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-medium text-text-secondary">Your Review *</label>
                  <textarea
                    value={formData.text}
                    onChange={(e) => setFormData({ ...formData, text: e.target.value })}
                    placeholder="Tell us what you think..."
                    rows={4}
                    className="w-full rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-text-primary placeholder:text-text-secondary/40 outline-none focus:border-primary/40 transition-colors resize-none"
                    required
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-medium text-text-secondary">Photo or Video (optional)</label>
                  <div className="relative">
                    <input
                      type="file"
                      accept="image/*,video/*"
                      onChange={handleFileChange}
                      className="hidden"
                      id="review-media"
                    />
                    <label
                      htmlFor="review-media"
                      className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-white/[0.12] bg-white/[0.02] px-4 py-3 text-sm text-text-secondary transition-colors hover:border-primary/30 hover:bg-white/[0.04]"
                    >
                      <Upload size={16} className="text-primary" />
                      <span>{mediaFile ? mediaFile.name : 'Click to upload photo or video'}</span>
                    </label>
                  </div>
                  {mediaPreview && (
                    <div className="mt-3 rounded-xl overflow-hidden border border-white/[0.06] max-w-xs">
                      {mediaFile?.type?.startsWith('video') ? (
                        <video src={mediaPreview} className="w-full h-32 object-cover" controls />
                      ) : (
                        <img src={mediaPreview} alt="Preview" className="w-full h-32 object-cover" />
                      )}
                    </div>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-primary w-full justify-center disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submitting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Submitting...
                    </>
                  ) : (
                    <>
                      <Star size={16} />
                      Submit Review
                    </>
                  )}
                </button>
              </form>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Reviews Grid */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 size={24} className="animate-spin text-primary" />
        </div>
      ) : reviews.length === 0 ? (
        <AnimatedSection className="text-center py-12">
          <MessageSquare size={40} className="mx-auto mb-4 text-text-secondary/30" />
          <p className="text-text-secondary">No reviews yet. Be the first to share your experience!</p>
        </AnimatedSection>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {reviews.map((review, i) => (
            <AnimatedSection key={review.id} delay={i * 0.08}>
              <button
                onClick={() => setSelectedReview(review)}
                className="group card h-full w-full text-left transition-all hover:border-primary/20"
              >
                <p className="text-sm leading-relaxed text-text-secondary line-clamp-4 flex-1">
                  "{review.text}"
                </p>

                {review.media_url && (
                  <div className="mt-4 flex items-center gap-2 text-xs text-primary">
                    {review.media_type?.startsWith('video') ? (
                      <Video size={14} />
                    ) : (
                      <ImageIcon size={14} />
                    )}
                    <span>View media</span>
                  </div>
                )}

                <div className="mt-6 flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 font-display text-sm font-bold text-primary">
                    {review.name?.split(' ').map(n => n[0]).join('') || '?'}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-text-primary">{review.name}</p>
                    <p className="text-xs text-text-secondary">{review.role || 'User'}</p>
                  </div>
                </div>
              </button>
            </AnimatedSection>
          ))}
        </div>
      )}

      {/* Review Popup */}
      {selectedReview && (
        <ReviewModal review={selectedReview} onClose={() => setSelectedReview(null)} />
      )}
    </section>
  )
}

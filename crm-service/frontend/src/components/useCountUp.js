import { useEffect, useRef, useState } from 'react'

// React hook: animates a number from 0 up to `target` over `duration` ms (ease-out), for dashboard counters.
export function useCountUp(target, duration = 1200) {
  const [value, setValue] = useState(0)
  const start = useRef(null)
  const frame = useRef(null)

  useEffect(() => {
    if (!target || isNaN(target)) return
    const num = parseFloat(target)
    start.current = null
    // One animation frame: work out progress, update the shown value, and request the next frame until done.
    const animate = (ts) => {
      if (!start.current) start.current = ts
      const progress = Math.min((ts - start.current) / duration, 1)
      // ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(eased * num)
      if (progress < 1) frame.current = requestAnimationFrame(animate)
      else setValue(num)
    }
    frame.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame.current)
  }, [target, duration])

  return value
}

import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

// Track the mouse over each .card so CSS can draw a spotlight glow at the cursor (--mx / --my).
document.addEventListener('mousemove', (e) => {
  document.querySelectorAll('.card').forEach((card) => {
    const rect = card.getBoundingClientRect()
    card.style.setProperty('--mx', `${e.clientX - rect.left}px`)
    card.style.setProperty('--my', `${e.clientY - rect.top}px`)
  })
})

// Draw slowly drifting coffee beans on a full-screen background canvas.
function initParticles() {
  const canvas = document.createElement('canvas')
  canvas.id = 'particle-canvas'
  document.body.prepend(canvas)
  const ctx = canvas.getContext('2d')
  // Keep the canvas the same size as the window.
  const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight }
  resize()
  window.addEventListener('resize', resize)

  // warm coffee bean colours
  const BEAN_COLORS = [
    'rgba(139,90,31,',
    'rgba(100,58,20,',
    'rgba(180,115,45,',
    'rgba(80,45,15,',
    'rgba(160,100,35,',
  ]

  const particles = Array.from({ length: 42 }, () => ({
    x: Math.random() * window.innerWidth,
    y: Math.random() * window.innerHeight,
    size: Math.random() * 6 + 3,
    speedX: (Math.random() - 0.5) * 0.32,
    speedY: (Math.random() - 0.5) * 0.26,
    opacity: Math.random() * 0.32 + 0.08,
    rotation: Math.random() * Math.PI * 2,
    rotSpeed: (Math.random() - 0.5) * 0.011,
    pulse: Math.random() * Math.PI * 2,
    color: BEAN_COLORS[Math.floor(Math.random() * BEAN_COLORS.length)],
  }))

  // Draw one coffee bean (an ellipse with a curved crease) at the given position, angle and opacity.
  function drawBean(ctx, x, y, size, rotation, opacity, color) {
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(rotation)
    ctx.globalAlpha = opacity
    ctx.fillStyle = color + '0.95)'
    ctx.strokeStyle = color + '0.5)'
    ctx.lineWidth = 0.7
    ctx.beginPath()
    ctx.ellipse(0, 0, size, size * 1.6, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
    // crease
    ctx.beginPath()
    ctx.strokeStyle = 'rgba(245,220,180,0.18)'
    ctx.lineWidth = 0.9
    ctx.moveTo(0, -size * 1.35)
    ctx.bezierCurveTo(size * 0.6, -size * 0.4, size * 0.6, size * 0.4, 0, size * 1.35)
    ctx.stroke()
    ctx.restore()
  }

  let raf
  // Move every bean one step, wrap it around the screen edges, redraw, and schedule the next frame.
  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    particles.forEach((p) => {
      p.x += p.speedX
      p.y += p.speedY
      p.rotation += p.rotSpeed
      p.pulse += 0.016
      const op = p.opacity + Math.sin(p.pulse) * 0.05
      if (p.x < -20) p.x = canvas.width + 20
      if (p.x > canvas.width + 20) p.x = -20
      if (p.y < -20) p.y = canvas.height + 20
      if (p.y > canvas.height + 20) p.y = -20
      drawBean(ctx, p.x, p.y, p.size, p.rotation, Math.max(0, op), p.color)
    })
    raf = requestAnimationFrame(animate)
  }
  animate()
  return () => cancelAnimationFrame(raf)
}

initParticles()

// Mount the React app, wrapped in the router so pages can use URLs.
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)

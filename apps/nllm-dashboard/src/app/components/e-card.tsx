"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";

/* ─────────────── Color Palette ─────────────── */
const PALETTE = {
  coral:   "#F25C54",
  teal:    "#2EC4B6",
  magenta: "#E71D73",
  mustard: "#F4D03F",
  maroon:  "#7B1F3A",
  pink:    "#FF8FA3",
  cream:   "#FFF9F0",
  text:    "#2D2D2D",
};

/* ─────────────── “Mom” in many languages ─────────────── */
const MOM_WORDS: { text: string; lang: string; size: number; x: number; y: number; rotate: number; color: string; weight: number }[] = [
  { text: "Mom",        lang: "en",    size: 56,  x: 10,  y: 12,  rotate: -6,  color: PALETTE.coral,   weight: 700 },
  { text: "Madre",      lang: "es",    size: 48,  x: 55,  y: 10,  rotate: 3,   color: PALETTE.mustard, weight: 600 },
  { text: "Mère",       lang: "fr",    size: 44,  x: 5,   y: 35,  rotate: -2,  color: PALETTE.teal,    weight: 500 },
  { text: "Mutter",     lang: "de",    size: 38,  x: 65,  y: 32,  rotate: 5,   color: PALETTE.maroon,  weight: 700 },
  { text: "Mamma",      lang: "it",    size: 50,  x: 30,  y: 22,  rotate: 1,   color: PALETTE.pink,    weight: 700 },
  { text: "Mamá",       lang: "es2",   size: 42,  x: 75,  y: 18,  rotate: -4,  color: PALETTE.coral,   weight: 600 },
  { text: "माँ",        lang: "hi",    size: 46,  x: 8,   y: 55,  rotate: 4,   color: PALETTE.magenta, weight: 600 },
  { text: "お母さん",    lang: "jp",    size: 34,  x: 50,  y: 50,  rotate: -3,  color: PALETTE.teal,    weight: 500 },
  { text: "Mãe",        lang: "pt",    size: 40,  x: 75,  y: 48,  rotate: 6,   color: PALETTE.mustard, weight: 600 },
  { text: "Мама",       lang: "ru",    size: 44,  x: 15,  y: 75,  rotate: -5,  color: PALETTE.maroon,  weight: 700 },
  { text: "엄마",       lang: "ko",    size: 38,  x: 55,  y: 72,  rotate: 2,   color: PALETTE.pink,    weight: 500 },
  { text: "妈妈",       lang: "zh",    size: 42,  x: 78,  y: 68,  rotate: -1,  color: PALETTE.coral,   weight: 600 },
  { text: "أم",         lang: "ar",    size: 48,  x: 5,   y: 88,  rotate: 3,   color: PALETTE.teal,    weight: 700 },
  { text: "Anne",       lang: "tr",    size: 36,  x: 35,  y: 88,  rotate: -2,  color: PALETTE.magenta, weight: 500 },
  { text: "Moeder",     lang: "nl",    size: 32,  x: 60,  y: 90,  rotate: 4,   color: PALETTE.mustard, weight: 500 },
  { text: "Mamm",       lang: "sv",    size: 34,  x: 82,  y: 88,  rotate: -3,  color: PALETTE.maroon,  weight: 600 },
  { text: "Μαμά",       lang: "el",    size: 38,  x: 20,  y: 95,  rotate: 1,   color: PALETTE.pink,    weight: 600 },
  { text: "אמא",        lang: "he",    size: 36,  x: 45,  y: 62,  rotate: 5,   color: PALETTE.coral,   weight: 700 },
  { text: "Ibu",        lang: "id",    size: 30,  x: 72,  y: 85,  rotate: -4,  color: PALETTE.teal,    weight: 500 },
  { text: "Mami",       lang: "ro",    size: 28,  x: 88,  y: 55,  rotate: 2,   color: PALETTE.magenta, weight: 500 },
  /* ── FOCAL POINT ── */
  { text: "મામી",       lang: "gu",    size: 82,  x: 50,  y: 45,  rotate: -1,  color: PALETTE.coral,   weight: 800 },
];

/* ─────────────── Floating Heart Particle ─────────────── */
function HeartParticle({ delay }: { delay: number }) {
  const randomX = Math.random() * 100;
  const randomScale = 0.5 + Math.random() * 1;
  const colors = [PALETTE.coral, PALETTE.pink, PALETTE.magenta, PALETTE.teal];
  const color = colors[Math.floor(Math.random() * colors.length)];

  return (
    <motion.div
      className="absolute pointer-events-none"
      initial={{ x: `${randomX}%`, y: "100%", opacity: 0, scale: 0 }}
      animate={{ y: "-20%", opacity: [0, 1, 1, 0], scale: randomScale }}
      transition={{ duration: 4 + Math.random() * 2, delay, ease: "easeOut" }}
      style={{ left: 0, right: 0 }}
    >
      <svg width="24" height="24" viewBox="0 0 24 24" fill={color}>
        <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
      </svg>
    </motion.div>
  );
}

/* ─────────────── Front Cover ─────────────── */
function CardFront({ onOpen }: { onOpen: () => void }) {
  return (
    <motion.div
      className="relative w-full h-full cursor-pointer select-none overflow-hidden rounded-2xl"
      style={{ background: "#FFFDF7", perspective: 1200 }}
      whileHover={{ scale: 1.02, boxShadow: "0 25px 60px rgba(0,0,0,0.15)" }}
      whileTap={{ scale: 0.98 }}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onOpen();
      }}
      role="button"
      tabIndex={0}
      aria-label="Tap to open Mother's Day card"
    >
      {/* Subtle texture overlay */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23000000' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")",
        }}
      />

      {/* Word collage */}
      <div className="absolute inset-0 p-4 sm:p-6">
        {MOM_WORDS.map((word, i) => (
          <span
            key={i}
            className="absolute inline-block leading-none whitespace-nowrap"
            style={{
              left: `${word.x}%`,
              top: `${word.y}%`,
              transform: `translate(-50%, -50%) rotate(${word.rotate}deg)`,
              fontSize: `${word.size * 0.65}px`,
              color: word.color,
              fontWeight: word.weight,
              fontFamily:
                word.lang === "gu" || word.lang === "hi" || word.lang === "ar"
                  ? "'Noto Sans Gujarati', 'Noto Sans Devanagari', sans-serif"
                  : "var(--font-inter), ui-sans-serif, system-ui, sans-serif",
              textShadow:
                word.lang === "gu"
                  ? "2px 2px 0px rgba(0,0,0,0.08)"
                  : "none",
              zIndex: word.lang === "gu" ? 10 : 1,
              letterSpacing: word.lang === "gu" ? "-0.02em" : "-0.01em",
            }}
          >
            {word.text}
          </span>
        ))}
      </div>

      {/* Bottom hint */}
      <motion.div
        className="absolute bottom-4 left-0 right-0 text-center"
        animate={{ y: [0, -4, 0] }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
      >
        <span
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium"
          style={{
            background: "rgba(242, 92, 84, 0.1)",
            color: PALETTE.maroon,
            backdropFilter: "blur(8px)",
          }}
        >
          Tap to open <span className="text-lg">💌</span>
        </span>
      </motion.div>
    </motion.div>
  );
}

/* ─────────────── Inside Message ─────────────── */
function CardInside() {
  return (
    <div
      className="relative w-full h-full flex flex-col items-center justify-center text-center px-6 py-8 sm:px-10 sm:py-12 select-none overflow-hidden rounded-2xl"
      style={{ background: PALETTE.cream }}
    >
      {/* Decorative corner flowers */}
      <svg className="absolute top-3 left-3 w-10 h-10 opacity-20" viewBox="0 0 40 40" fill={PALETTE.coral}>
        <circle cx="20" cy="8" r="6" /><circle cx="8" cy="20" r="6" /><circle cx="32" cy="20" r="6" /><circle cx="20" cy="32" r="6" /><circle cx="20" cy="20" r="5" fill={PALETTE.mustard} />
      </svg>
      <svg className="absolute top-3 right-3 w-10 h-10 opacity-20" viewBox="0 0 40 40" fill={PALETTE.teal}>
        <circle cx="20" cy="8" r="6" /><circle cx="8" cy="20" r="6" /><circle cx="32" cy="20" r="6" /><circle cx="20" cy="32" r="6" /><circle cx="20" cy="20" r="5" fill={PALETTE.pink} />
      </svg>
      <svg className="absolute bottom-3 left-3 w-10 h-10 opacity-20" viewBox="0 0 40 40" fill={PALETTE.magenta}>
        <circle cx="20" cy="8" r="6" /><circle cx="8" cy="20" r="6" /><circle cx="32" cy="20" r="6" /><circle cx="20" cy="32" r="6" /><circle cx="20" cy="20" r="5" fill={PALETTE.coral} />
      </svg>
      <svg className="absolute bottom-3 right-3 w-10 h-10 opacity-20" viewBox="0 0 40 40" fill={PALETTE.mustard}>
        <circle cx="20" cy="8" r="6" /><circle cx="8" cy="20" r="6" /><circle cx="32" cy="20" r="6" /><circle cx="20" cy="32" r="6" /><circle cx="20" cy="20" r="5" fill={PALETTE.teal} />
      </svg>

      {/* Title */}
      <motion.h1
        className="text-3xl sm:text-4xl md:text-5xl leading-tight mb-4 sm:mb-6"
        style={{
          fontFamily: "var(--font-libre), 'Georgia', serif",
          fontStyle: "italic",
          color: PALETTE.coral,
        }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.8, ease: "easeOut" }}
      >
        Happy Mother&apos;s Day,
        <br />
        Mami!
      </motion.h1>

      {/* Divider */}
      <motion.div
        className="w-16 h-0.5 rounded-full mb-5 sm:mb-7"
        style={{ background: PALETTE.coral }}
        initial={{ scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ delay: 0.6, duration: 0.5 }}
      />

      {/* Message */}
      <motion.p
        className="text-sm sm:text-base md:text-lg leading-relaxed max-w-md mb-6 sm:mb-8"
        style={{ color: PALETTE.text, fontFamily: "var(--font-inter), sans-serif", lineHeight: 1.7 }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.7, duration: 0.8, ease: "easeOut" }}
      >
        Thank you for being the incredible woman you are — full of love,
        laughter, and endless wisdom. You make every moment brighter and
        every heart warmer. Wishing you a day as wonderful as you are!
      </motion.p>

      {/* Signature */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.0, duration: 0.8, ease: "easeOut" }}
      >
        <p
          className="text-base sm:text-lg mb-1"
          style={{
            fontFamily: "var(--font-libre), 'Georgia', serif",
            fontStyle: "italic",
            color: PALETTE.teal,
          }}
        >
          With all my love,
        </p>
        <p
          className="text-2xl sm:text-3xl md:text-4xl"
          style={{
            fontFamily: "'Dancing Script', 'Brush Script MT', cursive",
            color: PALETTE.magenta,
            fontWeight: 700,
          }}
        >
          NIL
        </p>
      </motion.div>
    </div>
  );
}

/* ─────────────── Main E-Card Component ─────────────── */
export default function ECard() {
  const [isOpen, setIsOpen] = useState(false);
  const [hearts, setHearts] = useState<number[]>([]);

  const handleOpen = useCallback(() => {
    if (isOpen) return;
    setIsOpen(true);
    // Spawn floating hearts
    const newHearts = Array.from({ length: 18 }, (_, i) => i);
    setHearts(newHearts);
    // Auto-clear after animation
    setTimeout(() => setHearts([]), 7000);
  }, [isOpen]);

  /* Reduced-motion support */
  const prefersReducedMotion =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  return (
    <div
      className="relative flex items-center justify-center w-full h-full"
      style={{ perspective: 1400 }}
    >
      {/* Ambient soft gradient background */}
      <div
        className="absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 50% 40%, rgba(255,143,163,0.12), transparent), radial-gradient(ellipse 60% 50% at 30% 70%, rgba(46,196,182,0.08), transparent), radial-gradient(ellipse 50% 40% at 70% 30%, rgba(244,208,63,0.08), transparent), #FFF9F0",
        }}
      />

      {/* Card container */}
      <div
        className="relative w-full max-w-[420px] sm:max-w-[520px] md:max-w-[720px] aspect-[3/4] sm:aspect-[4/3]"
        style={{ perspective: 1400 }}
      >
        <AnimatePresence mode="wait">
          {!isOpen ? (
            /* ── Closed state: front cover ── */
            <motion.div
              key="closed"
              className="absolute inset-0"
              initial={{ rotateY: 0 }}
              exit={{
                rotateY: prefersReducedMotion ? 0 : -180,
                transformOrigin: "left center",
                transition: { duration: 1.2, ease: [0.22, 1, 0.36, 1] },
              }}
              style={{ transformStyle: "preserve-3d", backfaceVisibility: "hidden" }}
            >
              <CardFront onOpen={handleOpen} />
            </motion.div>
          ) : (
            /* ── Open state: inside + back cover swinging away ── */
            <motion.div
              key="open"
              className="absolute inset-0 flex flex-col sm:flex-row gap-0 shadow-2xl rounded-2xl overflow-hidden"
              initial={{ opacity: 0, scale: 0.92 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
              style={{ boxShadow: "0 30px 80px rgba(0,0,0,0.12)" }}
            >
              {/* Left inside panel (decorative) */}
              <div
                className="hidden sm:flex w-1/3 items-center justify-center relative overflow-hidden"
                style={{ background: "#FFFDF7" }}
              >
                <motion.div
                  className="absolute inset-0 flex items-center justify-center opacity-[0.06]"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 0.06, scale: 1 }}
                  transition={{ delay: 0.5, duration: 1 }}
                >
                  <svg viewBox="0 0 200 300" className="w-48 h-72">
                    <defs>
                      <linearGradient id="floralGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor={PALETTE.coral} />
                        <stop offset="100%" stopColor={PALETTE.pink} />
                      </linearGradient>
                    </defs>
                    <path
                      d="M100 20 C120 40, 140 60, 130 90 C160 80, 180 100, 170 130 C190 150, 180 180, 150 190 C170 220, 150 250, 120 240 C100 270, 80 250, 70 220 C40 230, 20 200, 40 170 C10 150, 20 120, 50 110 C30 80, 50 50, 80 60 C70 30, 90 20, 100 20Z"
                      fill="url(#floralGrad)"
                    />
                    <circle cx="100" cy="140" r="25" fill={PALETTE.mustard} opacity="0.5" />
                    <circle cx="100" cy="140" r="12" fill={PALETTE.cream} />
                  </svg>
                </motion.div>
              </div>

              {/* Right inside panel (message) */}
              <div className="flex-1 relative">
                <CardInside />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Floating hearts overlay */}
        <AnimatePresence>
          {hearts.map((h) => (
            <HeartParticle key={h} delay={h * 0.2} />
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

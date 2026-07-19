"use client";
import { motion, useScroll, useSpring } from "framer-motion";

export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 140, damping: 28, mass: 0.4 });
  return (
    <motion.div
      className="no-print fixed inset-x-0 top-0 z-[60] h-[2px] origin-left bg-accent/70"
      style={{ scaleX }}
    />
  );
}

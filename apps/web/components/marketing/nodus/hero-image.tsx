"use client";
import React, { useRef } from "react";
import { Container } from "./container";
import Image from "next/image";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { Dot } from "./common/dots";

const springConfig = {
  stiffness: 300,
  damping: 30,
};

export const HeroImage = () => {
  const ref = useRef<HTMLDivElement>(null);

  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  const springX = useSpring(mouseX, springConfig);
  const springY = useSpring(mouseY, springConfig);

  const translateX = useTransform(springX, [-0.5, 0.5], [-40, 40]);
  const translateY = useTransform(springY, [-0.5, 0.5], [-40, 40]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;

    const rect = ref.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    const x = (e.clientX - centerX) / rect.width;
    const y = (e.clientY - centerY) / rect.height;

    mouseX.set(x);
    mouseY.set(y);
  };

  const handleMouseLeave = () => {
    mouseX.set(0);
    mouseY.set(0);
  };

  return (
    <Container className="border-divide relative flex items-start justify-start overflow-hidden border-x bg-gray-100 p-2 perspective-distant md:p-4 lg:p-8 dark:bg-neutral-800">
      <Dot top left />
      <Dot top right />
      <Dot bottom left />
      <Dot bottom right />
      <div className="relative w-full">
        <motion.div
          ref={ref}
          className="relative z-10 h-full w-full cursor-pointer"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          style={{
            translateX,
            translateY,
          }}
        >
          <Image
            src="/nodus/dashboard@3x.png"
            alt="Gravitre product preview"
            className="w-full"
            priority
            fetchPriority="high"
            sizes="(max-width: 1024px) 100vw, min(100vw, 1280px)"
            width={1000}
            height={1000}
            draggable={false}
          />
        </motion.div>
        <div className="absolute inset-0 z-0 m-auto h-[90%] w-[95%] rounded-lg border border-(--pattern-fg) bg-[image:repeating-linear-gradient(315deg,_var(--pattern-fg)_0,_var(--pattern-fg)_1px,_transparent_0,_transparent_50%)] bg-[size:10px_10px] bg-fixed"></div>
      </div>
    </Container>
  );
};

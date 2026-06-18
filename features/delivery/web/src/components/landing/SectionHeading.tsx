import { motion } from "framer-motion";

interface SectionHeadingProps {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  align?: "left" | "center";
}

export function SectionHeading({ eyebrow, title, subtitle, align = "center" }: SectionHeadingProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className={`mb-12 ${align === "center" ? "mx-auto max-w-3xl text-center" : "max-w-3xl"}`}
    >
      {eyebrow && (
        <span className="mb-3 inline-block text-sm font-semibold uppercase tracking-widest text-electric-cyan">
          {eyebrow}
        </span>
      )}
      <h2 className="mb-4 font-heading text-4xl font-bold text-text-primary md:text-5xl">
        {title}
      </h2>
      {subtitle && (
        <p className="text-lg leading-relaxed text-text-secondary">{subtitle}</p>
      )}
    </motion.div>
  );
}

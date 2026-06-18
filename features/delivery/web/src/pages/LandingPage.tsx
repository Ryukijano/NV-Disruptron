import { AmbientBackground } from "@/components/landing/AmbientBackground";
import { ArchitectureSection } from "@/components/landing/ArchitectureSection";
import { CommunitySection } from "@/components/landing/CommunitySection";
import { DemoSection } from "@/components/landing/DemoSection";
import { FooterSection } from "@/components/landing/FooterSection";
import { HardwareSection } from "@/components/landing/HardwareSection";
import { HeroSection } from "@/components/landing/HeroSection";
import { ProblemSection } from "@/components/landing/ProblemSection";
import { TechStackSection } from "@/components/landing/TechStackSection";

export function LandingPage() {
  return (
    <div className="min-h-screen bg-canvas text-text-primary">
      <AmbientBackground />
      <main className="relative z-10">
        <HeroSection />
        <ProblemSection />
        <TechStackSection />
        <DemoSection />
        <ArchitectureSection />
        <HardwareSection />
        <CommunitySection />
      </main>
      <FooterSection />
    </div>
  );
}

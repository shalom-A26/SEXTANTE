import { Hero } from "@/components/hero";
import { HowItWorks } from "@/components/how-it-works";
import { About } from "@/components/landing-sections";

export default function Home() {
  return (
    <>
      <Hero />
      <About />
      <HowItWorks />
    </>
  );
}

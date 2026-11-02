import { Hero } from "@/components/hero";
import { About, HowItWorks } from "@/components/landing-sections";

export default function Home() {
  return (
    <>
      <Hero />
      <About />
      <HowItWorks />
    </>
  );
}

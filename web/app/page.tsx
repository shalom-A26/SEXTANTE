import { HowItWorks } from "@/components/how-it-works";
import { Audiences } from "@/components/landing/audiences";
import { Chapters } from "@/components/landing/chapters";
import { Numbers } from "@/components/landing/numbers";
import { Scene } from "@/components/scene";

export default function Home() {
  return (
    <>
      <Scene />
      <Chapters />
      <div className="after-chapters">
        <Audiences />
        <HowItWorks />
        <Numbers />
      </div>
    </>
  );
}

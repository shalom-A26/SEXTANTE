import { Guide } from "@/components/guide/guide";
import { Chapters } from "@/components/landing/chapters";
import { Intro } from "@/components/landing/intro";
import { Ledger } from "@/components/landing/ledger";
import { Profiles } from "@/components/landing/profiles";
import { WhatWeDo } from "@/components/landing/what-we-do";

export default function Home() {
  return (
    <>
      <Intro />
      <Chapters />
      <WhatWeDo />
      <Guide />
      <Profiles />
      <Ledger />
    </>
  );
}

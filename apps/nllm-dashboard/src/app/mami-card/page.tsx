"use client";

import dynamic from "next/dynamic";

const ECard = dynamic(() => import("@/app/components/e-card"), { ssr: false });

export default function MamiCardPage() {
  return (
    <div className="w-full h-full">
      <ECard />
    </div>
  );
}

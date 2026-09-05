"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { BrandLoader } from "@/components/BrandLoader";

export default function WorkspaceIndex() {
  return (
    <Suspense fallback={<Loader />}>
      <Redirect />
    </Suspense>
  );
}

function Redirect() {
  const router = useRouter();
  const params = useSearchParams();
  useEffect(() => {
    const legacyTab = params.get("tab");
    const tab = legacyTab === "ask" || legacyTab === "law" ? legacyTab : "assess";
    const session = params.get("session");
    router.replace(`/workspace/${tab}${session ? `?session=${session}` : ""}`);
  }, [router, params]);
  return <Loader />;
}

function Loader() {
  return (
    <WorkspaceShell>
      <div className="grid min-h-[60vh] place-items-center">
        <BrandLoader />
      </div>
    </WorkspaceShell>
  );
}

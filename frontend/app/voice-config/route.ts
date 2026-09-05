import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export function GET() {
  const voiceUrl = process.env.VOICE_URL || process.env.NEXT_PUBLIC_VOICE_URL || "";
  return NextResponse.json(
    {
      voiceUrl,
      stunUrl:
        process.env.STUN_URL ||
        process.env.NEXT_PUBLIC_STUN_URL ||
        "stun:stun.l.google.com:19302",
      turnUrl: process.env.TURN_URL || process.env.NEXT_PUBLIC_TURN_URL || "",
      turnUsername:
        process.env.TURN_USERNAME || process.env.NEXT_PUBLIC_TURN_USERNAME || "",
      turnCredential:
        process.env.TURN_CREDENTIAL || process.env.NEXT_PUBLIC_TURN_CREDENTIAL || "",
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}

import { NextResponse } from "next/server";

export function GET() {
  return NextResponse.json({ messages: [] }, { headers: { "Cache-Control": "no-store" } });
}

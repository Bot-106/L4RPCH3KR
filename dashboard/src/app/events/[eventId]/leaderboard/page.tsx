import { redirect } from "next/navigation";

export default async function EventLeaderboardPage({ params }: { params: Promise<{ eventId: string }> }) {
  const { eventId } = await params;
  redirect(`/leaderboard?event_id=${encodeURIComponent(eventId)}`);
}

import { redirect } from "next/navigation";

/* The three tools are now tabs of a single workspace session. Keep the old route
   working by sending visitors to the matching tab. */
export default function PredictRedirect() {
  redirect("/workspace?tab=assess");
}

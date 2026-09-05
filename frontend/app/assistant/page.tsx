import { redirect } from "next/navigation";

export default function AssistantRedirect() {
  redirect("/workspace/ask");
}

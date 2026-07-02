import { redirect } from "next/navigation";

/* Document analysis lives in the Assess-a-case tab (attach a file there).
   Keep the old route working by redirecting anyone who lands here. */
export default function DocumentsRedirect() {
  redirect("/workspace?tab=assess");
}

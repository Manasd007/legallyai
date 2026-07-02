/* A persisted message as returned by GET /api/sessions/{id} → conversations[].messages.
   Tabs rebuild their live UI state from these on rehydration. `payload` holds the
   full structured response of an assistant turn (prediction, statutes, doc, …). */
export type StoredMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  payload: any | null;
  case_id?: string | null;
  created_at: string;
};

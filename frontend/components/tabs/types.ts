export type StoredMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  payload: any | null;
  case_id?: string | null;
  created_at: string;
};

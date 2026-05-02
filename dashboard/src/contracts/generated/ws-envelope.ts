export interface WsEnvelope {
  id: string;
  type: string;
  ts: string;
  session_id?: string | null;
  data: {
    [k: string]: unknown;
  };
}

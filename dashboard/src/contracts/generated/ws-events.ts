/**
 * Per-`type` payload schemas. The full message wraps these in WsEnvelope.
 */
export interface WsEventPayloads {
  [k: string]: unknown;
}

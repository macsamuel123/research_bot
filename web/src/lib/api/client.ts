import { createHttpClient } from "./http";
import { getMockClient } from "./mock";
import type {
  Finding,
  ResearchDetail,
  ResearchSummary,
  Run,
  WatchPatch,
} from "./types";

/**
 * Every backend call from the UI goes through this interface (INV-14).
 * `mock.ts` and `http.ts` both implement it; components never call fetch.
 */
export interface ApiClient {
  listResearches(): Promise<ResearchSummary[]>;
  createResearch(topic: string): Promise<ResearchSummary>;
  getResearch(id: number): Promise<ResearchDetail>;
  markRead(id: number): Promise<void>;
  /** PATCH /api/researches/{id} {watch_enabled?, schedule?}; returns the sidebar summary. */
  updateWatch(id: number, patch: WatchPatch): Promise<ResearchSummary>;
  /** DELETE /api/researches/{id}; removes messages, findings and runs too. */
  deleteResearch(id: number): Promise<void>;
  /** Non-dismissed findings, newest first. */
  listFindings(researchId: number): Promise<Finding[]>;
  /** Idempotent. */
  dismissFinding(findingId: number): Promise<void>;
  /** Run history, newest first. */
  listRuns(researchId: number): Promise<Run[]>;
}

export function usingMocks(): boolean {
  return process.env.NEXT_PUBLIC_USE_MOCKS === "1";
}

let httpClient: ApiClient | null = null;

export function getApiClient(): ApiClient {
  if (usingMocks()) return getMockClient();
  httpClient ??= createHttpClient();
  return httpClient;
}
